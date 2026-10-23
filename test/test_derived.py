"""The store must be regenerable and must refuse a stale value.

An accepting run is not enough: a check that never refuses is a formatter. So one test asserts the
committed store matches a fresh derivation and one plants a wrong value and asserts the refusal names it.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
TOOL = ROOT / "tools" / "derive.py"


class Derived(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([PY, "-P", str(TOOL), *args], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=300)

    def test_committed_store_matches_a_fresh_derivation(self):
        p = self.run_tool("--check")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("derive: ok", p.stdout)

    def test_a_wrong_value_is_refused_and_named(self):
        store = ROOT / "symbols" / "derived.json"
        orig = store.read_text()          # restore the BYTES read, never a retyped digit
        payload = json.loads(orig)
        try:
            payload["values"]["catalogue.functions"] = 1
            store.write_text(json.dumps(payload, indent=1))
            p = self.run_tool("--check")
            self.assertEqual(p.returncode, 1)
            self.assertIn("catalogue.functions", p.stdout)
            self.assertIn("stored 1", p.stdout)
        finally:
            store.write_text(orig)
            p = self.run_tool("--check")
            self.assertEqual(p.returncode, 0, "store not restored: " + p.stdout)


if __name__ == "__main__":
    unittest.main()
