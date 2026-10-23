"""Every gate that owns a shrink-only allowlist must actually be INVOKED by the hook.

This exists because one was not. `check_catalogue.py` had a shrink-only allowlist, a rosters.compare
in both directions, and 55 grandfathered files -- and the pre-commit hook never ran it. What the hook
printed was `progress.py`'s own DictReader count, in a line shaped like a verdict, so a raw
`csv.DictReader` in a new file passed with rc=0. **A gate that exists and is not invoked is a gate
nobody runs, and a number that looks like its verdict is worse than no number.**
"""
import os
import re
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'hooks', 'pre-commit')

# The gates whose baselines may only shrink. Each one must appear as an invocation, not as prose:
# the header comment names them too, and naming is not running.
SHRINK_ONLY = ('check_catalogue.py', 'check_readable.py')


class TheHookRunsWhatItNames(unittest.TestCase):
    def setUp(self):
        self.text = open(HOOK).read()

    def test_every_shrink_only_gate_is_invoked_not_merely_named(self):
        for gate in SHRINK_ONLY:
            with self.subTest(gate=gate):
                invoked = re.search(r'^\s*python3 [^\n]*' + re.escape(gate), self.text, re.M)
                self.assertIsNotNone(invoked, f'{gate} is not invoked by the pre-commit hook')
                self.assertIn(f'$tmp/tools/{gate}', invoked.group(0),
                              f'{gate} must run against the staged tree under $tmp, not the worktree')

    def test_the_header_list_and_the_invocations_agree(self):
        named = set(re.findall(r'tools/(check_[a-z_]+\.py)', self.text))
        invoked = set(re.findall(r'python3 [^\n]*tools/(check_[a-z_]+\.py)', self.text))
        self.assertEqual(named - invoked, set(),
                         'these gates are named in the hook but never run: %s' % (named - invoked))


if __name__ == '__main__':
    unittest.main()
