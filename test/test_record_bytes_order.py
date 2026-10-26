"""Which artifact may move first when the byte family's flip fails partway.

`record_bytes_family` records the ledger row, then flips `functions.csv`, then sorts. The two
writers are atomic, so the surviving question is order: on a table-write failure, may the evidence
exist without the claim? The design answer is yes -- evidence may lead its claim; a claim may not
lead its evidence. This test pins that direction, and its positive control proves the same fixture
would flip when nothing fails, so "refuses everything" cannot pass for the invariant.
"""
import csv
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import catalogue as C  # noqa: E402
import record_bytes_family as rf  # noqa: E402


FUNCTIONS_HEADER = ['address', 'size', 'name', 'system', 'status', 'notes']
FUNCTIONS_ROW = ['0x00400020', '5', 'leaf_mov_al_00400020', 'leaf', 'original', '']


def tree():
    root = tempfile.mkdtemp(prefix='record-bytes-order-')
    os.mkdir(os.path.join(root, 'symbols'))
    with open(os.path.join(root, 'symbols', 'functions.csv'), 'w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(FUNCTIONS_HEADER)
        w.writerow(FUNCTIONS_ROW)
    with open(os.path.join(root, 'symbols', 'replacement_origins.csv'), 'w', newline='') as f:
        f.write('address,origin\n')
    with open(os.path.join(root, 'symbols', 'install_mode.csv'), 'w', newline='') as f:
        f.write('address,mode\n')
    return root


def read(path):
    with open(path, 'rb') as f:
        return f.read()


class Ordering(unittest.TestCase):
    def run_family(self, root, fail_table=False):
        with mock.patch.object(rf, 'assert_no_control_flow'), \
             mock.patch.object(rf, 'assert_position_independent'), \
             mock.patch.object(rf, 'assert_no_trap'), \
             mock.patch.object(rf, 'digest', return_value='d' * 16), \
             mock.patch.object(rf.V, 'source_hash', return_value='s' * 16), \
             mock.patch.object(rf.P, 'ledger', return_value={
                 'functions': 1, 'byte_backed': 1, 'differential_backed': 0, 'rows': 1}):
            if fail_table:
                with mock.patch.object(rf, '_write_rows', side_effect=OSError('injected table failure')):
                    return rf.main(['--family', 'leaf_mov_al_', '--root', root])
            return rf.main(['--family', 'leaf_mov_al_', '--root', root])

    def test_a_table_failure_leaves_the_claim_unflipped_and_the_evidence_recorded(self):
        root = tree()
        before = read(os.path.join(root, 'symbols', 'functions.csv'))
        with self.assertRaises(OSError):
            self.run_family(root, fail_table=True)
        self.assertEqual(read(os.path.join(root, 'symbols', 'functions.csv')), before,
                         'the table was written even though its writer raised')
        rows = list(rf.V.read_csv(os.path.join(root, 'symbols', 'verification.csv'),
                                  rf.V.VERIFICATION_HEADER))
        self.assertEqual(len(rows), 1, 'the evidence row should exist so a retry can replace it')
        self.assertEqual(rows[0]['function'], 'leaf_mov_al_00400020')
        self.assertEqual(rows[0]['cases'], 'bytes')

    def test_the_same_fixture_flips_when_no_write_fails(self):
        root = tree()
        self.assertEqual(self.run_family(root, fail_table=False), 0)
        rows = list(C.read_rows(os.path.join(root, 'symbols', 'functions.csv')))
        self.assertEqual(rows[0]['status'], 'edge-verified')
        self.assertEqual(len(list(rf.V.read_csv(os.path.join(root, 'symbols', 'verification.csv'),
                                                rf.V.VERIFICATION_HEADER))), 1)


if __name__ == '__main__':
    unittest.main()
