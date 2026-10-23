"""The hook that enforces every other gate: installed by a tracked script, and checkable in both directions."""
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, "-P", str(REPO / "tools" / "check_hooks.py"), *args],
                          capture_output=True, text=True, cwd=REPO)


class Hooks(unittest.TestCase):
    def test_this_clone_passes(self):
        r = run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sources tracked", r.stdout)

    def test_a_hooks_path_without_commit_msg_is_refused(self):
        """The gate deletion: git looks for commit-msg directly in core.hooksPath; no dispatch layer."""
        r = run("--hooks-path", "tools/hooks")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("commit-msg", r.stdout)


if __name__ == "__main__":
    unittest.main()
