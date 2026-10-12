#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_get_wall_time_us (0x02e61140), for tools/verify.py run.

usage: get_time_us_cases.py OUT_DIR

The function reads gettimeofday and returns seconds*1000000 + microseconds as one 64-bit value.
The cases pin down that width: the arithmetic is 64-bit on both sides of the add, so a time near
the 1970 epoch and a time far past 2038 both survive without truncation or sign flip, which is
exactly what separates this from the 32-bit monotonic clocks. A negative seconds (a clock set
before 1970) must stay negative.

Real inputs come from an in-game run; the values here are the boundaries a short run would not
reach on its own.
"""
import json
import os
import struct
import sys

ADDRESS = '0x02e61140'
GETTIMEOFDAY = 'gettimeofday'

US_PER_SECOND = 1000000


def case(cid, seconds, microseconds):
    tv = struct.pack('<qq', seconds, microseconds)
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i64',                    # IMUL/ADD on RAX: a full 64-bit signed count
        'args': {},
        'buffers': {},
        'memory': [],
        'imports': [{'name': GETTIMEOFDAY, 'argc': 2, 'ret': 0,
                     'writes': [{'arg': 0, 'offset': 0, 'size': 16, 'bytes': tv.hex()}]}],
    }


CASES = [
    case('epoch', 0, 0),
    # A whole second, and the microsecond field at both of its ends.
    case('one_second', 1, 0),
    case('last_us_of_second', 1000, 999999),
    case('first_us_of_second', 1001, 0),
    # The 32-bit truncation boundary: 4295 s is where a 32-bit count of microseconds overflows.
    # This one must not wrap, which is what the 64-bit IMUL buys.
    case('past_32_bit_us', 4295, 0),
    case('just_past_32_bit_us', 4296, 1),
    # The Y2038 boundary: a signed 32-bit seconds value flips here, the product must not.
    case('y2038', 2147483647, 999999),
    case('past_y2038', 2147483648, 0),
    # A time far beyond any 32-bit microsecond count.
    case('far_future', 1 << 40, 123456),
    # A clock set before 1970: the count stays negative instead of wrapping positive.
    case('before_epoch', -1, 0),
    case('one_us_before_epoch', -1, 999999),
    case('negative_seconds', -1000, 500000),
    # The largest bounded pair: the product must not overflow a signed 64-bit result.
    case('max_bounded', 9223372036854, 775807),
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
