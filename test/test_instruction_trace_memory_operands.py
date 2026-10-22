"""A memory *operand* is not a memory *access*.

The tracer classified every explicit memory operand as an access, so a multi-byte nop
(`nop DWORD PTR [rax+0x0]`) was reported as reading through rax. It only surfaced because the
computed address was zero and unmapped; for `lea rax,[rip+K]` the address lands inside the
image and the tracer silently counted it. LEA was already special-cased; the class is
"instructions that never touch memory", not "the one instruction I happened to notice".
"""
import unittest

from instruction_trace import Capstone


class MemoryOperandClassification(unittest.TestCase):
    def setUp(self):
        self.cap = Capstone()

    def test_multi_byte_nop_performs_no_access(self):
        d = self.cap.decode(0x1000, bytes.fromhex('0f1f8000000000'))
        self.assertEqual(d['mnemonic'], 'nop')
        self.assertEqual(d['operands'], [], 'a nop carries a memory operand but accesses nothing')
        self.assertTrue(d['address_calculation'])

    def test_prefetch_performs_no_access(self):
        d = self.cap.decode(0x1000, bytes.fromhex('0f1800'))
        self.assertEqual(d['operands'], [], 'prefetch hints do not access memory')

    def test_lea_performs_no_access(self):
        d = self.cap.decode(0x1000, bytes.fromhex('488d0500000000'))
        self.assertEqual(d['operands'], [])
        self.assertTrue(d['address_calculation'])

    def test_a_real_load_still_records_its_access(self):
        d = self.cap.decode(0x1000, bytes.fromhex('8b00'))
        self.assertEqual(len(d['operands']), 1, 'the control: a real load must keep its operand')
        self.assertFalse(d['address_calculation'])


if __name__ == '__main__':
    unittest.main()
