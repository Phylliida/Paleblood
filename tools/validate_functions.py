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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:                                  # a hanging gate should print its own frame, not hang
    import stacks
    stacks.arm()
except ImportError:                   # run from a tree without tools/ on sys.path
    pass

import verification

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDR = re.compile(r'^0x[0-9a-f]{8}$')
IMAGE_BASE = 0x00400000
NAME = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$')
STATUSES = ('original', 'replaced', 'edge-verified', 'verified')
HOOKED = ('replaced', 'edge-verified', 'verified')
FUNC_HEADER = ['address', 'size', 'name', 'system', 'status', 'notes']
ORIGIN_HEADER = ['address', 'origin']
ORIGINS = ('hand', 'generated')
EXPORT_HEADER = ['address', 'size']
HOOK_HEADER = ['address', 'replacement', 'system']
MAX_NOTE = 200



_install_mode_cache: dict = {}      # (path, mtime_ns, size) -> frozenset of host addresses


def _install_mode_hosts():
    """Addresses declared installed as host calls rather than by a game hook.

    A pool B body is shorter than the 14-byte absolute jump a hook needs, so the differential
    verifies it by calling the replacement as a host symbol. Declaring that is the only way past
    the hooks-entry requirement; an absent declaration still refuses.

    This is a reason, not a policy. `jmp qword ptr [rip+0]` plus its target is 14 bytes; the
    smallest hookable row in game/hooks.csv is 16 (then 18, 19, 20, 21, 22; largest 3,222), so every
    declared hook fits — while pool B's shapes do not even fit a 5-byte `jmp rel32` (`xor eax,eax;
    ret` is 3 bytes, `mov rax,[rdi+K]; ret` is 6 to 8). Patching one would overwrite the next
    function's first instruction and the run would stay green, which is why no size floor lift is
    ever coming: the instruction is too short to hold a jump, not merely short of our preference.
    """
    import csv as _csv
    import pathlib as _pathlib
    path = _pathlib.Path(__file__).resolve().parents[1] / "symbols" / "install_mode.csv"
    if not path.exists():
        return frozenset()
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _install_mode_cache.get(key)
    if hit is not None:
        return hit
    with open(path, newline="") as handle:
        hosts = frozenset(row["address"].lower() for row in _csv.DictReader(handle)
                          if row.get("mode") == "host")
    _install_mode_cache.clear()             # one entry: the table as it stands on disk
    _install_mode_cache[key] = hosts
    return hosts

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
    print(f"{'row':<12} {row['address']},{name},<date>,<reviewer>,approved,function,"
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

    origin_path = os.path.join(root, 'symbols', 'replacement_origins.csv')
    if os.path.exists(origin_path):
        origins = load(origin_path, ORIGIN_HEADER, errs)
        check_sorted_unique(origins, 'symbols/replacement_origins.csv', errs)
    else:
        # The requirement is that replacements have provenance, not that a file exists: a tree
        # with no replacements has nothing to attribute, and the coverage rule below still fires
        # the moment one appears.
        origins = []
        if any(r['status'] != 'original' for r in funcs):
            errs.append('symbols/replacement_origins.csv: missing, but the tree has replacements')
    declared = {o['address']: o['origin'] for o in origins}
    for o in origins:
        where = f"symbols/replacement_origins.csv:{o['_line']}"
        if o['origin'] not in ORIGINS:
            errs.append(f"{where}: origin '{o['origin']}' must be one of {'|'.join(ORIGINS)}")
        f = by_addr.get(o['address'])
        if f is None:
            errs.append(f'{where}: no row in symbols/functions.csv for {o["address"]}')
        elif f['status'] == 'original' and o['origin'] != 'generated':
            # A generated body exists before its evidence does: tools/static_guard_gen.py emits
            # rows at status 'original' and the authoring session flips them after recording.
            # 'hand' on an original row would be a provenance claim about no replacement at all.
            errs.append(f"{where}: {f['name']} is 'original', which has no replacement to attribute; "
                        f"only 'generated' may precede the status flip")
    # Every replacement carries its provenance or the burndown's hand/generated split is a guess:
    # the tree's first generated rows landed with this rule, and a marker added later never gets
    # added to the rows that preceded it.
    for r in funcs:
        if r['status'] != 'original' and r['address'] not in declared:
            errs.append(f"symbols/functions.csv:{r['_line']}: {r['name']} is {r['status']} but has no "
                        f'replacement_origins.csv row (hand or generated)')
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
    hosts = _install_mode_hosts()      # read once, not once per functions.csv row
    for r in funcs:
        if r['status'] in HOOKED and r['address'] not in hooked:
            if r['address'].lower() not in hosts:
                errs.append(f"symbols/functions.csv:{r['_line']}: {r['name']} is {r['status']} but has no game/hooks.csv entry")

    errs += check_reviews(root, funcs)
    errs += verification.check(root, funcs)

    for e in errs:
        print(f'validate: {e}', file=sys.stderr)
    return 1 if errs else 0


REVIEW_SCOPES = ('function', 'shape')
REVIEW_HEADER = ['address', 'name', 'date', 'reviewer', 'verdict', 'scope', 'source_hash',
                 'cases_sha256',
                 'notes']
REVIEW_PINS = ('source_hash', 'cases_sha256')


def defining_files(root: str, name: str) -> list[str]:
    """Files under game/ that define the replacement bb_<name>.

    This was a second copy of verification.defining_files, drifted (unsorted) and paying the
    per-call walk twice. One resolver, two callers: the agreement is code now, not a comment.
    """
    return verification.defining_files(root, name)


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
        got = rv[column].strip()
        if got == verification.CASES_UNAVAILABLE:
            continue            # a person looked and could not pin it; the absence is declared
        if not current:
            # This used to `continue`, which meant a review whose replacement source had been
            # deleted compared against nothing and passed -- the fail-open that record()'s
            # empty-HEAD stamp turned out to be, one file over. Absence refuses.
            errs.append(f"{where}: {r['name']} is approved against a {subject} this tree does not "
                        f"have, so the approval cannot be checked (no defining file, or no ledger "
                        f"rows); record the evidence, or write {verification.CASES_UNAVAILABLE}")
            continue
        if not got:
            errs.append(f"{where}: {r['name']} is approved without a {column}, so the approval does "
                        f"not say which {subject} it approved")
        elif got != current:
            errs.append(f"{where}: the {subject} changed since this approval ({column} {got}, now "
                        f"{current}); {r['name']} needs a new review, not the old approval")
    return errs



def shape_answer(root: str) -> bool:
    """True only if the user's own answer file says `scope=shape`.

    The review row is a reviewer's statement; the scope is the owner's decision. Reading the decision
    from the file the user writes means a shape approval cannot be manufactured by editing reviews.csv,
    and the flag and the answer are the same object rather than two things kept in step by hand."""
    path = os.path.join(root, 'docs', 'approval-answers.md')
    if not os.path.isfile(path):
        return False
    with open(path) as f:
        for line in f:
            if line.lstrip().startswith('#'):
                continue
            if re.search(r'\bscope\s*=\s*shape\b', line, re.I):
                return True
    return False


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
                if not r['scope'].strip():
                    r['scope'] = 'function'      # absent is the narrower default, never the wider one
                if r['scope'] not in REVIEW_SCOPES:
                    errs.append(f"symbols/reviews.csv:{n}: scope must be one of {', '.join(REVIEW_SCOPES)}, "
                                f"got {r['scope']!r}")
                elif r['scope'] == 'shape' and not shape_answer(root):
                    errs.append(f"symbols/reviews.csv:{n}: a shape review is only meaningful once the user has "
                                f"answered docs/approval-request.md; append '<date> scope=shape' to "
                                f"docs/approval-answers.md, or write the review per function")
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

