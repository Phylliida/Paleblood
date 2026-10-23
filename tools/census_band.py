#!/usr/bin/env python3
"""Size-band census: how many UNLANDED catalogue rows in [min,max] B pass the byte tier?

    python3 -P tools/census_band.py --min 1 --max 16      # control: must reproduce the leaf census
    python3 -P tools/census_band.py --min 17 --max 64     # the band the companion asked about

Passes means: blocks.census -> decoded == size, no unplaced target, ONE block, zero calls (1h), AND
no instruction whose value depends on its own address (1j iv: RIP-relative operand, fs:/gs: segment
base, relative branch, guest-space immediate), and no trap or privileged instruction (1j v, via
record_bytes_family.TRAPS -- one list, so the counter and the gate cannot disagree about the class).
Every refusal is counted by reason, so a zero cannot be a silent zero.
"""
import argparse
import collections
import csv

import capstone
from capstone.x86_const import (X86_OP_IMM, X86_OP_MEM, X86_REG_EIP, X86_REG_FS,
                                  X86_REG_GS, X86_REG_RIP)

import record_bytes_family as R

import blocks as B
import leaf_family_census as C


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=int, default=1)
    ap.add_argument('--max', type=int, default=16)
    ap.add_argument('--out', default='')
    o = ap.parse_args(argv)

    md = open(C.ELF, 'rb').read()
    landed = {int(r['address'], 16) for r in csv.DictReader(open('symbols/functions.csv'))}
    cat = [(int(r['address'], 16), int(r['size'])) for r in csv.DictReader(open('symbols/ghidra_functions.csv'))]
    band = [(a, s) for a, s in cat if o.min <= s <= o.max and a not in landed]
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    why = collections.Counter()
    shapes = collections.Counter()
    good = []
    for addr, size in band:
        off = addr - C.FILE_BIAS
        c = B.census(md, addr, size)
        if c['decoded'] != c['size'] or c['unplaced']:
            why['decode'] += 1; continue
        if c['blocks'] != 1 or c['calls']:
            why['control flow'] += 1; continue
        ins = list(cs.disasm(md[off:off + size], addr))
        if any(i.mnemonic in R.TRAPS for i in ins):
            why['trap (1j v)'] += 1; continue
        hit = any(i.mnemonic.startswith(('j', 'call'))
                  or any((op.type == X86_OP_MEM and op.mem.base in (X86_REG_RIP, X86_REG_EIP))
                         or (op.type == X86_OP_MEM and op.mem.segment in (X86_REG_FS, X86_REG_GS))
                         or (op.type == X86_OP_IMM and 0x400000 <= op.imm < 0x600000)
                         for op in i.operands) for i in ins)
        if hit:
            why['address dependent'] += 1; continue
        good.append((addr, size))
        shapes[' ; '.join(f'{i.mnemonic} {i.op_str}'.strip() for i in ins)] += 1
    print(f'band {o.min}..{o.max} B: unlanded {len(band)} · '
          f'TRANSCRIBABLE AND POSITION-INDEPENDENT {len(good)} over {len(shapes)} shapes · '
          f'{sum(s for _, s in good)} B')
    print('  refused:', dict(why))
    for k, v in shapes.most_common(5):
        print(f'    {v:5d}  {k[:88]}')
    if o.out:
        with open(o.out, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['address', 'size']); w.writerows(good)
        print('  wrote', o.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(__import__('sys').argv[1:]))
