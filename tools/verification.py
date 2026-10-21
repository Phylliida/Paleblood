#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The verification record: which case sets a function's replacement passed, and the quarantine.

symbols/verification.csv   one row per function, case set and option: the latest
                           `tools/verify.py run --record` of it. Counts only, never case data.
  function     the functions.csv name
  cases        recorded (recorded in a game run), edge (the generated edge cases), or
               option-recorded (recorded in a game run with the option on)
  option       the option the run checked ('' for none: unpatched, no option environment)
  total, passed, failed, quarantined
               failed counts failing cases that are not quarantined; quarantined counts failing
               cases that are (a quarantined case that passes counts as passed)
  source       a hash of the replacement's source (its defining files and every header they
               include from game/ and runtime/include/, recursively): results for other code
               are stale
  cases_sha256 a hash of the case files the run used (every *.json in the capture directory
               except abi.json, by name and content): results for other inputs are stale too.
               A row is the claim "this code agrees with the original on these inputs"; the
               source hash pins the first half, this pins the second. It cannot be rechecked
               by tools/validate_functions.py, because the row does not record where the
               capture directory was; verification.cases_hash(DIR) recomputes it for a
               directory you supply.
               A row whose capture directory is not in this checkout carries 'unavailable'
               instead. That is a statement someone made after looking for the cases -- rows
               recorded elsewhere (captures kept outside the archive) are the usual reason --
               not a default: record() never writes it, and check() treats a blank as an error
               on a verified function so the question cannot be skipped.
  date         the day of the run

