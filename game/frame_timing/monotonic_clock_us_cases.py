#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_get_monotonic_us (0x0111a760), for tools/verify.py run.

usage: monotonic_clock_us_cases.py OUT_DIR

Writes one case file per situation: first call, later calls, the nanosecond truncation boundaries
that separate microseconds from milliseconds, seconds wrapping and truncation, and a failing
clock. Real inputs come from an in-game run with BB_CAPTURE_DIR set (the replacement records
them); these cover what a short run does not.
"""
import json
import os
import struct
import sys

ADDRESS = '0x0111a760'
CLOCK_STATE_POINTER = '0x056d6ae8'


def case(cid, base, sec, nsec, ret=0):
    state = bytes(16) + struct.pack('<I', base & 0xffffffff)
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid, 'returns': 'i32',
        'args': {'rdi': 'buf:out'},
        'buffers': {'out': {'size': 4, 'bytes': 'a5a5a5a5'}, 'state': {'size': 20, 'bytes': state.hex()}},
        'memory': [{'addr': CLOCK_STATE_POINTER, 'pointer': 'state'}],
        'imports': [{'name': 'sceKernelClockGettime', 'argc': 2, 'ret': ret,
                     'writes': [{'arg': 1, 'offset': 0, 'size': 16,
                                 'bytes': struct.pack('<qq', sec, nsec).hex()}]}],
    }


CASES = [
    case('first_call', 0, 1000, 123456789),
    case('later_call', 1000, 1005, 250000000),
    case('same_second', 1000, 1000, 0),
    # 999 ns truncates to 0 us, and 1000 ns is the first microsecond: a millisecond clock would
    # report 0 for both.
    case('nsec_below_us', 1000, 1000, 999),
    case('nsec_one_us', 1000, 1000, 1000),
    # Still 0 ms but 999 us, which is what tells the two clocks' scales apart.
    case('nsec_just_below_ms', 1000, 1001, 999999),
    case('nsec_just_above_ms', 1000, 1001, 1000000),
    case('nsec_max', 1000, 1001, 999999999),
    case('seconds_before_base', 2000, 1999, 500000000),
    case('long_uptime_wrap', 1, 4294968, 0),
    case('seconds_above_32_bits', 7, (1 << 32) + 9, 1000000),
    case('negative_base', -5, 3, 1000000),
    # 4295 s of difference times 1000000 overflows 32 bits and wraps, as in the original.
    case('elapsed_overflow_32_bits', 0, 4295, 0),
    case('clock_fails', 1000, 0, 0, ret=0x80020016),
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
