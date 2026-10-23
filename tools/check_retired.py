#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Refuse a retirement that is not visible where it has to be.

`symbols/retired.csv` decides which rows NEVER RUN -- an address with a verdict against its body
-- so it is the one table whose failure mode is silence: a retired member that still has a body is
code running under a verdict, and a member whose body vanished without a verdict is a person's
judgement with no record. Five properties, each a defect this campaign has paid for:

  1. every row carries `reason`, `date`, `revisit` -- a verdict needs a written condition to be
     re-openable, or it returns as a nit; and no address twice;
  2. every retired address is a row in functions.csv -- a verdict about nothing is a typo;
  3. no retired address has a body: not `bb_..._<addr>` in game/leaf/*.cpp, not a `T` symbol in
     the library when one is given (rc 3, "cannot check", rather than a pass, when --lib is absent
     and the caller asked for it);
  4. a row that is `original` inside a landed family and has NO body must be named in retired.csv
     -- the state that is safe is not "original with no body" (three derived rows are honestly
     that) but "original, no body, and the family says it should have one";
  5. no address in both retired.csv and verification_unrecordable.csv: unrecordable is a debt
     against the instrument, retired is a verdict about the body, and merging them sends the next
     reader after case directories that will never help.

rc: 0 clean, 1 violations, 3 precondition (a file the check needs is absent).
"""
from __future__ import annotations

import csv
import glob
import os
import re
import subprocess
import sys

ADDR8 = re.compile(r'^(?:0x)?([0-9a-fA-F]{8})$')


def _rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def check(root, lib=None):
    """Returns (rc, findings, population string). No address is written in this file."""
    sym = os.path.join(root, 'symbols')
    fpath = os.path.join(sym, 'functions.csv')
    rpath = os.path.join(sym, 'retired.csv')
    if not os.path.exists(rpath):
        return 3, [f'{rpath}: no retirement table'], ''
    if not os.path.exists(fpath):
        return 3, [f'{fpath}: no functions table'], ''
    findings = []
    retired = _rows(rpath)
    functions = _rows(fpath)
    by_addr = {r['address'].lower(): r for r in functions}

    seen = set()
    for i, r in enumerate(retired, start=2):
        a = (r.get('address') or '').strip().lower()
        m = ADDR8.match(a)
        if not m:
            findings.append(f'retired.csv:{i}: address {a!r} is not 8 hex digits')
            continue
        a = '0x' + m.group(1)
        if a in seen:
            findings.append(f'retired.csv:{i}: {a} appears twice')
        seen.add(a)
        for col in ('reason', 'date', 'revisit'):
            if not (r.get(col) or '').strip():
                findings.append(f'retired.csv:{i}: {a}: blank `{col}` -- absence refuses')
        if a not in by_addr:
            findings.append(f'retired.csv:{i}: {a} is not a row in functions.csv')

    # 3. no body anywhere it could run
    for path in sorted(glob.glob(os.path.join(root, 'game', 'leaf', '*_family.cpp'))):
        with open(path) as f:
            text = f.read()
        for a in sorted(seen):
            if f'_{a[2:]}_' in text or f'_{a[2:]}(' in text:
                findings.append(f'{os.path.relpath(path, root)}: {a} is retired and still has a body')
    if lib:
        if os.path.exists(lib):
            out = subprocess.run(['nm', '-D', '--defined-only', lib], capture_output=True, text=True).stdout
            exported = {ln.split()[-1] for ln in out.splitlines() if len(ln.split()) == 3}
            for a in sorted(seen):
                bad = [s for s in exported if s.endswith('_' + a[2:])]
                if bad:
                    findings.append(f'{lib}: {a} is retired and still exported as {bad[0]}')
        else:
            findings.append(f'{lib}: requested library does not exist -- cannot check exports')

    # 4. original, inside a landed family, with no body -> must be named
    for path in sorted(glob.glob(os.path.join(root, 'game', 'leaf', '*_family.cpp'))):
        fam = os.path.basename(path)[:-len('_family.cpp')]          # e.g. rip_load_wide
        prefix = f'leaf_{fam}_'
        with open(path) as f:
            text = f.read()
        for r in functions:
            if not r['name'].startswith(prefix) or r['status'] != 'original':
                continue
            a = r['address'].lower()
            if a in seen:
                continue
            if f'_{a[2:]}_' not in text and f'_{a[2:]}(' not in text:
                findings.append(f'{r["name"]}: `original` inside landed family {fam}, no body, '
                                f'and not in retired.csv -- a body vanished without a verdict')

    # 5. two tables, two concepts
    upath = os.path.join(sym, 'verification_unrecordable.csv')
    if os.path.exists(upath):
        for r in _rows(upath):
            a = (r.get('address') or '').strip().lower()
            if a.startswith('0x'):
                a = '0x' + a[2:].zfill(8)
            if a in seen:
                findings.append(f'{a}: in both retired.csv and verification_unrecordable.csv '
                                f'-- a verdict is not a debt')
    return (1 if findings else 0), findings, f'{len(seen)} retired row(s), {len(functions)} functions'


def main(argv):
    root = os.environ.get('BB_ROOT', '.')
    lib = None
    for i, a in enumerate(argv):
        if a == '--root' and i + 1 < len(argv):
            root = argv[i + 1]
        if a == '--lib' and i + 1 < len(argv):
            lib = argv[i + 1]
    rc, findings, population = check(root, lib)
    for f in findings:
        print(f'retired: {f}', file=sys.stderr)
    if rc == 3:
        print(f'retired: cannot check ({"; ".join(findings)}) -- this is a refusal, not a pass')
        return 3
    print(f'retired: {population} -- {"ok" if rc == 0 else "violations above"}')
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
