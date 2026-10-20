#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Measure what the function catalog actually contains, and how many shapes it is made of.

Two questions, because they decide the plan rather than describing it:

1. The denominator. `symbols/ghidra_functions.csv` has an address and a size per row, and nothing
   says a row is a function entry. This counts how many are: inside an executable segment, decoding
   to exactly the declared size, not padding, not a thunk, and either a direct branch target or the
   start of a run of code no other row contains. A row that begins inside another row's range is a
   label, not an entry.

2. The shape count. For each entry, the mnemonic sequence with every operand erased is its shape;
   entries with the same sequence are the same code at different addresses, which is what makes one
   replacement, one case generator and one review serve all of them. The histogram says whether
   reaching the whole catalog is a handful of templates or thousands of hand-written translations.

usage: shape_census.py [--elf PATH] [--limit N] [--top N] [--json OUT]

--elf defaults to $BB_IMAGE. The report goes to stdout; --json writes the same numbers per entry so
a later slice can group by a different key without decoding the image again.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import struct
import sys

import capstone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNCTIONS = os.path.join(ROOT, 'symbols', 'ghidra_functions.csv')

# The catalog's addresses are guest PS4 addresses (they start at 0x400020, which is where the image
# begins above its ELF header), and the ELF's p_vaddr is relative to EBOOT_BASE. So the file offset is
# guest - EBOOT_BASE - p_vaddr + p_offset, which for this eboot is guest - 0x3fc000. Getting this
# wrong does not fail: it decodes plausible instructions from the wrong place, and the first version
# of this tool measured 3,000 such rows before a known function was used as a control.
EBOOT_BASE = 0x400000
FILE_BIAS = 0x4000
PT_LOAD = 1
PF_X = 1

# A shape is compared with operands erased, but a long function's tail says little about which
# template it belongs to and makes two copies of the same idiom look different. Truncation is a
# declared limit, not an accident: SHAPE_LIMIT instructions, then the sequence as it stands.
SHAPE_LIMIT = 48

PADDING = {0x00, 0xCC}


def load_segments(path: str) -> tuple[bytes, list[dict]]:
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'\x7fELF':
        raise SystemExit(f'{path}: not an ELF')
    phoff, = struct.unpack_from('<Q', data, 0x20)
    phentsize, phnum = struct.unpack_from('<HH', data, 0x36)
    segs = []
    for i in range(phnum):
        p_type, p_flags, p_offset, p_vaddr, _, p_filesz, p_memsz, _ = struct.unpack_from(
            '<IIQQQQQQ', data, phoff + i * phentsize)
        if p_type == PT_LOAD:
            segs.append({'offset': p_offset, 'vaddr': p_vaddr, 'filesz': p_filesz,
                         'memsz': p_memsz, 'flags': p_flags})
    return data, segs


def entry_rows(path: str, limit: int | None) -> list[tuple[int, int]]:
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            rows.append((int(r['address'], 16), int(r['size'])))
    rows.sort()
    return rows[:limit] if limit else rows


