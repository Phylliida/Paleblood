"""The extent line must print on every invocation and must never enter the document.

Two defects of one class: the line was first appended INSIDE the JSON branch (prose in a document),
then moved into a flag-gated branch (a line that must always print, living where it does not). This
test fails on either, so whoever moves it next sees red instead of noticing nothing.
"""
import json
import pathlib
import subprocess
import sys
import unittest

PY_ = sys.executable
# ctest runs this from build-release/, so a relative "tools/progress.py" is a test about the directory
# the author happened to launch it from -- it passed in the repo root and failed under ctest, which is
# the only place it will ever run in CI.
REPO = pathlib.Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([PY_, "-P", str(REPO / "tools/progress.py"), *args],
                          cwd=REPO, capture_output=True, text=True)


class ExtentLineTest(unittest.TestCase):
    def _synthetic(self, rows):
        """A catalogue the tie branch CAN fire on, because the real one is disjoint by construction.

        A guard whose docstring says "this cannot occur here" is otherwise unfalsifiable: the fixture is
        the only thing that ever enters the branch, and it is the receipt that the branch is reachable.
        """
        import os, tempfile, pathlib
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "symbols").mkdir()
        (d / "symbols" / "ghidra_functions.csv").write_text(
            "address,size\n" + "".join(f"0x{a:08x},{s}\n" for a, s in rows))
        (d / "symbols" / "functions.csv").write_text(
            "address,size,name,system,status,notes\n")
        return d

    def _extent(self, d):
        # Same discipline as run(): the script, its import root and the process cwd are all
        # absolute. ctest invokes this from build-release/, where a relative "tools/progress.py"
        # is a test about the author's shell rather than about the tool.
        import os, subprocess
        env = dict(os.environ, PB_SYMBOLS_DIR=str(d / "symbols"),
                   PYTHONPATH=str(REPO / "tools"))
        r = subprocess.run([PY_, "-P", str(REPO / "tools/progress.py")],
                           capture_output=True, text=True, env=env, cwd=REPO)
        return r.stdout + r.stderr

    def test_tie_in_a_synthetic_catalogue_is_counted(self):
        out = self._extent(self._synthetic([(0x1000, 10), (0x1005, 10)]))
        self.assertIn("same-length overlapping extents 2", out)

    def test_disjoint_catalogue_is_zero(self):
        """The negative fixture, and the one that would have caught the tautology.

        Without it, "2 counted" is satisfied by a predicate that counts everything -- the same blindness as
        a mutant that cannot be seen. A guard's fixture needs an input where the ANSWER IS ZERO.
        """
        out = self._extent(self._synthetic([(0x1000, 10), (0x100A, 10), (0x1014, 4)]))
        self.assertIn("same-length overlapping extents 0", out)

    def test_duplicate_start_is_counted_as_tied(self):
        out = self._extent(self._synthetic([(0x1000, 10), (0x1000, 10)]))
        self.assertIn("same-length overlapping extents 2", out)

    def test_line_prints_on_every_mode(self):
        for mode in ((), ("--burndown",), ("--status",)):
            r = run(*mode)
            self.assertEqual(r.returncode, 0, f"mode {mode}: {r.stderr[-300:]}")
            self.assertIn("extents:", r.stderr, f"mode {mode} lost the extent line")
            self.assertIn("--min-size 14", r.stderr)
            self.assertNotIn("extents:", r.stdout, f"mode {mode} put prose in the document")

    def test_default_stdout_is_still_json(self):
        r = run()
        json.loads(r.stdout)  # a document, not a document-with-a-sentence


if __name__ == "__main__":
    unittest.main()
