#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate symbols/functions.csv, symbols/ghidra_functions.csv and game/hooks.csv.

usage: validate_functions.py [--root DIR]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

import verification

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDR = re.compile(r'^0x[0-9a-f]{8}$')
IMAGE_BASE = 0x00400000
NAME = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$')
STATUSES = ('original', 'replaced', 'edge-verified', 'verified')
HOOKED = ('replaced', 'edge-verified', 'verified')
FUNC_HEADER = ['address', 'size', 'name', 'system', 'status', 'notes']
EXPORT_HEADER = ['address', 'size']
HOOK_HEADER = ['address', 'replacement', 'system']
MAX_NOTE = 200


def load(path: str, header: list[str], errs: list[str]) -> list[dict]:
    rel = os.path.basename(os.path.dirname(path)) + '/' + os.path.basename(path)
    if not os.path.isfile(path):
        errs.append(f'{rel}: missing')
        return []
    with open(path, newline='') as f:
        rd = csv.reader(f)
        head = next(rd, None)
        if head != header:
            errs.append(f'{rel}: header must be {",".join(header)}')
            return []
        rows = []
        for n, r in enumerate(rd, 2):
            if len(r) != len(header):
                errs.append(f'{rel}:{n}: expected {len(header)} columns, got {len(r)}')
                continue
            d = dict(zip(header, r))
            d['_line'] = n
            rows.append(d)
    return rows


def check_sorted_unique(rows: list[dict], rel: str, errs: list[str]) -> None:
    prev = None
    for r in rows:
        if not ADDR.match(r['address']):
            errs.append(f"{rel}:{r['_line']}: address '{r['address']}' must be 0x + 8 lowercase hex digits")
            continue
        if int(r['address'], 16) < IMAGE_BASE:
            errs.append(f"{rel}:{r['_line']}: address {r['address']} is below the image base "
                        f"0x{IMAGE_BASE:08x}; addresses are PS4 virtual addresses (QUIRKS.md)")
            continue
        if prev is not None and r['address'] <= prev:
            errs.append(f"{rel}:{r['_line']}: addresses must be unique and ascending")
        prev = r['address']


