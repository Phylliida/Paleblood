"""symbols/leaf_frontier.csv is the leaf campaign's whole remaining worklist: regenerate and diff.

Two invariants beyond the diff, because a stale frontier and a wrong frontier look identical:
no frontier row may be landed, and no frontier row may contain a branch -- in the artifact that
defines both facts (symbols/branch_band.csv.gz), not in this file's own opinion.
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]

import catalogue as C  # noqa: E402 -- PYTHONPATH is the runner's; this file is discovery-shaped


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
        band = {r["address"]: (r["branch"], r["landed"])
                for r in C.read_rows(REPO / "symbols" / "branch_band.csv.gz")}
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



    # THE TWO TESTS BELOW TAKE ~1.1 s; `test_committed_frontier_reproduces` above takes ~87 s, and the 80x is
    # not redundancy to be tidied. They answer different questions: these ask "do the two artifacts agree?"
    # (consistency), that one asks "does the deriver produce what the artifact should contain?" (correctness).
    # A stale band and a wrong frontier both make the cheap tests red; a broken deriver whose artifact was
    # regenerated to match makes them GREEN and only the slow one red. Keep both -- a suite shortened by
    # deleting the expensive half deletes the only check on the predicate that produced the frontier.
    def test_band_has_body_count_matches_the_catalogue(self):
        """THE ONE FRESHNESS CHECK THAT CAN WORK, and `landed` could not have been it.

        `landed` means "status is not original", so a landing to `original` moves the catalogue and not the
        column -- which is why a stale band looked fresh for a whole slice. `has_body` must move on EVERY
        landing, so a band built before one disagrees with functions.csv by exactly the rows since. The two
        counts also agree with the trio total by a different route, which makes 38,101 double-sourced.
        """
        import pathlib as _p
        ROOT = _p.Path(__file__).resolve().parent.parent
        has_body = sum(1 for r in C.read_rows(ROOT / 'symbols/branch_band.csv.gz')
                       if r['has_body'] == 'True')
        bodies = len({r['address'] for r in C.read_rows(str(ROOT / 'symbols/functions.csv'))})
        self.assertEqual(has_body, bodies, f'band says {has_body} bodies, the catalogue has {bodies} -- '
                         'regenerate symbols/branch_band.csv.gz with tools/branch_census.py')

    def test_no_advertised_row_has_a_body(self):
        import pathlib as _p
        ROOT = _p.Path(__file__).resolve().parent.parent
        marks = {r['address']: r['has_body'] for r in C.read_rows(ROOT / 'symbols/branch_band.csv.gz')}
        adv = {r['address'] for r in C.read_rows(ROOT / 'symbols/leaf_frontier.csv')}
        bodies = {r['address'] for r in C.read_rows(str(ROOT / 'symbols/functions.csv'))}
        self.assertEqual(adv & bodies, set(), 'the frontier advertises rows that already have a body')
        self.assertFalse([hex(a) for a in adv if marks.get(a) == 'True'])


if __name__ == "__main__":
    unittest.main()