def segment_of(segs: list[dict], va: int) -> dict | None:
    for s in segs:
        if EBOOT_BASE + s['vaddr'] <= va < EBOOT_BASE + s['vaddr'] + s['memsz']:
            return s
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', default=os.environ.get('BB_IMAGE', ''))
    ap.add_argument('--functions', default=FUNCTIONS)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--json')
    args = ap.parse_args()
    if not args.elf:
        print('shape_census: set BB_IMAGE or pass --elf', file=sys.stderr)
        return 2

    data, segs = load_segments(args.elf)
    image = [s for s in segs if s['flags'] & PF_X]
    rows = entry_rows(args.functions, args.limit)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False   # groups are not needed: a direct branch renders as 'mnemonic 0x<target>'

    if not image:
        raise SystemExit(f'{args.elf}: no executable PT_LOAD')
    seg = image[0]

    def fetch(va: int, size: int) -> bytes | None:
        off = va - EBOOT_BASE - seg['vaddr'] + seg['offset']
        if va < EBOOT_BASE + seg['vaddr'] or off + size > seg['offset'] + seg['filesz']:
            return None
        return data[off: off + size]

    # Rows that begin strictly inside another row's range are labels inside a function, not entries.
    nested = set()
    prev_end, prev_start = -1, -1
    for va, size in rows:
        if va < prev_end:
            nested.add(va)
        if va + size > prev_end:
            prev_end, prev_start = va + size, va
    union_bytes = 0
    cursor = -1
    for va, size in rows:
        lo = max(va, cursor)
        if va + size > lo:
            union_bytes += va + size - lo
        cursor = max(cursor, va + size)

    tally = collections.Counter()
    last_mnemonic = collections.Counter()
    shapes = collections.Counter()
    shape_members: dict[tuple, list[int]] = collections.defaultdict(list)
    by_target: collections.Counter = collections.Counter()   # direct branch targets
    by_call: set[int] = set()
    per_entry = []
    total_decoded_bytes = 0
    inside = set(va for va, _ in rows)

    for va, size in rows:
        raw = fetch(va, size)
        if raw is None:
            tally['not_in_exec_segment'] += 1
            continue
        tally['in_exec_segment'] += 1
        if size == 0:
            tally['zero_size'] += 1
            continue
        if va in nested:
            tally['starts_inside_another_row'] += 1
        if all(b in PADDING for b in raw):
            tally['all_padding_bytes'] += 1
        insns = list(md.disasm(raw, va))
        decoded = sum(i.size for i in insns)
        total_decoded_bytes += decoded
        if not insns:
            tally['undecodable'] += 1
            continue
        if decoded != size:
            tally['does_not_decode_to_declared_size'] += 1
        for i in insns:
            if i.mnemonic in ('call', 'jmp') and i.op_str.startswith('0x'):
                t = int(i.op_str, 16)
                by_target[t] += 1
                if i.mnemonic == 'call':
                    by_call.add(t)
        last = insns[-1]
        last_mnemonic[last.mnemonic] += 1
        if len(insns) == 1 and insns[0].mnemonic == 'jmp' and insns[0].op_str.startswith('0x'):
            tally['single_jmp_rel32_thunk'] += 1
        if len(insns) == 1 and insns[0].mnemonic == 'jmp' and 'rip' in insns[0].op_str:
            tally['single_jmp_rip_thunk'] += 1
        shape = tuple(i.mnemonic for i in insns[:SHAPE_LIMIT])
        if len(insns) > SHAPE_LIMIT:
            shape += ('...',)
        shapes[shape] += 1
        if len(shape_members) < 100000:
            shape_members[shape].append(va)
        per_entry.append({'address': f'0x{va:08x}', 'size': size, 'instructions': len(insns),
                          'shape_instructions': len(shape), 'last_mnemonic': last.mnemonic,
                          'bytes_sha256': hashlib.sha256(raw).hexdigest()[:16],
                          'shape': ' '.join(shape)})

    reached = sum(1 for va, _ in rows if va in by_target)
    called = sum(1 for va, _ in rows if va in by_call)
    targets_not_in_catalog = len([t for t in by_target if t not in inside])
    content = collections.Counter(e['bytes_sha256'] for e in per_entry)
    distinct_content = len(content)
    duplicated = sum(c for c in content.values() if c > 1)

    out = {
        'rows': len(rows),
        'declared_bytes': sum(s for _, s in rows),
        'decoded_bytes': total_decoded_bytes,
        'union_bytes': union_bytes,
        'positive_bytes': len(set(v for v, s in rows if s > 0)),
        'distinct_content': distinct_content,
        'entries_sharing_content_with_another': duplicated,
        'reached_by_direct_branch': reached,
        'called_directly': called,
        'branch_targets_outside_catalog': targets_not_in_catalog,
        'shapes': len(shapes),
        'tally': dict(tally),
        'last_mnemonic': dict(last_mnemonic.most_common(15)),
        'top_shapes': [{'instructions': k, 'members': v} for k, v in shapes.most_common(args.top)],
        'top_content_clusters': content.most_common(10),
    }
    print(f'entries: {out["rows"]}')
    print(f'declared bytes: {out["declared_bytes"]:,}  union: {out["union_bytes"]:,}  '
          f'overlap: {out["declared_bytes"] - out["union_bytes"]:,}  '
          f'positive-size distinct addresses: {out["positive_bytes"]}')
    for k in sorted(tally):
        print(f'  {k}: {tally[k]}')
    print(f'direct branch targets inside the catalog: {reached}  called directly: {called}  '
          f'targets outside the catalog: {targets_not_in_catalog}')
    print(f'distinct byte contents: {distinct_content}  '
          f'entries whose bytes equal another entry\'s: {duplicated}')
    print('last instruction:', dict(last_mnemonic.most_common(10)))
    print(f'shapes (mnemonic sequence, operands erased): {len(shapes)}')
    covered = 0
    for shape, count in shapes.most_common(args.top):
        covered += count
        print(f'  {count:6d}  {len(shape):2d} insns  {" ".join(shape[:10])}{" ..." if len(shape) > 10 else ""}')
    print(f'top {args.top} shapes cover {covered} entries ({100.0 * covered / max(1, len(rows)):.1f}%)')
    if args.json:
        with open(args.json, 'w') as f:
            json.dump({'summary': out, 'entries': per_entry}, f)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
