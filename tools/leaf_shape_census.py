"""Shape census over the committed leaf frontier: what families are actually left.

WHY THIS EXISTS. `emit_leaf_family.py` lands a family only if a TEMPLATE names its exact
mnemonic tuple and operand form. On the day this was written every one of the sixteen templates
reported `0 unlanded members` -- fifteen exhausted, the sixteenth refusing 161/161 as zero-fill
absence -- while symbols/leaf_frontier.csv still carried 6,288 addressable branch-free rows.
So the frontier was not blocked by a repair; it was blocked by a population with no family.
That is a shape question, and it is answerable from committed artifacts alone: the frontier CSV
and the ELF. No catalogue JSON, no Ghidra pipeline, no /tmp surrogate.

WHAT IT PRINTS, and what it refuses to print. Rows, not guesses: each shape carries the row
count, the byte count, and -- for single-instruction shapes -- the number of distinct K, because
a family with one K is one member repeated, while a family with n distinct K is n members whose
cases can each be made to read their own constant. Top-N only, with the population printed
beside it: a histogram is a summary, and a summary divided by itself is 100%.

SELECTOR. `--max-insns` bounds what a template could plausibly express; the default 3 is a
choice, so it is named on the command line and printed in the output. Rows beyond it are
counted, never dropped silently.
"""
import argparse
import collections
import csv
import os
import sys

import capstone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
FRONTIER = os.path.join(ROOT, 'symbols', 'leaf_frontier.csv')
# Uniform across this ELF's PT_LOADs (readelf: RX off 0x4000/vaddr 0x0, RW off 0x50e0000/
# vaddr 0x50dc000, both vaddr - off = -0x4000). Off by 0x4000 a patch reads back perfectly and
# fires at a site nobody selected.
BIAS = 0x3FC000


def frontier():
    rows = [r for r in (l.split(',') for l in open(FRONTIER, newline='').read().splitlines()) if r]
    return [(int(r[0], 16), int(r[1])) for r in rows if r[2] == 'addressable']


def shape_of(ins, max_insns):
    """A template-shaped name: mnemonics plus operand forms with every number replaced by K."""
    parts = []
    for i in ins[:max_insns]:
        ops = []
        for op in i.operands:
            if op.type == capstone.x86.X86_OP_IMM:
                ops.append('K')
            elif op.type == capstone.x86.X86_OP_MEM:
                m = op.mem
                reg = i.reg_name(m.base) if m.base else '-'
                idx = i.reg_name(m.index) if m.index else None
                d = '+K' if m.disp else ''
                ops.append(f'{i.reg_name(m.segment)+":" if m.segment else ""}[{reg}{"+"+idx if idx else ""}{d}]')
            elif op.type == capstone.x86.X86_OP_REG:
                ops.append(i.reg_name(op.reg))
            else:
                ops.append('?')
        parts.append(i.mnemonic + (' ' + ','.join(ops) if ops else ''))
    return ' ; '.join(parts)


def main(argv):
    ap = argparse.ArgumentParser(description='shape census over the leaf frontier')
    ap.add_argument('--max-insns', type=int, default=3)
    ap.add_argument('--top', type=int, default=15)
    # --elf exists so the refusal arm is reachable by a test. A path constant that no argument can
    # vary gives a refusal nobody can execute, and an unexecuted refusal arm is a paragraph.
    ap.add_argument('--elf', default=ELF)
    a = ap.parse_args(argv)
    if a.max_insns < 1 or a.top < 1:
        print('leaf_shape_census: --max-insns and --top must be positive', file=sys.stderr)
        return 2
    if not os.path.exists(a.elf):
        print(f'leaf_shape_census: {a.elf} not found -- the frontier is committed but the bytes it '
              f'names are not; nothing can be decoded and nothing is claimed about them',
              file=sys.stderr)
        return 3
    md = open(a.elf, 'rb').read()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    rows = frontier()
    shapes = collections.Counter()
    bytes_of = collections.Counter()
    ks = collections.defaultdict(set)
    undecoded, long_rows, over = 0, 0, 0
    for addr, size in rows:
        off = addr - BIAS
        if off < 0 or off + size > len(md):
            undecoded += 1
            continue
        ins = list(cs.disasm(md[off:off + size], addr))
        if not ins:
            undecoded += 1
            continue
        if len(ins) > a.max_insns:
            over += 1
            continue
        s = shape_of(ins, a.max_insns)
        shapes[s] += 1
        bytes_of[s] += size
        if len(ins) == 1:
            for op in ins[0].operands:
                if op.type == capstone.x86.X86_OP_MEM and op.mem.disp:
                    ks[s].add(op.mem.disp)
                elif op.type == capstone.x86.X86_OP_IMM:
                    ks[s].add(op.imm)
    covered = sum(shapes.values())
    print(f'frontier {len(rows)} addressable rows | decoded {covered} | over {a.max_insns} '
          f'insns {over} (counted, not dropped) | undecoded {undecoded} | '
          f'max-insns {a.max_insns} (a choice, printed beside its consequence)')
    print(f'distinct shapes {len(shapes)} | covered bytes {sum(bytes_of.values())} | '
          f'{100.0 * covered / len(rows) if rows else 0:.1f}% of the frontier is expressible '
          f'within {a.max_insns} instruction(s)')
    print()
    print(f'{"rows":>6} {"bytes":>8} {"distinctK":>9}  shape')
    for s, n in shapes.most_common(a.top):
        k = len(ks[s]) if s in ks else 'n/a'
        print(f'{n:>6} {bytes_of[s]:>8} {k:>9}  {s}')
    return 0 if covered else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
