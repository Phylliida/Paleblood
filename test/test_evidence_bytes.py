"""The evidence kind lives in the row's `cases` field, not in the ladder status.

`original | edge-verified | verified` is a partition; a fourth status would make `edge-verified`
mean "a differential ran" for some rows and "the bytes were compared" for others. So the new tier
is a case-set value, and these tests hold the two properties that makes it work: it is accepted,
and it moves the evidence hash, so an approval cannot survive a change in what backs it.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import verification as V  # noqa: E402

HEADER = ','.join(V.VERIFICATION_HEADER) + '\n'
DIGEST = '70aaace800000000'


def row(cases):
    return f'f_0001,{cases},,3,3,0,0,hand,{DIGEST},2026-01-01\n'


class EvidenceKindTest(unittest.TestCase):
    def _hash(self, cases):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'symbols'))
            with open(os.path.join(root, 'symbols', 'verification.csv'), 'w') as f:
                f.write(HEADER + row(cases))
            return V.evidence_hash(root, 'f_0001')

    def test_bytes_is_accepted_as_an_evidence_kind(self):
        self.assertIn('bytes', V.CASE_SETS)

    def test_changing_the_evidence_kind_moves_the_hash(self):
        # The direction that matters: an approval recorded against a differential must NOT survive
        # the row being re-recorded as a byte comparison, because that is a different claim.
        differential, bytewise = self._hash('edge'), self._hash('bytes')
        self.assertTrue(differential and bytewise, 'both kinds must hash, not degrade to empty')
        self.assertNotEqual(differential, bytewise,
                            'the evidence kind must be inside the hash, or an approval outlives '
                            'a change in what backs it')

    def test_an_unknown_kind_is_still_refused(self):
        with self.assertRaises(ValueError):
            V.record_many('/nonexistent', [{'function': 'f', 'cases': 'byts'}])


if __name__ == '__main__':
    unittest.main()