symbols/quarantine.csv     cases that cannot be used, each with the reason.
  function, cases, option, case (the case file's name without .json), reason, date

A function may be verified only when it has current recorded and edge rows without an option,
and none of its current rows has a failure that is not quarantined (docs/VERIFY.md,
"Quarantine"); tools/validate_functions.py enforces it.
"""
from __future__ import annotations

import csv
import datetime
import fcntl
import glob
import hashlib
import io
import os
import shutil
import subprocess
import re

VERIFICATION_HEADER = ['function', 'cases', 'option', 'total', 'passed', 'failed', 'quarantined', 'source',
                       'cases_sha256', 'date']
QUARANTINE_HEADER = ['function', 'cases', 'option', 'case', 'reason', 'date']
CASE_SETS = ('recorded', 'edge', 'option-recorded')
SOURCE_HASH_LENGTH = 16
# A row whose case files are not in this checkout carries this instead of a hash. It says "someone
# looked and the inputs are not here", which is why record() never writes it: silence and an
# absence are different claims, and only one of them is worth anything.
CASES_UNAVAILABLE = 'unavailable'
INCLUDE = re.compile(r'^\s*#\s*include\s*"([^"]+)"', re.M)


_DEFINING_INDEX: dict = {}      # root -> {bb_ name -> sorted defining files}, built once per process
DEFINER = re.compile(r'\bbb_([A-Za-z0-9_]+)\s*\(')
PLAIN_NAME = re.compile(r'^[A-Za-z0-9_]+$')


def _defining_index(root: str) -> dict:
    """One walk of game/ that records every bb_<name> each source defines.

    `defining_files` used to walk and read all of game/ per call: 44.6 ms measured, which is
    fine for the 21 rows checked today and 7,051 s in `verification.check` the day all 157,757
    entries are verified -- the same shape as the 507 s `_install_mode_hosts` quadratic, waking
    up exactly at the finish condition. A process never edits game/ mid-run, so one walk is
    the whole truth for its lifetime; a caller that does edit must call forget_defining_index.
    """
    key = os.path.realpath(root)
    index = _DEFINING_INDEX.get(key)
    if index is not None:
        return index
    index = {}
    for dp, _, fns in os.walk(os.path.join(root, 'game')):
        for fn in sorted(fns):
            if not fn.endswith(('.c', '.cc', '.cpp')):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            with open(path, errors='replace') as f:
                for found in set(DEFINER.findall(f.read())):
                    index.setdefault(found, []).append(rel)
    for files in index.values():
        files.sort()
    _DEFINING_INDEX.clear()         # one root per process in practice; keep the map honest
    _DEFINING_INDEX[key] = index
    return index


def forget_defining_index() -> None:
    """Drop the cached index (a caller that writes sources between lookups must ask for this)."""
    _DEFINING_INDEX.clear()


def defining_files(root: str, name: str) -> list[str]:
    """Files under game/ that define the replacement bb_<name>."""
    if not PLAIN_NAME.match(name):
        out = []
        pattern = re.compile(rf'\bbb_{re.escape(name)}\s*\(')
        for dp, _, fns in os.walk(os.path.join(root, 'game')):
            for fn in sorted(fns):
                if fn.endswith(('.c', '.cc', '.cpp')):
                    path = os.path.join(dp, fn)
                    with open(path, errors='replace') as f:
                        if pattern.search(f.read()):
                            out.append(os.path.relpath(path, root).replace(os.sep, '/'))
        return sorted(out)
    return list(_defining_index(root).get(name, ()))


_FILE_BYTES: dict = {}


def file_bytes(path: str) -> bytes:
    """The file's bytes, read once per process per (realpath, mtime_ns, size).

    source_files() and source_hash() each opened every defining file and every included header
    once per call, so auditing 21,128 ledger pins read the same 105 files tens of thousands of
    times: 6.5 ms per row, 2 m 18 s for one audit, and half an hour at the finish condition for
    a check that reads about three megabytes of source in total."""
    real = os.path.realpath(path)
    st = os.stat(path)
    key = (real, st.st_mtime_ns, st.st_size)
    got = _FILE_BYTES.get(key)
    if got is None:
        with open(path, 'rb') as f:
            got = f.read()
        if len(_FILE_BYTES) > 8192:
            _FILE_BYTES.clear()
        _FILE_BYTES[key] = got
    return got


_FILE_INCLUDES: dict = {}


def includes_of(path: str) -> tuple:
    """The #include names in PATH, scanned once per (realpath, mtime_ns, size).

    Caching the bytes was not enough: the leaf family's translation unit is one megabyte of
    generated bodies, so decoding it and running the include regex over it cost 5 ms of CPU per
    source_hash() call -- 1 m 52 s for one pin audit even after every read was served from
    memory. The scan is a property of the file, so it is done when the file is first seen."""
    real = os.path.realpath(path)
    st = os.stat(path)
    key = (real, st.st_mtime_ns, st.st_size)
    got = _FILE_INCLUDES.get(key)
    if got is None:
        got = tuple(INCLUDE.findall(file_bytes(path).decode(errors='replace')))
        if len(_FILE_INCLUDES) > 8192:
            _FILE_INCLUDES.clear()
        _FILE_INCLUDES[key] = got
    return got


def forget_sources() -> None:
    """Drop the cached source text and file bytes: for a caller that writes game/ mid-process."""
    _FILE_BYTES.clear()
    _FILE_INCLUDES.clear()
    _DEFINING_INDEX.clear()


def source_files(root: str, name: str) -> list[str]:
    """The defining files and every header they include from game/ or runtime/include/."""
    search = [os.path.join(root, 'game'), os.path.join(root, 'runtime', 'include')]
    seen: set[str] = set()
    todo = [os.path.join(root, p) for p in defining_files(root, name)]
    while todo:
        path = os.path.normpath(todo.pop())
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        for inc in includes_of(path):
            for base in [os.path.dirname(path)] + search:
                candidate = os.path.normpath(os.path.join(base, inc))
                if os.path.isfile(candidate):
                    todo.append(candidate)
                    break
    return sorted(os.path.relpath(p, root).replace(os.sep, '/') for p in seen)


_SOURCE_HASH_CACHE: dict = {}


def source_hash(root: str, name: str) -> str:
    files = source_files(root, name)
    if not files:
        return ''
    # The hash is a function of the defining file list and those files' contents, and nothing
    # else, so every member of a generated family has the same one: 3,619 mov_rax members share
    # one translation unit. Keyed on the list plus each file's (mtime_ns, size), a repeat costs a
    # few stats instead of a megabyte of sha256, and a file that changes cannot hit a stale entry.
    versions = []
    for rel in files:
        st = os.stat(os.path.join(root, rel))
        versions.append((rel, st.st_mtime_ns, st.st_size))
    key = (os.path.realpath(root), tuple(versions))
    got = _SOURCE_HASH_CACHE.get(key)
    if got is not None:
        return got
    h = hashlib.sha256()
    for rel, _, _ in versions:
        h.update(rel.encode() + b'\0')
        h.update(file_bytes(os.path.join(root, rel)) + b'\0')
    got = h.hexdigest()[:SOURCE_HASH_LENGTH]
    if len(_SOURCE_HASH_CACHE) > 8192:
        _SOURCE_HASH_CACHE.clear()
    _SOURCE_HASH_CACHE[key] = got
    return got


def cases_hash(captures: str) -> str:
    """A hash of the case files in CAPTURES, which are the inputs a recorded run fed to both
    sides. Names are hashed with the contents, so adding, removing, renaming or editing a case
    all change it; a case file's name is part of what it is, since the ledger counts them.

    abi.json is excluded for the same reason tools/verify.py skips it: it describes the
    function's calling convention for the catalog, it is not a case."""
    paths = sorted(p for p in glob.glob(os.path.join(captures, '*.json'))
                   if os.path.basename(p) != 'abi.json')
    if not paths:
        return ''
    h = hashlib.sha256()
    for path in paths:
        h.update(os.path.basename(path).encode() + b'\0')
        with open(path, 'rb') as f:
            h.update(f.read() + b'\0')
    return h.hexdigest()[:SOURCE_HASH_LENGTH]


# A ledger cache keyed on (path, mtime_ns, size) was tried here and removed: the suite's
# test_the_evidence_hash_does_not_depend_on_how_the_ledger_was_written rewrites the file three
# times with a 16-hex pin changed, so path, size and mtime tick are all identical and the cache
# served the first answer for the third write. A changed pin stopped changing the evidence -- the
# one property that test exists to hold. Correct invalidation needs the content, and reading the
# content is the cost being avoided, so the cost stands until the ledger write itself is batched.


def evidence_hash(root: str, name: str) -> str:
    """What the ledger says the evidence for NAME is: each case set's name and its case pin.

    This is the half of a review's subject that is not the code. It changes when a case file
    changes (cases_sha256), when a set appears or disappears (cases), and not when a row is
    re-recorded against the same case files -- re-running unchanged inputs is the same evidence,
    while a different input set is a different claim and needs a new review. `unavailable` is
    hashed as the literal claim it is, so approving a function whose captures are not in the
    checkout pins that absence rather than pretending to a hash it never had.

    Rows are hashed in the ledger's own CANONICAL order -- CASE_SETS rank, then option -- and not
    in the order the file happens to hold them. A row's place in the file is a fact about when it
    was appended, so hashing file order makes an approval stale when someone rewrites the CSV in a
    different order, which is a change to how the file was written and not to what was approved.
    The order is total on today's ledger (no function has two rows with the same set and option),
    and sorting is a no-op on all 30 approvals in it, so the invariant costs nothing and no longer
    depends on anyone remembering the convention.
    """
    rows = [r for r in read_csv(os.path.join(root, 'symbols', 'verification.csv'),
                                     VERIFICATION_HEADER) if r['function'] == name]
    if not rows:
        return ''
    def canonical(r: dict) -> tuple:
        # An unknown set sorts after every known one rather than raising: the ledger's own reader
        # reports that row as malformed, and a hash is the wrong place to discover it.
        rank = CASE_SETS.index(r['cases']) if r['cases'] in CASE_SETS else len(CASE_SETS)
        return rank, r['option']

    h = hashlib.sha256()
    for r in sorted(rows, key=canonical):
        h.update(f"{r['cases']}|{r['option']}|{r['cases_sha256']}".encode() + b'\0')
    return h.hexdigest()[:SOURCE_HASH_LENGTH]


def read_csv(path: str, header: list[str]) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, newline='') as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != header:
        raise ValueError(f'{path}: header must be {",".join(header)}')
    return [dict(zip(header, r), _line=n) for n, r in enumerate(rows[1:], 2)]


