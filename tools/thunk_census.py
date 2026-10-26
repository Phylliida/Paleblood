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
import sys
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # -P strips the script dir; no PYTHONPATH help
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


def compute(max_b=13, floor=None):
    """The two thunk figures. ONE implementation: derive.py calls this, it does not recount."""
    floor = length_floor() if floor is None else floor
    md = pathlib.Path(C.ELF).read_bytes()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    landed = C.landed_addresses()
    extents = J.load_extents('symbols/ghidra_functions.csv')
    size_of = dict(extents)
    ownership = J.index(extents)
    pop = sorted(a for a, s in extents
                 if s <= max_b and a not in landed and len(J.owners_indexed(ownership, a)) == 1)
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
    return {'rows': len(pop), 'branch_free': by_sel.get('family_scan:jump-free', 0),
            'multi': multi, 'none_e': none_e, 'by_sel': by_sel, 'sets': sets, 'table': rows,
            'max_b': max_b}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=13)
    ap.add_argument('--out', default='')
    o = ap.parse_args(argv)
    f = compute(o.max)
    print(f'thunks: {f["rows"]} independent unlanded rows <= {f["max_b"]} B')
    print(f'  LANDABLE AND MISSED (no selector refuses them): {len(f["none_e"])}'
          + (f' -- {[hex(a) for a in f["none_e"][:8]]}' if f['none_e'] else ''))
    print(f'  EXCLUDED BY TWO OR MORE SELECTORS: {f["multi"]}'
          '  <- no individual selector report could surface these')
    for k, v in f['by_sel'].most_common():
        print(f'    {v:5d}  {k}')
    print('  by exact selector set:')
    for k, v in f['sets'].most_common():
        print(f'    {v:5d}  {" + ".join(k) if k else "<none>"}')
    if o.out:
        with open(o.out, 'w', newline='') as fh:
            # Every row here is EXCLUDED -- that is the file's whole content ("landable and missed: 0").
            # A column saying so is not redundant with excluded_by: it is the difference between a list of
            # candidates and a list of refusals, and the next reader gets one glance instead of an audit.
            w = csv.writer(fh)
            w.writerow(['address', 'size', 'shape', 'excluded_by', 'landable'])
            w.writerows([tuple(r) + ('no',) for r in f['table']])
        print(f'  wrote {len(f["table"])} (address, selector) rows to {o.out}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
