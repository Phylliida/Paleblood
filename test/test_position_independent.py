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
# The twin of RIP, one register over: `mov rax, qword ptr fs:[0]` computes from a segment base.
# 19 B, and the fs: operand is the SECOND instruction, so the refusal names fs: and not the RIP
# operand further down -- the branch under test is the one that fires.
FS = {'function': 'leaf_fs_sample_002a69130', 'address': '0x2a69130', 'size': '19'}
UD2 = {'function': 'leaf_ud2_sample_000e6e390', 'address': '0xe6e390', 'size': '2'}
INT41 = {'function': 'leaf_int_sample_002e40da0', 'address': '0x2e40da0', 'size': '3'}


class PositionIndependence(unittest.TestCase):
    def test_a_rip_relative_leaf_is_refused(self):
        # lea rax,[rip+0x5392de1]; mov [rax],rdi; ret -- byte identity would not preserve meaning
        with self.assertRaises(SystemExit) as cm:
            R.assert_position_independent([RIP])
        self.assertIn('RIP-relative', str(cm.exception))

    def test_a_position_independent_leaf_passes(self):
        R.assert_position_independent([SAFE])

    def test_an_fs_relative_leaf_is_refused_as_dependent_on_a_base(self):
        # Byte identity here preserves the encoding and not the meaning: the differential reaches
        # a body from the host (harness.py: ctypes.CDLL then getattr(lib, name)), where %fs is the
        # host TCB, while the hook path runs the same bytes under the guest base.
        with self.assertRaises(SystemExit) as cm:
            R.assert_position_independent([FS])
        message = str(cm.exception)
        self.assertIn('fs: -relative', message)
        self.assertIn(FS['function'], message)

    def test_a_trap_is_not_a_returning_body(self):
        # decisions.md 1j (v). ud2 alone: decodes clean, no RIP, no branch, no address immediate,
        # so every earlier tooth passes it and it must be refused by the trap clause.
        with self.assertRaises(SystemExit) as cm:
            R.assert_no_trap([UD2])
        self.assertIn('ud2', str(cm.exception))

    def test_an_int_leaf_is_refused_and_named(self):
        with self.assertRaises(SystemExit) as cm:
            R.assert_no_trap([INT41])
        message = str(cm.exception)
        self.assertIn('int 0x41', message)
        self.assertIn(INT41['function'], message)

    def test_the_trap_clause_passes_a_real_leaf(self):
        R.assert_no_trap([SAFE])

    def test_the_refusal_names_the_family_member(self):
        with self.assertRaises(SystemExit) as cm:
            R.assert_position_independent([SAFE, RIP])
        self.assertIn(RIP['function'], str(cm.exception))


if __name__ == '__main__':
    unittest.main()
