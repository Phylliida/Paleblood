import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import emit_byte_leaves as E  # noqa: E402


class TheAskRefusesUntilRatified(unittest.TestCase):
    """The .byte emitter is the ASK; its refusal is the thing being tested, in both directions.

    There is deliberately NO test asserting today's tree state: a fixture that hardcodes "not yet
    ratified" has an expiry date (the hour the user ratifies it, it reddens for the wrong reason).
    """

    def test_absent_authorises_nothing(self):
        self.assertFalse(E.authorised('# nothing authorising anything\n'))

    def test_a_proposal_does_not_authorise(self):
        self.assertFalse(E.authorised('### 1j — PROPOSED, NOT IN FORCE: .byte bodies\n'))

    def test_prose_quoting_the_heading_does_not_authorise(self):
        # the first version of this guard was defeated by exactly this line
        self.assertFalse(E.authorised('the tool looks for `### 1j.` in the decisions file\n'))

    def test_a_ratified_heading_authorises(self):
        self.assertTrue(E.authorised('### 1j. byte bodies for the leaf tier\n'))


if __name__ == '__main__':
    unittest.main()
