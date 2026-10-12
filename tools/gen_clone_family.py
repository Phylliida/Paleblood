#!/usr/bin/env python3
"""Generate the source for one family of clonable functions.

usage: gen_clone_family.py CATALOG --elf EBOOT.elf --group N --prefix NAME --patch bb_system --out DIR

A family is a set of functions whose bodies are the same sequence of instructions and differ only in
immediates: field offsets, register numbers, source constants. They are read out of the image with
the independent objdump decoder, so the struct layout written into the replacement comes from the
bytes rather than from a note about them.

Only bodies in which every instruction moves memory to or from an XMM register, through one base
register for the loads and one for the stores, are emitted. Anything else is skipped rather than
guessed at.

The original loads every slot in its own order and only then stores, so the replacement reads all
of them into a staging object first and stores afterwards. That ordering is load-bearing whenever
the caller passes overlapping buffers, and it is also what makes one staging type per layout
sufficient: the loads happen before any store can disturb the source.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

blob_cache = {}

FILE_BIAS = 0x3FC000
LINE = re.compile(r'^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} )+)\s*(\S+)?\s*(.*)$')
MEMORY = re.compile(r'^(?P<width>byte|word|dword|qword|xmmword) ptr \[(?P<base>r[a-z0-9]+)'
                    r'(?:\+0x(?P<disp>[0-9a-f]+))?\]$')
# objdump renders a memory operand as "dword ptr [rax+0x8]", so the width lives in the operand and
# the mnemonic only names the form. vmovsd moves sixty-four bits, not a scalar double, which is why
# the width comes from the operand rather than from a table keyed by mnemonic.
WIDTHS = {'byte': 1, 'word': 2, 'dword': 4, 'qword': 8, 'xmmword': 16}
REGISTER = re.compile(r'^xmm\d+$')
CXX = {4: 'std::uint32_t', 8: 'std::uint64_t', 16: 'unsigned __int128'}


def memory(operand):
    """(width, base, displacement) for a plain [base] or [base+disp] operand, else None."""
    match = MEMORY.match(operand)
    if match is None:
        return None
    return (WIDTHS[match.group('width')], match.group('base'),
            int(match.group('disp'), 16) if match.group('disp') else 0)


def move(instruction):
    """(width, kind, base, displacement) for one xmm/memory move, else None."""
    if not instruction['mnemonic'].startswith('vmov'):
        return None
    operands = instruction['operands'].split(',')
    if len(operands) != 2:
        return None
    target, source = (operand.strip() for operand in operands)
    if REGISTER.match(target) and memory(source):
        width, base, displacement = memory(source)
        return (width, 'load', base, displacement)
    if memory(target) and REGISTER.match(source):
        width, base, displacement = memory(target)
        return (width, 'store', base, displacement)
    return None


def pregates(function, blob):
    """Cheap catalogue-level filters, then the body itself: a plain RET tail and no jump."""
    address = int(function['address'], 16)
    size = function.get('size_bytes') or 0
    if size == 0 or size > 256:
        return None
    calls = function.get('calls') or {}
    if not calls.get('analysis_complete') or calls.get('unresolved_indirect'):
        return None
    if calls.get('direct') or (function.get('memory_dependencies') or {}).get('static_references'):
        return None
    body = blob[address - FILE_BIAS:address - FILE_BIAS + size]
    if len(body) != size or body[-1] != 0xC3 or b'\xe9' in body or b'\xeb' in body:
        return None
    return body


def decode_batch(candidates):
    """Decode every candidate body in one objdump pass.

    One objdump process per body costs about twenty milliseconds, which is hours over the whole
    image, so the bodies are concatenated and decoded together. Each body is aligned to sixteen
    bytes and preceded by an INT3 marker, so no instruction can be read across a body boundary:
    objdump's linear sweep begins each body at a byte the original's own decoder would agree is an
    instruction boundary.
    """
    parts, offsets, cursor = [], {}, 0
    for address, size in candidates:
        padding = (-cursor - 16) % 16
        if padding:
            parts.append(bytes(padding))
            cursor += padding
        parts.append(bytes.fromhex('cc') * 16)
        cursor += 16
        offsets[address] = cursor
        parts.append(blob_cache[address])
        cursor += len(blob_cache[address])
    blob = b''.join(parts)
    fd = os.memfd_create('pb-family-decode', flags=0)
    try:
        with os.fdopen(os.dup(fd), 'wb') as stream:
            stream.write(blob)
        result = subprocess.run(['objdump', '-D', '-b', 'binary', '-m', 'i386:x86-64', '-M', 'intel',
                                 '--adjust-vma=0x0', f'/proc/self/fd/{fd}'],
                                pass_fds=(fd,), check=True, capture_output=True, text=True)
    finally:
        os.close(fd)
    decoded = {}
    for line in result.stdout.splitlines():
        match = LINE.match(line)
        if not match:
            continue
        raw = bytes.fromhex(match.group(2))
        mnemonic = (match.group(3) or '').lower()
        operands = match.group(4).split('<')[0].strip().lower()
        decoded[int(match.group(1), 16)] = (mnemonic, operands, raw)
    return decoded, offsets


def body_instructions(address, size, decoded, offsets):
    """The decoded instructions of one body, in order, with any marker line dropped.

    The walk advances by each instruction's own length rather than one byte at a time: a linear
    sweep knows the boundary of the instruction it just decoded, and inventing boundaries from the
    dictionary would misread any instruction longer than a byte as missing bytes.
    """
    start = offsets[address]
    instructions = []
    offset = start
    while offset < start + size:
        entry = decoded.get(offset)
        if entry is None:
            raise SystemExit(f'0x{address:08x}: objdump decoded nothing at +{offset - start}')
        mnemonic, operands, raw = entry
        if mnemonic == 'int3':
            raise SystemExit(f'0x{address:08x}: a marker byte landed inside the body')
        if offset + len(raw) > start + size:
            raise SystemExit(f'0x{address:08x}: the last instruction runs past the body')
        instructions.append({'mnemonic': mnemonic, 'operands': operands, 'size': len(raw)})
        offset += len(raw)
    if offset != start + size:
        raise SystemExit(f'0x{address:08x}: decoded {offset - start} of {size} bytes')
    return instructions


def decode_family(catalog, elf, groups):
    """Every member of the requested families, decoded from the image bytes."""
    blob = pathlib.Path(elf).read_bytes()
    blob_cache.clear()
    candidates = []
    for function in json.load(open(catalog))['functions']:
        body = pregates(function, blob)
        if body is None:
            continue
        address = int(function['address'], 16)
        blob_cache[address] = body
        candidates.append((address, len(body)))
    decoded, offsets = decode_batch(candidates)

    members = []
    for address, size in candidates:
        instructions = body_instructions(address, size, decoded, offsets)
        group = len(instructions) - 1
        if group not in groups or instructions[-1]['mnemonic'] != 'ret':
            continue
        moves = []
        for instruction in instructions[:-1]:
            parsed = move(instruction)
            if parsed is None:
                moves = None
                break
            moves.append(parsed)
        if not moves:
            continue
        loads = {m[2] for m in moves if m[1] == 'load'}
        stores = {m[2] for m in moves if m[1] == 'store'}
        # One base register per direction and they differ: a copy between two objects, not a shuffle
        # within one or a gather across several.
        if len(loads) != 1 or len(stores) != 1 or loads == stores:
            continue
        members.append({'address': address, 'size': size, 'moves': moves,
                        'load': loads.pop(), 'store': stores.pop()})
    members.sort(key=lambda m: m['address'])
    return members


def layout(moves, base):
    fields = {}
    for width, kind, register, disp in moves:
        if register != base:
            continue
        if disp in fields and fields[disp] != width:
            raise SystemExit(f'conflicting widths at +0x{disp:x}')
        fields[disp] = width
    return sorted(fields.items())


def prepare(members):
    """Members whose two sides are the same shape, with the layout read off the actual offsets.

    A member whose load and store sides disagree in offsets or widths is a different transform --
    a widening copy, or a gather into one object -- and one staging type cannot describe it. Those
    are counted and reported rather than guessed at.
    """
    prepared, skipped = [], []
    for member in members:
        load = layout(member['moves'], member['load'])
        store = layout(member['moves'], member['store'])
        if load != store:
            skipped.append(member['address'])
            continue
        # The original's load order, which the staging reads must reproduce for overlapping buffers.
        order = [offset for _, kind, register, offset in member['moves'] if kind == 'load']
        if sorted(order) != [offset for offset, _ in load]:
            skipped.append(member['address'])
            continue
        prepared.append({**member, 'layout': load, 'total': max(o + w for o, w in load), 'order': order})
    return prepared, skipped


def struct_name(layout_):
    return 'Slots_' + '_'.join(f'{offset:x}_{width}' for offset, width in layout_)


def render_header(prepared, patch):
    lines = ['// SPDX-License-Identifier: GPL-2.0-or-later',
             '// Generated by tools/gen_clone_family.py from the image bytes. Edit the generator.',
             '#pragma once',
             '',
             '#include <cstdint>',
             '',
             'namespace bb::clone {',
             '']
    seen = {}
    for member in prepared:
        name = struct_name(member['layout'])
        if name in seen:
            continue
        seen[name] = member
        lines.append(f'// {member["total"]} bytes, from 0x{member["address"]:08x}')
        lines.append(f'struct {name}')
        lines.append('{')
        cursor = 0
        for offset, width in member['layout']:
            if offset > cursor:
                lines.append(f'    unsigned char pad_{cursor:x}[0x{offset - cursor:x}];')
            lines.append(f'    {CXX[width]} at_{offset:x};')
            cursor = offset + width
        lines.append('};')
        lines.append(f'static_assert(sizeof({name}) == 0x{member["total"]:x});')
        lines.append('')
    lines.append('}  // namespace bb::clone')
    lines.append('')
    return '\n'.join(lines), seen


def render_source(prepared, seen, patch):
    lines = ['// SPDX-License-Identifier: GPL-2.0-or-later',
             '// Generated by tools/gen_clone_family.py from the image bytes. Edit the generator.',
             '#include "clone_slots.h"',
             '',
             'namespace {',
             '',
             '// Each body loads every slot before storing any of them, so overlapping buffers behave the',
             '// way the original\'s interleaved loads and stores do: the original reads all of its slots',
             '// before it writes any of them, which is why one staging object per layout is enough.',
             'template <typename Slots>',
             'void copy_slots(const void *source, void *target)',
             '{',
             '    const auto *from = static_cast<const Slots *>(source);',
             '    auto *to = static_cast<Slots *>(target);',
             '    Slots staging{};']
    emitted = set()
    for member in prepared:
        name = struct_name(member['layout'])
        if name in emitted:
            continue
        emitted.add(name)
        for offset in member['order']:
            lines.append(f'    staging.at_{offset:x} = from->at_{offset:x};')
        for offset in member['order']:
            lines.append(f'    to->at_{offset:x} = staging.at_{offset:x};')
    lines.extend(['}', '', '}  // namespace', ''])
    for member in prepared:
        name = struct_name(member['layout'])
        lines.append(f'// 0x{member["address"]:08x}, {member["size"]} bytes, {len(member["moves"])} moves '
                     f'through {member["load"]} and {member["store"]}')
        lines.append(f'extern "C" void {patch}_clone_{member["address"]:08x}(const void *source, void *target)')
        lines.append('{')
        lines.append(f'    copy_slots<bb::clone::{name}>(source, target);')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('catalog')
    parser.add_argument('--elf', default=os.environ.get('BB_ELF', ''))
    parser.add_argument('--group', type=int, nargs='+', required=True)
    parser.add_argument('--patch', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()

    members = decode_family(args.catalog, args.elf, set(args.group))
    if args.limit:
        members = members[:args.limit]
    if args.list:
        for member in members:
            print(f"0x{member['address']:08x} {member['size']:3d}  load {member['load']} "
                  f"store {member['store']}  moves={len(member['moves'])}")
        print(f'{len(members)} member(s)')
        return 0

    prepared, skipped = prepare(members)
    if skipped:
        print(f'{len(skipped)} member(s) skipped: sides not mirrored or loads out of order')
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    header, seen = render_header(prepared, args.patch)
    (out / 'clone_slots.h').write_text(header)
    (out / 'clone_slots.cpp').write_text(render_source(prepared, seen, args.patch))
    print(f'{len(prepared)} function(s), {len(seen)} layout(s) -> {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
