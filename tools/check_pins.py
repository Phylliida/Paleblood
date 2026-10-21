#!/usr/bin/env python3
"""Audit the pins this tree has already written down, against the tree it is now.

A ledger row in symbols/verification.csv records `source`, the hash of the replacement source it
was recorded against. Nothing ever recomputed it, so a row can go on claiming evidence about code
that no longer exists. Measured on 2026-10-21: 3,012 of 21,129 rows carried a pin from a version of
their replacement source that had since changed, in five whole-family groups -- 2,978 leaf_mov_eax_k
rows after the readable pass renamed their constants, 25 leaf_mov_rax rows, 6 static_guard rows and
the 3 frame_timing ones that had been found by hand, once, by accident. Three of those cannot be
re-recorded at all: their captures are not on this machine, and they are declared in
symbols/verification_unrecordable.csv so that this tool does not send the next reader hunting. A review row carries two pins
for the same reason (source_hash, cases_sha256) and validate_functions.review_pin_errors() checks
them only for `verified` rows, only during validation.

What makes this affordable is two content caches in verification.py, not the index alone: the
index removed the 105-file walk (45 ms -> a dict hit), but the per-call cost was then dominated by
re-reading and re-scanning the same headers, and by hashing the leaf family's one-megabyte
translation unit once per member. Files are now read and scanned once per (mtime_ns, size), and a
source hash is memoised on the defining file set and those versions, so the 3,619 members of one
family share one computation. Measured: 2 m 18 s -> 2.2 s for 21,128 rows.

Exit 0 when every pin still describes the tree. --root checks a staged tree (the pre-commit hook
extracts one with `git checkout-index`).
"""
import argparse
import csv
import os
import sys

try:                                  # a hanging gate should print its own frame, not hang
    import stacks
    stacks.arm()
except ImportError:                   # run from a tree without tools/ on sys.path
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verification
import validate_functions as vf


def rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument('--limit', type=int, default=20, help='how many stale rows to name')
    o = ap.parse_args(argv)
    root = os.path.abspath(o.root)

    ledger = rows(os.path.join(root, 'symbols', 'verification.csv'))
    current = {}
    stale, orphan = [], []
    for r in ledger:
        name = r['function']
        if name not in current:
            current[name] = verification.source_hash(root, name)
        now = current[name]
        if not now:
            orphan.append((name, r['cases'], r['source']))
        elif r['source'] and r['source'] != now:
            stale.append((name, r['source'], now))

    # What the ledger can and cannot say about its own evidence. Every row carries a
    # cases_sha256 but no path, and two layouts coexist on disk: generated families under
    # ../data/cases/<tag>/0x<addr>/, hand-written functions under ../data/cases/<tag>/ with
    # case-named files and no address directory. So an address-keyed lookup finds the generated
    # families and says nothing about the hand-written ones -- reported as a count, never as a
    # failure, because "not found by address" is a fact about conventions, not about evidence.
    have = set()
    cases_root = os.path.join(os.path.dirname(root), 'data', 'cases')
    for prefix in os.listdir(cases_root) if os.path.isdir(cases_root) else []:
        d = os.path.join(cases_root, prefix)
        if os.path.isdir(d):
            for entry in os.listdir(d):
                have.add(entry)
    funcs = {r['address']: r for r in rows(os.path.join(root, 'symbols', 'functions.csv'))}
    by_name = {r['name']: r for r in funcs.values()}
    missing_cases = sorted(name for name in current
                           if by_name.get(name)
                           and f"0x{by_name[name]['address'][2:].lower().zfill(8)}" not in have)

    # A declared absence is legal; an undeclared one refuses. Three rows were recorded from
    # captures that are not on this machine, so their pins can never be re-derived here, and a
    # tool that reported them as ordinary staleness would send the next reader hunting for a
    # directory that does not exist. They are declared in symbols/verification_unrecordable.csv
    # with a reason; any other row that cannot be re-recorded is a failure.
    declared_path = os.path.join(root, 'symbols', 'verification_unrecordable.csv')
    declared = {r['function'] for r in rows(declared_path)} if os.path.exists(declared_path) else set()
    # stale is a list of (name, recorded, now) triples: reading it as names compares a tuple
    # against a string, matches nothing, and leaves the declaration silently unused.
    unrecordable = [n for n, _, _ in stale if n in declared]
    stale = [s for s in stale if s[0] not in declared]

    reviews = rows(os.path.join(root, 'symbols', 'reviews.csv'))
    review_errs = []
    for line, rv in enumerate(reviews, start=2):
        rv['_line'] = str(line)
        review_errs += vf.review_pin_errors(root, {'name': rv['name'], '_line': line}, rv)

    print(f'ledger rows {len(ledger)} · functions {len(current)} · '
          f'stale pins {len(stale)} · pins with no source now {len(orphan)} · '
          f'review pin errors {len(review_errs)} · unrecordable (declared) {len(unrecordable)}'
          f' · not address-keyed {len(missing_cases)}')
    for name, was, now in stale[:o.limit]:
        print(f'  stale {name}: recorded {was}, now {now}')
    for name, cases, was in orphan[:o.limit]:
        print(f'  no source now {name} ({cases}): recorded {was}')
    for e in review_errs[:o.limit]:
        print('  review ' + e)
    for name in unrecordable[:o.limit]:
        print(f'  unrecordable {name} (declared in symbols/verification_unrecordable.csv)')
    return 1 if (stale or orphan or review_errs) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
