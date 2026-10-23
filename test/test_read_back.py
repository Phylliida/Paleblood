"""The seed's read-back: the only instrument that sees a fixture that silently missed.

`check_seeding` proves the case FILE says to seed a slot. It cannot prove the seed landed, because the
image is mapped once and mutated by every run. The failure it cannot see is quiet: the body reads zero,
the store goes to 0 + K2, the differential compares two zero-filled tails, and the row lands green.

`read_back_mismatch` takes its reader as a parameter precisely so this file can show it refusing -- a
read-back tested only against a working image is a read-back nobody has watched work.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

import harness as H

SLOT, SEED = 0x5956678 + 0x400000, (0x5956678).to_bytes(8, 'little')


def image(memory):
    """A fake mapping: addresses outside it read as zero, exactly as an unmapped slot would."""
    return lambda a, n: memory.get(a, bytes(n))


class TheSeedMustLand(unittest.TestCase):
    def test_a_landed_seed_reads_back_and_passes(self):
        self.assertIsNone(H.read_back_mismatch(image({0x1000: SEED}), [(0x1000, SEED)]))

    def test_a_seed_that_missed_is_refused_with_both_values(self):
        addr, want, got = H.read_back_mismatch(image({}), [(0x1000, SEED)])
        self.assertEqual((addr, want), (0x1000, SEED))
        self.assertEqual(got, bytes(8))          # the zero the body would have read

    def test_a_seed_that_partially_landed_is_refused(self):
        # Mutate a byte that is NOT already zero. My first version zeroed byte 7 of 0x5956678, which is
        # 0x00 anyway, so the "mutation" changed nothing and the test asserted a refusal that was not owed
        # -- a falsification that alters a byte already at that value tests exactly as much as a differential
        # that compares two zero-filled tails.
        half = bytearray(SEED)
        i = next(k for k, b in enumerate(half) if b)
        half[i] = 0
        self.assertNotEqual(bytes(half), SEED)
        out = H.read_back_mismatch(image({0x1000: bytes(half)}), [(0x1000, SEED)])
        self.assertIsNotNone(out)

    def test_every_written_range_is_checked_not_only_the_first(self):
        sentinel = bytes([0x05]) * 4
        mem = {0x1000: SEED, 0x2000: bytes(4)}   # the second write is the destination sentinel
        out = H.read_back_mismatch(image(mem), [(0x1000, SEED), (0x2000, sentinel)])
        self.assertEqual(out[0], 0x2000)


class ItIsWiredIntoTheFixturePath(unittest.TestCase):
    def test_the_harness_calls_it(self):
        import ast
        src = open(H.__file__).read()
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'read_back_mismatch']
        self.assertTrue(calls, 'the harness does not read its own fixture writes back')


if __name__ == '__main__':
    unittest.main()
