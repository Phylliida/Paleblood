"""The pilot is chosen by rule: the member that exercises the most mechanisms, not the first row."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

import emit_leaf_family as E


class ThePilotIsChosenByRule(unittest.TestCase):
    def setUp(self):
        self.ms = E.members('chain_deref')

    def test_the_family_is_seventy_eight_members(self):
        self.assertEqual(len(self.ms), 78)
        self.assertEqual(len({m['address'] for m in self.ms}), 78)

    def test_the_pilot_is_the_widest_shared_key_not_the_first_address(self):
        chosen, key, n_shared = E.pilot_choice(self.ms)
        self.assertEqual(key[3], 4, 'the pilot must exercise the widest store')
        self.assertGreater(n_shared, 1, 'the pilot must share its case with another member')
        self.assertEqual(chosen['address'], 0x01735230)
        self.assertNotEqual(chosen['address'], min(m['address'] for m in self.ms),
                            '--limit 1 takes the first address; that is exactly the choice this rule rejects')

    def test_the_pilot_key_is_really_shared_by_three_rows(self):
        chosen, key, n_shared = E.pilot_choice(self.ms)
        rows = [m for m in self.ms if (m['slot'], m['k2'], m['imm'], m['width']) == key]
        self.assertEqual(n_shared, 3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['k'] for r in rows}), 3, 'three displacements, one behaviour')


if __name__ == '__main__':
    unittest.main()
