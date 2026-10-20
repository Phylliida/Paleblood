#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for bb_engine_time_over_period (0x01088550), for tools/verify.py run.

usage: time_over_period_cases.py OUT_DIR

The function reads gettimeofday, builds seconds*1000000 + microseconds as one 64-bit count and
divides it by the 64-bit period at offset 0x1d8 of the object it is given. The cases pin the two
things that are easy to get wrong:

  * the division is unsigned while the count is built signed, so a clock set before 1970 gives a
    huge quotient rather than a negative one, and no case may return a negative result;
  * the quotient is truncated, and the remainder is dropped rather than rounded or kept.

The object is a case buffer, so the period sits at its true byte offset 0x1d8 and the buffer is
long enough for it. A zero period faults (SIGFPE) on both sides, which is how the original
behaves -- it divides before it checks its stack canary.

Real inputs come from an in-game run; the values here are the boundaries a short run would not
reach on its own.
"""
import json
import os
import struct
import sys

ADDRESS = '0x01088550'
GETTIMEOFDAY = 'gettimeofday'

US_PER_SECOND = 1000000
PERIOD_OFFSET = 0x1D8
OBJECT_SIZE = 0x200


def case(cid, seconds, microseconds, period, note='', fault=''):
    tv = struct.pack('<qq', seconds, microseconds)
    obj = bytearray(OBJECT_SIZE)
    obj[PERIOD_OFFSET:PERIOD_OFFSET + 8] = struct.pack('<Q', period & 0xFFFFFFFFFFFFFFFF)
    doc = {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i64',                    # DIV: a full 64-bit unsigned quotient
        'args': {'rdi': 'buf:object'},
        'buffers': {'object': {'size': OBJECT_SIZE, 'bytes': bytes(obj).hex()}},
        'memory': [],
        'imports': [{'name': GETTIMEOFDAY, 'argc': 2, 'ret': 0,
                     'writes': [{'arg': 0, 'offset': 0, 'size': 16, 'bytes': tv.hex()}]}],
        'note': note,
    }
    if fault:
        # A case that faults declares it: a shared fault otherwise compares nothing, so tools/verify.py
        # refuses an undeclared one instead of counting it as a pass.
        doc['expected_fault'] = fault
    return doc


CASES = [
    # Zero over anything: the smallest possible quotient.
    case('zero_time', 0, 0, 1000000, 'no time has passed'),
    # A whole second against a period of one second.
    case('one_second_one_period', 1, 0, US_PER_SECOND),
    # Drop the remainder: 2.5 seconds in one-second periods is 2, not 3 and not 2.5.
    case('truncates_remainder', 2, 500000, US_PER_SECOND),
    # One microsecond short of the next whole period -- still the lower quotient.
    case('one_us_short', 2, 999999, US_PER_SECOND),
    # The microsecond field alone can carry the quotient over the line.
    case('us_tips_over', 1, 999999, US_PER_SECOND),
    case('us_exactly_one_period', 0, US_PER_SECOND, US_PER_SECOND),
    # Period larger than the time: quotient 0, smallest non-zero dividend.
    case('period_exceeds_time', 0, 1, US_PER_SECOND),
    case('period_just_under_us', 1, 0, US_PER_SECOND - 1),
    case('period_one', 1, 0, 1, 'period of one: the quotient is the count itself'),
    # Powers of two: a shift on one side of the divisor would show up as a wrong quotient here.
    case('period_pow2', 3, 141592, 1024),
    case('period_pow2_large', 12345, 678901, 1 << 20),
    # The largest quotient a bounded pair can make: far_future over the smallest non-zero period.
    case('huge_quotient', 1 << 40, 123456, 1),
    # Past Y2038 -- a signed 32-bit seconds value would have flipped long before this.
    case('past_y2038', 2147483648, 0, US_PER_SECOND),
    # The 32-bit microsecond boundary: 4295 s is where a 32-bit count overflows, so a truncated
    # dividend would give a visibly different quotient.
    case('past_32_bit_us', 4296, 1, US_PER_SECOND),
    case('at_32_bit_us', 4294, 967295, US_PER_SECOND),
    # A clock set before 1970. The count is negative, so read as unsigned it is enormous: the
    # quotient must be huge, not negative. DIV on a signed divisor would fault instead.
    case('before_epoch', -1, 0, US_PER_SECOND),
    case('one_us_before_epoch', -1, 999999, US_PER_SECOND),
    case('negative_seconds_small_period', -1000, 500000, 1000),
    # A period above 2^31: signed division would fault or go negative where unsigned divides.
    case('large_period', 1000, 0, 1 << 40),
    case('period_high_bit', 1000, 0, 1 << 63),
    # The largest period the divider can be given: the quotient is 0 or 1.
    case('period_max', 1000, 0, 0xFFFFFFFFFFFFFFFF),
    case('period_max_exact', 9223372036854, 775807, 0xFFFFFFFFFFFFFFFF),
    # A zero period faults on both sides. The original divides before it reads its stack canary,
    # so no canary report can appear on either side.
    case('period_zero', 1, 0, 0, 'division by zero: SIGFPE on both sides', fault='signal 8'),
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
