#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Progress numbers, derived only from files under symbols/.

Denominator: symbols/ghidra_functions.csv (address,size), the functions Ghidra
finds in the executable blocks of the target eboot (see tools/ghidra/).
Numerator: rows of symbols/functions.csv by status. Each level includes the next:
replaced (hooked and builds) > edge-verified (verify.py passes on the generated edge cases)
> verified (and on inputs recorded in the game).
Runtime: symbols/boot.json, written by tools/boot.py from a run of the boot harness
(runtime/boot.c): of the executable's imports, how many the game's own bundled modules provide,
how many the runtime implements and how many remain; the furthest boot milestone; where the
boot stops.

usage: progress.py [--root DIR] [--out FILE] [--update-readme] [--check] [--status-line]
  (no flag)        print the progress JSON
  --out FILE       write the JSON to FILE
  --status-line    print the current-status sentence (plain text, for issues and descriptions)
  --update-readme  rewrite the status, progress and target blocks of README.md, the status
                   block of CONTRIBUTING.md (and the progress
                   block of STATUS.md when it has one)
  --check          exit 1 if those blocks differ from the generated ones
"""
from __future__ import annotations

import argparse
import gzip
import pathlib
import csv
import hashlib
import json
import bisect
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPLEMENTED = ('replaced', 'edge-verified', 'verified')
EDGE = ('edge-verified', 'verified')
BLOCKS = ('progress', 'target')


def sha256_file(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_csv(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 2) if whole else None


def compute(root: str) -> dict:
    export = read_csv(os.path.join(root, 'symbols', 'ghidra_functions.csv'))
    funcs = read_csv(os.path.join(root, 'symbols', 'functions.csv'))
    total_f = len(export)
    total_b = sum(int(r['size']) for r in export)

    # Denominator 2 -- maximal extents.  Most catalogue rows do not begin a function: a row
    # whose start lies strictly inside another row's extent is an interior address, not a
    # boundary.  Counting it as a function inflates the denominator, so the two ratios are
    # printed together and neither may be quoted without the other.
    spec = sorted((int(r['address'], 16), int(r['size'])) for r in export)
    starts = [a for a, _ in spec]
    ends = [a + s for a, s in spec]

    def _interior(a: int) -> bool:
        i = bisect.bisect_right(starts, a) - 1
        return any(starts[j] < a < ends[j] for j in (i - 1, i) if j >= 0)

    maximal = {a for a, _ in spec if not _interior(a)}

    def tally(rows: list[dict]) -> dict:
        return {'functions': len(rows), 'bytes': sum(int(r['size']) for r in rows)}

    impl = [r for r in funcs if r['status'] in IMPLEMENTED]
    edge = [r for r in funcs if r['status'] in EDGE]
    ver = [r for r in funcs if r['status'] == 'verified']
    systems: dict[str, dict] = {}
    for r in funcs:
        s = systems.setdefault(r['system'], {'tracked': 0, 'replaced': 0, 'edge_verified': 0, 'verified': 0,
                                             'replaced_bytes': 0})
        s['tracked'] += 1
        if r['status'] in IMPLEMENTED:
            s['replaced'] += 1
            s['replaced_bytes'] += int(r['size'])
        if r['status'] in EDGE:
            s['edge_verified'] += 1
        if r['status'] == 'verified':
            s['verified'] += 1
    statuses = {s: sum(1 for r in funcs if r['status'] == s) for s in
                {r['status'] for r in funcs}}
    return {
        'schema': 1,
        'slices': slices(export, funcs),
        'statuses': statuses,
        'ledger': ledger(root),
        'origins': replacement_origins(root),
        'inputs': {
            'ghidra_functions_sha256': sha256_file(os.path.join(root, 'symbols', 'ghidra_functions.csv')),
            'functions_sha256': sha256_file(os.path.join(root, 'symbols', 'functions.csv')),
        },
        'total': {'functions': total_f, 'bytes': total_b},
        'tracked': tally(funcs),
        'replaced': {**tally(impl), 'functions_pct': pct(len(impl), total_f),
                     'bytes_pct': pct(tally(impl)['bytes'], total_b)},
        'edge_verified': {**tally(edge), 'functions_pct': pct(len(edge), total_f),
                          'bytes_pct': pct(tally(edge)['bytes'], total_b)},
        'verified': {**tally(ver), 'functions_pct': pct(len(ver), total_f),
                     'bytes_pct': pct(tally(ver)['bytes'], total_b)},
        'maximal': {'extents': len(maximal), 'contained': len(export) - len(maximal),
                    'edge': sum(1 for r in edge if int(r['address'], 16) in maximal),
                    'tracked': sum(1 for r in funcs if int(r['address'], 16) in maximal)},
        'systems': {k: systems[k] for k in sorted(systems)},
        'runtime': runtime(root),
    }


def replacement_origins(root: str) -> dict | None:
    """How many replacements were hand-written and how many a generator emitted.

    `symbols/replacement_origins.csv` holds one row per non-original function. The split is
    printed on every burndown because the tree's first generated rows are indistinguishable from
    hand-written ones in every other artifact: same CSV shape, same readable C++ after the
    generator's output is reviewed. A count that does not say where its rows came from is a count
    about volume, and this project's claims are about provenance."""
    path = os.path.join(root, 'symbols', 'replacement_origins.csv')
    if not os.path.exists(path):
        return None
    replaced = {r['address'] for r in read_csv(os.path.join(root, 'symbols', 'functions.csv'))
                if r['status'] != 'original'}
    counts = {'hand': 0, 'generated': 0}
    for r in read_csv(path):
        # Only rows that are actually replacements: a generated body may sit at status 'original'
        # waiting for its evidence, and counting it would print a split that does not partition
        # the 'replaced' figure it is printed beside.
        if r['address'] in replaced:
            counts[r['origin']] = counts.get(r['origin'], 0) + 1
    return counts


