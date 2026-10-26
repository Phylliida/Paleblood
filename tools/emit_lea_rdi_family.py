#!/usr/bin/env python3
"""Emit the `lea rax,[rdi+K]; ret` family, deriving every member from the bytes.

The member list is never read from a file a previous run printed: the strict operand
predicate below is the only source, so a template key that masks an index register cannot
smuggle a second family into the count (1,462 by string grouping, 483 by parsing the operand).

Pre-registered end state, asserted rather than read:
  members 483 · all unlanded before · every K >= 0xc · distinct K 114 · sizes {5, 8}
Each of those is an assertion; a mismatch names which one moved.
"""
import argparse, csv, io, json, os, re, sys, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from case_dir import case_dir
import atomicio
import install_mode

ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
FILE_BIAS = 0x3FC000
EXPECT_MEMBERS, EXPECT_DISTINCT_K, EXPECT_MIN_K, EXPECT_SIZES = 483, 114, 0xC, {5: 294, 8: 189}
EXACT = re.compile(r'^rax, \[rdi \+ (0x[0-9a-f]+)\]$')


def members():
    data = open(ELF, 'rb').read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    land = {int(r['address'], 16) for r in csv.DictReader(open(os.path.join(ROOT, 'symbols', 'functions.csv')))}
    out = []
    for r in csv.DictReader(open(os.path.join(ROOT, 'symbols', 'ghidra_functions.csv'))):
        addr, size = int(r['address'], 16), int(r['size'])
        if not 3 <= size <= 16:
            continue
        ins = list(md.disasm(data[addr - FILE_BIAS:addr - FILE_BIAS + size], addr))
        if len(ins) != 2 or ins[0].mnemonic != 'lea' or ins[1].mnemonic != 'ret':
            continue
        m = EXACT.match(ins[0].op_str)
        if not m:
            continue
        out.append({'address': addr, 'size': size, 'k': int(m.group(1), 16), 'landed': addr in land})
    return out


def body_text(ms):
    lines = ['#include <cstdint>', '',
             '// Generated: lea rax, [rdi + K]; ret. Pointer arithmetic on the argument; nothing',
             '// is dereferenced, so no memory model or region validation applies. K is the',
             '// member\'s own displacement, read out of its bytes, and it is the only variation.', '']
    for m in ms:
        n = f'leaf_lea_rdi_{m["address"]:08x}'
        lines += [f'constexpr std::uint64_t k_{n} = {m["k"]:#x}u;',
                  f'extern "C" std::uint64_t bb_{n}(std::uint64_t a) {{ return a + k_{n}; }}']
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='write the family body (tables still require --record)')
    a = ap.parse_args()
    ms = members()
    unlanded = [m for m in ms if not m['landed']]
    ks = collections.Counter(m['k'] for m in ms)
    sizes = collections.Counter(m['size'] for m in ms)
    print(f'members {len(ms)} unlanded {len(unlanded)} distinct_K {len(ks)} min_K {hex(min(ks))} sizes {dict(sorted(sizes.items()))}')
    for name, got, want in (('members', len(ms), EXPECT_MEMBERS), ('unlanded', len(unlanded), EXPECT_MEMBERS),
                            ('distinct_K', len(ks), EXPECT_DISTINCT_K), ('min_K', min(ks), EXPECT_MIN_K),
                            ('sizes', dict(sizes), EXPECT_SIZES), ('landed', sum(m['landed'] for m in ms), 0)):
        if got != want:
            print(f'PRE-REGISTRATION FAILED: {name} is {got}, expected {want}', file=sys.stderr)
            return 1
    target = os.path.join(ROOT, 'game', 'leaf', 'lea_rdi_family.cpp')
    if a.apply:
        # Every refusal first. The old shape opened `target` before reading the tables, so a clash
        # truncated the translation unit it was refusing to write; the dead second `if a.apply`
        # below `return 0` was the only `makedirs`, so the live path also failed on a fresh tree.
        cs_path = os.path.join(ROOT, 'symbols', 'functions.csv')
        cs = list(csv.DictReader(open(cs_path)))
        known = {int(r['address'], 16) for r in cs}
        modes = list(install_mode.rows(ROOT))
        known_mode = {r['address'] for r in modes}
        cases = case_dir('lea_rdi')
        new_cs = [{'address': f'{m["address"]:#010x}', 'size': str(m['size']), 'name': f'leaf_lea_rdi_{m["address"]:08x}',
                   'system': 'leaf', 'status': 'edge-verified', 'notes': 'generated: return arg0 + K'} for m in ms]
        clash = [m for m in ms if m['address'] in known or m['address'] in known_mode]
        if clash:
            print(f'REFUSED: {len(clash)} of {len(ms)} already present, e.g. {clash[0]["address"]:#x}', file=sys.stderr)
            return 1
        if len(new_cs) != len(ms):
            print(f'REFUSED: functions rows {len(new_cs)} != {len(ms)}', file=sys.stderr); return 1
        # The mode table is written through its one writer; the callers pass addresses, never a path.
        added_mode = install_mode.append_host(ROOT, [m['address'] for m in ms])
        allrows = sorted(cs + new_cs, key=lambda r: int(r['address'], 16))
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cs[0].keys(), lineterminator='\n')
        w.writeheader(); w.writerows(allrows)
        atomicio.atomic_write(cs_path, buf.getvalue())
        cases.ensure()
        made = 0
        for i, m in enumerate(ms):
            vals = {'small': 0x1000 + (i % 7), 'wrap': 0xFFFFFFFFFFFFFFFF - m['k'] + 1}
            if i < 3:
                vals['window'] = 0x800000000 - m['k'] + 0x1000
            for tag, val in vals.items():
                name = f'leaf_lea_rdi_{m["address"]:08x}_{tag}'
                atomicio.atomic_write(cases.bare(name + '.json'), json.dumps(
                    {'schema': 1, 'address': f'{m["address"]:#010x}', 'id': name, 'returns': 'i64',
                     'args': {'rdi': f'{val & 0xFFFFFFFFFFFFFFFF:#x}'}}, indent=1))
                made += 1
        atomicio.atomic_write(target, body_text(ms))
        print(f'wrote body ({len(ms)} members), functions.csv +{len(new_cs)} (now {len(allrows)}), '
              f'install_mode.csv +{added_mode} (now {len(modes) + added_mode}), cases {made}')
        return 0
    print('dry run: pass --apply to write the body')
    return 0


if __name__ == '__main__':
    sys.exit(main())
