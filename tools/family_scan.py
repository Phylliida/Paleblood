#!/usr/bin/env python3
"""Scan the image for groups of structurally identical leaf functions.

usage: family_scan.py CATALOG --elf EBOOT.elf [--min-members N] [--min-size N] [--max-size N] [--limit N] [--shape]

gen_clone_family.py retires one named family. This finds the families worth naming: it decodes every
candidate body with the same independent objdump decoder and groups them two ways.

  clone      the decoded instruction bytes are identical, so the bodies differ only in their address.
             A clone group is the safest work in the image: one body settles every member, and the
             generated replacement is a straight transcription rather than a template with holes.
  structural the bytes differ, but only in registers, displacements and immediates. These need one
             template parameterised by the varying operand, which is what gen_clone_family renders.

Ranking is by bytes retired per unit of work, so a clone group of 528 bodies outranks a structural
group of four. Registry rows are excluded, so a group is only reported while it is still open.

The gate is the one gen_clone_family.py already applies, so a reported group can be handed to that
tool without re-deriving eligibility: a plain RET tail, no jump, no call, no static memory reference,
and a body inside the size window.
"""
import argparse
import collections
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_clone_family as family

REGISTER = re.compile(r'^(?:r[a-z0-9]+|e[a-z]+|xmm\d+|ymm\d+|mm\d+|[abcd][lhx]|[sd]il?|[sb]pl?)$')
IMMEDIATE = re.compile(r'^(?:0x[0-9a-f]+|-?[0-9]+)$')
WORDY = re.compile(r'^(?:byte|word|dword|qword|xmmword|ymmword|tbyte)$')


def normalise(operands):
    """Operands with registers and immediates replaced by placeholders.

    A structural family is a set of bodies that differ only in which register or constant they name,
    so those are exactly what has to be erased for the bodies to compare equal. Displacement values
    are deliberately kept: two bodies that touch [rsi+0x70] and [rsi+0x68] in different orders are
    different code, and a placeholder would fuse them into one meaningless group.
    """
    text = operands.replace(',', ' ').replace('[', ' [ ').replace(']', ' ] ')
    out = []
    for token in text.split():
        if token in ('[', ']'):
            out.append(token)
        elif WORDY.match(token):
            out.append(token)
        elif REGISTER.match(token):
            out.append('<r>')
        elif IMMEDIATE.match(token):
            out.append('<i>')
        else:
            out.append(token)
    return ' '.join(out)


def shape_of(instructions):
    return tuple((i['mnemonic'], normalise(i['operands'])) for i in instructions)


def bytes_of(instructions):
    """The encoded size and rendering of each instruction, with the trailing RET dropped.

    Exact clones have to be compared on the encoding rather than on the rendered operands alone,
    because objdump prints one encoding several ways and two bodies that print identically can still
    differ in a byte the printer elides. The decoder hands back each instruction's length but not its
    bytes, so the length plus the rendering is what stands in for the encoding: two bodies with the
    same rendering at every position and the same length at every position are the same code.
    """
    return tuple((entry['mnemonic'], entry['operands'], entry['size']) for entry in instructions)


def bytes_per(instructions):
    """The encoded length of one body, taken from the decoder rather than from the catalogue."""
    return sum(entry['size'] for entry in instructions)


def registered(path):
    addresses = set()
    if not os.path.exists(path):
        return addresses
    with open(path, newline='') as handle:
        for line in handle:
            fields = line.strip().split(',')
            if len(fields) >= 3 and fields[0].startswith('0x'):
                addresses.add(int(fields[0], 16))
    return addresses