def write_csv(path: str, header: list[str], rows: list[dict]) -> None:
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    w.writerow(header)
    for r in rows:
        w.writerow([r[k] for k in header])
    with open(path, 'w', newline='') as f:
        f.write(out.getvalue())


def quarantined(root: str, function: str, cases: str, option: str) -> dict[str, str]:
    """case -> reason for one function, case set and option."""
    rows = read_csv(os.path.join(root, 'symbols', 'quarantine.csv'), QUARANTINE_HEADER)
    return {r['case']: r['reason'] for r in rows
            if r['function'] == function and r['cases'] == cases and r['option'] == option}


def _head_or_refuse(root: str) -> str:
    """The commit a pre-record snapshot belongs to. Empty output refuses; it is never a stamp.

    The snapshot exists to be diffed against the tree that produced it. `git rev-parse HEAD`
    that fails -- no repo, no git, a killed pipe -- used to be swallowed by `except OSError`
    and then written as an empty first line, which is a snapshot claiming a provenance it does
    not have: the promote.py-exits-0-while-unable class, in the one file the value-identity
    check reads. A caller that genuinely has no HEAD must say so out loud.
    """
    proc = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True)
    head = proc.stdout.strip()
    if proc.returncode == 0 and head:
        return head
    if os.environ.get('BB_ALLOW_NO_HEAD') == '1':
        return 'no-head:' + datetime.datetime.now().isoformat(timespec='seconds')
    why = proc.stderr.strip() or f'git rev-parse exited {proc.returncode}'
    raise RuntimeError(f'{root}: cannot read HEAD ({why}). The pre-record snapshot is diffed '
                       'against a commit; set BB_ALLOW_NO_HEAD=1 to stamp "no-head:<time>" instead.')


