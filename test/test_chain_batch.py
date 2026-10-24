"""The batch's pre-registration: right on the real tree, and refusing where a delta is not the batch.

Before the run the live state is exactly the pre-registered state minus the batch; after it, exactly the
pre-registered state. Anything else is a different family, and the check must say so rather than print a
number that looks like progress.
"""
import csv
import os
import shutil
import sys
import tempfile
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import catalogue
import chain_family as C
from mutate import replace_field


def tree_with(**edit):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'symbols'))
    for f in ('functions.csv', 'branch_band.csv.gz'):
        shutil.copy(os.path.join(ROOT, 'symbols', f), os.path.join(d, 'symbols', f))
    # A FIXTURE THAT CANNOT REPRESENT THE QUANTITY ITS TEST IS ABOUT IS A FORMATTER. Without `game/` the
    # fixture's byte total is 0, so the two-state refusal fired on BOTH delta tests *and on the un-edited
    # tree*, identically -- the edits were decoration. Symlinked, not copied: the bytes are read from the
    # real bodies, so the fixture differs from the real tree in exactly the field the test edits.
    os.symlink(os.path.join(ROOT, 'game'), os.path.join(d, 'game'))
    if edit:
        path = os.path.join(d, 'symbols', 'functions.csv')
        rows = list(catalogue.read_rows(path))
        header = list(rows[0].keys())
        for r in rows:
            if r['status'] in ('edge', 'verified'):
                # replace_field refuses if the value is already there; no separate assertion needed
                if edit['field'] == 'size':
                    r[edit['field']] += edit['delta']
                else:
                    replace_field(r, edit['field'], edit['value'], 'landed row')
                break
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
    return d


class TheBatchIsPreRegistered(unittest.TestCase):
    def test_the_real_tree_owes_exactly_the_batch(self):
        # owed == 0 ==> no refusal: the property, at every point in the record's life. (unittest's diff shows
        # the FIRST argument with '-', so a '-' refusal and a '+' [] means the tool refused, not the test.)
        self.assertEqual(C.batch_problems(ROOT), [])

    def test_the_fixture_itself_is_clean(self):
        # THE CONTROL, AND IT MUST EXIST BEFORE THE TWO TESTS BELOW MEAN ANYTHING: an un-edited fixture must
        # produce no problem. It refused before this line existed -- for a reason (game/ absent, bytes 0)
        # that had nothing to do with either edit, which made both delta tests pass while discriminating
        # nothing.
        self.assertEqual(C.batch_problems(tree_with()), [])

    def test_a_byte_delta_the_batch_cannot_explain_is_refused(self):
        problems = C.batch_problems(tree_with(field='size', delta=1))
        self.assertEqual(len(problems), 1)
        self.assertIn('bytes', problems[0])

    def test_a_row_delta_the_batch_cannot_explain_is_refused(self):
        # `original` is the ONLY status that is not landed (landed.py: status != 'original'), so this is the
        # mutation that mutates. My first version wrote 'unknown' -- still landed -- and demanded a refusal
        # that was not owed: a mutation carries an assertion that it mutated.
        problems = C.batch_problems(tree_with(field='status', value='original'))
        # Two arms fire, correctly: defeating a row also removes its bytes (670 B), so the byte check
        # refuses too. Asserting exactly one problem was my assertion being narrower than the truth.
        self.assertGreaterEqual(len(problems), 1)
        self.assertTrue(any('landed' in p for p in problems))


if __name__ == '__main__':
    unittest.main()
