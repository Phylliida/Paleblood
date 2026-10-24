"""The chain family's population, pinned against numbers written before any case existed.

These tests import the tool rather than a copy of its predicate, so a change to
`leaf_shape_census.shape_of` reaches them. What they assert is the PRE-REGISTRATION: if any of these
move, the family is a different family and the batch must be re-registered, not re-run.
"""
import os
import subprocess
import sys
import tempfile
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
            cls.rows = chain_family.table()
            cls.cand = []
            return
        # THE FAMILY is the committed table. The frontier is CANDIDATES -- and for a landed family it
        # returns none, which is a fact to assert, never a zero to feed the pre-registration.
        cls.rows = chain_family.table()
        cls.cand = chain_family.candidates()

    def test_the_family_shape_has_left_the_candidate_frontier(self):
        """A landed family is not a candidate, and the candidate instrument says so BY NAME.

        This is the absence that cost five reds: after the 78 landed, `frontier()` dropped to 6,210
        candidates and `--targets-for` the family's own shape refused -- correctly. The refusal was
        read as a defect because the shape was a private literal no test could name.
        """
        tool = str(ROOT / 'tools' / 'leaf_shape_census.py')
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        p = subprocess.run([PY, '-P', tool, '--targets-for', self.C.WANT], capture_output=True,
                           text=True, cwd='/tmp', env=env)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(f'no frontier row has shape {self.C.WANT!r}', p.stderr)
        self.assertIn('is not a measurement of that shape', p.stderr)
        self.assertEqual(self.cand, [], 'the family is landed: candidates() must return none')

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

    def test_rescan_refuses_to_empty_a_landed_family(self):
        """The truncation guard, observed firing. A family of zero members against a table of 78 is a
        truncation wearing a regeneration's name -- the `emit_leaf_family.py:681` class, one tier up:
        there a refusal truncated the artifact; here a successful rescan would have.
        """
        out = Path(tempfile.mkdtemp()) / 'empty.csv'
        p = subprocess.run([PY, '-P', str(ROOT / 'tools' / 'chain_family.py'), '--rescan', '--write',
                            '--out', str(out)], capture_output=True, text=True,
                           env={**os.environ, 'PYTHONPATH': ''}, cwd='/tmp')
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn('REFUSED rescan: the frontier yields 0 candidates', p.stderr)
        self.assertIn('a truncation, not a regeneration', p.stderr)
        self.assertFalse(out.exists(), 'a refused rescan wrote the file it refused to write')

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
