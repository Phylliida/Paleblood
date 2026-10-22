"""The axes are named before any run can produce a number on one of them.

`runtime-witnessed` is observation, not equivalence: a hook firing proves the body ran, and one
execution cannot compare a replacement with an original. If it ever becomes a `status` value the first
capture is quotable as progress, so this test makes that edit fail rather than argue about it later.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import validate_functions


class CoverageAxes(unittest.TestCase):
    def test_runtime_witness_is_not_a_status(self):
        self.assertNotIn('runtime-witnessed', validate_functions.STATUSES,
                         'a fired hook is a witness, not a differential: it must not be a status value')

    def test_the_status_vocabulary_is_the_two_evidence_axes(self):
        self.assertEqual(validate_functions.STATUSES,
                         ('original', 'replaced', 'edge-verified', 'verified'))

    def test_the_definition_exists_and_names_all_three(self):
        with open(os.path.join(ROOT, 'docs', 'coverage-axes.md')) as f:
            text = f.read()
        for axis in ('edge-verified', 'verified', 'runtime-witnessed'):
            self.assertIn(axis, text)
        self.assertIn('anything about equivalence', text)


if __name__ == '__main__':
    unittest.main()
