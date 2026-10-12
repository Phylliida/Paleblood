#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for bb_engine_time_id (0x02e61280), for tools/verify.py run.

usage: time_id_cases.py OUT_DIR

The function reads gettimeofday and returns a 128-bit stamp in RAX:RDX, salting both halves with
a process-wide counter it bumps by two:

    RAX = u32(seconds) | u64(u32(microseconds)) << 32
    RDX = u32(counter + seconds) | u64(u32(counter + 1 + microseconds)) << 32

Both halves are built from 32-bit halves of the timeval, so a timeval past 2^32 microseconds
truncates rather than carrying, and the counter wrap is taken in 32 bits as well. The cases pin
those boundaries.

0x0570d83c and 0x057e3be0 are words the harness also uses: the first holds the address of the
counter the function salts its result with, and the second is the stack-cookie slot, which the
harness fills with its own import-data pointer. Seeding either would fight the harness rather
than the function, so the cases below seed only the counter itself and leave both slots as the
harness left them. The original dereferences the cookie slot but only compares the value against
the copy it saved at entry, so the cookie never reaches either half of the result.

Real inputs come from an in-game run; the values here are the boundaries a short run would not
reach on its own.
"""
import json
import os
import struct
import sys

ADDRESS = '0x02e61280'
GETTIMEOFDAY = 'gettimeofday'

COUNTER_ADDR = 0x0570D83C          # the counter the result is salted with


def case(cid, seconds, microseconds, counter, note=''):
    """One case: the stubbed clock and the seeded counter."""
    tv = struct.pack('<qq', seconds, microseconds)
    counter_bytes = struct.pack('<Q', counter & 0xFFFFFFFFFFFFFFFF)
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i128',                   # RAX:RDX
        'args': {'rdi': 0, 'rsi': 0},
        'memory': [
            {'addr': hex(COUNTER_ADDR), 'bytes': counter_bytes.hex()},
        ],
        'imports': [{'name': GETTIMEOFDAY, 'argc': 2, 'ret': 0,
                     'writes': [{'arg': 0, 'offset': 0, 'size': 16, 'bytes': tv.hex()}]}],
        'note': note,
    }


CASES = [
    # The smallest stamp: nothing has happened and the counter wraps to zero.
    case('zero', 0, 0, 0xFFFFFFFE, 'counter wraps to 0 in the low half'),
    case('epoch', 0, 0, 0),
    # A plain reading, one second past the epoch.
    case('one_second', 1, 0, 1),
    case('one_us', 0, 1, 0),
    # The counter is added to both halves, and the high half gets one more.
    case('counter_carries', 0, 0xFFFFFFFF, 1, 'microsecond half carries into the counter sum'),
    case('counter_high_wrap', 0, 0xFFFFFFFF, 0xFFFFFFFF, 'both halves wrap together'),
    # The microsecond field is truncated to 32 bits, so a timeval past 2^32 us drops the excess.
    case('past_32_bit_us', 4296, 1, 0, 'seconds past the 32-bit microsecond span'),
    case('at_32_bit_us', 4294, 967295, 0),
    # Microseconds that already exceed a second: the function does not normalise them.
    case('us_over_a_second', 5, 1000001, 0, 'microseconds are not normalised'),
    # Seconds past Y2038 -- the halves are 32-bit, so only the low word may appear.
    case('past_y2038', 2147483648, 0, 0, 'low 32 bits of seconds: 0x80000000'),
    case('seconds_high_word', 0x1FFFFFFFF, 0, 0, 'only the low word of seconds reaches RAX'),
    # A clock set before 1970: the low half of a negative second is still just its low word.
    case('before_epoch', -1, 0, 0, 'seconds -1 reads as 0xffffffff'),
    case('before_epoch_us', -1, -1, 0),
    # Counter values that push each half over its own 32-bit edge.
    case('counter_low_edge', 1, 1, 0xFFFFFFFE),
    case('counter_mid', 0x11223344, 0x55667788, 0x99AABBCC),
    case('counter_max', 0, 0, 0xFFFFFFFF),
    case('counter_zero_seconds_max', 0xFFFFFFFF, 0xFFFFFFFF, 0),
    # The largest low words both halves can hold.
    case('all_ones', 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF),
    # The counter is read and bumped before anything else, so a second call must salt with the
    # value the first one left behind; this case records the value one call sees.
    case('counter_odd', 3, 7, 0x12345679),
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
