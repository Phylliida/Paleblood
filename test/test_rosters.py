"""Both directions, and a live set that matches exactly must produce nothing."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import rosters  # noqa: E402


class Rosters(unittest.TestCase):
    def test_both_directions(self):
        unlisted, stale = rosters.compare({"a", "b"}, {"b", "c"})
        self.assertEqual(unlisted, ["c"])   # live, not listed
        self.assertEqual(stale, ["a"])      # listed, not live

    def test_exact_match_is_silent(self):
        self.assertEqual(rosters.report({"a"}, {"a"}, fmt_unlisted=str, fmt_stale=str), [])

    def test_report_carries_both(self):
        lines = rosters.report({"a"}, {"c"}, fmt_unlisted=lambda x: f"new {x}", fmt_stale=lambda x: f"gone {x}")
        self.assertEqual(sorted(lines), ["gone a", "new c"])


if __name__ == "__main__":
    unittest.main()
