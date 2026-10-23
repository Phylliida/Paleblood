"""The helper that makes a wasted falsification unrepresentable, and the refusals that prove it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

from mutate import mutate, mutate_hex, replace_field

SEED = (0x5956678).to_bytes(8, 'little')


class AMutationMustMutate(unittest.TestCase):
    def test_a_real_mutation_changes_exactly_one_byte(self):
        out = mutate(SEED, 3, 0xff)
        self.assertEqual(out[3], 0xff)
        self.assertEqual(len(out), len(SEED))
        self.assertEqual(sum(a != b for a, b in zip(out, SEED)), 1)

    def test_the_original_is_not_mutated_in_place(self):
        before = bytes(SEED)
        mutate(SEED, 3, 0xff)
        self.assertEqual(bytes(SEED), before)

    def test_mutating_to_the_value_already_there_is_refused_with_its_reason(self):
        with self.assertRaises(AssertionError) as cm:
            mutate(SEED, 7, 0, 'seed')
        self.assertIn('already 0x00', str(cm.exception))
        self.assertIn('nothing to test', str(cm.exception))

    def test_an_offset_outside_the_subject_is_refused(self):
        with self.assertRaises(AssertionError) as cm:
            mutate(SEED, len(SEED), 0xff)
        self.assertIn('outside', str(cm.exception))

    def test_the_same_rule_for_a_case_files_hex_bytes(self):
        self.assertEqual(mutate_hex('001100', 1, 0x22), '002200')
        with self.assertRaises(AssertionError):
            mutate_hex('000000', 0, 0)

    def test_the_same_rule_for_a_structured_fixture(self):
        row = {'status': 'edge'}
        self.assertEqual(replace_field(row, 'status', 'original')['status'], 'original')
        with self.assertRaises(AssertionError) as cm:
            replace_field({'status': 'unknown'}, 'status', 'unknown')
        self.assertIn('nothing to test', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
