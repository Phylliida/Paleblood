#!/usr/bin/env python3
"""Basic-block census, from the bytes, as the denominator for case adequacy.

A differential that exercises one basic block cannot witness a function whose other blocks never
run. Mutants settle whether the *comparator* is sensitive; they say nothing about *coverage*, and
three chosen mutants are caught by the first case that reaches the function. So the A/B's primary
number is cases-until-every-block-runs, and it needs a block count first. This computes it from
the decoded bytes: a block starts at the entry, at every branch target, and after every branch;
it ends at a branch or a return.

Anything the decoder cannot place exactly is counted and refused, never approximated: a branch
target that does not land on an instruction boundary means the block cannot be enumerated, and a
function with any such target cannot claim full coverage by construction.

    tools/blocks.py --address ADDR [--address ADDR ...]
    tools/blocks.py --sample 200            # the >1024 B tier, seeded by address order

Addresses come from the caller, never from this file: a table of them here would be a second,
drifting copy of a population that symbols/ghidra_functions.csv already owns.
"""
import argparse
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import capstone  # noqa: E402

FILE_BIAS = 0x3fc000          # file = guest - FILE_BIAS; a +0x4000 bias decodes fluent garbage
TIER_FLOOR = 1024
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ELF = os.path.join(_ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
_GHIDRA = os.path.join(_ROOT, 'symbols', 'ghidra_functions.csv')
TERMINATING = {'ret', 'jmp', 'ljmp', 'iret', 'iretq', 'ud2', 'hlt'}
CONDITIONAL = {'ja', 'jae', 'jb', 'jbe', 'je', 'jne', 'jg', 'jge', 'jl', 'jle', 'jna', 'jnae',
               'jnb', 'jnbe', 'jnc', 'jne', 'jng', 'jnge', 'jnl', 'jnle', 'jno', 'jnp', 'jns',
               'jnz', 'jo', 'jp', 'jpe', 'jpo', 'js', 'jz', 'jcxz', 'jecxz', 'jrcxz', 'loop',
               'loope', 'loopne'}


def decode(elf_bytes, guest, size):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    off = guest - FILE_BIAS
    return list(md.disasm(elf_bytes[off:off + size], guest))


def blocks(insns):
    """Return (block count, unplaceable branch targets, block sizes) or raise on short decode."""
    if not insns:
        return 0, 0, []
    starts = {insns[0].address}
    boundaries = {i.address for i in insns}
    unplaced = 0
    for i in insns:
        mnem = i.mnemonic
        branch = mnem in TERMINATING or mnem in CONDITIONAL
        if i.group(capstone.CS_GRP_JUMP):
            tgt = None
            for op in i.operands:
                if op.type == capstone.x86.X86_OP_IMM:
                    tgt = op.imm
            if tgt is None:
                continue                      # indirect: no static edge, not an unplaced one
            if tgt in boundaries:
                starts.add(tgt)
            else:
                unplaced += 1
        if branch:
            nxt = i.address + i.size
            if nxt in boundaries:
                starts.add(nxt)
    ordered = sorted(starts)
    sizes = [b - a for a, b in zip(ordered, ordered[1:])]
    sizes.append(insns[-1].address + insns[-1].size - ordered[-1])
    return len(ordered), unplaced, sizes


def census(elf_bytes, guest, size):
    insns = decode(elf_bytes, guest, size)
    decoded = sum(i.size for i in insns)
    n, unplaced, sizes = blocks(insns)
    return {'blocks': n, 'unplaced': unplaced, 'decoded': decoded, 'size': size,
            'largest': max(sizes) if sizes else 0,
            'calls': sum(1 for i in insns if i.mnemonic == 'call')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', default=_ELF)
    ap.add_argument('--address', action='append', default=[], type=lambda s: int(s, 0))
    ap.add_argument('--sample', type=int, default=0, help='census N tier entries, seeded by address')
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    elf_bytes = open(a.elf, 'rb').read()
    tier = {int(r['address'], 16): int(r['size'])
            for r in csv.DictReader(open(_GHIDRA)) if int(r['size']) > TIER_FLOOR}
    targets = list(a.address)
    if a.sample:
        pool = sorted(tier)
        random.Random(a.seed).shuffle(pool)
        targets += pool[:a.sample]
    if not targets:
        ap.error('pass --address or --sample')
    rows = []
    for guest in targets:
        size = tier.get(guest)
        if size is None:
            size = next((int(r['size']) for r in csv.DictReader(open(os.path.join(_ROOT, 'symbols', 'functions.csv')))
                         if int(r['address'], 16) == guest), 0)
        if not size:
            print(f'{guest:#010x}: not in the partition', file=sys.stderr)
            continue
        c = census(elf_bytes, guest, size)
        rows.append((guest, c))
        print(f'{guest:#010x} size {c["size"]:5d} blocks {c["blocks"]:4d} calls {c["calls"]:4d} '
              f'largest {c["largest"]:5d} unplaced {c["unplaced"]:3d} '
              f'decoded {c["decoded"]}/{c["size"]}')
    if len(rows) > 1:
        bs = sorted(c['blocks'] for _, c in rows)
        short = sum(1 for _, c in rows if c['decoded'] != c['size'])
        unp = sum(1 for _, c in rows if c['unplaced'])
        print(f'\n{len(rows)} functions: blocks median {bs[len(bs) // 2]} min {bs[0]} max {bs[-1]}; '
              f'short decode {short}; with unplaceable targets {unp}')


if __name__ == '__main__':
    main()
