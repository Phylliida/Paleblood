"""rc.sh: the process rc, and a refusal for the shape that got it wrong six times.

A function-style module here is INVISIBLE to `unittest discover` -- it prints `Ran 0 tests` and exits 0,
which is a denominator collapsing to zero rather than a pass. Everything is a TestCase method on purpose.
"""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RcSh(unittest.TestCase):
    def run_sh(self, bash_src):
        return subprocess.run(['bash', '-c', '. tools/rc.sh\n' + bash_src],
                              cwd=ROOT, capture_output=True, text=True,
                              env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')})

    def test_the_rc_is_the_process_not_the_pipeline_member(self):
        r = self.run_sh('run sh -c "echo visible; exit 7"')
        self.assertEqual(r.returncode, 7, (r.returncode, r.stdout, r.stderr))
        self.assertIn('rc=7', r.stdout)

    def test_zero_is_printable_and_success_propagates(self):
        r = self.run_sh('run sh -c "exit 0" && echo propagated')
        self.assertEqual(r.returncode, 0)
        self.assertIn('rc=0', r.stdout)
        self.assertIn('propagated', r.stdout)

    def test_a_pipeline_passed_as_words_is_refused(self):
        r = self.run_sh('run "sh -c true | tail -1"')
        self.assertEqual(r.returncode, 2, (r.returncode, r.stderr))
        self.assertIn('refusing a shell string', r.stderr)

    def test_the_output_is_kept_when_the_process_fails(self):
        r = self.run_sh('RC_TAIL=1 run sh -c "echo last-line; exit 3"')
        self.assertEqual(r.returncode, 3)
        self.assertIn('last-line', r.stdout)
        self.assertIn('rc=3', r.stdout)
