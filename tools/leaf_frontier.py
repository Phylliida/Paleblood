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
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # -P strips the script dir; no PYTHONPATH help

import catalogue as C
import join_import_pc as J

BAND = pathlib.Path('symbols') / 'branch_band.csv.gz'


def compute(band=BAND, extents_path='symbols/ghidra_functions.csv'):
    """The four frontier figures. ONE implementation: derive.py calls this, it does not recount."""
    rows = list(C.read_rows(band))
    ext = J.load_extents(extents_path)
    # RETIRED ROWS ARE NOT CANDIDATES. A retired body is a verdict about the body, not a debt against
    # this instrument: advertising one as a candidate re-offers work already judged done-and-wrong.
    # The exclusion is counted and printed -- a filter that removes rows silently is the same defect as
    # one that removes none.
    retired = {r['address'] for r in C.read_rows(str(pathlib.Path(band).parent / 'retired.csv'))}
    free_unlanded_all = [(r['address'], r['size']) for r in rows
                         if r['branch'] == '0' and r['landed'] == 'False']
    free_unlanded = [(a, s) for a, s in free_unlanded_all if a not in retired]
    # A BODY IS NOT A CANDIDATE, whatever its status. The band's `landed` column means "status is not
    # original", so a row an emitter landed as `original` -- transcription, all an emitter CAN land -- reads
    # False here and is re-offered as work already done. The cache is NOT stale: its 38,096 landed rows equal
    # functions.csv's 38,096 non-original rows exactly. One word, two meanings. Excluded and COUNTED.
    # ONE SOURCE: the band's own `has_body` column. Reading functions.csv here was a second copy of the
    # same truth in a different artifact -- the shape this file just stopped committing one layer down.
    if 'has_body' not in (rows[0] if rows else {}):
        raise SystemExit('frontier: branch_band.csv.gz has no has_body column -- regenerate it with '
                         'tools/branch_census.py; a band without it cannot tell a body from a status')
    bodies = {r['address'] for r in rows if str(r['has_body']) == 'True'}
    bodied = [(a, s) for a, s in free_unlanded if a in bodies]
    free_unlanded = [(a, s) for a, s in free_unlanded if a not in bodies]
    indep = [(a, s) for a, s in free_unlanded if len(J.owners(ext, a)) == 1]
    out = [(a, s, 'short' if s < 14 else 'addressable') for a, s in indep]
    assert not ({a for a, _, _ in out} & bodies), \
        'a frontier that advertises a body is a menu of work already done'
    short = sum(1 for _, _, b in out if b == 'short')
    return {'retired_excluded': len(free_unlanded_all) - len(free_unlanded) - len(bodied),
            'bodied_excluded': len(bodied),
            'branch_free_unlanded': len(free_unlanded), 'independent': len(indep),
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
    print(f'retired excluded {fig["retired_excluded"]} · bodied excluded {fig["bodied_excluded"]} · '
          f'branch-free unlanded {fig["branch_free_unlanded"]} · independent {fig["independent"]} '
          f'· nested {fig["nested"]}')
    print(f'  frontier by band: addressable (family_scan can propose them today) {fig["addressable"]} '
          f'· short, size < 14 (floor + byte tier must move together) {fig["short"]}')
    print(f'  wrote {o.out}: {len(fig["rows"])} rows')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
