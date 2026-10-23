"""The seeding gate's three links, each shown to refuse and one shown to pass.

The passing case is the positive control: without it, four refusals would be four ways for the gate
to be broken. And the refusal texts are asserted to NAME their link, because a gate that refuses for
an unnamed reason is a gate whose next reader re-derives it.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

import check_seeding as C

RW = (0x54dc000, 0x5f70f4)          # the RW PT_LOAD's guest base and memsz, from the program headers
SLOT = 0x5400000
ROW = {'address': 0x2426450, 'load_target': SLOT, 'store_k2': 0x100, 'store_width': 4, 'imm': 0x0}


def case(*memory):
    return {'memory': list(memory)}


GOOD = case({'addr': f'{SLOT:#x}', 'guest': '0x5500000'},
            {'addr': '0x5500100', 'bytes': '05050505'})


class TheThreeLinks(unittest.TestCase):
    def test_a_case_that_satisfies_all_three_links_passes(self):
        self.assertEqual(C.check(ROW, GOOD, RW, 0x05), [])

    def test_link_1_refuses_a_slot_the_case_never_wrote(self):
        out = C.check(ROW, case({'addr': '0x5500100', 'bytes': '05050505'}), RW, 0x05)
        self.assertTrue(out and out[0].startswith('link 1:'), out)

    def test_link_2_refuses_a_sandbox_pointer_naming_the_space_rule(self):
        out = C.check(ROW, case({'addr': f'{SLOT:#x}', 'pointer': 'buf:x'},
                                {'addr': '0x5500100', 'bytes': '05050505'}), RW, 0x05)
        self.assertTrue(out and 'sandbox' in out[0] and 'snapshot()' in out[0], out)

    def test_link_2_refuses_a_destination_past_memsz(self):
        v = f'{RW[0] + RW[1] - 0x100:#x}'
        out = C.check(ROW, case({'addr': f'{SLOT:#x}', 'guest': v},
                                {'addr': f'{RW[0] + RW[1] + 4:#x}', 'bytes': '05050505'}), RW, 0x05)
        self.assertTrue(any('outside the writable segment' in s for s in out), out)

    def test_link_3_refuses_an_unseeded_destination(self):
        out = C.check(ROW, case({'addr': f'{SLOT:#x}', 'guest': '0x5500000'}), RW, 0x05)
        self.assertTrue(any(s.startswith('link 3:') and 'zero to zero' in s for s in out), out)

    def test_link_3_refuses_a_destination_that_is_not_the_sentinel(self):
        out = C.check(ROW, case({'addr': f'{SLOT:#x}', 'guest': '0x5500000'},
                                {'addr': '0x5500100', 'bytes': '00000000'}), RW, 0x05)
        self.assertTrue(any('not the sentinel' in s for s in out), out)


class TheSentinelIsDerived(unittest.TestCase):
    def test_it_skips_every_immediate_the_family_holds(self):
        rows = [dict(ROW, imm=i, store_width=1) for i in (0x0, 0x1, 0x2, 0x3, 0x4, 0x8, 0xa, 0xf, 0xff)]
        self.assertEqual(C.derive_sentinel(rows)[0], 0x05)

    def test_a_family_storing_0xa5_gets_a_different_sentinel_not_a_failure(self):
        rows = [dict(ROW, imm=i, store_width=1) for i in range(0x0, 0x10)] + [dict(ROW, imm=0xa5, store_width=1)]
        self.assertEqual(C.derive_sentinel(rows)[0], 0x10)


if __name__ == '__main__':
    unittest.main()