def collect(options, blob):
    """Decode every candidate body, keeping the registry names so open groups can be identified.

    A catalogue row is not proof that a function exists. The export assigns an extent to every
    address Ghidra sized, including content that is plainly data, and a five-byte row over data can
    still decode as five plausible instructions. A body is therefore only accepted when objdump
    emits the full span as contiguous instructions: the byte column must carry exactly as many bytes
    as the extent claims, with no gap and no trailing fragment. A truncated body is a decode that ran
    off the end of something.
    """
    names = {}
    if os.path.exists(options.functions):
        with open(options.functions, newline='') as handle:
            for line in handle:
                fields = line.strip().split(',')
                if len(fields) >= 4 and fields[0].startswith('0x'):
                    names[int(fields[0], 16)] = fields[2]

    candidates = []
    for function in json.load(open(options.catalog))['functions']:
        size = function.get('size_bytes') or 0
        if size < options.min_size or size > options.max_size:
            continue
        address = int(function['address'], 16)
        if not (options.base <= address < options.limit_address):
            continue
        body = family.pregates(function, blob)
        if body is None:
            continue
        family.blob_cache[address] = body
        candidates.append((address, len(body)))

    decoded, offsets = family.decode_batch(candidates)
    bodies, rejected = {}, 0
    for address, size in candidates:
        try:
            instructions = family.body_instructions(address, size, decoded, offsets)
        except SystemExit:
            rejected += 1
            continue
        encoded = sum(entry['size'] for entry in instructions)
        if encoded != size:
            rejected += 1
            continue
        # A blank mnemonic is not a defect. objdump prints an instruction whose encoding does not fit
        # the byte column across two lines, and the decoder records the continuation as its own entry,
        # so a one-byte tail such as the 0x00 finishing an eight-byte MOV appears here with no
        # mnemonic. The walk still measures the body correctly -- the recorded sizes sum to the size
        # Ghidra gave -- so the gate is the byte total and the RET tail, not the blank entry.
        if instructions[-1]['mnemonic'] != 'ret':
            rejected += 1
            continue
        if options.jump_free and any(entry['size'] == 0 or entry['mnemonic'].startswith('j')
                                     or entry['mnemonic'] == 'call' for entry in instructions):
            rejected += 1
            continue
        bodies[address] = instructions
    return bodies, names, rejected


def rank(bodies, names, done, options):
    """Clone and structural groups over the verified bodies, ranked by work retired per unit.

    Exact clones and structural groups are computed together because the first refines the second:
    a structural group is what remains interesting after its byte-identical members are known, and
    the count of distinct encodings inside a structural group is what says whether the group needs a
    template with one hole or a template with many.
    """
    clones = collections.defaultdict(list)
    shapes = collections.defaultdict(list)
    for address, instructions in bodies.items():
        lower = [i for i in instructions if i['mnemonic'] != 'ret']
        clones[bytes_of(lower)].append(address)
        shapes[shape_of(lower)].append(address)

    rows = []
    for members in clones.values():
        members.sort()
        fresh = [a for a in members if a not in done]
        if len(members) < options.min_members or not fresh:
            continue
        rows.append({'kind': 'clone', 'members': members, 'fresh': fresh,
                     'shape': shape_of([i for i in bodies[members[0]] if i['mnemonic'] != 'ret']),
                     'bytes': bytes_per(bodies[members[0]]), 'instr': len(bodies[members[0]]),
                     'spread': 1})
    for members in shapes.values():
        members.sort()
        fresh = [a for a in members if a not in done]
        if len(members) < options.min_members or not fresh:
            continue
        encodings = {bytes_of([i for i in bodies[a] if i['mnemonic'] != 'ret']) for a in members}
        rows.append({'kind': 'structural', 'members': members, 'fresh': fresh,
                     'shape': shape_of([i for i in bodies[members[0]] if i['mnemonic'] != 'ret']),
                     'bytes': bytes_per(bodies[members[0]]), 'instr': len(bodies[members[0]]),
                     'spread': len(encodings)})

    for row in rows:
        row['cost'] = len(row['fresh']) * row['bytes']
    if options.by_members:
        rows.sort(key=lambda r: (-len(r['fresh']), -r['cost']))
    else:
        rows.sort(key=lambda r: (-r['cost'], -len(r['fresh'])))
    return rows



