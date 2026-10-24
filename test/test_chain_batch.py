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


def live_pair(d):
    """The fixture's OWN landed (rows, bytes), read from the files it holds -- never from the real tree."""
    import landed
    land = landed.landed_addresses(os.path.join(d, 'symbols', 'functions.csv'))
    rows = [r for r in catalogue.read_rows(os.path.join(d, 'symbols', 'functions.csv'))
            if r['address'] in land]
    return len(rows), sum(int(r['size']) for r in rows)


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
        # NO LITERAL FROM THE REAL TREE APPEARS HERE. The expected total is computed from the fixture's own
        # files, and the assertion is RELATIVE to the un-edited fixture -- so the next batch to land moves
        # every real number and this test does not decay into a stale constant. (A fixture whose expected
        # value is a constant from the real tree is a test with an expiry date nobody wrote down.)
        base, edited = tree_with(), tree_with(field='size', delta=1)
        (n0, b0), (n1, b1) = live_pair(base), live_pair(edited)
        self.assertEqual((n1, b1), (n0, b0 + 1), 'the edit must be one byte and nothing else')
        p0, p1 = C.batch_problems(base), C.batch_problems(edited)
        self.assertEqual(len(p1), len(p0) + 1, f'the edit must add exactly one problem: {p1}')
        self.assertIn(f'{b1:,}', p1[-1], 'the refusal must name the fixture\'s own byte total')
        self.assertIn('bytes', p1[-1])

    def test_a_row_delta_the_batch_cannot_explain_is_refused(self):
        # `original` is the ONLY status that is not landed (landed.py: status != 'original'), so this is the
        # mutation that mutates: a row that stops being landed takes its bytes with it.
        base, edited = tree_with(), tree_with(field='status', value='original')
        (n0, b0), (n1, b1) = live_pair(base), live_pair(edited)
        self.assertEqual(n1, n0 - 1, 'the edit must defeat exactly one row')
        # THE BYTES THE ROW TOOK WITH IT, READ FROM THE FIXTURE. My first version asserted
        # `b1 == b0 - (b0 - b1)`, which is true for every possible value of b1 -- an assertion whose
        # truth is arithmetic rather than evidence, the `139 + 6,749 = 6,888` shape inside a test.
        dead = next(r for r in catalogue.read_rows(os.path.join(base, 'symbols', 'functions.csv'))
                    if r['status'] in ('edge', 'verified'))
        self.assertGreater(int(dead['size']), 0)
        self.assertEqual(b1, b0 - int(dead['size']), 'the row lost its own bytes, no others')
        p0, p1 = C.batch_problems(base), C.batch_problems(edited)
        self.assertEqual(len(p1), len(p0) + 1, f'the edit must add exactly one problem: {p1}')
        self.assertIn(f'{n1} rows', p1[-1])
        self.assertIn(f'{b1:,} bytes_landed', p1[-1], 'the row lost its bytes and the sentence must say so')


if __name__ == '__main__':
    unittest.main()