def review_row(root: str, name: str) -> int:
    """Print the row a reviewer can paste into symbols/reviews.csv, with both pins computed here.

    A pin a person types is a pin a person can mistype, and the failure would be a review that
    silently approves nothing. The row leaves the reviewer's own fields as placeholders: they are
    the parts only the reviewer can fill."""
    errs: list[str] = []
    funcs = load(os.path.join(root, 'symbols', 'functions.csv'), FUNC_HEADER, errs)
    row = next((f for f in funcs if f['name'] == name), None)
    if row is None:
        print(f'review-row: {name}: not in symbols/functions.csv', file=sys.stderr)
        return 1
    source = verification.source_hash(root, name)
    evidence = verification.evidence_hash(root, name)
    if not source:
        print(f'review-row: no file under game/ defines bb_{name}, so there is no source to pin',
              file=sys.stderr)
    if not evidence:
        print(f'review-row: no symbols/verification.csv row for {name}, so there is no evidence to pin',
              file=sys.stderr)
    print(f"{'address':<12} {row['address']}")
    print(f"{'name':<12} {name}")
    print(f"{'source_hash':<12} {source or verification.CASES_UNAVAILABLE}")
    print(f"{'cases_sha256':<12} {evidence or verification.CASES_UNAVAILABLE}")
    print(f"{'row':<12} {row['address']},{name},<date>,<reviewer>,approved,"
          f"{source or verification.CASES_UNAVAILABLE},{evidence or verification.CASES_UNAVAILABLE},<notes>")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--review-row', metavar='NAME',
                    help='print the symbols/reviews.csv row for NAME, with both pins computed')
    a = ap.parse_args()
    root = a.root
    if a.review_row:
        return review_row(root, a.review_row)
    errs: list[str] = []

    export = load(os.path.join(root, 'symbols', 'ghidra_functions.csv'), EXPORT_HEADER, errs)
    check_sorted_unique(export, 'symbols/ghidra_functions.csv', errs)
    exp_size: dict[str, int] = {}
    end = -1
    for r in export:
        if not r['size'].isdigit() or int(r['size']) < 1:
            errs.append(f"symbols/ghidra_functions.csv:{r['_line']}: size must be a positive integer")
            continue
        if not ADDR.match(r['address']):
            continue
        a, s = int(r['address'], 16), int(r['size'])
        if a < end:
            errs.append(f"symbols/ghidra_functions.csv:{r['_line']}: overlaps the previous function")
        end = max(end, a + s)
        exp_size[r['address']] = s

    systems_dir = os.path.join(root, 'game')
    systems = sorted(d for d in os.listdir(systems_dir)
                     if os.path.isdir(os.path.join(systems_dir, d))) if os.path.isdir(systems_dir) else []

    funcs = load(os.path.join(root, 'symbols', 'functions.csv'), FUNC_HEADER, errs)
    check_sorted_unique(funcs, 'symbols/functions.csv', errs)
    names: set[str] = set()
    by_addr: dict[str, dict] = {}
    for r in funcs:
        where = f"symbols/functions.csv:{r['_line']}"
        if not r['size'].isdigit() or int(r['size']) < 1:
            errs.append(f'{where}: size must be a positive integer')
        if r['system'] not in systems:
            errs.append(f"{where}: system '{r['system']}' has no game/{r['system']}/ directory")
        if not NAME.match(r['name']):
            errs.append(f"{where}: name '{r['name']}' must be snake_case with a system prefix")
        elif not r['name'].startswith(r['system'] + '_'):
            errs.append(f"{where}: name '{r['name']}' must start with '{r['system']}_'")
        if r['name'] in names:
            errs.append(f"{where}: duplicate name '{r['name']}'")
        names.add(r['name'])
        if r['status'] not in STATUSES:
            errs.append(f"{where}: status '{r['status']}' must be one of {'|'.join(STATUSES)}")
        if len(r['notes']) > MAX_NOTE:
            errs.append(f'{where}: notes longer than {MAX_NOTE} characters (put detail in the issue or docs/systems/)')
        if export:
            if r['address'] not in exp_size:
                errs.append(f"{where}: {r['address']} is not a function in the Ghidra export")
            elif r['size'].isdigit() and int(r['size']) != exp_size[r['address']]:
                errs.append(f"{where}: size {r['size']} differs from the export ({exp_size[r['address']]})")
        by_addr[r['address']] = r

    hooks = load(os.path.join(root, 'game', 'hooks.csv'), HOOK_HEADER, errs)
    check_sorted_unique(hooks, 'game/hooks.csv', errs)
    hooked: set[str] = set()
    for h in hooks:
        where = f"game/hooks.csv:{h['_line']}"
        f = by_addr.get(h['address'])
        if f is None:
            errs.append(f'{where}: no row in symbols/functions.csv for {h["address"]}')
            continue
        hooked.add(h['address'])
        if f['status'] not in HOOKED:
            errs.append(f"{where}: {f['name']} is '{f['status']}', only replaced, edge-verified or verified functions are hooked")
        if h['system'] != f['system']:
            errs.append(f"{where}: system '{h['system']}' differs from functions.csv ('{f['system']}')")
        if f['size'].isdigit() and int(f['size']) < 14:
            errs.append(f"{where}: {f['name']} is {f['size']} bytes; a hook needs at least 14 (QUIRKS.md)")
        if h['replacement'] != 'bb_' + f['name']:
            errs.append(f"{where}: replacement must be 'bb_{f['name']}'")
    for r in funcs:
        if r['status'] in HOOKED and r['address'] not in hooked:
            errs.append(f"symbols/functions.csv:{r['_line']}: {r['name']} is {r['status']} but has no game/hooks.csv entry")

    errs += check_reviews(root, funcs)
    errs += verification.check(root, funcs)

    for e in errs:
        print(f'validate: {e}', file=sys.stderr)
    return 1 if errs else 0


