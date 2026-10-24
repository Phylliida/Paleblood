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
        lines = [l for l in (REPO / "symbols" / "leaf_frontier.csv").read_text().splitlines() if l]
        self.assertEqual(lines[0], "address,size,class",
                         "the frontier must declare its columns: without a header every DictReader "
                         "over it eats the first data row and reports a population short by one")
        rows = [line.split(",") for line in lines[1:]]
        self.assertTrue(rows, "an empty worklist with a nonempty branch-free unlanded population "
                              "would read as success")
        for addr, size, bandname in rows:
            b, landed = band[int(addr, 16)]
            self.assertEqual(landed, "False", f"{addr} is on the worklist and already landed")
            self.assertEqual(b, "0", f"{addr} contains a branch and no leaf selector may take it")
            self.assertIn(bandname, ("short", "addressable"))
            self.assertEqual(bandname, "short" if int(size) < 14 else "addressable")


    def test_band_has_body_count_matches_the_catalogue(self):
        """THE ONE FRESHNESS CHECK THAT CAN WORK, and `landed` could not have been it.

        `landed` means "status is not original", so a landing to `original` moves the catalogue and not the
        column -- which is why a stale band looked fresh for a whole slice. `has_body` must move on EVERY
        landing, so a band built before one disagrees with functions.csv by exactly the rows since. The two
        counts also agree with the trio total by a different route, which makes 38,101 double-sourced.
        """
        import csv as _csv, gzip as _gzip, pathlib as _p, catalogue as C
        ROOT = _p.Path(__file__).resolve().parent.parent
        with _gzip.open(ROOT / 'symbols/branch_band.csv.gz', 'rt', newline='') as f:
            has_body = sum(1 for r in _csv.DictReader(f) if r['has_body'] == 'True')
        bodies = len({r['address'] for r in C.read_rows(str(ROOT / 'symbols/functions.csv'))})
        self.assertEqual(has_body, bodies, f'band says {has_body} bodies, the catalogue has {bodies} -- '
                         'regenerate symbols/branch_band.csv.gz with tools/branch_census.py')

    def test_no_advertised_row_has_a_body(self):
        import csv as _csv, gzip as _gzip, pathlib as _p, catalogue as C
        ROOT = _p.Path(__file__).resolve().parent.parent
        with _gzip.open(ROOT / 'symbols/branch_band.csv.gz', 'rt', newline='') as f:
            marks = {int(r['address'], 16): r['has_body'] for r in _csv.DictReader(f)}
        with open(ROOT / 'symbols/leaf_frontier.csv', newline='') as f:
            adv = {int(r['address'], 16) for r in _csv.DictReader(f)}
        bodies = {r['address'] for r in C.read_rows(str(ROOT / 'symbols/functions.csv'))}
        self.assertEqual(adv & bodies, set(), 'the frontier advertises rows that already have a body')
        self.assertFalse([hex(a) for a in adv if marks.get(a) == 'True'])


if __name__ == "__main__":
    unittest.main()
