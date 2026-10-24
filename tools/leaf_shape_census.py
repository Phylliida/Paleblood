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
import json
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


def load_segments(md, flags=False):
    """PT_LOADs as (vaddr, filesz, memsz) in GUEST space, or 4-tuples with p_flags if asked.

    `flags=True` is a defaulted keyword so every existing two- and three-value caller keeps its shape;
    the seeding gate needs p_flags because "inside memsz" is not the same question as "writable", and
    a destination that is reserved but read-only is a fault, not a target.

    guest = vaddr + 0x400000 (EBOOT_BASE) on this ELF; `file = guest - 0x3FC000` is the same fact
    one step later. Both halves of a segment matter and they are not the same number: p_filesz is
    what the loader FILLS, p_memsz what it RESERVES. A target past filesz and inside memsz reads
    as a constant zero in the shipped process, so a body and its mutant both see it and the
    differential compares zero to zero.
    """
    phoff = int.from_bytes(md[0x20:0x28], 'little')
    entsize = int.from_bytes(md[0x36:0x38], 'little')
    n = int.from_bytes(md[0x38:0x3a], 'little')
    out = []
    for i in range(n):
        b = md[phoff + i * entsize:]
        if int.from_bytes(b[0:4], 'little') != 1:  # PT_LOAD
            continue
        vaddr = int.from_bytes(b[0x10:0x18], 'little')
        filesz = int.from_bytes(b[0x20:0x28], 'little')
        memsz = int.from_bytes(b[0x28:0x30], 'little')
        fl = int.from_bytes(b[0x04:0x08], 'little')
        out.append((vaddr + 0x400000, filesz, memsz, fl) if flags else (vaddr + 0x400000, filesz, memsz))
    return out


def classify_target(segs, addr):
    """'filesz' / 'zerofill' / 'unmapped' for a guest address -- the gate's three outcomes."""
    for base, filesz, memsz in segs:
        if base <= addr < base + filesz:
            return 'filesz'
        if base + filesz <= addr < base + memsz:
            return 'zerofill'
    return 'unmapped'


def targets_for(md, cs, rows, want, segs):
    """Per-row targets for one shape: the rip load's static address and the store's K.

    The load target is static (addr + insn size + disp) and therefore checkable before a body is
    written. The store target is NOT: it is [loaded pointer + K], so the case has to supply the
    pointer -- argument->obligation, not addr-only.
    """
    out = []
    for addr, size in rows:
        ins = list(cs.disasm(md[addr - BIAS:addr - BIAS + size], addr))
        if len(ins) < 2 or shape_of(ins, 3) != want:
            continue
        load_disp = next((op.mem.disp for op in ins[0].operands
                          if op.type == capstone.x86.X86_OP_MEM), None)
        if load_disp is None:
            continue
        tgt = addr + ins[0].size + load_disp
        store = next((op.mem.disp for op in ins[1].operands
                      if op.type == capstone.x86.X86_OP_MEM), 0)
        src = next((op for op in ins[1].operands
                    if op.type in (capstone.x86.X86_OP_IMM, capstone.x86.X86_OP_REG)), None)
        out.append({'address': addr, 'size': size, 'load_target': tgt,
                    'where': classify_target(segs, tgt),
                    'store_k': store,
                    'src': ('imm' if src is not None and src.type == capstone.x86.X86_OP_IMM
                            else 'reg' if src is not None else 'none')})
    return out


COLUMNS = ('address', 'size', 'class')


def frontier_lines(path=None):
    """The frontier's records, header checked and removed.

    A reader that requires a header refuses a first record that is data. csv.DictReader swallows
    such a record silently -- that cost one population here (6,809 rows counted from a file holding
    6,810) and the shortage read as a finding -- so the columns are declared here and anything else
    is a refusal with a sentence in it.
    """
    lines = [l for l in open(path or FRONTIER, newline='').read().splitlines() if l]
    if not lines:
        raise ValueError('the frontier is empty: an absent worklist is not an empty one')
    head = tuple(lines[0].split(','))
    if head != COLUMNS:
        raise ValueError(f'first record is {head!r}, not {COLUMNS!r} -- a file whose first record '
                         f'is data is a population short by one row in every DictReader')
    return [l.split(',') for l in lines[1:]]


def frontier(path=None):
    return [(int(r[0], 16), int(r[1])) for r in frontier_lines(path) if r[2] == 'addressable']


