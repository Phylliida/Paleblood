#!/usr/bin/env python3
"""Thunk census: the short band, and WHICH selector excluded each row.

    python3 -P tools/thunk_census.py --max 13 [--out symbols/thunks.csv]

The population is the unlanded, INDEPENDENTLY-OWNED rows at or below --max bytes. A row nested inside
a larger extent is a tail or an inlined block with no entry a guest can call, so landing it would
create a row for code nothing reaches -- the join decides that, not this tool.

One row per (address, selector), because a row refused by two predicates that never consulted each
other is invisible from either selector's own output. The selectors are the real ones: the length
floor is read out of family_scan.py's own argument parser (never a second copy of 14), and the byte
tier's four refusals come from census_band.refusal -- one implementation, so the census and the gate
cannot disagree about a class.

A row with NO selector is landable and was missed. That count is printed first.
"""
import argparse
import collections
import csv
import pathlib
import re

import capstone

import census_band as CB
import join_import_pc as J
import leaf_family_census as C


def length_floor() -> int:
    """family_scan.py's own --min-size default, read from its source. A missing floor refuses."""
    src = pathlib.Path(__file__).with_name('family_scan.py').read_text()
    m = re.search(r"--min-size', type=int, default=(\d+)", src)
    if not m:
        raise SystemExit("thunk_census: family_scan.py declares no --min-size default -- refusing "
                         "rather than assuming 14")
    return int(m.group(1))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=13)
    ap.add_argument('--out', default='')
    o = ap.parse_args(argv)
    floor = length_floor()
    md = open(C.ELF, 'rb').read()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    landed = C.landed_addresses()
    extents = J.load_extents('symbols/ghidra_functions.csv')
    size_of = dict(extents)
    pop = sorted(a for a, s in extents
                 if s <= o.max and a not in landed and len(J.owners(extents, a)) == 1)
    rows, by_sel, multi, sets = [], collections.Counter(), 0, collections.Counter()
    none_e = []
    for a in pop:
        s = size_of[a]
        sels = []
        if s < floor:
            sels.append(f'family_scan:min-size={floor}')
        ins = list(cs.disasm(md[a - C.FILE_BIAS:a - C.FILE_BIAS + s], a))
        # family_scan's own default, from --any-control-flow's store_false on dest='jump_free':
        # it keeps only jump-free bodies unless told otherwise, so a tail jmp excludes a row here
        # as surely as the length floor does, and the two never consult each other.
        if any(i.mnemonic.startswith(('j', 'call')) for i in ins):
            sels.append('family_scan:jump-free')
        r = CB.refusal(md, cs, a, s)
        if r:
            sels.append(f'bytes:{r}')
        if not sels:
            none_e.append(a)
        if len(sels) >= 2:
            multi += 1
        sets[tuple(sels)] += 1
        for sel in sels:
            by_sel[sel] += 1
        shape = ' ; '.join((i.mnemonic + ' ' + i.op_str).strip() for i in ins) or '<undecoded>'
        for sel in sels:
            rows.append((f'{a:#010x}', s, shape, sel))
    print(f'thunks: {len(pop)} independent unlanded rows <= {o.max} B')
    print(f'  LANDABLE AND MISSED (no selector refuses them): {len(none_e)}'
          + (f' -- {[hex(a) for a in none_e[:8]]}' if none_e else ''))
    print(f'  EXCLUDED BY TWO OR MORE SELECTORS: {multi}'
          '  <- no individual selector report could surface these')
    for k, v in by_sel.most_common():
        print(f'    {v:5d}  {k}')
    print('  by exact selector set:')
    for k, v in sets.most_common():
        print(f'    {v:5d}  {" + ".join(k) if k else "<none>"}')
    if o.out:
        with open(o.out, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['address', 'size', 'shape', 'excluded_by']); w.writerows(rows)
        print(f'  wrote {len(rows)} (address, selector) rows to {o.out}')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
