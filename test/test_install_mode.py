"""A non-original ledger row must say how it is installed, and absence must refuse.

Pool B bodies are shorter than the 14-byte absolute jump a hook needs (`QUIRKS.md`), so they can
be verified by the differential - which calls the replacement as a host symbol - while never being
installable in the running game. `validate_functions.py` has required a `game/hooks.csv` row for
every non-original row, which recorded a fact verification never depended on and made those bodies
unrepresentable.

This is the gate. It is deliberately a separate file rather than an edit to the validator, so it
can be proven by counterexample before anything depends on it, and wired in afterwards by one call.
Two ways to satisfy a non-original row - a hooks row, or `symbols/install_mode.csv` saying `host` -
and nothing else. Absence refuses: a forgotten blank is indistinguishable from a refusal, which is
the property that keeps this fail-closed.
"""

import csv
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYMBOLS = ROOT / 'symbols'
FUNCTIONS = SYMBOLS / 'functions.csv'
INSTALL_MODE = SYMBOLS / 'install_mode.csv'
HOOKS = ROOT / 'game' / 'hooks.csv'
MODES = {'hook', 'host'}


def _rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def violations(functions, hooks, install):
    """Every way the installation record can disagree with the ledger."""
    errs = []
    hook_addrs = {r['address'] for r in hooks}
    func_addrs = {r['address'] for r in functions}
    seen = set()
    for row in install:
        addr, mode = row['address'], row['mode']
        if addr in seen:
            errs.append(f'install_mode.csv: {addr} appears twice')
        seen.add(addr)
        if mode not in MODES:
            errs.append(f'install_mode.csv: {addr} has mode {mode!r}, not one of {sorted(MODES)}')
        if addr not in func_addrs:
            errs.append(f'install_mode.csv: {addr} is not in functions.csv')
        if mode == 'hook':
            return_ = 'hook mode but no game/hooks.csv entry'
            if addr not in hook_addrs:
                errs.append(f'install_mode.csv: {addr} is {return_}')
    for row in functions:
        addr = row['address']
        if row['status'] == 'original':
            continue
        if addr not in hook_addrs and not any(r['address'] == addr and r['mode'] == 'host'
                                              for r in install):
            errs.append(f'functions.csv: {row["name"]} is {row["status"]} with neither a '
                        f'game/hooks.csv entry nor an install_mode row saying host')
    return errs


def burndown_lines(functions, hooks, install):
    """Three lines, and only the first two may carry a number.

    `observed executing in game` is a constant nothing can contradict until the runtime keeps a
    hook-entry counter, so it prints as unknown rather than as a zero someone forgets to move.
    """
    hook_addrs = {r['address'] for r in hooks}
    host = {r['address'] for r in install if r['mode'] == 'host'}
    replaced = [r for r in functions if r['status'] != 'original']
    n_hook = sum(1 for r in replaced if r['address'] in hook_addrs and r['address'] not in host)
    return (f'hook-registered {n_hook:,}   host-only {len(replaced) - n_hook:,}',
            'observed executing in game: unknown (no runtime witness)')


class TestInstallMode(unittest.TestCase):
    def test_tree_is_consistent(self):
        self.assertEqual(violations(_rows(FUNCTIONS), _rows(HOOKS), _rows(INSTALL_MODE)), [])

    def test_absent_installation_record_refuses(self):
        """The counterexample: drop a record and the gate must name the row."""
        funcs = [dict(r) for r in _rows(FUNCTIONS)]
        hooks = _rows(HOOKS)
        # The baseline must be the real tree, install rows included: a host-only
        # member is consistent, and an empty install table stopped describing it
        # the moment the first one landed.
        install = _rows(INSTALL_MODE)
        hooked = {h['address'] for h in hooks}
        target = next(r for r in funcs
                      if r['status'] != 'original' and r['address'] in hooked)
        self.assertEqual(violations(funcs, hooks, install), [])
        del_hook = [h for h in hooks if h['address'] != target['address']]
        errs = violations(funcs, del_hook, install)
        # TWO errors, and that is the correct number now that the tables carry a real population: the same
        # disagreement is reported from each side -- install_mode.csv says "hook with no hooks entry", and
        # functions.csv says "neither a hooks entry nor a host row". Asserting one would have encoded the
        # empty-table era; the pair is the cross-check, and both must name the site.
        self.assertEqual(len(errs), 2, errs)
        self.assertTrue(any('install_mode.csv' in e and 'hook mode but no' in e for e in errs), errs)
        self.assertTrue(any('neither' in e for e in errs), errs)
        for e in errs:
            self.assertIn(target['name'] if 'functions.csv' in e else target['address'], e)

    def test_host_row_needs_an_ledger_row(self):
        funcs = _rows(FUNCTIONS)
        hooks = _rows(HOOKS)
        errs = violations(funcs, hooks, [{'address': '0xdeadbeef', 'mode': 'host'}])
        self.assertIn('is not in functions.csv', ' '.join(errs))

    def test_hook_mode_without_hook_row_refuses(self):
        funcs = _rows(FUNCTIONS)
        addr = next(r['address'] for r in funcs if r['status'] != 'original')
        hooks = [h for h in _rows(HOOKS) if h['address'] != addr]
        errs = violations(funcs, hooks, [{'address': addr, 'mode': 'hook'}])
        self.assertTrue(any('no game/hooks.csv entry' in e for e in errs), errs)

    def test_burndown_does_not_print_a_constant_as_a_measurement(self):
        line, observed = burndown_lines(_rows(FUNCTIONS), _rows(HOOKS), _rows(INSTALL_MODE))
        self.assertIn('hook-registered', line)
        self.assertIn('host-only', line)
        self.assertNotIn('0', observed.split(':')[1].replace('unknown', ''))


if __name__ == '__main__':
    unittest.main()
