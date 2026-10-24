import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import board  # noqa: E402


class Board(unittest.TestCase):
    def test_the_committed_board_is_what_the_artifacts_say(self):
        """The board is generated, so a sentence that disagrees with the tree is red.

        Named failure: the first differing line, with both sides -- a diff is the claim.
        """
        path = os.path.join(ROOT, 'docs', 'board.md')
        self.assertTrue(os.path.exists(path), 'docs/board.md missing; run tools/board.py --write')
        with open(path) as fh:
            committed = fh.read()
        fresh = board.render()
        a, b = committed.splitlines(), fresh.splitlines()
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else '<absent>'
            y = b[i] if i < len(b) else '<absent>'
            if x != y:
                self.fail(f'line {i + 1} differs\n  committed: {x}\n  artifacts: {y}')

    def test_the_board_tool_runs_bare(self):
        # Bare means bare: an inherited relative PYTHONPATH resolves against cwd, which puts /tmp on
        # sys.path, where a stray bisect.py shadowed the stdlib and broke `import progress`. A test
        # that claims to run without environment help must not quietly supply some.
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'BB_PBBOOT', 'BB_LOADER')}
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'board.py')],
                           cwd='/tmp', capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('not sourced', r.stdout)

    def test_the_frontier_advertises_nothing_it_should_not(self):
        """The defect this tool was built to keep dead: a body in the ledger or retired.csv, offered again."""
        rendered = board.render()
        line = next(ln for ln in rendered.splitlines() if 'frontier n bodied' in ln)
        self.assertIn('**0**', line, line)
        # retired is a separate class, printed as an open defect until the frontier is regenerated
        retired = next(ln for ln in rendered.splitlines() if 'frontier n retired' in ln)
        self.assertTrue('**0**' in retired or 'OPEN DEFECT' in retired, retired)


if __name__ == '__main__':
    unittest.main()

class PlantedControl(unittest.TestCase):
    """A branch that has stopped firing and a branch that cannot fire look identical from outside."""

    def test_a_retired_address_advertised_as_a_candidate_reads_open_defect(self):
        import tempfile
        import board
        with tempfile.TemporaryDirectory() as d:
            sym = os.path.join(d, 'symbols')
            os.makedirs(sym)
            def put(name, text):
                with open(os.path.join(sym, name), 'w') as fh:
                    fh.write(text)
            put('functions.csv', 'address,size,name,system,status,notes\n'
                                 '0x024264d0,34,x,game,original,\n')
            put('retired.csv', 'address,reason,date,revisit\n0x024264d0,why,2026-10-23,never\n')
            put('leaf_frontier.csv', 'address,size,class\n0x024264d0,34,addressable\n')
            put('ghidra_functions.csv', 'address,size\n0x024264d0,34\n')
            for name, head in (('verification.csv', 'function,cases\n'),
                               ('reviews.csv', 'address,name\n'),
                               ('quarantine.csv', 'function,cases\n')):
                put(name, head)
            text = board.render(d)
        self.assertIn('OPEN DEFECT', text)
        self.assertIn('0x24264d0', text)
        # and the override is restored: the real tree still renders its real board
        self.assertNotIn('OPEN DEFECT', board.render())