def loaded_window(path, blob):
    """The loaded address range in catalogue addresses, read from the executable's program headers.

    The headers carry link-time addresses starting at zero, while the catalogue and the byte lookup
    work in image addresses; the shift between the two is the one the shared decoder already uses to
    find a body's bytes. The upper bound is checked against the file, so a window that ran past the
    image would be reported rather than producing reads that are silently short.
    """
    with open(path, 'rb') as handle:
        header = handle.read(64)
        if header[:4] != b'\x7fELF' or header[4] != 2:
            raise SystemExit(f'{path}: not a 64-bit ELF image')
        count = int.from_bytes(header[56:58], 'little')
        handle.seek(int.from_bytes(header[32:40], 'little'))
        spans = []
        for _ in range(count):
            entry = handle.read(56)
            if int.from_bytes(entry[0:4], 'little') != 1:  # PT_LOAD
                continue
            base = int.from_bytes(entry[16:24], 'little')
            size = int.from_bytes(entry[32:40], 'little')
            spans.append((base, base + size))
    low = min(start for start, _ in spans) + family.FILE_BIAS
    high = max(end for _, end in spans) + family.FILE_BIAS
    if high > len(blob):
        raise SystemExit(f'{path}: the loaded window ends past the end of the file')
    return low, high


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('catalog')
    parser.add_argument('--elf', default=os.environ.get('BB_ELF', ''))
    parser.add_argument('--functions', default=str(pathlib.Path(__file__).resolve().parent.parent
                                                    / 'symbols' / 'functions.csv'))
    parser.add_argument('--min-members', type=int, default=4)
    # The floor excludes every catalogue row <= 13 bytes: 37,629 of 157,757, of which 3,826 are
    # unlanded and 64 are independent entries (owned, owners==1) -- the rest nest inside a
    # larger extent and have no entry a guest can call.
    # MEASURED, not assumed: this floor is necessary and NOT sufficient. Of those 64 independent
    # rows, every one is also refused by a second selector -- 51 by this tool's own jump-free
    # default, 7 by the byte tier's position-dependence rule, 6 by its trap rule. Lifting
    # --min-size alone therefore proposes nothing, and lifting jump_free alone leaves them
    # size-excluded: the two must move together. Table: symbols/thunks.csv, gate:
    # test/test_thunk_census.py, census: tools/thunk_census.py.
    # And jump_free is the FAR larger exclusion: 116,475 of 157,757 catalogue rows (73.8%)
    # contain a branch or call, and only 1,919 of those are landed -- so this default, not this
    # floor, is what binds family discovery, at every size rather than only the short band.
    parser.add_argument('--min-size', type=int, default=14)
    parser.add_argument('--max-size', type=int, default=256)
    parser.add_argument('--base', type=lambda v: int(v, 0), default=None,
                        help='lowest address to consider; defaults to the executable load address')
    parser.add_argument('--limit-address', type=lambda v: int(v, 0), default=None,
                        help='exclusive upper address; defaults to the end of the loadable image')
    parser.add_argument('--any-control-flow', dest='jump_free', action='store_false',
                        help='keep bodies containing branches, calls and indirect jumps')
    parser.add_argument('--by-members', action='store_true',
                        help='rank by member count instead of bytes retired')
    parser.add_argument('--limit', type=int, default=15)
    parser.add_argument('--shape', action='store_true', help='print the instruction shape of each group')
    options = parser.parse_args(argv)

    blob = pathlib.Path(options.elf).read_bytes()
    low, high = loaded_window(options.elf, blob)
    if options.base is None:
        options.base = low
    if options.limit_address is None:
        options.limit_address = high
    family.blob_cache.clear()
    bodies, names, rejected = collect(options, blob)
    done = registered(options.functions)
    rows = rank(bodies, names, done, options)

    kinds = collections.Counter(r['kind'] for r in rows)
    print(f'bodies verified: {len(bodies)}   rejected as data or fragments: {rejected}')
    print(f'open clone groups: {kinds["clone"]}   open structural groups: {kinds["structural"]}')

    covered = set()
    shown = 0
    for row in rows:
        shown += 1
        first = row['members'][0]
        print(f"\n[{row['kind']}] {len(row['fresh'])} open / {len(row['members'])} members, "
              f"{row['bytes']} bytes per member, {row['instr']} instructions, "
              f"{row['cost']} bytes open, "
              f"{row['spread']} distinct encoding(s), first 0x{first:08x}"
              f"{', known as ' + names[first] if first in names else ''}")
        if options.shape:
            for mnemonic, operands in row['shape']:
                print(f'    {mnemonic} {operands}')
        print('    addresses: ' + ' '.join(f'0x{a:08x}' for a in row['members'][:10]))
        covered.update(row['members'])
        if shown >= options.limit:
            break
    print(f'\nbodies covered by the {shown} groups shown: {len(covered)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