REVIEW_HEADER = ['address', 'name', 'date', 'reviewer', 'verdict', 'source_hash', 'cases_sha256',
                 'notes']
REVIEW_PINS = ('source_hash', 'cases_sha256')


def defining_files(root: str, name: str) -> list[str]:
    """Files under game/ that define the replacement bb_<name>."""
    out = []
    pattern = re.compile(rf'\bbb_{re.escape(name)}\s*\(')
    for dp, _, fns in os.walk(os.path.join(root, 'game')):
        for fn in fns:
            if fn.endswith(('.c', '.cc', '.cpp')):
                path = os.path.join(dp, fn)
                with open(path, errors='replace') as f:
                    if pattern.search(f.read()):
                        out.append(os.path.relpath(path, root).replace(os.sep, '/'))
    return out


def review_pin_errors(root: str, r: dict, rv: dict) -> list[str]:
    """A review approves a claim about a particular replacement and a particular evidence set, so
    the row names both. Without the pins an approval survives edits to either one silently, which
    is how a `verified` function comes to mean "someone checked something once".

    `unavailable` is accepted the way the ledger accepts it: a person who looked and could not pin
    the subject says so in a word, and the absence is then visible instead of implied. An empty
    field is not that -- it is an approval that never said what it approved."""
    errs = []
    where = f"symbols/reviews.csv:{rv['_line']}"
    for column, current, subject in (
            ('source_hash', verification.source_hash(root, r['name']), 'replacement source'),
            ('cases_sha256', verification.evidence_hash(root, r['name']), 'evidence set')):
        if not current:
            continue            # nothing here to compare against: no defining file, or no rows
        got = rv[column].strip()
        if got == verification.CASES_UNAVAILABLE:
            continue
        if not got:
            errs.append(f"{where}: {r['name']} is approved without a {column}, so the approval does "
                        f"not say which {subject} it approved")
        elif got != current:
            errs.append(f"{where}: the {subject} changed since this approval ({column} {got}, now "
                        f"{current}); {r['name']} needs a new review, not the old approval")
    return errs


def check_reviews(root: str, funcs: list[dict]) -> list[str]:
    """A verified function needs an approved independent review (symbols/reviews.csv), unless its
    code is still grandfathered (tools/readable_allowlist.txt, STYLE.md)."""
    errs = []
    allow_path = os.path.join(root, 'tools', 'readable_allowlist.txt')
    allow = set()
    if os.path.isfile(allow_path):
        with open(allow_path) as f:
            allow = {ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')}
    path = os.path.join(root, 'symbols', 'reviews.csv')
    reviews: dict[str, dict] = {}
    if os.path.isfile(path):
        with open(path, newline='') as f:
            rd = csv.reader(f)
            head = next(rd, None)
            if head != REVIEW_HEADER:
                return [f"symbols/reviews.csv: header must be {','.join(REVIEW_HEADER)}"]
            for n, row in enumerate(rd, 2):
                if len(row) != len(REVIEW_HEADER):
                    errs.append(f'symbols/reviews.csv:{n}: expected {len(REVIEW_HEADER)} fields')
                    continue
                r = dict(zip(REVIEW_HEADER, row), _line=n)
                if r['verdict'] not in ('approved', 'changes requested'):
                    errs.append(f"symbols/reviews.csv:{n}: verdict must be 'approved' or 'changes requested'")
                if not r['reviewer'].strip():
                    errs.append(f'symbols/reviews.csv:{n}: reviewer is empty')
                reviews[r['address']] = r       # the latest row for an address counts
    for r in funcs:
        if r['status'] != 'verified':
            continue
        files = defining_files(root, r['name'])
        if files and all(f in allow for f in files):
            continue
        rv = reviews.get(r['address'])
        if not rv or rv['verdict'] != 'approved':
            errs.append(f"symbols/functions.csv:{r['_line']}: {r['name']} is verified without an approved review "
                        f"in symbols/reviews.csv (CONTRIBUTING.md, \"Definition of done\")")
            continue
        errs += review_pin_errors(root, r, rv)
    return errs


if __name__ == '__main__':
    sys.exit(main())
