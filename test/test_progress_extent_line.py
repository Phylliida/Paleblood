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
