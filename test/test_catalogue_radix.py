"""The radix equality is load-bearing for a prediction, so it is a test, not a heredoc in a transcript.

`symbols/ghidra_functions.csv` is `address,size` with addresses in HEX and sizes in DECIMAL. A hex parse of
`size` inflated every body and made four loaders decode past the neighbour's `ret`; it manufactured 116,475,
13,307, 37,629, 6,749, 139 and 71.3%, all since withdrawn. Whoever changes `parse_size` next must be told by
this file, not by reading an exchange.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import catalogue  # noqa: E402

CAT = pathlib.Path(__file__).resolve().parent.parent / "symbols" / "ghidra_functions.csv"


class Radix(unittest.TestCase):
    def test_read_rows_equals_a_raw_decimal_parse_elementwise(self):
        rows = catalogue.load_extents(CAT)       # [(address:int, size:int)] -- read_rows yields dicts
        raw = []
        with CAT.open() as f:
            next(f)                              # the header is part of the file
            for line in f:
                a, s = line.rstrip("\n").split(",")
                raw.append((int(a, 16), int(s)))     # addresses hex, sizes DECIMAL
        self.assertEqual(len(rows), len(raw))
        first = next((i for i, (x, y) in enumerate(zip(rows, raw)) if x != y), None)
        if first is not None:            # the detail must not be computed on the passing path
            self.fail(f"first divergence at row {first}: {rows[first]!r} != {raw[first]!r}")

    def test_the_aggregate_matches_too(self):
        self.assertEqual(sum(s for _a, s in catalogue.load_extents(CAT)), 42_487_347)

    def test_a_hex_size_is_refused_rather_than_guessed(self):
        with self.assertRaises(ValueError):
            catalogue.parse_size("0x1c")

    def test_read_rows_carries_the_same_ints_as_dicts(self):
        d = next(iter(catalogue.read_rows(CAT)))
        self.assertIsInstance(d["address"], int)
        self.assertIsInstance(d["size"], int)

    def test_no_size_field_in_the_file_needs_a_guess(self):
        with CAT.open() as f:
            next(f)
            bad = [i for i, line in enumerate(f, 2) if not line.rstrip("\n").split(",")[1].strip().lstrip("+-").isdigit()]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
