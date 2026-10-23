"""symbols/retired.csv decides which rows never run, so each of its refusals must fire on demand.

A gate proved by its green is a gate that has not been proved. Every case below plants one
violation in a fixture tree and requires rc 1 with a message naming the address -- and the last
case runs the check over the real tree, because a check that only ever sees fixtures has never
met the population it governs.
"""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import check_retired as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RET = ('address', 'reason', 'date', 'revisit')
FUN = ('address', 'name', 'status', 'size')


class RetiredRefuses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        for d in ('symbols', os.path.join('game', 'leaf')):
            os.makedirs(os.path.join(self.root, d), exist_ok=True)

    def _write(self, rel, header, rows):
        path = os.path.join(self.root, rel)
        with open(path, 'w', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(header)
            w.writerows(rows)
        return path

    def _family(self, fam, addrs):
        body = ''.join(f'extern "C" std::uint64_t bb_leaf_{fam}_{a}() {{ return 0; }}\n' for a in addrs)
        open(os.path.join(self.root, 'game', 'leaf', f'{fam}_family.cpp'), 'w').write(body)

    def _base(self, retired_rows, funcs_rows, body_addrs=(), unrec=()):
        self._write(os.path.join('symbols', 'retired.csv'), RET, retired_rows)
        self._write(os.path.join('symbols', 'functions.csv'), FUN, funcs_rows)
        if unrec:
            self._write(os.path.join('symbols', 'verification_unrecordable.csv'),
                        ('address', 'function', 'reason'), unrec)
        self._family('demo', body_addrs)

    def _ok_row(self, a='00000001'):
        return ('0x' + a, 'magic division, load-only template discards the function', '2026-10-23',
                'if the family splits into load-only and load-plus-arith')

    def test_a_clean_tree_is_green(self):
        self._base([self._ok_row()],
                   [('0x00000001', 'leaf_demo_00000001', 'original', '34'),
                    ('0x00000002', 'large_derived_thing', 'original', '8')],
                   body_addrs=('00000002',))
        rc, findings, pop = C.check(self.root)
        self.assertEqual(rc, 0, findings)
        self.assertIn('1 retired row(s)', pop)

    def test_a_blank_revisit_refuses(self):
        row = list(self._ok_row())
        row[3] = '   '
        self._base([tuple(row)], [('0x00000001', 'leaf_demo_00000001', 'original', '34')])
        rc, findings, _ = C.check(self.root)
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('blank `revisit`' in f for f in findings), findings)

    def test_a_duplicate_address_refuses(self):
        self._base([self._ok_row(), self._ok_row()],
                   [('0x00000001', 'leaf_demo_00000001', 'original', '34')])
        rc, findings, _ = C.check(self.root)
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('appears twice' in f for f in findings), findings)

    def test_a_verdict_about_nothing_refuses(self):
        self._base([self._ok_row('00000099')],
                   [('0x00000001', 'leaf_demo_00000001', 'original', '34')])
        rc, findings, _ = C.check(self.root)
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('not a row in functions.csv' in f for f in findings), findings)

    def test_a_retired_address_with_a_body_refuses(self):
        # The one that matters: a retired member whose body is still compiled.
        self._base([self._ok_row()],
                   [('0x00000001', 'leaf_demo_00000001', 'original', '34')],
                   body_addrs=('00000001',))
        rc, findings, _ = C.check(self.root)
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('still has a body' in f for f in findings), findings)

    def test_a_body_that_vanished_without_a_verdict_refuses(self):
        self._base([],
                   [('0x00000001', 'leaf_demo_00000001', 'original', '34'),
                    ('0x00000002', 'leaf_demo_00000002', 'edge-verified', '34')],
                   body_addrs=('00000002',))
        rc, findings, _ = C.check(self.root)
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('vanished without a verdict' in f for f in findings), findings)

    def test_an_address_cannot_be_both_retired_and_unrecordable(self):
        self._base([self._ok_row()],
                   [('0x00000001', 'leaf_demo_00000001', 'original', '34')],
                   unrec=[('0x00000001', 'leaf_demo_00000001', 'no case directory')])
        rc, findings, _ = C.check(self.root)
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('a verdict is not a debt' in f for f in findings), findings)

    def test_a_requested_library_that_does_not_exist_refuses(self):
        self._base([self._ok_row()], [('0x00000001', 'leaf_demo_00000001', 'original', '34')])
        rc, findings, _ = C.check(self.root, lib=os.path.join(self.root, 'nope.so'))
        self.assertEqual(rc, 1, findings)
        self.assertTrue(any('cannot check exports' in f for f in findings), findings)

    def test_the_real_tree_is_clean(self):
        rc, findings, pop = C.check(ROOT)
        self.assertEqual(rc, 0, findings)
        self.assertIn('retired row(s)', pop)


if __name__ == '__main__':
    unittest.main()
