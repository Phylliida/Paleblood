"""Both denominators must print, and the arithmetic between them must hold.

PROGRESS (landed / branch-free) is what the leaf toolchain can address; SCOPE (landed / catalogued) is
how much of Ghidra's reach that is. One number was doing both jobs, which made closing a carried item
read as a stall. This test does not pin the counts -- rows land -- it pins the CONTRACT: both lines on
stderr in all three modes, stdout still a JSON document, and scope equal to landed/total recomputed.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
LINE = re.compile(r"^reach: (\d+) landed / (\d+) branch-free = ([\d.]+)% PROGRESS "
                  r"· (\d+) / (\d+) catalogued = ([\d.]+)% SCOPE", re.M)


class ReachLineTest(unittest.TestCase):
    def _run(self, *args):
        env = dict(os.environ, PYTHONPATH=str(REPO / "tools"))
        return subprocess.run([sys.executable, "-P", str(REPO / "tools" / "progress.py"), *args],
                              cwd=str(REPO), env=env, capture_output=True, text=True)

    def test_both_denominators_print_in_all_three_modes(self):
        for args in ((), ("--burndown",), ("--status",)):
            r = self._run(*args)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            m = LINE.search(r.stderr)
            self.assertIsNotNone(m, f"no reach line for args={args}: {r.stderr[-800:]}")
            landed, free, pct, landed2, total, scope = (int(m[1]), int(m[2]), float(m[3]),
                                                        int(m[4]), int(m[5]), float(m[6]))
            self.assertEqual(landed, landed2, "two landed counts on one line must be one number")
            self.assertAlmostEqual(scope, 100.0 * landed / total, places=2)
            self.assertLessEqual(pct, 100.0)
            self.assertNotIn("reach:", r.stdout, "prose in a machine document")

    def test_default_mode_stdout_is_still_json(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("edge_verified", json.loads(r.stdout))


if __name__ == "__main__":
    unittest.main()
