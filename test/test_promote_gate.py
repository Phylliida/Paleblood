"""The edge-verified door asks 1ab before it moves a row.

`promote_edge` had no test caller, and `tier_authority.grants('1ab')` answers False today. Both
arms are tested here: the refusal writes nothing, and a granted authority flips the fixture. The
positive arm patches only the authority and the source hash; the flip itself is the product's.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

import catalogue  # noqa: E402
import promote  # noqa: E402
import tier_authority  # noqa: E402


def fixture(root: Path) -> None:
    (root / 'symbols').mkdir()
    (root / 'symbols' / 'functions.csv').write_text(
        'address,size,name,system,status,notes\n'
        '0x00400020,5,leaf_demo,leaf,original,\n', encoding='utf-8')
    (root / 'symbols' / 'verification.csv').write_text(
        'function,cases,option,total,passed,failed,quarantined,source,cases_sha256,date\n'
        'leaf_demo,edge,,1,1,0,0,s,abc,2026-01-01\n', encoding='utf-8')


class PromoteGate(unittest.TestCase):
    def test_ungranted_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            before = (root / 'symbols' / 'functions.csv').read_bytes()
            with mock.patch.object(tier_authority, 'grants', return_value=False):
                rc = promote.promote_edge(str(root), 'leaf_demo', dry_run=False)
            self.assertEqual(rc, 1)
            self.assertEqual((root / 'symbols' / 'functions.csv').read_bytes(), before)
            self.assertIn(',original,', (root / 'symbols' / 'functions.csv').read_text())

    def test_granted_flips_one_row(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            with mock.patch.object(tier_authority, 'grants', return_value=True):
                # promote_edge imports verification inside the call; patch the module it will import.
                import verification
                with mock.patch.object(verification, 'source_hash', return_value='s'):
                    rc = promote.promote_edge(str(root), 'leaf_demo', dry_run=False)
            self.assertEqual(rc, 0)
            rows = list(catalogue.read_rows(root / 'symbols' / 'functions.csv'))
            self.assertEqual(rows[0]['status'], 'edge-verified')

    def test_a_failed_write_leaves_the_table_byte_identical(self):
        """The write is beside-then-replace; a producer that raises must not have truncated first."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            before = (root / 'symbols' / 'functions.csv').read_bytes()
            import verification
            with mock.patch.object(tier_authority, 'grants', return_value=True), \
                 mock.patch.object(verification, 'source_hash', return_value='s'), \
                 mock.patch.object(promote.atomicio, 'atomic_write', side_effect=OSError('disk')):
                with self.assertRaises(OSError):
                    promote.promote_edge(str(root), 'leaf_demo', dry_run=False)
            self.assertEqual((root / 'symbols' / 'functions.csv').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
