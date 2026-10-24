"""The default tier must be the one that requires nothing the tool cannot obtain.

`--to verified` needs a review; `promote` cannot issue one and has never been handed one. So a bare
invocation must refuse for want of a family (the edge-verified tier's own requirement) rather than
attempt the verified tier over every row whose captures pass.
"""
import os
import subprocess
import sys
import unittest


class PromoteTierTest(unittest.TestCase):
    def test_the_default_tier_is_the_one_that_requires_nothing(self):
        r = subprocess.run([sys.executable, '-P', os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'tools', 'promote.py')],
            cwd='/tmp', capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=''))
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0,
                            'a bare promote must refuse: with --to verified as the default it would '
                            'attempt the tier whose precondition is a review\n' + out[-2000:])
        self.assertIn('--family', out,
                      'the refusal must name the requirement of the default tier\n' + out[-2000:])

    def test_the_verified_tier_names_its_review_requirement(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
        try:
            import promote
        finally:
            sys.path.pop(0)
        self.assertIn('review', promote.TIERS['verified'][1],
                      'the tier that needs an authority must say so in its own table')
        self.assertEqual(promote.TIERS['verified'][0], 'edge-verified')