def ledger(root: str) -> dict | None:
    """Rows and functions in `symbols/verification.csv`, plus the approval count.

    `functions.csv`'s status column is what this tool tallies; the ledger is what proves it.
    They can disagree -- a status flipped by hand is not a recorded run -- so the burndown
    line prints both and drift is visible without joining anything."""
    path = os.path.join(root, 'symbols', 'verification.csv')
    if not os.path.isfile(path):
        return None
    rows = read_csv(path)
    out = {'rows': len(rows), 'functions': len({r['function'] for r in rows})}
    # A row whose `cases_sha256` is 'unavailable' records a comparison whose inputs are not in
    # the tree: it can be read and it cannot be repeated. Counting the functions that rest on
    # such a row is what keeps the headline honest -- "verified" claims a comparison happened,
    # and this is how many of those claims nobody can re-check.
    unrerun = {r['function'] for r in rows if r.get('cases_sha256') == 'unavailable'}
    out['unrerunnable'] = len(unrerun)
    # The evidence kind lives in the row's `cases` field. A `bytes` row says "the replacement's
    # executed bytes equal the original extent's" -- nothing ran. Printing the split beside the
    # headline is what stops it merging differentially-backed members with byte-backed ones,
    # because the first question anyone asks of a coverage number is which of them ran.
    byte_backed = {r['function'] for r in rows if r['cases'] == 'bytes'}
    out['byte_backed'] = len(byte_backed)
    out['differential_backed'] = out['functions'] - len(byte_backed)
    fpath = os.path.join(root, 'symbols', 'functions.csv')
    if os.path.isfile(fpath):
        verified = {r['name'] for r in read_csv(fpath) if r['status'] == 'verified'}
        out['verified'] = len(verified)
        out['unrerunnable_verified'] = len(unrerun & verified)
    rpath = os.path.join(root, 'symbols', 'reviews.csv')
    if os.path.isfile(rpath):
        approved = [r for r in read_csv(rpath) if r.get('verdict', '').strip() == 'approved']
        out['approvals'] = len(approved)
        out['approved_functions'] = len({r['address'] for r in approved})
    return out


