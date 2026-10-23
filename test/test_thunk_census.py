"""symbols/thunks.csv is a gate, not a file: regenerate it and diff against the committed copy.

The capture_ok.csv pattern -- the tool writes its own output by redirection and this test compares,
so a selector's predicate changing without the artifact changing (or the reverse) is red here rather
than silent. No --write flag anywhere: a tool that can rewrite the file it is checked against is a
tool that can pass its own test.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


class ThunkCensusTest(unittest.TestCase):
    def test_committed_thunks_csv_reproduces(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "thunks.csv")
            env = dict(os.environ, PYTHONPATH=str(REPO / "tools"))
            r = subprocess.run([sys.executable, "-P", str(REPO / "tools" / "thunk_census.py"),
                                "--max", "13", "--out", out],
                               cwd=str(REPO), env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-3000:])
            self.assertIn("LANDABLE AND MISSED (no selector refuses them): 0", r.stdout,
                          "a row in the band is landable and was missed -- that is the finding, "
                          "not a flake: read the stdout above")
            got = pathlib.Path(out).read_text()
            want = (REPO / "symbols" / "thunks.csv").read_text()
            self.assertEqual(want, got,
                             "symbols/thunks.csv is stale: regenerate with "
                             "tools/thunk_census.py --max 13 --out symbols/thunks.csv")


if __name__ == "__main__":
    unittest.main()
