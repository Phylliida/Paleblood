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
import tempfile
import unittest
from unittest import mock

import install_mode

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
    # AN INDEX, NOT A SCAN. This was `any(r['address'] == addr and r['mode'] == 'host' for r in install)`
    # inside a loop over every landed function: 38k rows x |install_mode| Python comparisons, which is
    # defining_files one tier down -- a per-row search that belongs in a per-process index. The predicate is
    # unchanged; it is simply answered once instead of 38,096 times.
    host_addrs = {r['address'] for r in install if r['mode'] == 'host'}
    for row in functions:
        addr = row['address']
        if row['status'] == 'original':
            continue
        if addr not in hook_addrs and addr not in host_addrs:
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


class TestOneReader(unittest.TestCase):
    def test_host_addresses_and_replacement_for_agree(self):
        rows = install_mode.rows(ROOT)
        host = next(r for r in rows if r['mode'] == 'host')
        name = next(r['name'] for r in _rows(FUNCTIONS) if int(r['address'], 16) == host['address'])
        self.assertIn(host['address'], install_mode.host_addresses(ROOT))
        self.assertEqual(install_mode.replacement_for(ROOT, name, host['address']), 'bb_' + name)

    def test_absent_table_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(install_mode.host_addresses(d), frozenset())
            self.assertIsNone(install_mode.replacement_for(d, 'x', '0x1'))


class TestAppendHost(unittest.TestCase):
    def test_absent_table_is_created_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            n = install_mode.append_host(d, ['0x20', 0x10])
            self.assertEqual(n, 2)
            self.assertEqual(symbols.joinpath('install_mode.csv').read_text(),
                             'address,mode\n0x00000010,host\n0x00000020,host\n')

    def test_existing_host_rows_are_skipped_not_duplicated(self):
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            symbols.joinpath('install_mode.csv').write_text(
                'address,mode\n0x00000010,host\n')
            self.assertEqual(install_mode.append_host(d, [0x10, 0x20]), 1)
            self.assertEqual([r['address'] for r in install_mode.rows(d)], [0x10, 0x20])

    def test_the_committed_table_has_the_header_the_writer_owns(self):
        # The writer's shape is not a fixture's shape. `address,mode` is what the committed file
        # carries; if a third column is added, this test is where the writer learns about it.
        with open(INSTALL_MODE, newline='') as f:
            self.assertEqual(next(csv.reader(f)), ['address', 'mode'])

    def test_extra_columns_survive_an_append(self):
        # The table is the module's shape, not `address,mode`'s: a third column it did not know
        # about used to be silently dropped by every writer.
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            symbols.joinpath('install_mode.csv').write_text(
                'address,mode,origin\n0x00000010,host,generated\n')
            self.assertEqual(install_mode.append_host(d, [0x20]), 1)
            text = symbols.joinpath('install_mode.csv').read_text()
            self.assertIn('address,mode,origin\n', text)
            self.assertIn('0x00000010,host,generated\n', text)
            self.assertIn('0x00000020,host,\n', text)

    def test_sort_host_orders_without_changing_columns(self):
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            symbols.joinpath('install_mode.csv').write_text(
                'address,mode,origin\n0x00000020,host,b\n0x00000010,hook,a\n')
            self.assertEqual(install_mode.sort_host(d), 2)
            text = symbols.joinpath('install_mode.csv').read_text()
            self.assertEqual(text, 'address,mode,origin\n0x00000010,hook,a\n0x00000020,host,b\n')

    def test_require_absent_refuses_a_present_address(self):
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            path = symbols / 'install_mode.csv'
            before = 'address,mode\n0x00000010,hook\n'
            path.write_text(before)
            with self.assertRaises(SystemExit) as e:
                install_mode.require_absent(d, [0x20, 0x10])
            self.assertIn('already present', str(e.exception))
            self.assertIn('0x00000010', str(e.exception))
            self.assertEqual(path.read_text(), before, 'a presence check writes nothing')
            install_mode.require_absent(d, [0x20])

    def test_sort_host_does_not_rewrite_a_sorted_table(self):
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            symbols.joinpath('install_mode.csv').write_text(
                'address,mode\n0x00000010,hook\n0x00000020,host\n')
            with mock.patch.object(install_mode, '_write_rows') as w:
                self.assertEqual(install_mode.sort_host(d), 2)
                w.assert_not_called()

    def test_a_conflicting_mode_refuses_and_leaves_the_file_alone(self):
        with tempfile.TemporaryDirectory() as d:
            symbols = pathlib.Path(d) / 'symbols'
            symbols.mkdir()
            path = symbols / 'install_mode.csv'
            before = 'address,mode\n0x00000010,hook\n'
            path.write_text(before)
            with self.assertRaises(SystemExit) as e:
                install_mode.append_host(d, [0x10])
            self.assertIn('refusing to write it as host', str(e.exception))
            self.assertEqual(path.read_text(), before)


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
