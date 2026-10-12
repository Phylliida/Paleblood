#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for kernel_pending_code (0x004663f0), for tools/verify.py run.

usage: pending_code_cases.py OUT_DIR

The function reads two words of a caller-owned object and returns one code. Both words are seeded
with sentinels whose byte patterns are distinctive, so the whole 0x38-byte object is compared and
any write at all -- including a partial one -- shows up as a difference.

The two comparisons that matter are signedness, on both words:

  * +0x34 is tested with JG, so only a value strictly greater than zero selects code 2. The cases
    walk zero, both directions away from it, and the largest positive value; `0x7fffffff` is the
    boundary the test can still see, and `0x80000000` is the first one it cannot.
  * bit 0 of +0x30 is taken with AND, so an odd value gives 1 and an even one 0, whatever the rest
    of the word holds.

Returns i64 rather than i32, so the high half of RAX is compared too: the original's two returns
are `mov eax,0x2` and a 32-bit `mov eax`, both zero-extending, and a replacement that returned a
stale or sign-extended upper half would be caught here and not by an i32 comparison.
"""
import json
import os
import sys

ADDRESS = '0x004663f0'

IDENTITY_OFFSET = 0x30
PENDING_OFFSET = 0x34
OBJECT_SIZE = 0x38


def object_bytes(identity, pending):
    """The caller's object: sentinels everywhere except the two words under test."""
    buf = bytearray(b'\x5a' * OBJECT_SIZE)
    buf[0x00:0x04] = b'\x11\x22\x33\x44'
    buf[0x08:0x10] = b'\xde\xad\xbe\xef\xca\xfe\xba\xbe'
    buf[IDENTITY_OFFSET:IDENTITY_OFFSET + 4] = (identity & 0xffffffff).to_bytes(4, 'little')
    buf[PENDING_OFFSET:PENDING_OFFSET + 4] = (pending & 0xffffffff).to_bytes(4, 'little')
    return bytes(buf)


def case(cid, identity, pending):
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid, 'returns': 'i64',
        'args': {'rdi': 'buf:object'},
        'buffers': {'object': {'size': OBJECT_SIZE, 'bytes': object_bytes(identity, pending).hex()}},
    }


CASES = [
    # Nothing in flight: the answer is bit 0 of the identity word.
    case('idle_identity_zero', 0x00000000, 0),
    case('idle_identity_one', 0x00000001, 0),
    case('idle_identity_even_high_bits', 0xfffffffe, 0),
    case('idle_identity_odd_high_bits', 0xffffffff, 0),
    case('idle_identity_bit0_only', 0x00000001, 0),
    case('idle_identity_high_bit_only', 0x80000000, 0),
    # The idle path must ignore every bit above bit 0.
    case('idle_identity_bit1_only', 0x00000002, 0),
    case('idle_identity_all_bits_but_0', 0xfffffffe, 0),

    # Something in flight: the identity word is not consulted at all.
    case('pending_one', 0x00000000, 1),
    case('pending_one_identity_odd', 0x00000001, 1),
    case('pending_max_positive', 0x00000000, 0x7fffffff),
    case('pending_small', 0x00000000, 2),

    # The signedness of +0x34. A JG test rejects both of these and falls through to the identity
    # word; an unsigned JA test would answer 2 for both.
    case('pending_negative_one', 0x00000001, -1),
    case('pending_negative_min', 0x00000001, -0x80000000),
    # And this is the last pending value the signed test can still see as positive.
    case('pending_above_negative_but_positive', 0xfffffffe, 0x7fffffff),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    os.makedirs(sys.argv[1], exist_ok=True)
    for c in CASES:
        with open(os.path.join(sys.argv[1], f"{c['id']}.json"), 'w') as f:
            json.dump(c, f, indent=1)
    print(f'{len(CASES)} cases written to {sys.argv[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
