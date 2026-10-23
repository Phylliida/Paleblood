"""symbols/leaf_frontier.csv is the leaf campaign's whole remaining worklist: regenerate and diff.

Two invariants beyond the diff, because a stale frontier and a wrong frontier look identical:
no frontier row may be landed, and no frontier row may contain a branch -- in the artifact that
defines both facts (symbols/branch_band.csv.gz), not in this file's own opinion.
"""
import csv
import gzip
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


class LeafFrontierTest(unittest.TestCase):
    def test_committed_frontier_reproduces(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "frontier.csv")
            env = dict(os.environ, PYTHONPATH=str(REPO / "tools"))
            r = subprocess.run([sys.executable, "-P", str(REPO / "tools" / "leaf_frontier.py"),
                                "--out", out], cwd=str(REPO), env=env, capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-3000:])
            got = pathlib.Path(out).read_text()
            want = (REPO / "symbols" / "leaf_frontier.csv").read_text()
            self.assertEqual(want, got, "symbols/leaf_frontier.csv is stale: regenerate with "
                             "tools/leaf_frontier.py --out symbols/leaf_frontier.csv")

    def test_frontier_rows_are_unlanded_and_branch_free(self):
        with gzip.open(REPO / "symbols" / "branch_band.csv.gz", "rt", newline="") as f:
            band = {int(r["address"], 16): (r["branch"], r["landed"]) for r in csv.DictReader(f)}
        rows = [line.split(",") for line in
                (REPO / "symbols" / "leaf_frontier.csv").read_text().splitlines()]
        self.assertTrue(rows, "an empty worklist with a nonempty branch-free unlanded population "
                              "would read as success")
        for addr, size, bandname in rows:
            b, landed = band[int(addr, 16)]
            self.assertEqual(landed, "False", f"{addr} is on the worklist and already landed")
            self.assertEqual(b, "0", f"{addr} contains a branch and no leaf selector may take it")
            self.assertIn(bandname, ("short", "addressable"))
            self.assertEqual(bandname, "short" if int(size) < 14 else "addressable")


if __name__ == "__main__":
    unittest.main()
