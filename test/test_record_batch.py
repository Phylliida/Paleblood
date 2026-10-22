"""`record_many` must produce the file `record` produces, or it is a second writer with a second opinion."""

import csv
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import verification as V  # noqa: E402


def a_row(name, cases="edge", option="", total=2):
    return {"function": name, "cases": cases, "option": option, "total": str(total),
            "passed": str(total), "failed": "0", "quarantined": "0", "source": "s", "cases_sha256": "h",
            "date": "2026-10-22"}


class BatchEqualsSequential(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, "symbols"))
        self.path = os.path.join(self.dir, "symbols", "verification.csv")
        V.write_csv(self.path, V.VERIFICATION_HEADER, [a_row("0x01"), a_row("0x03")])

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_with(self, rows, batched):
        with mock.patch.object(V, "_head_or_refuse", lambda root: "deadbeef"):
            if batched:
                V.record_many(self.dir, rows)
            else:
                for r in rows:
                    V._append_rows(self.dir, [r])
        with open(self.path) as fh:
            return fh.read()

    def test_two_rows_identical_either_way(self):
        rows = [a_row("0x02", cases="edge"), a_row("0x03", cases="option-recorded", option="cpu")]
        sequential = self.run_with(rows, batched=False)
        shutil.copy2(self.path + ".pre", self.path)      # reset the ledger, keep nothing of the first pass
        os.unlink(self.path + ".pre")
        batched = self.run_with(rows, batched=True)
        self.assertEqual(sequential, batched)
        self.assertIn("0x02", batched)
        self.assertIn("option-recorded", batched)

    def test_batch_rejects_an_unknown_case_set(self):
        with self.assertRaises(ValueError):
            V.record_many(self.dir, [a_row("0x04", cases="not-a-set")])


if __name__ == "__main__":
    unittest.main()