def record(root: str, function: str, cases: str, option: str, case_names: list[str], failing: list[str],
           captures: str) -> dict:
    """Writes the row for one run, including a hash of the case files it ran; returns it."""
    if cases not in CASE_SETS:
        raise ValueError(f'case set must be one of {", ".join(CASE_SETS)}')
    digest = cases_hash(captures)
    if not digest:
        # A row claims agreement on a set of inputs. Recording one without being able to see the
        # inputs would be a claim with nothing behind it -- the same fail-open as a fault that
        # compares nothing.
        raise ValueError(f'{captures}: no case files, so there is nothing to record a result about')
    q = quarantined(root, function, cases, option)
    failed = [c for c in failing if c not in q]
    row = {'function': function, 'cases': cases, 'option': option, 'total': str(len(case_names)),
           'passed': str(len(case_names) - len(failing)), 'failed': str(len(failed)),
           'quarantined': str(len(failing) - len(failed)), 'source': source_hash(root, function),
           'cases_sha256': digest, 'date': datetime.date.today().isoformat()}
    path = os.path.join(root, 'symbols', 'verification.csv')
    # Runs may record at the same time (one per function): read, update and write under a lock.
    with open(path + '.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # A snapshot you have to remember is a snapshot you will not have. Keep the first
        # pre-record state seen for this path, with the HEAD it belongs to, so a re-record can
        # be diffed against what it replaced instead of against nothing.
        # Only a ledger that exists has a prior state worth preserving: the first record on a
        # fresh tree creates it, and a snapshot of nothing is not a failure, it is an absence.
        if os.path.exists(path) and not os.path.exists(path + '.pre'):
            head = _head_or_refuse(root)
            try:
                shutil.copy2(path, path + '.pre')
                stamp, tmp = path + '.pre.stamp', path + '.pre.stamp.tmp'
                with open(tmp, 'w') as s:
                    s.write(f'{head}\n{datetime.datetime.now().isoformat(timespec="seconds")}\n')
                os.replace(tmp, stamp)
            except OSError as e:
                for stray in (path + '.pre', path + '.pre.stamp.tmp'):
                    if os.path.exists(stray):
                        os.unlink(stray)
                raise RuntimeError(f'cannot snapshot {path} before recording: {e}') from e
        rows = [r for r in read_csv(path, VERIFICATION_HEADER)
                if (r['function'], r['cases'], r['option']) != (function, cases, option)]
        rows.append(row)
        rows.sort(key=lambda r: (r['function'], CASE_SETS.index(r['cases']) if r['cases'] in CASE_SETS else 99,
                                 r['option']))
        write_csv(path, VERIFICATION_HEADER, rows)
    return row


def check(root: str, funcs: list[dict]) -> list[str]:
    """Errors for verified functions without a clean, current record, and for malformed rows."""
    errs: list[str] = []
    try:
        results = read_csv(os.path.join(root, 'symbols', 'verification.csv'), VERIFICATION_HEADER)
        quarantine = read_csv(os.path.join(root, 'symbols', 'quarantine.csv'), QUARANTINE_HEADER)
    except ValueError as e:
        return [str(e)]
    names = {f['name'] for f in funcs}
    for q in quarantine:
        where = f"symbols/quarantine.csv:{q['_line']}"
        if q['function'] not in names:
            errs.append(f"{where}: {q['function']} is not in symbols/functions.csv")
        if q['cases'] not in CASE_SETS:
            errs.append(f"{where}: cases must be one of {', '.join(CASE_SETS)}")
        if not q['reason'].strip():
            errs.append(f"{where}: a quarantined case needs its reason")
        if not q['case'].strip():
            errs.append(f"{where}: case is empty")
    counts: dict[tuple, int] = {}
    for q in quarantine:
        key = (q['function'], q['cases'], q['option'])
        counts[key] = counts.get(key, 0) + 1
    by_function: dict[str, list[dict]] = {}
    for r in results:
        where = f"symbols/verification.csv:{r['_line']}"
        if r['cases'] not in CASE_SETS:
            errs.append(f"{where}: cases must be one of {', '.join(CASE_SETS)}")
            continue
        try:
            total, passed, failed, held = (int(r[k]) for k in ('total', 'passed', 'failed', 'quarantined'))
        except ValueError:
            errs.append(f'{where}: total, passed, failed and quarantined must be numbers')
            continue
        if passed + failed + held != total:
            errs.append(f'{where}: passed + failed + quarantined must equal total')
        if held > counts.get((r['function'], r['cases'], r['option']), 0):
            errs.append(f'{where}: {held} quarantined, but symbols/quarantine.csv lists fewer cases for it')
        by_function.setdefault(r['function'], []).append(r)
    for f in funcs:
        if f['status'] != 'verified':
            continue
        where = f"symbols/functions.csv:{f['_line']}: {f['name']} is verified"
        current = source_hash(root, f['name'])
        rows = by_function.get(f['name'], [])
        stale = [r for r in rows if r['source'] != current]
        fresh = [r for r in rows if r['source'] == current]
        for need in ('recorded', 'edge'):
            if not any(r['cases'] == need and r['option'] == '' for r in fresh):
                errs.append(f"{where} without a current {need} result in symbols/verification.csv "
                            f"(tools/verify.py run --record {need})")
        for need in ('recorded', 'edge'):
            pinned = [r for r in fresh if r['cases'] == need and r['option'] == ''
                      and (r['cases_sha256'] == CASES_UNAVAILABLE
                           or re.fullmatch(r'[0-9a-f]{%d}' % SOURCE_HASH_LENGTH, r['cases_sha256']))]
            if not pinned:
                errs.append(f"{where} without a current {need} result that pins its case files "
                            f"(symbols/verification.csv has no cases_sha256 for it, and no "
                            f"'{CASES_UNAVAILABLE}' either): run it again with --record, or look for "
                            f"the captures and say so if they are not in this checkout")
        for r in fresh:
            if int(r['failed']) or int(r['total']) == 0:
                label = r['cases'] + (f" with {r['option']}" if r['option'] else '')
                errs.append(f"{where} with {r['failed']} unexplained failure(s) in its {label} cases "
                            f"(symbols/verification.csv:{r['_line']}): fix them or quarantine them with the reason")
        for r in stale:
            label = r['cases'] + (f" with {r['option']}" if r['option'] else '')
            errs.append(f"{where} but its {label} result (symbols/verification.csv:{r['_line']}) is for other code: "
                        f"run it again with --record")
    return errs


def replacement_symbol(root: str, name: str, address: str) -> str | None:
    """The replacement symbol for a function, resolved in one place.

    The hook registry is binding; a row declared `host` in symbols/install_mode.csv
    is verified without being installed in the running game. verify.py and
    validate_functions.py both call this, so the two tools cannot drift into
    disagreeing about what a non-`original` row means.
    """
    hooks = os.path.join(root, 'game', 'hooks.csv')
    if os.path.exists(hooks):
        with open(hooks, newline='') as f:
            for r in csv.DictReader(f):
                if r['address'] == address:
                    return r['replacement']
    modes = os.path.join(root, 'symbols', 'install_mode.csv')
    if os.path.exists(modes):
        with open(modes, newline='') as f:
            for r in csv.DictReader(f):
                if r['address'] == address and r['mode'] == 'host':
                    return 'bb_' + name
    return None
