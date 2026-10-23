"""The helper exists because five spellings of one address produced three wrong totals."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import addrs  # noqa: E402


class ParseAddress(unittest.TestCase):
    def test_the_five_spellings_of_one_address_agree(self):
        for spelling in ('0x186ea70', '0186ea70', '186ea70', '0X186EA70', ' 0x186ea70 '):
            self.assertEqual(addrs.parse_address(spelling), 0x186EA70, spelling)
        self.assertEqual(addrs.parse_address(0x186EA70), 0x186EA70)

    def test_the_join_key_is_canonical(self):
        self.assertEqual(addrs.key('0x186ea70'), '0186ea70')
        self.assertEqual(addrs.key('0186EA70'), '0186ea70')

    def test_a_non_address_refuses_rather_than_returning_zero(self):
        for bad in ('', 'zzz', '0x', None):
            with self.assertRaises(ValueError):
                addrs.parse_address(bad)

    def test_the_zero_padding_that_broke_the_lookup(self):
        sizes = {addrs.parse_address('0186ea70'): 7}
        self.assertEqual(sizes.get(addrs.parse_address('0x186ea70')), 7)


if __name__ == '__main__':
    unittest.main()
