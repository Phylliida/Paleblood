"""One shape approval must cash out into per-function rows before the real one arrives.

Tested against a synthetic approval in a throwaway root, and refused in three ways: no answer in the
owner's file, a member set that moved since the review, and a member with nothing to pin. The refusals
run through the real code paths, not through a copy of them.
"""

import contextlib
import csv
import io
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import shape_approval as SA  # noqa: E402
from validate_functions import REVIEW_HEADER, check_reviews  # noqa: E402

# Synthetic addresses, not game addresses: check_agnostic flags a test that hard-codes a value from
# symbols/*.csv, and a fixture that names real functions expires with the catalogue it borrowed from.
MEMBERS = [("0x00e01000", "5", "leaf_demo_00e01000"), ("0x00e01100", "8", "leaf_demo_00e01100"),
           ("0x00e01200", "5", "leaf_demo_00e01200")]


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


class ShapeApprovalCascade(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        for sub in ("symbols", "docs"):
            os.makedirs(os.path.join(self.root, sub))
        write_csv(os.path.join(self.root, "symbols", "functions.csv"),
                  ["address", "size", "name", "system", "status", "notes"],
                  [[a, s, n, "leaf", "edge-verified", ""] for a, s, n in MEMBERS])
        write_csv(os.path.join(self.root, "symbols", "verification.csv"),
                  ["function", "cases", "option", "total", "passed", "failed", "quarantined", "source",
                   "cases_sha256", "date"],
                  [[n, "edge", "", "5", "5", "0", "0", "src", "cases", "2026-10-22"] for _, _, n in MEMBERS])
        self.members_hash = SA.member_set_hash(
            [{"address": a, "size": s, "name": n, "system": "leaf", "status": "edge-verified", "notes": ""}
             for a, s, n in MEMBERS])
        self.shape_row = ["0x00000000", "leaf_demo", "2026-10-22", "independent session", "approved", "shape",
                          "unavailable", "unavailable", "members=%s" % self.members_hash]
        self.write_reviews([self.shape_row])
        self.answer("2026-10-22 scope=shape")

    def tearDown(self):
        shutil.rmtree(self.root)

    def write_reviews(self, rows):
        write_csv(os.path.join(self.root, "symbols", "reviews.csv"), REVIEW_HEADER, rows)

    def answer(self, text):
        with open(os.path.join(self.root, "docs", "approval-answers.md"), "w") as f:
            f.write("# Answers\n\n%s\n" % text)

    def reviews(self):
        with open(os.path.join(self.root, "symbols", "reviews.csv"), newline="") as f:
            return list(csv.DictReader(f))

    def cascade(self, apply=True):
        with mock.patch.object(SA.verification, "source_hash", lambda root, name: "SRC:" + name), \
             mock.patch.object(SA.verification, "evidence_hash", lambda root, name: "EVD:" + name):
            return SA.cascade(self.root, apply=apply)

    def test_one_shape_row_becomes_one_row_per_member(self):
        self.assertEqual(self.cascade(), 0)
        rows = [r for r in self.reviews() if r["scope"] == "function"]
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertTrue(r["reviewer"].startswith("derived from shape approval"))
            self.assertEqual(r["source_hash"], "SRC:" + r["name"])
            self.assertEqual(r["cases_sha256"], "EVD:" + r["name"])
            self.assertIn("scope=shape members=%s" % self.members_hash, r["notes"])
        self.assertEqual([r["address"] for r in rows], sorted((a for a, _, _ in MEMBERS), key=lambda x: int(x, 16)))

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.cascade(apply=False), 0)
        self.assertEqual(len(self.reviews()), 1)

    def test_the_write_message_names_the_path_it_wrote(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.cascade(apply=True), 0)
        self.assertIn(os.path.join(self.root, "symbols", "reviews.csv"), out.getvalue())

    def test_refused_without_the_owners_answer(self):
        self.answer("nothing decided yet")
        self.assertEqual(self.cascade(), 1)
        self.assertEqual(len(self.reviews()), 1)

    def test_refused_when_the_member_set_moved(self):
        row = list(self.shape_row)
        row[8] = "members=deadbeefdeadbeef"
        self.write_reviews([row])
        self.assertEqual(self.cascade(), 1)
        self.assertEqual(len(self.reviews()), 1)

    def test_refused_when_a_member_has_nothing_to_pin(self):
        with mock.patch.object(SA.verification, "source_hash", lambda root, name: ""), \
             mock.patch.object(SA.verification, "evidence_hash", lambda root, name: "EVD:" + name):
            self.assertEqual(SA.cascade(self.root, apply=True), 1)
        self.assertEqual(len(self.reviews()), 1)

    def test_the_validator_refuses_a_shape_row_the_owner_never_allowed(self):
        funcs = [{"address": a, "size": s, "name": n, "system": "leaf", "status": "edge-verified", "notes": ""}
                 for a, s, n in MEMBERS]
        self.answer("nothing decided yet")
        errs = check_reviews(self.root, funcs)
        self.assertTrue(any("a shape review is only meaningful once the user has answered" in e for e in errs), errs)
        self.answer("2026-10-22 scope=shape")
        errs = check_reviews(self.root, funcs)
        self.assertFalse([e for e in errs if "shape review is only meaningful" in e], errs)

    def test_an_unknown_scope_is_refused(self):
        row = list(self.shape_row)
        row[5] = "family"
        self.write_reviews([row])
        funcs = [{"address": a, "size": s, "name": n, "system": "leaf", "status": "edge-verified", "notes": ""}
                 for a, s, n in MEMBERS]
        self.assertTrue(any("scope must be one of function, shape" in e for e in check_reviews(self.root, funcs)))

    def test_a_blank_scope_means_function(self):
        row = list(self.shape_row)
        row[5] = ""
        self.write_reviews([row])
        funcs = []
        self.assertFalse([e for e in check_reviews(self.root, funcs) if "scope" in e])


if __name__ == "__main__":
    unittest.main()
