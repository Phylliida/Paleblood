"""The capture wrapper's float refusal, proved in both directions."""
import os
import sys
import unittest

# Discovery puts `test/` on sys.path, not the repo root, and `-P` keeps the cwd off it: import the module the
# way the rest of the suite does rather than relying on where I happened to run it from.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from capture_precheck import scan, verdict, write_table, TABLE


class CaptureRefusesVolatileXmm(unittest.TestCase):
    def test_float_reading_body_is_refused_and_named(self):
        ok, why = verdict(bytes.fromhex("f30f1007"))          # movss xmm0, dword ptr [rdi]
        self.assertFalse(ok, why)
        self.assertIn("xmm0", why)

    def test_gpr_only_body_passes_and_names_its_base(self):
        ok, why = verdict(bytes.fromhex("488b07c3"))          # mov rax, [rdi]; ret
        self.assertTrue(ok, why)
        self.assertIn("rdi", why)

    def test_control_a_body_with_no_xmm_really_scans_clean(self):
        found = scan(bytes.fromhex("488b07c3"))
        self.assertEqual(set(), found["xmm"])
        self.assertIn("rdi", found["bases"])

    def test_the_committed_table_matches_a_fresh_scan(self):
        """The staleness guard: regenerate and diff, so an edited body or a new candidate is a red test rather
        than an install-time refusal in the game -- and the row's sha256 is the key that makes it expire."""
        self.assertTrue(TABLE.exists(), f"no table at {TABLE}: generate it with --table")
        fresh = write_table()
        committed = TABLE.read_text()
        self.assertEqual(committed, fresh,
                         "symbols/capture_ok.csv is stale: regenerate with "
                         "`capture_precheck.py --table > symbols/capture_ok.csv` "
                         "(the tool prints; the shell writes -- the bare command leaves this file alone)")
        rows = [r for r in committed.splitlines()[1:] if r]
        self.assertGreater(len(rows), 0, "the table must carry at least one candidate row")
        for row in rows:                                  # a row must be a verdict plus a key, never one alone
            address, verdict, digest, so = row.split(",")
            self.assertTrue(address.startswith("0x"), row)
            self.assertIn(verdict, ("none",), row)         # candidates are the bodies we intend to capture
            self.assertRegex(digest, r"^[0-9a-f]{64}$", row)
            # The install-time key: one value for the library the rows came from, compared as a string by C.
            self.assertRegex(so, r"^[0-9a-f]{64}$", row)

    def test_scanning_nothing_is_not_a_pass(self):
        ok, why = verdict(b"")
        self.assertFalse(ok)
        self.assertIn("no bytes", why)


if __name__ == "__main__":
    unittest.main()
