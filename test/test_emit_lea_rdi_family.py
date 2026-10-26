"""The lea_rdi emitter's pre-registration refusal is a verdict, not a log line.

The tool's own census is settled (483 landed, 0 unlanded), so its pre-registration now refuses on
every run. That refusal must reach a caller as a nonzero rc: a refusal printed to stderr with rc=0
is a pass to every `&&` chain in this tree.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, 'tools', 'emit_lea_rdi_family.py')


class PreRegistration(unittest.TestCase):
    def test_the_settled_census_refuses_with_a_nonzero_rc(self):
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        run = subprocess.run([sys.executable, '-P', TOOL], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn('PRE-REGISTRATION FAILED', run.stderr)
        self.assertIn('unlanded is 0, expected 483', run.stderr)
        self.assertIn('members 483 unlanded 0', run.stdout)


if __name__ == '__main__':
    unittest.main()
