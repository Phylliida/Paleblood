"""The chain family's population, pinned against numbers written before any case existed.

These tests import the tool rather than a copy of its predicate, so a change to
`leaf_shape_census.shape_of` reaches them. What they assert is the PRE-REGISTRATION: if any of these
move, the family is a different family and the batch must be re-registered, not re-run.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PY = str(Path(sys.executable))


class ChainFamily(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import chain_family
        cls.C = chain_family
        if not os.path.isfile(chain_family.S.ELF):
            print(f"NOTE: {chain_family.S.ELF} absent -- this test measured nothing", file=sys.stderr)
            cls.rows = []
            return
        cls.rows = chain_family.scan()

    def test_the_population_is_the_pre_registration(self):
        got = self.C.summarise(self.rows)
        self.assertEqual(got, self.C.PREREG)
        print(f"\n{got}")

    def test_no_member_is_testable_from_the_shipped_image(self):
        # Every load target sits in the zero-fill tail, so the shipped qword is zero and the store
        # degenerates to the address K2. A member here whose slot were inside filesz would be testable
        # without a case, which is a different family -- and would mean the pre-registration is wrong.
        self.assertTrue(self.rows, "no rows: the census measured nothing")
        self.assertEqual({r['where'] for r in self.rows}, {'zerofill'})

    def test_the_triples_are_distinct_so_no_case_can_be_shared(self):
        triples = {(r['load_disp'], r['store_k2'], r['imm']) for r in self.rows}
        self.assertEqual(len(triples), len(self.rows))

    def test_every_row_carries_what_its_case_must_satisfy(self):
        # link two of the seeding gate needs both numbers per row; a row missing either cannot be
        # authored at all, and would show up later as a fault at the store.
        self.assertTrue(self.rows, "no rows: the census measured nothing")
        for r in self.rows:
            self.assertGreater(r['store_width'], 0)
            self.assertGreaterEqual(r['store_k2'], 0)

    def test_the_committed_table_reproduces(self):
        out = ROOT / "symbols" / "chain_family.csv"
        if not out.is_file():
            self.skipTest("chain_family.csv not committed yet")
        p = subprocess.run([PY, "-P", str(ROOT / "tools" / "chain_family.py"), "--check"],
                           capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": ""}, cwd="/tmp")
        self.assertEqual(p.returncode, 0, p.stderr[-800:])
        self.assertIn("reproduced byte-for-byte", p.stdout)


if __name__ == "__main__":
    unittest.main()
