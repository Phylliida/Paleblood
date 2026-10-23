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
        self.assertIn("moved against the pre-registration", p.stdout)

    def _prereg(self, mutate, prereg):
        """Baseline = the real store, so the only disagreement is the one the test introduces."""
        import tempfile
        values = json.loads((ROOT / "symbols" / "derived.json").read_text())["values"]
        mutate(values)
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(prereg, f); f.close()
        g = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump({"values": values}, g); g.close()
        return subprocess.run([PY, "-P", str(TOOL), "--compare", g.name, "--prereg", f.name], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=300)

    def test_an_empty_baseline_refuses_instead_of_comparing_nothing(self):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump({"values": {}}, f); f.close()
        p = subprocess.run([PY, "-P", str(TOOL), "--compare", f.name], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)   # it used to print a refusal and then compare

    def test_a_key_predicted_to_move_that_does_not_move_is_a_finding(self):
        # catalogue.functions is in both sides with the same value; predicting a change makes silence a finding
        p = self._prereg(lambda v: None, {"predicted": {"catalogue.functions": {"prediction": "up"}}})
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[MISSED] catalogue.functions", p.stdout)

    def test_a_key_that_moves_against_its_predicted_direction_is_a_finding(self):
        p = self._prereg(lambda v: v.__setitem__("catalogue.functions", v["catalogue.functions"] + 1),
                         {"predicted": {"catalogue.functions": {"prediction": "up"}}})
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[AGAINST] catalogue.functions", p.stdout)

    def test_a_key_predicted_to_move_in_the_right_direction_passes(self):
        p = self._prereg(lambda v: v.__setitem__("catalogue.functions", v["catalogue.functions"] - 1),
                         {"predicted": {"catalogue.functions": {"prediction": "up"}}})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("[mutable] catalogue.functions", p.stdout)

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
