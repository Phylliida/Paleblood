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

    def _doctored(self, mutate):
        import tempfile
        store = ROOT / "symbols" / "derived.json"
        payload = json.loads(store.read_text())
        mutate(payload["values"])
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, f); f.close()
        return subprocess.run([PY, "-P", str(TOOL), "--compare", f.name], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=300)

    def test_compare_labels_an_absent_current_key_as_GONE_and_prints_both_values(self):
        # build() does not yet emit the provisional keys, so until the migration lands them the only
        # thing a provisional key can do is appear (NEW) or leave (GONE) -- "moved" is not expressible
        # yet, and this test says so instead of pretending otherwise.
        p = self._doctored(lambda v: v.__setitem__("branch.functions", 1))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("[mutable/GONE] branch.functions: 1 -> None", p.stdout)

    def test_compare_refuses_a_frozen_key_that_moves(self):
        p = self._doctored(lambda v: v.__setitem__("catalogue.functions", 1))
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[FROZEN] catalogue.functions", p.stdout)
        self.assertIn("frozen key(s) moved", p.stdout)

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
