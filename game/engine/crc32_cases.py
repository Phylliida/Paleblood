#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for the engine CRC-32 kernels, for tools/verify.py run.

usage: crc32_cases.py OUT_DIR

engine_crc32_update_byte (0x02e613c0) and engine_crc32_update (0x02e613e0) fold bytes into a
running reflected CRC-32 through the table at 0x04cdcf50. Neither produces a finished CRC on its
own: the state word is both read and written, and the caller owns both the initial value and the
final XOR with 0xffffffff. So the cases are built around two questions the disassembly answers only
by reading: whether the bulk loop agrees byte-for-byte with repeated single-byte calls, and what a
zero length does.

The table is genuine CRC-32/ISO-HDLC, so the cases check the functions against the standard
published check value (the ASCII bytes "123456789" from an initial 0xffffffff give 0xcbf43926) and
against "The quick brown fox jumps over the lazy dog" from the same start (0x414fa339). Those two
pin the polynomial, the reflection and the byte order at once; a private or mis-reflected table
would satisfy neither.

The range loop is a do/while in the original, so a zero length must leave the state untouched; a
null pointer is only reachable with a zero length, and that pair is here because it is the one input
where the loop condition is what stands between the function and a dereference it does not guard.
"""
import json
import os
import struct
import sys

ADDRESS_BYTE = '0x02e613c0'
ADDRESS_RANGE = '0x02e613e0'

MAX_CRC = 0xFFFFFFFF
REFERENCE_INIT = 0xFFFFFFFF


def state_bytes(crc):
    # Buffers are filled with the given bytes verbatim, so the word goes in little-endian memory
    # order; writing it big-endian here would silently test a byteswapped state.
    return struct.pack('<I', crc & MAX_CRC).hex()


def case_byte(cid, crc, byte, note):
    return {
        'schema': 1, 'address': ADDRESS_BYTE, 'id': cid,
        'returns': 'void',                   # the original ends in RET with no defined EAX
        # The argument registers are the full 64-bit ones; the harness zero-extends, which is what
        # the original's 32-bit reads see.
        'args': {'rdi': 'buf:state', 'rsi': f'0x{byte & 0xffffffff:x}'},
        'buffers': {'state': {'size': 4, 'bytes': state_bytes(crc)}},
        'memory': [],
        'imports': [],
        'note': note,
    }


def case_range(cid, crc, data, note, length=None):
    # The range form takes a raw pointer, so the payload lives in guest scratch and rsi carries its
    # address; buf: is the form that hands over a translated pointer.
    memory = [{'addr': 'buf:payload', 'bytes': data.hex()}]
    args = {'rdi': 'buf:state', 'rsi': 'buf:payload',
            'rdx': f'0x{len(data) if length is None else length:x}'}
    return {
        'schema': 1, 'address': ADDRESS_RANGE, 'id': cid,
        'returns': 'void',
        'args': args,
        'buffers': {
            'state': {'size': 4, 'bytes': state_bytes(crc)},
            'payload': {'size': max(len(data), 4)},
        },
        'memory': memory,
        'imports': [],
        'note': note,
    }


CHECK_DATA = b'123456789'
FOX = b'The quick brown fox jumps over the lazy dog'

CASES = [
    # --- the single-byte kernel ---
    case_byte('byte_zero_byte_zero', 0, 0, 'the identity: no state, no byte'),
    case_byte('byte_zero_byte_one', 0, 1, 'the first entry of the walk after the index'),
    case_byte('byte_one_byte_zero', 1, 0, 'a set bit in the state, which the shift drops'),
    case_byte('byte_state_all_ones', MAX_CRC, 0, 'the largest state the walk can carry'),
    case_byte('byte_byte_all_ones', 0, 0xff, 'the largest byte the index can take'),
    case_byte('byte_state_and_byte_all_ones', MAX_CRC, 0xff, 'both operands at their maximum'),
    case_byte('byte_high_bit_only', 0x80000000, 0, 'the bit the eight-bit shift removes'),
    case_byte('byte_alternating', 0xAAAAAAAA, 0x55, 'an index whose halves cancel'),

    # --- the range kernel, against single-byte calls ---
    case_range('range_empty_from_zero', 0, b'', 'zero length: the do/while must not run'),
    case_range('range_empty_from_garbage', 0xDEADBEEF, b'',
               'zero length with a non-zero state: the state must come back unchanged'),
    case_range('range_one_byte', 0, b'A', 'one byte, the same fold as the single-byte kernel'),
    case_range('range_two_bytes', 0, b'AB', 'two iterations'),
    case_range('range_four_bytes', 0, b'\x00\x01\x02\x03', 'ascending bytes'),
    case_range('range_all_zero_byte', 0, b'\x00' * 16, 'sixteen zero bytes: the index stays untested'),

    # --- the range kernel, against published CRC-32 values ---
    case_range('range_check_123456789', REFERENCE_INIT, CHECK_DATA,
               'CRC-32/ISO-HDLC check: 0xcbf43926 before the final XOR'),
    case_range('range_check_fox', REFERENCE_INIT, FOX,
               'the second standard vector: 0x414fa339 before the final XOR'),
    case_range('range_check_123456789_from_zero', 0, CHECK_DATA,
               'the same data from a zero state, to show the initial value is the caller\'s'),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    # The two kernels are separate functions, so their cases go to one directory each: verify.py
    # runs a directory against a single address and rejects a case that names another.
    for c in CASES:
        c.pop('note', None)
        out = os.path.join(sys.argv[1], c['address'])
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, f"{c['id']}.json"), 'w') as f:
            json.dump(c, f, indent=1)
    byte_n = sum(1 for c in CASES if c['address'] == ADDRESS_BYTE)
    range_n = len(CASES) - byte_n
    print(f'{byte_n} byte cases and {range_n} range cases written under {sys.argv[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
