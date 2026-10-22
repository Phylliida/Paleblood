import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import record_bytes_family as R  # noqa: E402

# Two real single-block leaves, both verified by tools/blocks.py: one whose value depends on where
# it sits (RIP-relative), one that is position independent. The guard must refuse the first and
# pass the second -- a guard proved only by its acceptance is not proved.
RIP = {'function': 'leaf_rip_sample_00454310', 'address': '0x454310', 'size': '11'}
SAFE = {'function': 'leaf_safe_sample_004002f0', 'address': '0x4002f0', 'size': '14'}


class PositionIndependence(unittest.TestCase):
    def test_a_rip_relative_leaf_is_refused(self):
        # lea rax,[rip+0x5392de1]; mov [rax],rdi; ret -- byte identity would not preserve meaning
        with self.assertRaises(SystemExit) as cm:
            R.assert_position_independent([RIP])
        self.assertIn('RIP-relative', str(cm.exception))

    def test_a_position_independent_leaf_passes(self):
        R.assert_position_independent([SAFE])

    def test_the_refusal_names_the_family_member(self):
        with self.assertRaises(SystemExit) as cm:
            R.assert_position_independent([SAFE, RIP])
        self.assertIn(RIP['function'], str(cm.exception))


if __name__ == '__main__':
    unittest.main()
