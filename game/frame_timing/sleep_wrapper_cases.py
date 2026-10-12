#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_sleep (0x0111a880), for tools/verify.py run.

usage: sleep_wrapper_cases.py OUT_DIR

The function multiplies its argument by 1000 and calls sceKernelUsleep with the product, then
returns 0 whatever that call returned. Its only observable effect is that one call, so the cases
pin down the nanosecond count the stub receives: the microsecond-to-nanosecond conversion, its
32-bit wrap (which the zero-extension into the stub's argument register does not undo), and that
the kernel call's own return value is discarded rather than passed through.

The 20 callers are the back-off sleeps of the middleware timing path (0x0110e...-0x0121b...); the
arguments they pass are not known, so these cover the arithmetic rather than one call site.
"""
import json
import os
import sys

ADDRESS = '0x0111a880'
USLEEP = 'sceKernelUsleep'

NS_PER_US = 1000
MAX_UNWRAPPED_US = 0xFFFFFFFF // NS_PER_US


def case(cid, microseconds, ret=0):
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i64',                    # XOR EAX,EAX: 0 either way
        'args': {'rdi': f'0x{microseconds & 0xffffffff:x}'},
        'buffers': {},
        'memory': [],
        'imports': [{'name': USLEEP, 'argc': 1, 'ret': ret}],
    }


CASES = [
    case('zero', 0),
    case('one_us', 1),
    case('one_ms', 1000),
    case('one_second', 1000000),
    # The wrap boundary: the last argument whose nanosecond count survives 32 bits, and the first
    # that does not.
    case('last_unwrapped', MAX_UNWRAPPED_US),
    case('first_wrapped', MAX_UNWRAPPED_US + 1),
    # 2**32 us is exactly one full turn of the 32-bit product, so the stub sees 0 ns.
    case('full_turn_to_zero', 0x1000000),
    case('high_bit', 0x80000000),
    case('max_argument', 0xFFFFFFFF),
    # The kernel call fails; the function still returns 0, which is what tells this apart from a
    # wrapper that passes the result through.
    case('usleep_fails', 1000, ret=0x80020016),
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
