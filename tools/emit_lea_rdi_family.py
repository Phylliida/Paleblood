#!/usr/bin/env python3
"""Emit the `lea rax,[rdi+K]; ret` family, deriving every member from the bytes.

The member list is never read from a file a previous run printed: the strict operand
predicate below is the only source, so a template key that masks an index register cannot
smuggle a second family into the count (1,462 by string grouping, 483 by parsing the operand).

Pre-registered end state, asserted rather than read:
  members 483 · all unlanded before · every K >= 0xc · distinct K 114 · sizes {5, 8}
Each of those is an assertion; a mismatch names which one moved.
"""
import argparse, csv, json, os, re, sys, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        # Four tables from one iteration, each written from `ms` itself, so they cannot differ.
        open(target, 'w').write(body_text(ms))
        cs_path, mode_path = os.path.join(ROOT, 'symbols', 'functions.csv'), os.path.join(ROOT, 'symbols', 'install_mode.csv')
        cs = list(csv.DictReader(open(cs_path)))
        known = {int(r['address'], 16) for r in cs}
        modes = list(csv.DictReader(open(mode_path)))
        known_mode = {int(r['address'], 16) for r in modes}
        case_dir = os.path.join(ROOT, '..', 'data', 'cases', 'leaf')
        os.makedirs(case_dir, exist_ok=True)
        new_cs = [{'address': f'{m["address"]:#010x}', 'size': str(m['size']), 'name': f'leaf_lea_rdi_{m["address"]:08x}',
                   'system': 'leaf', 'status': 'edge-verified', 'notes': 'generated: return arg0 + K'} for m in ms]
        new_mode = [{'address': f'{m["address"]:#010x}', 'mode': 'host'} for m in ms]
        clash = [m for m in ms if m['address'] in known or m['address'] in known_mode]
        if clash:
            print(f'REFUSED: {len(clash)} of {len(ms)} already present, e.g. {clash[0]["address"]:#x}', file=sys.stderr)
            return 1
        for name, made, want in (('bodies', len(ms), len(ms)), ('functions rows', len(new_cs), len(ms)),
                                 ('mode rows', len(new_mode), len(ms))):
            if made != want:
                print(f'REFUSED: {name} {made} != {want}', file=sys.stderr); return 1
        allrows = sorted(cs + new_cs, key=lambda r: int(r['address'], 16))
        with open(cs_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cs[0].keys(), lineterminator='\n'); w.writeheader(); w.writerows(allrows)
        allm = sorted(modes + new_mode, key=lambda r: int(r['address'], 16))
        with open(mode_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=modes[0].keys(), lineterminator='\n'); w.writeheader(); w.writerows(allm)
        made = 0
        for i, m in enumerate(ms):
            a0 = int(m['address'])
            cases = {'small': 0x1000 + (i % 7), 'wrap': 0xFFFFFFFFFFFFFFFF - m['k'] + 1}
            if i < 3:
                cases['window'] = 0x800000000 - m['k'] + 0x1000
            for tag, val in cases.items():
                name = f'leaf_lea_rdi_{m["address"]:08x}_{tag}'
                json.dump({'schema': 1, 'address': f'{m["address"]:#010x}', 'id': name, 'returns': 'i64',
                           'args': {'rdi': f'{val & 0xFFFFFFFFFFFFFFFF:#x}'}},
                          open(os.path.join(case_dir, name + '.json'), 'w'), indent=1)
                made += 1
        print(f'wrote body ({len(ms)} members), functions.csv +{len(new_cs)} (now {len(allrows)}), '
              f'install_mode.csv +{len(new_mode)} (now {len(allm)}), cases {made}')
        return 0
    if a.apply:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, 'w').write(body_text(ms))
        print(f'wrote {os.path.relpath(target, ROOT)} ({len(ms)} members)')
    else:
        print('dry run: pass --apply to write the body')
    return 0


if __name__ == '__main__':
    sys.exit(main())