def burndown_line(d: dict) -> str:
    """The whole project's progress on one line, in functions and in bytes.

    The ladder here is cumulative -- replaced > edge-verified > verified, each row including
    the next -- so an unlabelled "623 edge-verified" beside "21 verified" reads as two disjoint
    buckets and never reconciles by hand. Printing the exclusive decomposition next to the
    cumulative rungs makes both readings true at once. Bytes are permanent, not decoration:
    the same count is 0.39% of functions and 0.20% of bytes, and only the second is what
    "how much of the game is done" means."""
    t, r, e, v = d['total'], d['replaced'], d['edge_verified'], d['verified']

    def rung(name: str, x: dict) -> str:
        # The referent, in words, beside the number. "bytes" fits two quantities -- the guest extent
        # of the replaced functions (this column) and the size of the replacement body written for
        # them (a different column that does not exist) -- and that confusion has produced a wrong
        # total three times. A column whose name fits two quantities keeps being filled with either.
        return (f'{name} {x["functions"]} ({fmt_pct(x["functions_pct"])}, '
                f'{x["bytes"]} B guest-extent {fmt_pct(x["bytes_pct"])})')

    ex = d.get('statuses') or {}
    parts = [
        rung('verified', v),
        rung('edge-verified incl. verified', e),
        (f'evidence: {d["ledger"]["differential_backed"]} differential / '
         f'{d["ledger"]["byte_backed"]} byte-identical' if d.get('ledger') else 'evidence: -'),
        rung('replaced', r),
    ]
    if d.get('origins'):
        o = d['origins']
        parts.append(f"hand {o['hand']} / generated {o['generated']}")
    parts += [
        (f'maximal extents {mx["extents"]} (edge-verified {mx["edge"]}, '
         f'{fmt_pct(pct(mx["edge"], mx["extents"]))}); '
         f'{mx["contained"]} of {t["functions"]} catalogue rows start inside another'
         if (mx := d.get('maximal')) else ''),
        f'target {t["functions"]} ({t["bytes"]} B)',
        'exclusive ' + ' + '.join(f'{ex[s]} {s}' for s in sorted(ex)),
    ]
    led = d.get('ledger')
    if led:
        parts.append(f'ledger {led["rows"]} rows / {led["functions"]} functions')
        if 'approvals' in led:
            parts.append(f'{led["approvals"]} approvals on {led["approved_functions"]} functions')
        if 'unrerunnable' in led:
            parts.append(f're-runnable evidence {led["functions"] - led["unrerunnable"]} of '
                         f'{led["functions"]} (verified {led.get("verified", 0) - led.get("unrerunnable_verified", 0)}'
                         f' of {led.get("verified", 0)})'
                         ' [all rows clean; the join prints the any-row-clean count beside it,'
                         ' and the two differ by functions holding one timestamp-less row]')
    return 'burndown: ' + ' | '.join(parts)


def runtime(root: str) -> dict | None:
    """The boot harness's last recorded run (symbols/boot.json, from tools/boot.py), or None."""
    path = os.path.join(root, 'symbols', 'boot.json')
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        b = json.load(f)
    bundled = b.get('imports_bundled', 0)
    covered = bundled + b['imports_implemented']
    unresolved = b.get('imports_unresolved', 0)
    return {'imports_total': b['imports_total'], 'imports_implemented': b['imports_implemented'],
            'imports_bundled': bundled, 'imports_covered': covered,
            'imports_unresolved': unresolved,
            'imports_unbound': b['imports_total'] - covered - unresolved,
            'imports_remaining': b['imports_total'] - covered,
            'imports_pct': pct(covered, b['imports_total']),
            'milestone': b['milestone'], 'milestone_index': b['milestone_index'],
            'milestones': len(b['milestones']) - 1, 'first_unimplemented': b.get('first_unimplemented'),
            'fault': b.get('fault'), 'outcome': b['outcome']}


SLICES = 64


