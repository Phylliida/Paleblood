#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Differential tester: original function vs replacement, same captured input.

Design: docs/VERIFY.md.

usage:
  verify.py run --function NAME --captures DIR [--elf EBOOT.elf] [--lib LIB.so] [--out DIR]
                [--patch FILE:NAME --env KEY=VALUE --option LABEL] [--record CASES]
  verify.py compare ORIGINAL.json REPLACEMENT.json
  verify.py --self-test

run: every case file in DIR (*.json) goes through tools/harness.py twice, once on the
original function and once on its replacement, each in its own process; the results are
written to OUT (default DIR/results) and compared. --elf defaults to $BB_ELF (then $BB_DATA_ROOT/elf/eboot.elf), --lib to
$BB_GAME_LIB or build/game/libbbgame.so.
--record CASES (recorded, edge or option-recorded) writes the run's counts to
symbols/verification.csv, with failing cases listed in symbols/quarantine.csv counted as
quarantined (tools/verification.py); --option LABEL names the option checked (needed with
--patch or --env when recording).

Exit codes: 0 all cases match, 1 mismatch, 3 bad input.
"""
from __future__ import annotations

import argparse
import copy
import csv
import glob
import json
import os
import re
import subprocess
import sys

import verification

SCHEMA = 1
RETURN_REGS = ('rax', 'rdx', 'xmm0', 'xmm1')
CALLEE_SAVED = ('rbx', 'rbp', 'rsp', 'r12', 'r13', 'r14', 'r15')
MAX_REPORTED = 8


class BadInput(Exception):
    pass



def default_elf() -> str | None:
    """$BB_DATA_ROOT/elf/eboot.elf (default ../data next to the repository), when it exists."""
    root = os.environ.get('BB_DATA_ROOT') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data')
    path = os.path.join(root, 'elf', 'eboot.elf')
    return path if os.path.isfile(path) else None

def split_addr(addr: str) -> tuple[str, int]:
    """'0x1234' -> ('', 0x1234); 'buf:out+0x4' -> ('buf:out', 4).

    The offset is read with base 0: the harness and runtime/include/runtime/recorder.hpp both
    write '0x'-prefixed hex, but a case written by an older recorder carried a bare decimal, and
    base 16 would read that 20 as 0x20. A leading zero is an error rather than a guess."""
    if addr.startswith('buf:'):
        name, _, off = addr.partition('+')
        return name, int(off, 0) if off else 0
    return '', int(addr, 16)


def byte_map(writes: list[dict]) -> dict[tuple[str, int], int]:
    """Final value of every byte written; a later write replaces an earlier one."""
    m: dict[tuple[str, int], int] = {}
    for w in writes:
        try:
            base, addr = split_addr(w['addr'])
            data = bytes.fromhex(w['bytes'])
        except (KeyError, ValueError) as e:
            raise BadInput(f'bad write record {w!r}') from e
        for i, b in enumerate(data):
            m[(base, addr + i)] = b
    return m


def compare_case(orig: dict, repl: dict, case: dict | None = None) -> list[str]:
    diffs: list[str] = []
    # A fault is a behaviour, so compare the two sides' faults against each other rather than
    # failing on any fault: a crash the original shares (an unguarded divide taking SIGFPE, say)
    # is agreement, while a fault on one side only -- or two different faults -- is not.
    #
    # A shared fault is not evidence, though. When both sides fault, nothing below this point runs:
    # the registers, writes and calls the case exists to compare are never looked at, so a
    # replacement that crashes in the same place for a different reason compares clean. That is
    # how a harness that segfaulted every case still reported 4/4 passed. So a shared fault has to
    # be declared by the case: `expected_fault` in the case file says "faulting here is the
    # behaviour", and the run reports it separately from a pass. Undeclared, it is a failure.
    of, rf = orig.get('fault'), repl.get('fault')
    if of != rf:
        for side, f in (('original', of), ('replacement', rf)):
            if f is not None:
                diffs.append(f'{side}: {f}')
    elif of is not None:
        declared = (case or {}).get('expected_fault')
        if declared is None:
            diffs.append(f'both sides faulted with {of}: the case does not declare expected_fault, '
                         'and a shared fault compares nothing the case sets up')
        elif str(declared) != str(of):
            diffs.append(f'both sides faulted with {of}, but the case declares expected_fault {declared}')
    for side, d in (('original', orig), ('replacement', repl)):
        trace = d.get('instruction_trace')
        if trace and (trace.get('skipped_host_calls') or trace.get('external_transitions') or
                      trace.get('import_observations')):
            diffs.append(f'{side}: untraced external execution; import boundary observations '
                         'do not establish instruction-memory or CFG coverage')
        if trace and not trace.get('complete', False):
            gaps = trace.get('gaps', [])
            if gaps:
                gap = gaps[0]
                diffs.append(
                    f'{side}: instruction trace incomplete at {gap.get("instruction", "unknown address")} '
                    f'{gap.get("mnemonic", "<unknown>")} '
                    f'[{gap.get("capability", "unknown capability")}]: '
                    f'{gap.get("reason", trace.get("stop_reason", "unsupported access class"))}')
            else:
                diffs.append(f'{side}: instruction trace incomplete: '
                             f'{trace.get("stop_reason", "unsupported access class")}')
        for e in d.get('errors', []):
            diffs.append(f'{side}: {e}')
    if of is not None or rf is not None:
        return diffs
    for group, regs in (('ret', RETURN_REGS), ('preserved', CALLEE_SAVED)):
        for r in regs:
            a = orig.get(group, {}).get(r)
            b = repl.get(group, {}).get(r)
            if a != b:
                diffs.append(f'{group}.{r}: original {a} replacement {b}')
    original_observed = set(orig.get('observed_registers', []))
    replacement_observed = set(repl.get('observed_registers', []))
    if original_observed != replacement_observed:
        diffs.append('registers: compared-register declarations differ')
    for reg in sorted(original_observed & replacement_observed):
        a = orig.get('registers', {}).get(reg)
        b = repl.get('registers', {}).get(reg)
        if a != b:
            diffs.append(f'registers.{reg}: original {a} replacement {b}')
    mo, mr = byte_map(orig.get('writes', [])), byte_map(repl.get('writes', []))
    bad = sorted(a for a in set(mo) | set(mr) if mo.get(a) != mr.get(a))
    for a in bad[:MAX_REPORTED]:
        o = f'{mo[a]:02x}' if a in mo else 'unwritten'
        r = f'{mr[a]:02x}' if a in mr else 'unwritten'
        diffs.append(f'memory {a[0]}+0x{a[1]:x}: original {o} replacement {r}')
    if len(bad) > MAX_REPORTED:
        diffs.append(f'memory: {len(bad) - MAX_REPORTED} more differing bytes')
    if orig.get('calls', []) != repl.get('calls', []):
        diffs.append('calls: external call sequence or arguments differ')
    original_accesses = orig.get('access_trace', [])
    replacement_accesses = repl.get('access_trace', [])
    if original_accesses != replacement_accesses:
        index = next((i for i, pair in enumerate(zip(original_accesses, replacement_accesses))
                      if pair[0] != pair[1]), min(len(original_accesses), len(replacement_accesses)))
        original_event = original_accesses[index] if index < len(original_accesses) else '<no event>'
        replacement_event = replacement_accesses[index] if index < len(replacement_accesses) else '<no event>'
        diffs.append(f'mediated memory access trace first difference at event {index}: '
                     f'original {original_event}; replacement {replacement_event}')
    if orig.get('redzone_writes', []) != repl.get('redzone_writes', []):
        diffs.append(f'buffer redzones: original {orig.get("redzone_writes", [])}; '
                     f'replacement {repl.get("redzone_writes", [])}')
    for side, result in (('original', orig), ('replacement', repl)):
        trace = result.get('instruction_trace')
        if trace:
            invalid = [event for event in trace.get('events', []) if not event.get('valid_region', False)]
            if invalid:
                diffs.append(f'{side}: instruction memory bounds violation at {invalid[0].get("instruction")} '
                             f'{invalid[0].get("access")} {invalid[0].get("address")}+{invalid[0].get("width")}')
    if bool(orig.get('instruction_trace')) != bool(repl.get('instruction_trace')):
        diffs.append('instruction memory trace is missing from one execution side')
    return diffs


def compare(orig: dict, repl: dict, cases: dict | None = None) -> dict:
    for name, d in (('original', orig), ('replacement', repl)):
        if d.get('schema') != SCHEMA or 'cases' not in d:
            raise BadInput(f'{name}: not a schema {SCHEMA} result file')
    if orig.get('address') != repl.get('address'):
        raise BadInput('results are for different addresses')
    oc = {c['id']: c for c in orig['cases']}
    rc = {c['id']: c for c in repl['cases']}
    failures = []
    diagnostics = []
    faults = []
    for cid in sorted(set(oc) | set(rc)):
        if cid not in oc or cid not in rc:
            failures.append({'case': cid, 'diffs': ['case missing from one side']})
            continue
        case = (cases or {}).get(cid)
        d = compare_case(oc[cid], rc[cid], case)
        if oc[cid].get('fault') is not None and oc[cid].get('fault') == rc[cid].get('fault'):
            faults.append({'case': cid, 'fault': oc[cid]['fault'],
                           'declared': (case or {}).get('expected_fault') == oc[cid]['fault'],
                           'compared': False})
        original_trace = oc[cid].get('instruction_trace')
        replacement_trace = rc[cid].get('instruction_trace')
        if original_trace or replacement_trace:
            oe = (original_trace or {}).get('events', [])
            re = (replacement_trace or {}).get('events', [])
            signature = lambda event: tuple(event.get(key) for key in
                                             ('access', 'region', 'region_offset', 'width', 'before', 'after'))
            first = next((index for index, (left, right) in enumerate(zip(oe, re))
                          if signature(left) != signature(right)), min(len(oe), len(re)))
            has_difference = first < max(len(oe), len(re))
            if has_difference:
                left = oe[first] if first < len(oe) else None
                right = re[first] if first < len(re) else None
                detail = {'classification': 'bounded_memory_trace_difference', 'event_index': first,
                          'observable_result_mismatch': bool(d), 'original': left, 'replacement': right,
                          'note': ('This is the earliest differing recorded memory event, not PC alignment. '
                                   'When final observable outputs match, it can represent an equivalent internal path.')}
            elif d:
                detail = {'classification': 'observable_mismatch_without_memory_trace_difference',
                          'observable_result_mismatch': True,
                          'compared_state_differences': d,
                          'note': 'The mismatch is in compared final state/calls; no earlier differing memory event was observed.'}
            else:
                detail = {'classification': 'no_observable_divergence', 'observable_result_mismatch': False,
                          'note': 'Final compared state agrees; differing instruction counts or PCs are not treated as failures.'}
            detail['trace_complete'] = bool(original_trace and replacement_trace and
                                             original_trace.get('complete') and replacement_trace.get('complete'))
            diagnostics.append({'case': cid, 'first_divergence': detail})
        if d:
            failures.append({'case': cid, 'diffs': d})
    n = len(set(oc) | set(rc))
    return {'schema': SCHEMA, 'address': orig.get('address'), 'cases': n,
            'passed': n - len(failures), 'failed': len(failures), 'failures': failures,
            'fault_agreement': faults,
            'instruction_diagnostics': diagnostics}


def falsification_report(original: dict, replacement: dict, cases: dict | None = None) -> dict:
    """Perturb the replacement and require the comparison to notice each perturbation.

    A comparison that passes everything is indistinguishable from one that checks nothing: a
    harness bug that made every case crash on both sides once reported 4/4 passed, because a
    matching fault was taken as agreement. Green is only worth something if the same machinery
    goes red on a real difference, so corrupt the replacement where the cases must be able to
    see it -- a return value, a written byte, a callee-saved register -- and require a failure
    for each. A perturbation nothing notices is a case set that could not have caught a mistake.

    Runs in-process on the two result files already written, so it costs no extra executions.
    """
    checks: list[dict] = []

    def first(mutated: dict, field: str):
        for cid in sorted(mutated):
            if mutated[cid].get(field):
                return cid, mutated[cid]
        return None, None

    def perturb(label, mutate):
        doc = copy.deepcopy(replacement)
        mutated = {c['id']: c for c in doc.get('cases', []) if isinstance(c.get('id'), str)}
        if not mutate(mutated):
            return
        summary = compare(original, doc, cases)
        checks.append({'perturbation': label, 'noticed': summary['failed'] > 0,
                       'failed': summary['failed']})

    def bump_ret(mutated):
        cid, c = first(mutated, 'ret')
        if c is None:
            return False
        reg = sorted(c['ret'])[0]
        try:
            c['ret'][reg] = f'0x{int(str(c["ret"][reg]), 0) + 1:x}'
        except ValueError:
            return False
        return True

    def flip_written_byte(mutated):
        cid, c = first(mutated, 'writes')
        if c is None or not c['writes'][0].get('bytes'):
            return False
        b = bytearray.fromhex(c['writes'][0]['bytes'])
        b[0] ^= 0x01
        c['writes'][0]['bytes'] = b.hex()
        return True

    def clobber_callee_saved(mutated):
        # preserved values are the verdict strings 'kept', not numbers: an int() here raised and
        # silently disabled this check for every function in the tree.
        cid, c = first(mutated, 'preserved')
        if c is None:
            return False
        reg = sorted(c['preserved'])[0]
        c['preserved'][reg] = 'clobbered'
        return True

    perturb('return value', bump_ret)
    perturb('written byte', flip_written_byte)
    perturb('callee-saved register', clobber_callee_saved)
    missed = [c['perturbation'] for c in checks if not c['noticed']]
    return {'checked': len(checks), 'noticed': len(checks) - len(missed), 'missed': missed,
            'checks': checks}


def case_expectations(captures: str) -> dict:
    """{id: case} for the cases in CAPTURES, so compare can see what a case declares about
    itself. Only `expected_fault` is read today; the whole file is kept so a later declaration
    does not have to thread a new argument through."""
    out = {}
    for path in sorted(glob.glob(os.path.join(captures, '*.json'))):
        if os.path.basename(path) == 'abi.json':
            continue
        with open(path) as f:
            case = json.load(f)
        if isinstance(case.get('id'), str):
            out[case['id']] = case
    return out


def load(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise BadInput(f'{path}: {e}') from e


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(ROOT, 'tools', 'harness.py')
CASE_TIMEOUT = 20


def lookup(name: str) -> tuple[str, str]:
    """(address, replacement symbol) of a function, from symbols/ and game/hooks.csv."""
    with open(os.path.join(ROOT, 'symbols', 'functions.csv'), newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['name'] == name]
    if not rows:
        raise BadInput(f'{name} is not in symbols/functions.csv')
    address = rows[0]['address']
    symbol = verification.replacement_symbol(ROOT, name, address)
    if not symbol:
        raise BadInput(f'{name} has no replacement in game/hooks.csv or symbols/install_mode.csv')
    return address, symbol


def run_side(boot: str, case: str, address: str, symbol: str | None, lib: str | None,
             timeout: int = CASE_TIMEOUT, trace_instructions: bool = False,
             trace_limit: int = 100_000) -> dict:
    cmd = [sys.executable, HARNESS, '--elf', boot, '--case', case, '--address', address]
    if symbol:
        cmd += ['--replacement', symbol, '--lib', lib]
    if trace_instructions:
        cmd += ['--trace-instructions', '--trace-instruction-limit', str(trace_limit)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'fault': f'timeout after {timeout} s'}
    if r.returncode == 3:
        raise BadInput(f'{os.path.basename(case)}: {r.stderr.strip()}')
    if r.returncode != 0:
        how = f'signal {-r.returncode}' if r.returncode < 0 else f'exit {r.returncode}'
        return {'fault': f'{how}: {r.stderr.strip()[-300:]}'}
    return json.loads(r.stdout)


def run_cases(boot: str, captures: str, address: str, symbol: str, lib: str,
              patch: str | None = None, env: dict | None = None, function: str | None = None,
              timeout: int = CASE_TIMEOUT, trace_instructions: bool = False,
              trace_limit: int = 100_000) -> dict:
    """Both sides of every case file in CAPTURES: {'original': [...], 'replacement': [...]}.
    One harness process per side maps the image once and forks per case."""
    cases = sorted(p for p in glob.glob(os.path.join(captures, '*.json')) if os.path.basename(p) != 'abi.json')
    if not cases:
        raise BadInput(f'no case files in {captures}')
    for path in cases:
        with open(path) as f:
            case = json.load(f)
        if case.get('address') != address:
            raise BadInput(f'{os.path.basename(path)} is for {case.get("address")}, not {address}')
        capture = case.get('capture')
        if capture is not None:
            if not isinstance(capture, dict):
                raise BadInput(f'{os.path.basename(path)} has invalid capture provenance')
            captured_function = capture.get('function')
            if not isinstance(captured_function, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,127}', captured_function) or captured_function in ('.', '..'):
                raise BadInput(f'{os.path.basename(path)} has invalid capture function')
            if function is not None and captured_function != function:
                raise BadInput(f'{os.path.basename(path)} records {capture.get("function")!r}, not {function!r}')
            run_id = capture.get('run_id')
            if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,63}', run_id) or run_id in ('.', '..'):
                raise BadInput(f'{os.path.basename(path)} has invalid capture run_id')
    results: dict[str, list] = {}
    for side, sym in (('original', None), ('replacement', symbol)):
        cmd = [sys.executable, HARNESS, '--elf', boot, '--cases', captures, '--address', address]
        side_env = None
        if sym:
            cmd += ['--replacement', sym, '--lib', lib]
            side_env = dict(os.environ, **(env or {}))
        if patch:
            # Both sides run on an image with a community patch applied (FILE:NAME): in the game an
            # option runs together with the patch, whose edits elsewhere (shared constants, other
            # functions) stay in place; its edits inside the replaced function never run.
            path, _, name = patch.partition(':')
            cmd += ['--patch', path, '--patch-name', name]
        cmd += ['--timeout', str(timeout)]
        if trace_instructions:
            cmd += ['--trace-instructions', '--trace-instruction-limit', str(trace_limit)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, env=side_env,
                               timeout=timeout * len(cases) + 30)
        except subprocess.TimeoutExpired as error:
            raise BadInput(f'{side}: total harness timeout exceeded') from error
        if r.returncode != 0:
            raise BadInput(f'{side}: {r.stderr.strip()[-400:]}')
        by_file = json.loads(r.stdout)
        # The file name is the case's identity: ids inside files can repeat across runs.
        results[side] = [by_file[k] for k in sorted(by_file)]
    return results


def run(name: str, captures: str, boot: str | None, lib: str | None, out: str | None,
        patch: str | None = None, env: list | None = None, record: str | None = None,
        option: str = '', timeout: int = CASE_TIMEOUT, trace_instructions: bool = False,
        trace_limit: int = 100_000, canary: bool = False) -> int:
    # A recorded row is evidence, so it may not come from a comparison that was never shown to be
    # able to fail: --record implies the canary.
    canary = canary or bool(record)
    boot = boot or os.environ.get('BB_ELF') or default_elf()
    lib = lib or os.environ.get('BB_GAME_LIB') or os.path.join(ROOT, 'build', 'game', 'libbbgame.so')
    if not boot or not os.path.isfile(boot):
        raise BadInput('no executable: pass --elf or set BB_ELF (your dump\'s eboot.elf, from tools/prepare_dump.sh)')
    if not os.path.isfile(lib):
        raise BadInput(f'no game library at {lib}: build the repository or pass --lib')
    address, symbol = lookup(name)
    extra = dict(e.split('=', 1) for e in (env or []))
    results = run_cases(boot, captures, address, symbol, lib, patch, extra, name, timeout,
                        trace_instructions, trace_limit)
    out = out or os.path.join(captures, 'results')
    os.makedirs(out, exist_ok=True)
    files = {}
    for side, cases_out in results.items():
        doc = {'schema': SCHEMA, 'address': address, 'function': name, 'cases': cases_out}
        files[side] = os.path.join(out, f'{side}.json')
        with open(files[side], 'w') as f:
            json.dump(doc, f, indent=1, sort_keys=True)
    original_doc, replacement_doc = load(files['original']), load(files['replacement'])
    expectations = case_expectations(captures)
    summary = compare(original_doc, replacement_doc, expectations)
    summary['function'] = name
    if canary:
        # Before trusting the green, require the same comparison to go red on a corrupted
        # replacement: green that cannot go red is not evidence.
        summary['falsification'] = falsification_report(original_doc, replacement_doc, expectations)
    if record:
        names = [os.path.basename(p)[:-len('.json')] for p in sorted(glob.glob(os.path.join(captures, '*.json')))
                 if os.path.basename(p) != 'abi.json']
        failing = [f['case'] for f in summary['failures']]
        row = verification.record(ROOT, name, record, option, names, failing, captures)
        summary['recorded'] = {k: row[k] for k in ('cases', 'option', 'failed', 'quarantined', 'source',
                                                  'cases_sha256')}
    print(json.dumps(summary, indent=2, sort_keys=True))
    if canary:
        falsification = summary['falsification']
        if falsification['missed'] or not falsification['checked']:
            print('verify: the comparison did not go red where it must: '
                  + (', '.join(falsification['missed']) if falsification['missed']
                     else 'no perturbation was applicable, so nothing was falsified'),
                  file=sys.stderr)
            return 1
    if record:
        # quarantined cases (listed with their reason) do not fail a recorded run
        return 1 if int(row['failed']) else 0
    return 1 if summary['failed'] else 0


def self_test() -> int:
    def case(cid, rax='0x1', writes=None, calls=None):
        return {'id': cid, 'ret': {'rax': rax}, 'preserved': {'rbx': '0x5'},
                'writes': writes or [], 'calls': calls or []}

    def res(*cases):
        return {'schema': SCHEMA, 'address': '0x00001000', 'cases': list(cases)}

    w1 = [{'addr': '0x100', 'bytes': '0102'}, {'addr': 'buf:out+0x0', 'bytes': '07'}]
    w1_split = [{'addr': '0x100', 'bytes': '01'}, {'addr': '0x101', 'bytes': '02'}, {'addr': 'buf:out+0x0', 'bytes': '07'}]
    w_over = [{'addr': '0x100', 'bytes': 'ff'}, {'addr': '0x100', 'bytes': '01'}, {'addr': '0x101', 'bytes': '02'},
              {'addr': 'buf:out', 'bytes': '07'}]
    ok = compare(res(case('a', writes=w1)), res(case('a', writes=w1_split)))
    ok2 = compare(res(case('a', writes=w1)), res(case('a', writes=w_over)))
    bad_ret = compare(res(case('a')), res(case('a', rax='0x2')))
    bad_mem = compare(res(case('a', writes=w1)), res(case('a', writes=[{'addr': '0x100', 'bytes': '0103'}])))
    bad_call = compare(res(case('a', calls=[{'target': '0x1', 'args': []}])), res(case('a')))
    missing = compare(res(case('a'), case('b')), res(case('a')))
    fault = compare(res(case('a')), res(dict(case('a'), fault='signal 11')))
    fault_both = compare(res(dict(case('a'), fault='signal 8')), res(dict(case('a'), fault='signal 8')))
    fault_declared = compare(res(dict(case('a'), fault='signal 8')), res(dict(case('a'), fault='signal 8')),
                             {'a': {'id': 'a', 'expected_fault': 'signal 8'}})
    fault_declared_wrong = compare(res(dict(case('a'), fault='signal 8')), res(dict(case('a'), fault='signal 8')),
                                   {'a': {'id': 'a', 'expected_fault': 'signal 11'}})
    fault_differs = compare(res(dict(case('a'), fault='signal 8')), res(dict(case('a'), fault='signal 11')))
    # A shared timeout is not agreement: nothing ran to completion on either side, so the case
    # compares nothing. It used to be a copy of fault_both under a misleading name.
    fault_timeout_shared = compare(res(dict(case('a'), fault='timeout after 30 s')),
                                   res(dict(case('a'), fault='timeout after 30 s')))
    checks = [ok['failed'] == 0, ok2['failed'] == 0, bad_ret['failed'] == 1,
              bad_mem['failed'] == 1, bad_call['failed'] == 1, missing['failed'] == 1,
              fault['failed'] == 1, fault_both['failed'] == 1,
              fault_declared['failed'] == 0, fault_declared['fault_agreement'][0]['declared'] is True,
              fault_both['fault_agreement'][0]['declared'] is False,
              fault_declared_wrong['failed'] == 1,
              fault_differs['failed'] == 1, fault_timeout_shared['failed'] == 1]
    if not all(checks):
        print(f'verify: self-test failed {checks}', file=sys.stderr)
        return 1
    print('verify: self-test ok')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--self-test', action='store_true')
    sub = ap.add_subparsers(dest='cmd')
    c = sub.add_parser('compare')
    c.add_argument('original')
    c.add_argument('replacement')
    r = sub.add_parser('run')
    r.add_argument('--function', required=True)
    r.add_argument('--captures', required=True)
    r.add_argument('--elf', dest='boot', help='the executable (eboot.elf); default $BB_ELF, then $BB_DATA_ROOT/elf/eboot.elf')
    r.add_argument('--lib')
    r.add_argument('--out')
    r.add_argument('--timeout', type=int, default=CASE_TIMEOUT, help='per case timeout in seconds')
    r.add_argument('--trace-instructions', action='store_true',
                   help='single-step guest memory operands (Linux x86-64, Capstone 5 required)')
    r.add_argument('--trace-instruction-limit', type=int, default=100_000,
                   help='bounded single-step instruction limit per fixture')
    r.add_argument('--patch', metavar='FILE:NAME',
                   help='run both sides on an image with this community patch applied (checks an option against it)')
    r.add_argument('--canary', action='store_true',
                   help='perturb the replacement and require the comparison to fail, so a run that '
                        'passes everything cannot be a run that checks nothing')
    r.add_argument('--env', action='append', metavar='KEY=VALUE', help='environment for the replacement side')
    r.add_argument('--record', choices=verification.CASE_SETS,
                   help='write the counts to symbols/verification.csv as this case set')
    r.add_argument('--option', default='', help='the option this run checks, for --record (e.g. 30, uncapped)')
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if a.cmd == 'compare':
        try:
            out = compare(load(a.original), load(a.replacement))
        except BadInput as e:
            print(f'verify: {e}', file=sys.stderr)
            return 3
        print(json.dumps(out, indent=2, sort_keys=True))
        return 1 if out['failed'] else 0
    if a.cmd == 'run':
        try:
            if a.record and (a.patch or a.env) and not a.option:
                raise BadInput('--record with --patch or --env needs --option LABEL')
            if a.timeout < 1 or a.timeout > 3600:
                raise BadInput('--timeout must be between 1 and 3600 seconds')
            if a.trace_instruction_limit < 1 or a.trace_instruction_limit > 10_000_000:
                raise BadInput('--trace-instruction-limit must be between 1 and 10000000')
            return run(a.function, a.captures, a.boot, a.lib, a.out, a.patch, a.env, a.record,
                       a.option, a.timeout, a.trace_instructions, a.trace_instruction_limit, a.canary)
        except (BadInput, OSError, json.JSONDecodeError) as e:
            print(f'verify: {e}', file=sys.stderr)
            return 3
    ap.print_help()
    return 3


if __name__ == '__main__':
    sys.exit(main())
