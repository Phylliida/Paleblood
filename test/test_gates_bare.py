"""Gates must resolve their own imports with NO environment help.

`PYTHONPATH=tools` masked a real defect for dozens of turns: a tool that forgets to put its own directory
on sys.path imports fine under the suite and dies in the hook, where no PYTHONPATH is set. Two mechanisms
for one resolution is the one-home rule wearing a shell.

So this test runs each gate as the hook would -- cwd=/tmp so no relative import of tools/ can work, and
PYTHONPATH DELETED from the environment -- and requires rc=0 from each. If a gate needs help to start,
this is where it is told, not in a commit that happens to run under the right shell.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES = ("check_externs.py", "check_catalogue.py")


class BareGates(unittest.TestCase):
    def run_bare(self, tool, *args):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        return subprocess.run([sys.executable, "-P", str(ROOT / "tools" / tool), *args],
                              cwd="/tmp", capture_output=True, text=True, timeout=300, env=env)

    def test_each_gate_starts_and_passes_with_no_environment_help(self):
        for tool in GATES:
            with self.subTest(tool=tool):
                p = self.run_bare(tool)
                self.assertEqual(p.returncode, 0, f"{tool}: " + p.stdout + p.stderr)

    def test_the_store_check_starts_bare_too(self):
        p = self.run_bare("derive.py", "--check")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("derive: ok", p.stdout)


if __name__ == "__main__":
    unittest.main()
