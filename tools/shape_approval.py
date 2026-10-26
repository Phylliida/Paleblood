#!/usr/bin/env python3
"""Turn one approved shape review into the per-function review rows it covers -- or refuse.

The user's answer (docs/approval-answers.md) decides whether `scope = shape` is meaningful at all;
this tool only cashes it in. It refuses when the answer is absent, when the member set no longer
hashes to what the shape row pinned, and when any member lacks the two pins a review row must carry.

A shape row is `address = 0x00000000`, `name = <family prefix>`, and `notes` carrying
`members=<sha256[:16]>` over the family's catalogue lines. Every derived row is an ordinary
`scope = function` row, so every existing consumer -- promote.py, check_pins.py, progress.py --
keeps working without learning a new vocabulary.
"""

import argparse
import csv
import datetime
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verification  # noqa: E402
from validate_functions import REVIEW_HEADER, REVIEW_SCOPES, shape_answer  # noqa: E402

SHAPE_ADDRESS = '0x00000000'
REVIEWS = os.path.join('symbols', 'reviews.csv')
FUNCS = os.path.join('symbols', 'functions.csv')


def read_rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def family_members(rows, prefix):
    return [r for r in rows if r['name'] == prefix or r['name'].startswith(prefix + '_')]


def member_set_hash(members):
    """The same recipe docs/approval-request.md quotes: sorted catalogue lines, hashed, first 16 hex."""
    lines = sorted(','.join(m[k] for k in ('address', 'size', 'name', 'system', 'status', 'notes'))
                   for m in members)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()[:16]


def pinned_hash(notes):
    for token in notes.split():
        if token.startswith('members='):
            return token.split('=', 1)[1]
    return ''


def cascade(root, apply=False):
    reviews_path = os.path.join(root, REVIEWS)
    rows = read_rows(reviews_path)
    shapes = [r for r in rows if (r['scope'] or 'function') == 'shape' and r['verdict'] == 'approved']
    answer_path = os.path.join(root, 'docs', 'approval-answers.md')
    if not shapes:
        print(f'shape: no approved shape review in {reviews_path}; nothing to cascade')
        return 0
    if not shape_answer(root):
        print(f'shape: refused -- {answer_path} does not say `scope=shape`; a shape review '
              'cannot stand in for the owner\'s decision', file=sys.stderr)
        return 1
    funcs = read_rows(os.path.join(root, FUNCS))
    made, errs = [], []
    for s in shapes:
        if s['address'].strip().lower() != SHAPE_ADDRESS:
            errs.append(f"shape: {s['name']}: a shape row must sit at {SHAPE_ADDRESS}, not {s['address']!r}")
            continue
        members = family_members(funcs, s['name'].strip())
        if len(members) < 2:
            errs.append(f"shape: {s['name']}: a family needs at least two members, found {len(members)}")
            continue
        want, got = pinned_hash(s['notes']), member_set_hash(members)
        if not want:
            errs.append(f"shape: {s['name']}: notes carry no members=<hash>, so the approval names no member set")
            continue
        if want != got:
            errs.append(f"shape: {s['name']}: the member set moved since the approval (members={want}, now {got}); "
                        f"the approval covers what was reviewed, not what is here")
            continue
        for i, m in enumerate(sorted(members, key=lambda r: int(r['address'], 16)), 1):
            source = verification.source_hash(root, m['name'])
            evidence = verification.evidence_hash(root, m['name'])
            if not source or not evidence:
                errs.append(f"shape: {m['name']}: refused -- no {'replacement source' if not source else 'ledger rows'}"
                            f", so the derived approval would pin nothing")
                continue
            made.append({'address': m['address'], 'name': m['name'],
                         'date': datetime.date.today().isoformat(),
                         'reviewer': f"derived from shape approval by {s['reviewer']}",
                         'verdict': 'approved', 'scope': 'function', 'source_hash': source,
                         'cases_sha256': evidence,
                         'notes': f"scope=shape members={got}; the rule was attested once, the pins recomputed "
                                  f"per member at cascade time ({i} of {len(members)})"})
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    print(f'shape: {len(shapes)} shape review(s) would derive {len(made)} function rows')
    if not apply:
        print(f'shape: dry run; pass --apply to write {reviews_path}')
        return 0
    covered = {r['address'] for r in made}
    keep = [r for r in rows if not (r['address'] in covered and r['reviewer'].startswith('derived from shape'))]
    out = keep + made
    out.sort(key=lambda r: (int(r['address'], 16), r['date']))
    with open(reviews_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_HEADER, lineterminator='\n')
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, '') for k in REVIEW_HEADER})
    print(f'shape: wrote {len(made)} derived rows; {reviews_path} now holds {len(out)}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    return cascade(a.root, a.apply)


if __name__ == '__main__':
    raise SystemExit(main())
