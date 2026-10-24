#!/usr/bin/env python3
"""The leaf campaign's remaining frontier, derived from committed artifacts only.

    python3 -P tools/leaf_frontier.py --out symbols/leaf_frontier.csv

Frontier = catalogue rows that are branch-free (so a leaf selector may address them at all) and
unlanded. Of those, INDEPENDENT = exactly one containing catalogue extent, i.e. a candidate entry
rather than a tail of a larger function; owners==1 is a candidate filter, not proof of entry.

The band column says which selector could reach the row today: 'short' rows are excluded by
family_scan's --min-size 14 before jump_free is even consulted, so they need the floor and the byte
tier to move together (see tools/thunk_census.py); 'addressable' rows pass every filter this tree
has and are simply not done yet.
"""
import argparse
import csv
import gzip
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # -P strips the script dir; no PYTHONPATH help

import join_import_pc as J

BAND = pathlib.Path('symbols') / 'branch_band.csv.gz'


def compute(band=BAND, extents_path='symbols/ghidra_functions.csv'):
    """The four frontier figures. ONE implementation: derive.py calls this, it does not recount."""
    with gzip.open(band, 'rt', newline='') as f:
        rows = list(csv.DictReader(f))
    ext = J.load_extents(extents_path)
    free_unlanded = [(int(r['address'], 16), int(r['size'])) for r in rows
                     if r['branch'] == '0' and r['landed'] == 'False']
    indep = [(a, s) for a, s in free_unlanded if len(J.owners(ext, a)) == 1]
    out = [(a, s, 'short' if s < 14 else 'addressable') for a, s in indep]
    short = sum(1 for _, _, b in out if b == 'short')
    return {'branch_free_unlanded': len(free_unlanded), 'independent': len(indep),
            'nested': len(free_unlanded) - len(indep), 'addressable': len(out) - short,
            'short': short, 'rows': out}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='symbols/leaf_frontier.csv')
    o = ap.parse_args(argv)
    fig = compute()
    # The header is part of the artifact. Without it every csv.DictReader over this file eats
    # its first data row silently, and the resulting count is short by one in a way that reads
    # like a finding (6,809 against a file holding 6,810 was exactly that).
    pathlib.Path(o.out).write_text('address,size,class\n' + ''.join(
        f'{a:#010x},{s},{b}\n' for a, s, b in fig['rows']))
    print(f'branch-free unlanded {fig["branch_free_unlanded"]} · independent {fig["independent"]} '
          f'· nested {fig["nested"]}')
    print(f'  frontier by band: addressable (family_scan can propose them today) {fig["addressable"]} '
          f'· short, size < 14 (floor + byte tier must move together) {fig["short"]}')
    print(f'  wrote {o.out}: {len(fig["rows"])} rows')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
