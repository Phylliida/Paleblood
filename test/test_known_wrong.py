"""1o: a known-wrong body cannot be recorded -- and its refusal has now been OBSERVED raising.

Every address here is read from the table under test. A literal would be refused by check_agnostic.py
(correctly), and it would also make this test agree with its own copy of the answer instead of with the
product: the table is data now, so the test can also move it, which is what the control below does.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep + 'tools')
import landed   # noqa: E402

HEADER = 'address,name,size,status,cases,notes\n'


def _fixture(dirname, address, status):
    path = os.path.join(dirname, 'functions.csv')
    with open(path, 'w') as f:
        f.write(HEADER)
        f.write('%#010x,fixture_body,1072,%s,,fixture\n' % (address, status))
    return path


class KnownWrong(unittest.TestCase):
    def setUp(self):
        self.assertGreater(len(landed.KNOWN_WRONG), 0,
                           'an empty refusal table refuses nothing and would make every test below vacuous')
        self.address = next(iter(landed.KNOWN_WRONG))
        self.reason = landed.KNOWN_WRONG[self.address]

    def test_the_table_is_data_and_typed(self):
        for a, why in landed.KNOWN_WRONG.items():
            self.assertIsInstance(a, int,
                                  'a str key can never match a row parsed as int -- a table that cannot match '
                                  'is indistinguishable from an empty one')
            self.assertGreater(len(why), 40, 'a refusal without its reason is one nobody can act on')

    def test_a_landed_status_raises_and_names_address_and_reason(self):
        with tempfile.TemporaryDirectory() as d:
            path = _fixture(d, self.address, 'edge-verified')
            with self.assertRaises(ValueError) as cm:
                landed.landed_addresses(path)
        msg = str(cm.exception)
        self.assertIn('%#010x' % self.address, msg, 'the refusal must name the address it refuses')
        self.assertIn(self.reason.split('.')[0][:24], msg, 'and the reason, taken from the table itself')

    def test_at_original_it_is_excluded_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            path = _fixture(d, self.address, 'original')
            self.assertEqual(landed.landed_addresses(path), set(),
                             'not landed, and not a refusal either -- the two outcomes are different facts')

    def test_with_the_entry_absent_the_same_row_is_admitted(self):
        saved = landed.KNOWN_WRONG
        try:
            landed.KNOWN_WRONG = {}
            with tempfile.TemporaryDirectory() as d:
                path = _fixture(d, self.address, 'edge-verified')
                self.assertEqual(landed.landed_addresses(path), {self.address},
                                 'the raise is a fact about the ENTRY, not about the row')
        finally:
            landed.KNOWN_WRONG = saved


if __name__ == '__main__':
    unittest.main()
