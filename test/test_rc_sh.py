"""rc.sh: the process rc, and a WHITELIST refusal rather than a list of remembered metacharacters.

Two things learned while writing this file, both kept as tests rather than comments:
  * a module of plain `test_*` FUNCTIONS is invisible to `unittest discover` -- it prints `Ran 0 tests` and
    exits 0, a denominator collapsing to zero that looks exactly like a pass. Everything here is a TestCase.
  * `run` prints only `rc=N`; the command's payload goes to RC_OUT. A payload printed beside the rc is a
    second copy of the facts and will diverge silently. RC_OUT is per-test: a shared scratch path makes the
    suite order-dependent.
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
        r = self.run_sh("run sh -c 'exit 7'")
        self.assertEqual(r.returncode, 7, (r.returncode, r.stdout, r.stderr))
        self.assertIn('rc=7', r.stdout)

    def test_zero_is_printable_and_success_propagates(self):
        r = self.run_sh('run true && echo propagated')
        self.assertEqual(r.returncode, 0)
        self.assertIn('rc=0', r.stdout)
        self.assertIn('propagated', r.stdout)

    def test_output_survives_with_RC_TAIL(self):
        r = self.run_sh('RC_OUT=/tmp/rc_sh_a.out RC_TAIL=1 run echo last-line')
        self.assertEqual(r.returncode, 0)
        self.assertIn('last-line', r.stdout)

    def test_every_metacharacter_in_the_class_is_refused_not_three_remembered_ones(self):
        for arg in ('a | tail -1', 'a;b', 'a&&b', 'a>b', 'a<b', 'a&b', 'a`id`b',
                    'a$(id)b', 'a*b', 'a?b', 'a[b]', 'a(b)', 'a{b}', 'a\\b', 'a"b', "a'b"):
            with self.subTest(arg=arg):
                quoted = "'" + arg + "'" if "'" not in arg else '"' + arg + '"'
                r = self.run_sh('run %s' % quoted)
                self.assertEqual(r.returncode, 3, (arg, r.returncode, r.stdout, r.stderr))
                self.assertIn('outside the allowed class', r.stderr)

    def test_ordinary_argv_is_accepted(self):
        r = self.run_sh('RC_OUT=/tmp/rc_sh_b.out run echo --flag=1 path/to/x.py a,b:c')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('rc=0', r.stdout)
        self.assertEqual(open('/tmp/rc_sh_b.out').read().strip(), '--flag=1 path/to/x.py a,b:c')

    def test_the_command_output_is_not_on_stdout(self):
        """A payload printed beside the rc is a second copy of the facts and will diverge silently."""
        r = self.run_sh('RC_OUT=/tmp/rc_sh_c.out run echo payload')
        self.assertNotIn('payload', r.stdout)

    def test_a_missing_command_is_a_precondition_not_a_failure(self):
        """rc 127 says the instrument was absent, which is not a verdict about the subject."""
        r = self.run_sh('run definitely-not-a-command-xyz')
        self.assertEqual(r.returncode, 3, (r.returncode, r.stdout, r.stderr))
        self.assertIn('precondition failure', r.stderr)
        # The SENTENCE is the evidence: 3 alone is also what a genuine refusal returns, and a bare number
        # cannot distinguish a transport answer from a subject verdict.
        self.assertIn('rc=3', r.stdout)

    def test_a_non_executable_file_is_also_a_precondition(self):
        r = self.run_sh("printf 'exit 0\\n' > /tmp/rc_sh_ne.sh\nrun /tmp/rc_sh_ne.sh")
        self.assertEqual(r.returncode, 3, (r.returncode, r.stdout, r.stderr))
        self.assertIn('not executable', r.stderr)


if __name__ == '__main__':
    unittest.main()
