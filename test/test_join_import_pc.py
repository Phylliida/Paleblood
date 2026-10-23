"""The join carries its own fixture: this test is the reason the tool exists in that shape."""
import unittest
import sys
sys.path.insert(0, "tools")
import join_import_pc as j


class JoinTest(unittest.TestCase):
    def test_self_test_passes(self):
        self.assertEqual(j.self_test(), 0)

    def test_window_sees_an_extent_that_starts_far_behind(self):
        # a 0x400-wide extent starting at 0 can own a pc at 0x3ff; a constant look-back window loses it.
        table = [(0, 0x400), (0x10000, 0x10)]
        self.assertEqual(j.owner(table, 0x3ff), (0, 0x400))

    def test_first_extent_is_reachable(self):
        table = [(0x1000, 0x10), (0x2000, 0x10)]
        self.assertEqual(j.owner(table, 0x1000), (0x1000, 0x10))

    def test_stray_is_none_not_zero(self):
        # a stray must not read as an owner at address 0, the way a defaulted field would
        self.assertIsNone(j.owner([(0x1000, 0x10)], 0x0))

    def test_tie_is_ambiguous_not_file_order(self):
        # equal-size extents both containing the pc: the answer is "ambiguous", never the lower address,
        # because the lower address is a property of the catalogue's order rather than of the binary.
        table = [(0x0FF0, 0x40), (0x1000, 0x40)]
        self.assertEqual(j.resolve(table, 0x1005), (None, "ambiguous"))

    def test_rows_parse_and_reject(self):
        text = "  #40 pc 0x8020b5c90 count 5\n  #not a row\n"
        rows = j.parse_rows(text)
        self.assertEqual(rows, [{"index": 40, "pc": 0x8020B5C90, "count": 5}])


if __name__ == "__main__":
    unittest.main()
