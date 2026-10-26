#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Upgrades edge-verified functions to verified once inputs recorded in the game exist and pass.

usage: promote.py [--captures DIR] [--dry-run]

For each row of symbols/functions.csv with status edge-verified: if the capture library
(--captures, default $BB_CAPTURES, then ../captures) holds recorded cases for it (CAPTURES/NAME/*.json),
runs tools/verify.py on those and on its edge cases (CAPTURES/NAME/edge); when every case passes
on both and the function's independent review is approved (symbols/reviews.csv, or its code is
still grandfathered in tools/readable_allowlist.txt), the status becomes verified. The two sets
have to be two input sets: an edge directory holding copies of the recorded cases is refused,
because it would satisfy the gate by path while adding no second provenance, and each set's
provenance (recorded from the game, or written by hand) is printed with the result. Both runs are
recorded in symbols/verification.csv (verify.py --record; failing cases listed in
symbols/quarantine.csv with their reason don't count as failures), and the function's whole
record must then satisfy tools/validate_functions.py's rule for verified: no unexplained
failure in any case set or option, nothing stale. Nothing changes otherwise; a failure is printed and makes the exit code 1. Without a capture library or an executable it does nothing and says so.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Not a case: it describes the calling convention the catalog uses to build cases (verify.run_cases
# and verification.cases_hash skip it for the same reason).
ABI = 'abi.json'


def cases(directory: str) -> int:
    return len(glob.glob(os.path.join(directory, '*.json')))


def case_contents(directory: str) -> list[str]:
    """One sha256 per case file, by content, ignoring the file's name, sorted.

    verification.cases_hash (the ledger's pin) includes the name, because the ledger counts case
    files and a rename is a different set there. This asks a different question -- are these the
    same inputs? -- and a copy of a set whose files were renamed still holds the same inputs, so
    the name is left out here.
    """
    digests = []
    for path in sorted(glob.glob(os.path.join(directory, '*.json'))):
        if os.path.basename(path) == ABI:
            continue
        with open(path, 'rb') as f:
            digests.append(hashlib.sha256(f.read()).hexdigest())
    return sorted(digests)


def duplicate_sets(recorded: list[str], edge: list[str]) -> str | None:
    """Why the two sets are not two independent input sets, or None when they are.

    The gate is two input provenances: what the game recorded, and cases written to cover
    boundaries the recording did not. A gate read off a path is satisfied by copying one directory
    into both places, which is how the recorder replay test first exercised it (one case written to
    <name>/ and <name>/edge/). Two identical sets agree with the original for the same reason one
    does, so a promotion resting on them claims more than it has; comparing contents rather than
    paths is what makes the difference checkable. A renamed copy is still caught, because the
    comparison ignores names -- though a copy whose contents were edited is a different set by this
    reading too, and only a reviewer can tell that it is not a second observation.

    Equality is not the only way one set can add nothing: an edge set every case of which is also
    recorded exercised no input the recorded set had not, and a recorded set contained in the edge
    set leaves the edge set as the only provenance with extra members. Both are refused here; an
    empty set is refused too, because an empty recorded set makes any edge set look different.
    """
    if not recorded or not edge:
        return (f'one of the two case sets is empty (recorded {len(recorded)}, edge {len(edge)} '
                f'case file(s)); an empty set makes any other set look different')
    r, e = set(recorded), set(edge)
    if r == e:
        return (f'the edge case set is a copy of the recorded set ({len(e)} case file(s), same '
                f'contents); one input set counted twice is not two provenances')
    if e <= r:
        return (f'every edge case is already a recorded case ({len(e)} of {len(r)}), so the edge '
                f'set exercises no input the recording did not; one input set counted twice is '
                f'not two provenances')
    if r <= e:
        return (f'every recorded case is also an edge case ({len(r)} of {len(e)}), so the two sets '
                f'are one input set with extra edge members; one input set counted twice is not '
                f'two provenances')
    return None


def provenance(directory: str) -> str:
    """Where a case set's inputs came from, read from the cases themselves.

    A case written by the recorder carries `capture` (function and run); a case written by hand
    carries nothing. tools/differential.py records the same reading per family as
    capture_provenance: "gameplay" when any case has a capture, else "synthetic_or_edge". Reported
    beside the result rather than gated on: every case in this checkout is synthetic, so requiring
    gameplay would refuse every promotion and say nothing about the ones that ran.
    """
    total = caught = 0
    for path in sorted(glob.glob(os.path.join(directory, '*.json'))):
        if os.path.basename(path) == ABI:
            continue
        try:
            with open(path) as f:
                case = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(case, dict):
            continue
        total += 1
        caught += bool(case.get('capture'))
    return f'gameplay {caught}/{total}' if caught else f'synthetic {total}'


def problems_for(root: str, path: str, name: str, line: int) -> list[str]:
    """The verify rule's complaints about one function, read against the whole function list.

    verification.check() cross-references every row of symbols/quarantine.csv against the function
    list it is handed, so passing only the function being promoted reports each other function's
    quarantined cases as "not in symbols/functions.csv" and refuses every promotion while that
    file is not empty. Hand it symbols/functions.csv and keep what belongs to this function: its
    own rows (by line) and anything naming it.
    """
    with open(path, newline='') as f:
        rows = [dict(r, _line=i + 2) for i, r in enumerate(csv.DictReader(f))]
    sys.path.insert(0, os.path.join(root, 'tools'))
    import verification
    return [p for p in verification.check(root, rows) if f'functions.csv:{line}:' in p or name in p]


def passes(name: str, directory: str, record: str | None, root: str = ROOT) -> tuple[bool, str]:
    cmd = [sys.executable, os.path.join(root, 'tools', 'verify.py'), 'run', '--function', name, '--captures', directory]
    if record:
        cmd += ['--record', record]
    # verify.py otherwise writes original/replacement result JSON under CAPTURES/results.
    # Keep comparison artifacts separate from the source cases in both normal and dry runs.
    with tempfile.TemporaryDirectory(prefix='paleblood-promote-') as output:
        p = subprocess.run(cmd + ['--out', output], capture_output=True, text=True)
    try:
        r = json.loads(p.stdout)
    except json.JSONDecodeError:
        return False, (p.stderr.strip().splitlines() or ['no output'])[-1]
    n = cases(directory)
    failed = int(r['recorded']['failed']) if record else r['failed']
    held = int(r['recorded']['quarantined']) if record else 0
    ok = p.returncode == 0 and failed == 0 and r['cases'] == n
    return ok, f"{r['passed']}/{n} passed" + (f', {held} quarantined' if held else '')



# ── TIER TABLE ────────────────────────────────────────────────────────────────────────────────
# promote.py owns ONE act -- read the ledger, move a status -- at two tiers. The tier decides
# which evidence is required; it never decides which FILE is written, which is why this is one
# tool and not a second recorder. (A byte-tier recorder gaining a differential mode would be two
# identities behind one `kind` column: the install_mode.csv/hooks.csv split.)
TIERS = {
    'verified':      ('edge-verified', 'recorded + edge captures must both pass, plus a review'),
    'edge-verified': ('original',      'a verification.csv row with cases=edge, failed=0, source==HEAD'),
}


def promote_edge(root, family, dry_run):
    """original -> edge-verified, derived from a ledger row that already exists.

    THREE REFUSALS, each a defect this campaign has paid for:
      1. no `edge` ledger row           -> no flip on intent;
      2. source != source_hash(name)    -> a flip against a stale row is a row paying for a paragraph;
      3. address in retired.csv         -> a retired body cannot be promoted (closes the table both ways).
    """
    sys.path.insert(0, os.path.join(root, 'tools'))
    import verification as V
    import tier_authority as TA
    # The door has a decision, and the decision answers False today. Wiring it here is a refusal by
    # construction: no grant, no flip, no write. A gate that has never answered False is a gate whose
    # positive arm is the only arm tested.
    if not TA.grants('1ab'):
        print(f'promote: {TA.why("1ab")}', file=sys.stderr)
        return 1
    fpath = os.path.join(root, 'symbols', 'functions.csv')
    text = open(fpath, newline='').read()
    rows = list(csv.reader(io.StringIO(text)))
    head = rows[0]
    st, nm, ad = head.index('status'), head.index('name'), head.index('address')
    led = [r for r in csv.DictReader(open(os.path.join(root, 'symbols', 'verification.csv'), newline=''))
           if r['cases'] == 'edge']
    retired = set()
    rp = os.path.join(root, 'symbols', 'retired.csv')
    if os.path.exists(rp):
        retired = {int(r['address'], 16) for r in csv.DictReader(open(rp)) if r.get('reason', '').strip()}
    # THE SELECTOR SHOWS ITS WORK, AND IT SHOWS IT OVER ALL ROWS, NOT OVER THE SURVIVORS OF A STATUS
    # FILTER. Tonight the tree was saved by the ORDER of two predicates -- a name filter that over-selected
    # sat upstream of a status filter (`original` only) that emptied the result. An ordering is not a
    # safeguard; it is a coincidence that survives until someone moves a line. So the family's population is
    # resolved and PRINTED before anything acts, whatever the statuses are, and a nested family landing
    # with `original` rows is visible at the count instead of discovered after a promotion.
    sel = [row for row in rows[1:]
           if re.fullmatch(re.escape(family) + r'(?:_[0-9a-f]{8})?', row[nm])]
    by_status = {}
    for row in sel:
        by_status[row[st]] = by_status.get(row[st], 0) + 1
    shown = ', '.join(f'{k} {v}' for k, v in sorted(by_status.items())) or 'none'
    print(f'promote: family {family} -> {len(sel)} row(s) ({shown}); '
          f'{by_status.get("original", 0)} promotable')
    moved, refusals, skipped = [], [], []
    for row in sel:
        if row[st] != 'original':
            continue
        name = row[nm]
        if int(row[ad], 16) in retired:
            # A VERDICT IS A SKIP, NOT A REFUSAL. `024264d0` is finished by verdict, so it is not
            # a candidate and must not make this tool exit 1 forever -- an rc that is always 1 is
            # an rc nobody reads. Absent or stale evidence is a refusal; a closed row is not.
            skipped.append(name)
            continue
        mine = [r for r in led if r['function'] == name and r['failed'] == '0'
                and int(r['passed']) == int(r['total']) and r['source']]
        if not mine:
            refusals.append(f'{name}: no edge ledger row with failed=0 -- no flip on intent')
            continue
        cur = V.source_hash(root, name)
        if not cur:
            refusals.append(f'{name}: current source hash unavailable -- cannot tell stale from fresh')
            continue
        if mine[-1]['source'] != cur:
            refusals.append(f'{name}: ledger source {mine[-1]["source"]} != current {cur} -- stale')
            continue
        row[st] = 'edge-verified'
        moved.append(name)
    if skipped:
        print(f'promote: {len(skipped)} already finished by verdict (retired.csv): {", ".join(skipped)}')
    for r in refusals:
        print(f'promote: {r}', file=sys.stderr)
    if moved and not dry_run:
        out = io.StringIO()
        csv.writer(out, lineterminator='\n').writerows(rows)
        with open(fpath, 'w', newline='') as f:
            f.write(out.getvalue())
    print(f'promote: {len(moved)} -> edge-verified{" (dry run)" if dry_run else ""}'
          + (f'; {len(refusals)} refused' if refusals else ''))
    return 1 if refusals else 0


def main(argv: list[str] | None = None, root: str = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--captures', default=os.environ.get('BB_CAPTURES') or os.path.join(root, '..', 'captures'))
    ap.add_argument('--dry-run', action='store_true')
    # The default is the tier that requires nothing but the record. --to verified requires a
    # review, which this tool cannot issue and has never been given: a default that selects it
    # turns a bare `promote --family X` into an attempt at a step whose precondition is absent, and
    # a default must fail toward the semantics it can actually satisfy. (pbl_image_base defaults to
    # 0 and never IMAGE for the same reason.)
    ap.add_argument('--to', choices=sorted(TIERS), default='edge-verified',
                    help='the tier to move to. Default edge-verified: the tier that requires '
                         'nothing but the record. --to verified additionally requires a review.')
    ap.add_argument('--family', help='name prefix; REQUIRED for --to edge-verified')
    a = ap.parse_args(argv)
    if a.to == 'edge-verified':
        if not a.family:
            print('promote: --family <prefix> is required for --to edge-verified: an unfiltered '
                  'sweep would promote every `original` row, including the derived ones',
                  file=sys.stderr)
            return 2
        return promote_edge(root, a.family, a.dry_run)
    if not os.path.isdir(a.captures):
        print(f'promote: no capture library at {a.captures}; nothing to do')
        return 0
    path = os.path.join(root, 'symbols', 'functions.csv')
    with open(path, newline='') as f:
        text = f.read()
    rows = list(csv.reader(io.StringIO(text)))
    head = rows[0]
    status, name_col = head.index('status'), head.index('name')
    changed, failed = [], False
    for line, row in enumerate(rows[1:], start=2):
        if row[status] != 'edge-verified':
            continue
        name = row[name_col]
        recorded = os.path.join(a.captures, name)
        if not cases(recorded):
            continue
        edge = os.path.join(recorded, 'edge')
        if not cases(edge):
            print(f'promote: {name}: recorded cases but no edge cases; left edge-verified')
            continue
        doubled = duplicate_sets(case_contents(recorded), case_contents(edge))
        if doubled:
            print(f'promote: {name}: {doubled}; left edge-verified', file=sys.stderr)
            failed = True
            continue
        sys.path.insert(0, os.path.join(root, 'tools'))
        from validate_functions import check_reviews
        if check_reviews(root, [{'address': row[head.index('address')], 'name': name, 'status': 'verified', '_line': 0}]):
            print(f'promote: {name}: recordings exist, but no approved review yet (symbols/reviews.csv); left edge-verified')
            continue
        where = f'[recorded {provenance(recorded)}, edge {provenance(edge)}]'
        record = None if a.dry_run else 'recorded'
        ok_r, msg_r = passes(name, recorded, record, root)
        ok_e, msg_e = passes(name, edge, record and 'edge', root) if ok_r else (False, 'not run')
        if ok_r and ok_e and not a.dry_run:
            problems = problems_for(root, path, name, line)
            if problems:
                print(f'promote: {name}: recorded {msg_r}, edge {msg_e} {where}, but: ' + '; '.join(problems), file=sys.stderr)
                failed = True
                continue
        if ok_r and ok_e:
            print(f'promote: {name}: recorded {msg_r}, edge {msg_e} {where}: verified')
            row[status] = 'verified'
            changed.append(name)
        else:
            print(f'promote: {name}: recorded {msg_r}, edge {msg_e} {where}: stays edge-verified', file=sys.stderr)
            failed = True
    if changed and not a.dry_run:
        out = io.StringIO()
        csv.writer(out, lineterminator='\n').writerows(rows)
        with open(path, 'w', newline='') as f:
            f.write(out.getvalue())
        print(f'promote: {len(changed)} verified; run tools/progress.py --update-readme')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