def frontier_population(path=None):
    """Every row of the frontier FILE, counted by its own third column.

    frontier() keeps `addressable` rows and drops the rest at the door, so their absence reads
    exactly like a clean census -- a size floor that no bucket names. The counts come from the same
    file the loader reads, so the dropped population is printed as its own bucket instead of being
    left for a reader to obtain by subtracting two other numbers. That subtraction has already been
    performed wrong here once (6,888 - 6,809 = 79, arithmetic looking for a home), and a population
    that requires subtraction will be subtracted wrong again.
    """
    cols = collections.Counter()
    for parts in frontier_lines(path):
        cols[parts[2] if len(parts) > 2 else '<no third column>'] += 1
    return cols


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
    # --targets-for answers the question that must be answered BEFORE a body is written: is the
    # static load target inside p_filesz? A shape whose targets are in the zero-fill tail cannot
    # be discriminated by any case, so authoring it first and refusing it after is 78 bodies of
    # evidence for nothing.
    ap.add_argument('--targets-for', default=None, metavar='SHAPE')
    # --targets-json prints EVERY member of that shape as one JSON object per line. Without it the
    # population's distribution had to be inferred from five printed rows, which produced a pre-
    # registration whose histogram was a derivation (47 x 14 = 658 divided equally). A tool that
    # renders five rows of a population whose distribution IS the question leaves its totals to be
    # guessed, and the guess is indistinguishable from a measurement once it is in a document.
    ap.add_argument('--targets-json', action='store_true')
    # --frontier exists so the header refusal is reachable by a test. A refusal no argument can
    # vary is a paragraph, not a guard.
    ap.add_argument('--frontier', default=FRONTIER)
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
    try:
        rows = frontier(a.frontier)
        cols = frontier_population(a.frontier)
    except ValueError as e:
        print(f'leaf_shape_census: {a.frontier}: {e}', file=sys.stderr)
        return 2
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
    if a.targets_for is not None:
        segs = load_segments(md)
        t = targets_for(md, cs, rows, a.targets_for, segs)
        if not t:
            print(f'leaf_shape_census: no frontier row has shape {a.targets_for!r} -- a shape '
                  f'filter that matches nothing is not a measurement of that shape',
                  file=sys.stderr)
            return 1
        import collections as _c
        where = _c.Counter(x['where'] for x in t)
        # The summary follows the stream, not the habit: with --targets-json stdout is a record
        # stream and nothing else, so a consumer can pipe it without a filter that guesses which
        # lines are data. A stageable shape needs no --out flag and no line filter.
        out = sys.stderr if a.targets_json else sys.stdout
        print(f'shape {a.targets_for}', file=out)
        print(f'rows {len(t)} | load target inside filesz {where["filesz"]} | '
              f'zero-fill tail {where["zerofill"]} | unmapped {where["unmapped"]}', file=out)
        print('population ' + ' | '.join(f'{n} {k}' for k, n in sorted(cols.items())), file=out)
        print(f'store src {_c.Counter(x["src"] for x in t)} | '
              f'distinct store K {len({x["store_k"] for x in t})} | '
              f'distinct load K {len({x["load_target"] - x["address"] for x in t})}', file=out)
        if a.targets_json:
            for x in t:
                print(json.dumps(x, sort_keys=True))
            return 0
        for x in t[:5]:
            print(f'  {x["address"]:#010x} size {x["size"]:>3} load->{x["load_target"]:#x} '
                  f'{x["where"]:>8} store +{x["store_k"]:#x} src {x["src"]}')
        # WHICH OUTCOMES ADMIT A BODY, and why this is not the same question as "is the target
        # file-backed". A target past p_filesz but inside p_memsz is a constant zero in the
        # SHIPPED process -- but the case is not limited to the shipped state: harness.py:458
        # admits a `fixture_setup` write anywhere inside a segment's memsz, and snapshot() reads
        # memsz, so a case can seed the slot and the snapshot will see what the body did with it.
        # Verified by mapping the image and reading the seed back through it. So `zerofill` is
        # admissible WITH a seeding case, and only `unmapped` -- outside every memsz, where a
        # write faults -- refuses. The old blanket refusal had the wrong reason: it said no case
        # can discriminate, when the case supplies the discriminating value itself.
        good = [x for x in t if x['where'] in ('filesz', 'zerofill')]
        seeded = sum(1 for x in good if x['where'] == 'zerofill')
        print(f'BATCH {len(good)} rows / {sum(x["size"] for x in good)} B '
              f'({seeded} needing a fixture-seeded slot, {len(good) - seeded} file-backed) | '
              f'{len(t) - len(good)} refused as unmapped')
        return 0 if good else 1

    covered = sum(shapes.values())
    print('population ' + ' | '.join(f'{n} {k}' for k, n in sorted(cols.items()))
          + f' | {sum(cols.values())} total (every row of the file, each in a named bucket)')
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
