#!/usr/bin/env python3
"""Branch census: which catalogue rows contain a branch or call, and what the two denominators are.

    python3 -P tools/branch_census.py --out symbols/branch_band.csv

Two numbers have been doing one job. 38,018/157,757 = 24.10% is SCOPE -- a fraction of Ghidra's
reach, the rows a leaf/byte selector could ever touch. 38,018/41,282 = 87.4% is PROGRESS -- a
fraction of the branch-free population, which is what the leaf toolchain can address at all. A
branch-containing row is not blocked by capability: it belongs to the function campaign, whose
generated-C path carries no single-block constraint. Widening jump_free would let leaf machinery
accept bodies whose control flow it cannot express, so this tool counts the boundary, it does not
move it.

The branch predicate is family_scan's own --any-control-flow negation (mnemonic starts with 'j' or
'call'), so the census and the selector cannot disagree about what a branch is.
"""
import argparse
import csv
import gzip
import io
import pathlib
import sys

import capstone

import join_import_pc as J
import leaf_family_census as C


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='symbols/branch_band.csv')
    o = ap.parse_args(argv)
    md = open(C.ELF, 'rb').read()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    landed = C.landed_addresses()
    extents = J.load_extents('symbols/ghidra_functions.csv')
    cat = [(int(r['address'], 16), int(r['size'])) for r in
           csv.DictReader(open('symbols/ghidra_functions.csv'))]
    rows = []
    undecoded = 0
    for a, s in cat:
        off = a - C.FILE_BIAS
        ins = list(cs.disasm(md[off:off + s], a)) if 0 <= off and off + s <= len(md) else []
        if not ins:
            undecoded += 1
            rows.append((a, s, '?', a in landed))
            continue
        rows.append((a, s, '1' if any(i.mnemonic.startswith(('j', 'call')) for i in ins) else '0',
                     a in landed))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['address', 'size', 'branch', 'landed'])
    w.writerows([(f'{a:#010x}', s, b, l) for a, s, b, l in rows])
    # 3.6 MB of repetitive rows is over the repo's 2 MB artifact limit, and it is regenerable from
    # the committed tool, so it ships gzipped with mtime=0: byte-reproducible, not merely small.
    if o.out.endswith('.gz'):
        pathlib.Path(o.out).write_bytes(gzip.compress(buf.getvalue().encode(), mtime=0))
    else:
        pathlib.Path(o.out).write_text(buf.getvalue())
    total = len(rows)
    branch = [r for r in rows if r[2] == '1']
    free = [r for r in rows if r[2] == '0']
    free_landed = [r for r in free if r[3]]
    land = [(a, s) for a, s, b, l in rows if l]
    unlanded_free = [a for a, s, b, l in free if not l]
    indep = [a for a in unlanded_free if len(J.owners(extents, a)) == 1]
    print(f'branch census over {total} catalogue rows (undecoded {undecoded}):')
    print(f'  branch or call      {len(branch):6d}  ({len(branch)/total:.1%})  landed {sum(1 for r in branch if r[3])}')
    print(f'  branch-FREE         {len(free):6d}  landed {len(free_landed)}')
    print(f'  PROGRESS   {len(land)} landed / {len(free)} branch-free = {len(free_landed)/len(free):.2%}'
          f'  (landed branch-free {len(free_landed)})')
    print(f'  SCOPE      {len(land)} landed / {total} catalogued = {len(land)/total:.2%}')
    print(f'  unlanded branch-free {len(unlanded_free)}: independent (owners==1) {len(indep)}, '
          f'nested {len(unlanded_free)-len(indep)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
