"""The capture wrapper's float refusal, proved in both directions."""
import os
import sys
import unittest

# Discovery puts `test/` on sys.path, not the repo root, and `-P` keeps the cwd off it: import the module the
# way the rest of the suite does rather than relying on where I happened to run it from.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from capture_precheck import scan, verdict


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

    def test_scanning_nothing_is_not_a_pass(self):
        ok, why = verdict(b"")
        self.assertFalse(ok)
        self.assertIn("no bytes", why)


if __name__ == "__main__":
    unittest.main()
