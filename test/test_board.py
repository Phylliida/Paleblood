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
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'board.py')],
                           cwd='/tmp', capture_output=True, text=True)
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