def slices(export: list[dict], funcs: list[dict]) -> list[dict]:
    """The exported code range in SLICES equal address ranges: functions and bytes in each
    (by entry address), and how many of those bytes are replaced and verified."""
    if not export:
        return []
    starts = [int(r['address'], 16) for r in export]
    lo = min(starts)
    hi = max(int(r['address'], 16) + int(r['size']) for r in export)
    step = -(-(hi - lo) // SLICES)
    out = [{'start': f'0x{lo + i * step:08x}', 'end': f'0x{min(hi, lo + (i + 1) * step):08x}',
            'functions': 0, 'bytes': 0, 'replaced_bytes': 0, 'verified_bytes': 0} for i in range(SLICES)]
    for r in export:
        sl = out[(int(r['address'], 16) - lo) // step]
        sl['functions'] += 1
        sl['bytes'] += int(r['size'])
    for r in funcs:
        a = int(r['address'], 16)
        if not lo <= a < hi:
            continue
        sl = out[(a - lo) // step]
        if r['status'] in IMPLEMENTED:
            sl['replaced_bytes'] += int(r['size'])
        if r['status'] == 'verified':
            sl['verified_bytes'] += int(r['size'])
    return out


def fmt_pct(p: float | None) -> str:
    return 'n/a' if p is None else f'{p:.2f}%'


def render_progress(d: dict) -> str:
    if not d['total']['functions']:
        return ('No Ghidra export committed yet (`symbols/ghidra_functions.csv`), '
                'so there is no denominator.\n')
    t, r, e, v = d['total'], d['replaced'], d['edge_verified'], d['verified']
    return '\n'.join([
        '| | Functions | Bytes |',
        '|---|---:|---:|',
        f"| Target (Ghidra export) | {t['functions']} | {t['bytes']} |",
        f"| Replaced | {r['functions']} ({fmt_pct(r['functions_pct'])}) | "
        f"{r['bytes']} ({fmt_pct(r['bytes_pct'])}) |",
        f"| Edge-verified | {e['functions']} ({fmt_pct(e['functions_pct'])}) | "
        f"{e['bytes']} ({fmt_pct(e['bytes_pct'])}) |",
        f"| Verified | {v['functions']} ({fmt_pct(v['functions_pct'])}) | "
        f"{v['bytes']} ({fmt_pct(v['bytes_pct'])}) |",
        '',
        'Each row includes the next: verified functions are also edge-verified and replaced.',
        '',
        *render_evidence(d),
        *render_runtime(d['runtime']),
        'Generated by `tools/progress.py --update-readme` from `symbols/`. Do not edit.',
        '',
    ])


def render_evidence(d: dict) -> list[str]:
    """How much of the ladder rests on evidence this tree can reproduce.

    A ledger row pins its cases with `cases_sha256`; the value 'unavailable' -- written by
    `verify.py --record` when the case directory is not in the tree -- means the row records a
    comparison whose inputs cannot be re-run. That is not a defect in any one row: it is the
    reason the count belongs beside the rung, where a reader meets it before quoting the rung."""
    led = d.get('ledger') or {}
    if 'unrerunnable' not in led:
        return []
    total, un = led['functions'], led['unrerunnable']
    ver, ver_un = led.get('verified', 0), led.get('unrerunnable_verified', 0)
    return [
        f'Of those {total} functions, {un} rest on ledger rows whose `cases_sha256` is '
        f'`unavailable`: the comparison is recorded, its inputs are not in this tree, so it '
        f'cannot be re-run. At the top rung that is {ver_un} of {ver}.',
        '',
    ]


def render_runtime(rt: dict | None) -> list[str]:
    if not rt:
        return ['Runtime: no boot run recorded yet (`tools/boot.py`).', '']
    return [
        '| Runtime | |',
        '|---|---|',
        f"| System imports implemented | {rt['imports_covered']} of {rt['imports_total']} "
        f"({fmt_pct(rt['imports_pct'])}): {rt['imports_bundled']} by the game's own modules, "
        f"{rt['imports_implemented']} by the runtime |",
        f"| Other imports | {rt['imports_unresolved']} registered fail-loud diagnostics, "
        f"{rt['imports_unbound']} unbound |",
        f"| Furthest boot milestone | {rt['milestone']} ({rt['milestone_index']} of {rt['milestones']}) |",
        f"| Boot stops at | {boot_stop(rt)} |",
        '',
    ]


def boot_stop(rt: dict) -> str:
    stop = rt['first_unimplemented']
    if stop:
        caller = stop.get('caller')
        by = f", called by {caller}" if caller and caller != 'eboot' else ''
        return f"`{stop['symbol'] or stop['nid']}` ({stop['library']}{by})"
    if rt.get('fault'):
        return f"{rt['outcome']} at `{rt['fault']['at']}`"
    return rt['outcome']


def status_sentence(d: dict, link: bool) -> str:
    """Where the project stands, in one or two sentences: the game does not run on Paleblood yet;
    how many functions are verified, and how far the executable boots on our own runtime."""
    v, t = d['verified'], d['total']
    text = (f"The game doesn't run on Paleblood yet: {v['functions']} of {t['functions']} functions are "
            f"verified ({fmt_pct(v['functions_pct'])}).")
    rt = d.get('runtime')
    if rt:
        runtime = '[our own runtime](runtime/)' if link else 'our own runtime'
        text += (f" On {runtime} the executable's boot gets as far as {boot_stop(rt)}, with "
                 f"{rt['imports_covered']} of {rt['imports_total']} system imports covered "
                 f"({rt['imports_implemented']} of them by the runtime).")
    return text


def render_status(d: dict) -> str:
    return status_sentence(d, True) + '\n'


def render_target(root: str) -> str:
    path = os.path.join(root, 'target.sha256')
    if not os.path.isfile(path):
        return 'No `target.sha256` yet.\n'
    with open(path) as f:
        lines = [ln.rstrip('\n') for ln in f if ln.strip()]
    return '```\n' + '\n'.join(lines) + '\n```\n'


def block_re(name: str) -> re.Pattern:
    return re.compile(rf'(<!-- {name}:start -->\n)(.*?)(<!-- {name}:end -->)', re.S)


def apply_blocks(text: str, bodies: dict[str, str]) -> str:
    for name, body in bodies.items():
        pat = block_re(name)
        if not pat.search(text):
            raise SystemExit(f'progress: README.md has no {name} block')
        text = pat.sub(lambda m: m.group(1) + body + m.group(3), text)
    return text


def evidence_join(root, argv=None):
    """Join claimed status against recorded evidence.

    A row counts as edge-verified only when symbols/functions.csv says so AND
    symbols/verification.csv holds a row for it. status and ledger-backed are
    different claims; re-runnable is a third. Fail on inability to read the
    ledger, not only on disagreement: rc=0 from an unrun check is the species
    this exists to kill.
    """
    import csv as _csv
    try:
        with open(os.path.join(root, 'symbols', 'functions.csv'), newline='') as f:
            funcs = list(_csv.DictReader(f))
        with open(os.path.join(root, 'symbols', 'verification.csv'), newline='') as f:
            ledger = list(_csv.DictReader(f))
    except (OSError, _csv.Error) as exc:
        print(f'join: cannot read the ledger: {exc}')
        return 1
    edge = [r for r in funcs if r['status'] in ('edge-verified', 'verified')]
    by_addr = {}
    for r in ledger:
        by_addr.setdefault(r.get('function', ''), []).append(r)
    names = {r['name'] for r in funcs}
    backed, rerun, rerun_all, unbacked, mixed = 0, 0, 0, [], []
    for r in edge:
        rows = by_addr.get(r['name']) or []
        if not rows:
            unbacked.append(r['address'])
            continue
        backed += 1
        clean = [(x.get('cases_sha256') or '') not in ('', 'unavailable') for x in rows]
        if any(clean):
            rerun += 1
        if all(clean):
            rerun_all += 1
        elif any(clean):
            mixed.append(r['address'])
    surplus = len(ledger) - len(funcs)
    # The surplus is arithmetic, not drift, and it has been misread as drift for several slices.
    # Measured 2026-10-21: 30 functions carry 101 rows beyond one apiece -- both a `recorded` and
    # an `edge` case set, most with options 30/60/uncapped -- and the two `original` rows carry no
    # evidence by design. 21,229 rows - 21,130 functions = 99 = 101 - 2. Printed decomposed so the
    # pair stops looking like two functions nobody has identified.
    per_fn = {}
    for _r in ledger:
        per_fn[_r['function']] = per_fn.get(_r['function'], 0) + 1
    multi_rows = sum(n - 1 for n in per_fn.values())
    no_evidence = len(funcs) - len(per_fn)
    print(f'join: status {len(edge)} \u00b7 ledger-backed {backed} \u00b7 '
          f're-runnable any row clean {rerun} \u00b7 all rows clean {rerun_all} '
          f'\u00b7 unbacked {len(unbacked)} \u00b7 surplus {surplus}'
          f' = {multi_rows} extra rows over {sum(1 for n in per_fn.values() if n > 1)} multi-row'
          f' functions - {no_evidence} with no evidence')
    for a in mixed[:10]:
        print(f'  mixed rows (one clean row and one timestamp-less row): {a}')
    for a in unbacked[:10]:
        print(f'  unbacked: {a}')
    if unbacked:
        print('join: FAIL -- status claims evidence the ledger does not hold')
        return 1
    return 0


def _parses_clause(root="."):
    """The catalogue-parse verdict, printed where it is READ -- and obtained from the gate.

    Two defects repaired in one line. It recomputed the count itself, in a shape that read like a verdict,
    while `check_catalogue.py` -- the tool that REFUSES a new raw DictReader -- was never invoked by the
    hook at all: a count is not a constraint, and a shaped line is not a check. And it called `scan()`
    with no root, so `--root <tmp>` printed a summary of THIS tree: two instruments, two roots, one output
    line, the second time on this page.

    Unread is not zero: if the gate cannot be imported the line says `not checked` in the same position.
    """
    try:
        import check_catalogue as K
        import gateline
        rc, detail, _problems = K.audit(root)
    except Exception as exc:  # noqa: BLE001
        return f" · parses: not checked ({exc.__class__.__name__}); unread is not zero"
    return f" · {gateline.gate_line('parses', rc, detail)}"


def _symbols_dir(root=".") -> str:
    """One place the symbols directory is computed: --root, or the test seam, never a bare cwd path.

    Every reader on this page used to build its own path, and two of them used a relative one, so a run
    from any directory but the repo root printed "cannot read the catalogue" beside a `--check` that had
    read it fine and returned 0. Two instruments, two roots, one output: the compare was honest and the
    diagnostics beside it were about a different tree.
    """
    return os.environ.get("PB_SYMBOLS_DIR") or os.path.join(root, "symbols")


def extent_line(root=".") -> str:
    """The catalogue's short-extent population, printed because a selector floor excludes it silently.

    family_scan.py:238 --min-size defaults to 14, so no family is ever proposed from a function shorter
    than that, and the unlanded short tail lies entirely inside that shadow. The tie count is here for
    the same reason: "smallest containing extent" has no unique answer when two catalogued extents of one
    length both contain an address, so an ownership claim carries an undefined tail and must say so.
    """
    import os
    import landed as L
    sroot = _symbols_dir(root)   # PB_SYMBOLS_DIR still wins, so a TEST can make a tie occur
    try:
        import catalogue
        cat = catalogue.load_extents(os.path.join(sroot, "ghidra_functions.csv"))
        # Landed is ONE selector, and it is leaf_family_census's: a row at "original" is bookkeeping for a
        # body nobody has written, so counting it as landed understates the work by exactly those rows.
        # Here it was one row, 0x0111a600 (8 B), which is why this line said 5,804 while thunk_census said
        # 5,805 -- one element, and the element had an address.
        landed = L.landed_addresses(os.path.join(sroot, "functions.csv"))
    except (OSError, KeyError, ValueError) as exc:
        return f"extents: cannot read the catalogue ({exc}) -- unread is not zero"
    import bisect
    by = {}
    for a, s in cat:
        by.setdefault(s, []).append(a)
    tied = 0
    for a, s in cat:
        starts = by[s]
        k = bisect.bisect_right(starts, a)
        # Two-sided, because a one-directional test (neighbour starts inside MY window) undercounts by
        # construction: in a tie the later row never sees the earlier one. A row has no unique smallest
        # extent when another extent of the same length OVERLAPS it -- starts in (a-s, a+s) -- or when a
        # second extent occupies its own start. The bracket form of that second test is a tautology:
        # bisect_left != bisect_right means "at least one occurrence", true for every row (157,757 of
        # 157,757 counted as tied), so the duplicate is counted by OCCURRENCES, not by a bracket.
        lo = bisect.bisect_right(starts, a - s)
        hi = bisect.bisect_left(starts, a + s)
        own = k - bisect.bisect_left(starts, a)
        if (hi - lo) - own > 0 or own > 1:
            tied += 1
    short = [a for a, s in cat if s <= 13]
    short_landed = sum(1 for a in short if a in landed)
    pct = 100.0 * tied / len(cat)
    return (f"extents: {len(cat)} catalogued \u00b7 <=13B {len(short)} (landed {short_landed}, "
            f"unlanded {len(short) - short_landed}) \u00b7 family_scan --min-size 14 excludes that whole band "
            f"by default \u00b7 same-length overlapping extents {tied} ({pct:.1f}%) have no unique smallest "
            "(expected 0: sizes are decimal and this catalogue's extents are disjoint, so the tie branch is "
            "a guard against a catalogue that does not exist here, not a live condition)"
            + _parses_clause(root))


def reach_line(root=".") -> str:
    """Both denominators, because two numbers have been doing one job.

    38,018 / 157,757 is SCOPE: a fraction of Ghidra's reach, every row a leaf selector could ever be
    asked about. 36,846 / 43,734 is PROGRESS: a fraction of the BRANCH-FREE population, which is what
    the leaf toolchain can address at all -- byte transcription needs one basic block and
    family_scan's default keeps only jump-free bodies. A branch-containing row belongs to the
    function campaign (generated C, no single-block constraint), so this line counts the boundary and
    never moves it: widening jump_free would let leaf machinery accept control flow it cannot express.
    """
    path = pathlib.Path(_symbols_dir(root)) / 'branch_band.csv.gz'
    try:
        with gzip.open(path, 'rt', newline='') as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        return f'reach: unavailable ({exc}) -- regenerate with tools/branch_census.py; unread is not zero'
    if not rows:
        return f'reach: {path} has no rows -- refusing to print a denominator about nothing'
    total = len(rows)
    branch = sum(1 for r in rows if r['branch'] == '1')
    free = sum(1 for r in rows if r['branch'] == '0')
    landed = sum(1 for r in rows if r['landed'] == 'True')
    free_landed = sum(1 for r in rows if r['branch'] == '0' and r['landed'] == 'True')
    # TWO BYTE NAMES, never the bare word: `landed` counts rows whose status is not 'original'
    # (evidence exists), `transcribed` counts every row that carries a body (evidence may not). One
    # name for both would have to pick which question it answers and would then be quoted as the other.
    try:
        from landed import byte_totals
        bt = byte_totals(os.path.join(_symbols_dir(root), 'functions.csv'))
        bytes_line = (f' · bytes_landed {bt["landed"]:,} (bytes_transcribed {bt["transcribed"]:,})')
    except OSError as exc:
        bytes_line = f' · bytes: unavailable ({exc}) -- unread is not zero'
    return (f'reach: {landed} landed / {free} branch-free = {100 * free_landed / free:.2f}% PROGRESS '
            f'· {landed} / {total} catalogued = {100 * landed / total:.2f}% SCOPE '
            f'· branch {branch} (landed {landed - free_landed}) '
            f'· unlanded branch-free {free - free_landed}' + bytes_line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--out')
    ap.add_argument('--update-readme', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--join', action='store_true', help='join status against recorded evidence')
    ap.add_argument('--status-line', action='store_true')
    ap.add_argument('--burndown', action='store_true')
    a = ap.parse_args()

    # ABSENCE REFUSES, once, before anything is computed: every line downstream degrades to a sentence
    # ("cannot read the catalogue", "reach: unavailable") and the rc would still have been 0, so a run
    # against a directory with no catalogue exited clean having measured nothing.
    for need in ('ghidra_functions.csv', 'functions.csv'):
        p = os.path.join(_symbols_dir(a.root), need)
        if not os.path.isfile(p):
            print(f"progress: refusing -- cannot read {p}; unread is not zero", file=sys.stderr)
            return 3
    data = compute(a.root)
    # Every run, not one branch: a line that prints only under a flag is a line that is
    # absent from the run that needed it. stderr, because the default output is JSON.
    print(extent_line(a.root), file=sys.stderr)
    print(reach_line(a.root), file=sys.stderr)
    if a.burndown:
        print(burndown_line(data))
        return 0
    if a.status_line:
        print(status_sentence(data, False))
        return 0
    js = json.dumps(data, indent=2, sort_keys=True) + '\n'
    if a.out:
        with open(a.out, 'w') as f:
            f.write(js)
    if a.join:
        return evidence_join(a.root)
    if not (a.update_readme or a.check):
        if not a.out:
            sys.stdout.write(js)
        return 0

    bodies = {'status': render_status(data), 'progress': render_progress(data), 'target': render_target(a.root)}
    stale = []
    for name, blocks in (('README.md', bodies), ('STATUS.md', {'progress': bodies['progress']}),
                         ('CONTRIBUTING.md', {'status': bodies['status']})):
        path = os.path.join(a.root, name)
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            cur = f.read()
        blocks = {k: b for k, b in blocks.items() if (name == 'README.md' and k != 'status') or block_re(k).search(cur)}
        if not blocks:
            continue
        new = apply_blocks(cur, blocks)
        if new == cur:
            continue
        if a.update_readme:
            with open(path, 'w') as f:
                f.write(new)
            print(f'progress: {name} updated')
        else:
            stale.append(name)
    if stale:
        print(f"progress: generated block stale in {', '.join(stale)}; run tools/progress.py --update-readme",
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
