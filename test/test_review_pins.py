"""symbols/reviews.csv pins: an approval that cannot be checked is not an approval.

The fail-open this closes: review_pin_errors() skipped the comparison when the *current* hash was
empty, so a review whose replacement source had been deleted compared against nothing and passed.
Absence refuses now -- the same shape as the empty-HEAD stamp in verification.record().
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import validate_functions as vf
import verification


class ReviewPinsRefuseAbsence(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, 'symbols'))
        self.func = {'name': 'nothing_defines_me', 'status': 'verified', '_line': 2}

    def tearDown(self):
        shutil.rmtree(self.root)

    def review(self, **kw):
        row = {'source_hash': '', 'cases_sha256': '', '_line': 7}
        row.update(kw)
        return row

    def test_a_pin_against_a_replacement_this_tree_does_not_have_is_refused(self):
        errs = vf.review_pin_errors(self.root, self.func,
                                    self.review(source_hash='0123456789abcdef'))
        self.assertTrue([e for e in errs if 'cannot be checked' in e], errs)

    def test_unavailable_is_how_a_person_says_they_could_not_pin_it(self):
        errs = vf.review_pin_errors(self.root, self.func,
                                    self.review(source_hash=verification.CASES_UNAVAILABLE,
                                                cases_sha256=verification.CASES_UNAVAILABLE))
        self.assertEqual([], errs)

    def test_the_fail_open_is_gone_an_absent_current_hash_and_no_pin_is_two_errors(self):
        # before: `if not current: continue` made this row pass with nothing compared at all
        self.assertEqual(2, len(vf.review_pin_errors(self.root, self.func, self.review())))
