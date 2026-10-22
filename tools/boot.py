#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Runs the boot harness (runtime/boot.c) on your executable and records the result.

usage: boot.py [--elf EBOOT.elf] [--nids NID_DB.xml] [--timeout S] [--trace] [--no-record]

The game's own system modules listed in game/modules.csv with action "map" are mapped next to the
executable (from the same directory: NAME.elf), and the executable's imports they export are
bound to them.

Writes, from the run:
  symbols/boot.json           where the boot stops, the furthest boot milestone and the import
                              counts (read by tools/progress.py)
  symbols/boot_history.csv    a dated row whenever boot progress or its failure location changes;
                              includes the outcome, phase, return site, and guest fault details
  symbols/imports.csv         every import of the executable and the mapped modules: importer,
                              library, symbol, kind, provider (a module, "runtime",
                              "runtime-unresolved", or empty);
                              tools/runtime_issues.py groups it
  symbols/module_functions.csv the mapped modules' functions the executable or another module
                              uses: tracked like game functions (status original), replaceable later
Prints "milestone reached: NAME" when the run gets further than the last recorded one.

--elf defaults to $BB_ELF, then $BB_DATA_ROOT/elf/eboot.elf. --nids (a public NID database, for
names) defaults to $BB_NID_DB, then GhidraOrbis's nid_db.xml under ../tools. The harness binary
is $BB_PBBOOT or build/runtime/pbboot.
"""
from __future__ import annotations

import collections
import io
import re

import argparse
import csv
import datetime
import glob
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FIELDS = ('date', 'milestone', 'milestone_index', 'imports_total', 'imports_bundled', 'imports_implemented',
                  'imports_remaining', 'stops_at', 'outcome', 'phase', 'returns_to', 'fault_at', 'fault_signal',
                  'fault_address')
KEPT = ('phase', 'outcome', 'milestone', 'milestone_index', 'milestones', 'imports_total', 'imports_implemented',
        'imports_bundled', 'imports_unresolved', 'imports_remaining', 'imports_called', 'modules',
        'first_unimplemented', 'fault')
IMPORT_FIELDS = ('importer', 'library', 'symbol', 'kind', 'provider')
MODULE_FIELDS = ('module', 'offset', 'size', 'symbol', 'status')


def default_elf() -> str:
    root = os.environ.get('BB_DATA_ROOT') or os.path.join(ROOT, '..', 'data')
    return os.environ.get('BB_ELF') or os.path.join(root, 'elf', 'eboot.elf')


def default_nids() -> str | None:
    if os.environ.get('BB_NID_DB'):
        return os.environ['BB_NID_DB']
    hits = sorted(glob.glob(os.path.join(ROOT, '..', 'tools', 'ghidra_*', 'Ghidra', 'Extensions', 'GhidraOrbis',
                                         'data', 'nid_db.xml')))
    return hits[-1] if hits else None


def mapped_modules(root: str) -> list[str]:
    path = os.path.join(root, 'game', 'modules.csv')
    if not os.path.isfile(path):
        return []
    with open(path, newline='') as f:
        return [r['module'] for r in csv.DictReader(f) if r['action'] == 'map']


def stops_at(b: dict) -> str:
    s = b.get('first_unimplemented')
    if s:
        return f"{s['caller']}->{s['library']}:{s['symbol'] or s['nid']}"
    if b.get('fault'):
        return f"{b['outcome']} at {b['fault']['at']}"
    return b['outcome']


def record(status: dict, root: str, today: str) -> str | None:
    """Writes boot.json and the history row; returns the milestone name if it advanced."""
    kept = {k: status[k] for k in KEPT if k in status}
    with open(os.path.join(root, 'symbols', 'boot.json'), 'w') as f:
        json.dump(kept, f, indent=2, sort_keys=True)
        f.write('\n')
    path = os.path.join(root, 'symbols', 'boot_history.csv')
    rows = []
    if os.path.isfile(path):
        with open(path, newline='') as f:
            rows = list(csv.DictReader(f))
    first = kept.get('first_unimplemented') or {}
    fault = kept.get('fault') or {}
    row = {
        'date': today,
        'stops_at': stops_at(kept),
        'outcome': kept.get('outcome', ''),
        'phase': kept.get('phase', ''),
        'returns_to': first.get('returns_to', ''),
        'fault_at': fault.get('at', ''),
        'fault_signal': fault.get('signal', ''),
        'fault_address': fault.get('address', ''),
    }
    for k in ('milestone', 'milestone_index', 'imports_total', 'imports_bundled', 'imports_implemented',
              'imports_remaining'):
        row[k] = str(kept.get(k, 0))
    last = rows[-1] if rows else None
    if not last or any(last.get(k, '') != row[k] for k in HISTORY_FIELDS[1:]):
        rows.append(row)
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=HISTORY_FIELDS, lineterminator='\n', restval='')
            w.writeheader()
            w.writerows({k: r.get(k, '') for k in HISTORY_FIELDS} for r in rows)
    if last and int(row['milestone_index']) > int(last['milestone_index']):
        return row['milestone']
    return None


NID_SHAPE = re.compile(r'^[A-Za-z0-9_+\-]{11}(#|$)')


def _refuse_raw_nids(what: str, symbols, allow_nids: bool) -> str:
    """A raw NID in a names column is a name that was not resolved. Writing one destroys the
    resolved name that was there, which this tree has done by accident twice."""
    if allow_nids:
        return None
    bad = [s for s in symbols if s and NID_SHAPE.match(s)]
    if bad:
        return (f'refusing to write {what}: {len(bad)} raw NID symbol(s) and --nids was not given '
                f'(first: {bad[0]}). Re-run with --nids, or without the listing, but not this.')
    return None


def _staged_write(path: str, header, rows) -> None:
    """Write beside the target and rename: a run that dies mid-write leaves the old table."""
    tmp = path + '.tmp'
    with open(tmp, 'w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, path)



def preserve(existing: str, rows: list, allow_nids: bool):
    """Keep resolved import names that this listing would replace by raw NIDs.

    The invariant is on the output, not the input. A run whose NID database resolves 795 of 845
    names would otherwise rewrite the other 50 as `-qLsfDAywIY#N#O`, and a guard that only checks
    that *some* database was supplied passes that through -- which is the same bug through a
    smaller door than having no database at all. So compare against what is already written: where
    a name would become a NID, keep the name. The file stores one symbol per row and no NID, so
    for a group of rows the same size the multiset of names is the whole of what can be preserved;
    where the group sizes differ the rows cannot be aligned, and that is a refusal rather than a
    guess. A genuinely new import is recorded as the NID it is, which is a fact about this run and
    not a loss. Returns (rows, error)."""
    if not existing:
        return rows, None
    groups = collections.defaultdict(list)
    for row in csv.DictReader(io.StringIO(existing)):
        groups[(row['importer'], row['library'], row['kind'], row['provider'])].append(row['symbol'])
    out, lost, dropped = [], [], []
    by_key = collections.defaultdict(list)
    for row in rows:
        by_key[(row[0], row[1], row[3], row[4])].append(row)
    for key, group in by_key.items():
        old = groups.get(key, [])
        names = sorted(n for n in old if not NID_SHAPE.match(n))
        degraded = [r for r in group if NID_SHAPE.match(r[2])]
        if not names or not degraded:
            out.extend(group)
            continue
        if len(group) != len(old):
            # the group changed size: modules get mapped and unmapped between runs, so rows come
            # and go. Keep every name there is room for; the surplus rows keep this run's NID.
            lost.append(f'{key[2]}: {len(names)} name(s) preserved across {len(group)} row(s)')
        # the file holds no NID, so names and NID-shaped rows cannot be paired one to one when a
        # group holds a name that already is a NID: hand out the preserved names in order, and let
        # the remaining rows keep the NID this run actually saw.
        keep, used = names, 0
        for row in group:
            symbol = row[2]
            if NID_SHAPE.match(symbol):
                if used == len(keep):
                    # a group already written with resolved names may not gain a NID in their
                    # place: there is no name left to keep, so the row is not written at all.
                    # Dropping an unresolved row costs one import next run; rewriting a name to a
                    # NID costs the name, and the name is the only thing the file is for.
                    dropped.append(f'{row[1]}:{symbol}')
                    continue
                symbol, used = keep[used], used + 1
            out.append(row[:2] + (symbol,) + row[3:])
    if lost:
        print('boot: ' + '; '.join(lost[:3]), file=sys.stderr)
    if dropped:
        print(f'boot: {len(dropped)} unresolved import(s) not written, because their library already'
              f' has resolved names this run could not match to them (first: {dropped[0]})',
              file=sys.stderr)
    return out, None


def write_listing(listing: str, root: str, allow_nids: bool = False) -> int:
    """imports.csv and module_functions.csv from `pbboot --imports` (tab-separated: importer,
    library, symbol, kind, provider, provider offset, size). Returns 0 when written, 3 when the
    write would destroy resolved names."""
    imports, functions = set(), {}
    for line in listing.splitlines():
        if not line:
            continue
        importer, library, symbol, kind, provider, offset, size = line.split('\t')
        imports.add((importer, library, symbol, kind, provider))
        if provider and provider not in ('runtime', 'runtime-unresolved'):
            functions[(provider, offset)] = (provider, offset, size, symbol, 'original')
    path = os.path.join(root, 'symbols', 'imports.csv')
    existing = open(path).read() if os.path.isfile(path) else ''
    imports, error = preserve(existing, sorted(imports), allow_nids)
    if error:
        print(f'boot: {error}', file=sys.stderr)
        return 3
    path = os.path.join(root, 'symbols', 'module_functions.csv')
    # a status other than original (a replacement, later) is kept
    old = {}
    if os.path.isfile(path):
        with open(path, newline='') as f:
            old = {(r['module'], r['offset']): r['status'] for r in csv.DictReader(f)}
    import_rows = sorted(imports)
    function_rows = []
    for key in sorted(functions):
        m, off, size, sym, status = functions[key]
        function_rows.append((m, off, size, sym, old.get(key, status)))
    # Validated together; replaced in sequence. A refusal therefore leaves both untouched, but a
    # kill between the two os.replace calls leaves a valid pair from two runs -- each table still
    # raw-NID-free, not each table from the same listing.
    for what, rows, idx in (('imports.csv', import_rows, 2),
                            ('module_functions.csv', function_rows, 3)):
        error = _refuse_raw_nids(what, [r[idx] for r in rows], allow_nids)
        if error:
            print(f'boot: {error}', file=sys.stderr)
            return 3
    _staged_write(os.path.join(root, 'symbols', 'imports.csv'), IMPORT_FIELDS, import_rows)
    _staged_write(os.path.join(root, 'symbols', 'module_functions.csv'), MODULE_FIELDS, function_rows)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--elf', default=None)
    ap.add_argument('--nids', default=None)
    ap.add_argument('--allow-nids', action='store_true',
                    help='record even if that turns resolved import names into raw NIDs')
    ap.add_argument('--timeout', type=int, default=30)
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--no-record', action='store_true', help='run and print only')
    a = ap.parse_args()
    nids = a.nids or default_nids()
    elf = a.elf or default_elf()
    pbboot = os.environ.get('BB_PBBOOT') or os.path.join(ROOT, 'build', 'runtime', 'pbboot')
    for path, what in ((elf, 'executable (your own dump\'s eboot.elf)'), (pbboot, 'boot harness: build the repository')):
        if not os.path.isfile(path):
            print(f'boot: {path}: no {what}', file=sys.stderr)
            return 3
    objects = [elf]
    for name in mapped_modules(ROOT):
        path = os.path.join(os.path.dirname(elf), f'{name}.elf')
        if not os.path.isfile(path):
            print(f'boot: {path}: no module (tools/prepare_dump.sh writes the game\'s modules next to eboot.elf)',
                  file=sys.stderr)
            return 3
        objects += ['--module', path]
    names = ['--nids', nids] if nids else []
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'status.json')
        cmd = [pbboot, *objects, '--status', out, '--timeout', str(a.timeout), *names]
        if a.trace:
            cmd.append('--trace')
        # The guest runs in this process's child; a hard limit covers a runaway harness.
        p = subprocess.run(cmd, timeout=a.timeout + 60)
        if p.returncode != 0 or not os.path.isfile(out):
            print(f'boot: harness failed (exit {p.returncode})', file=sys.stderr)
            return 3
        with open(out) as f:
            status = json.load(f)
    if a.no_record:
        return 0
    listing = subprocess.run([pbboot, *objects, '--imports', *names], capture_output=True, text=True, timeout=120)
    if listing.returncode:
        print(f'boot: listing imports failed: {listing.stderr.strip()}', file=sys.stderr)
        return 3
    if write_listing(listing.stdout, ROOT, a.allow_nids):
        return 3
    reached = record(status, ROOT, datetime.date.today().isoformat())
    if reached:
        print(f'milestone reached: {reached}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
