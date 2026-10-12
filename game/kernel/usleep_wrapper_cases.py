#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for kernel_usleep (0x00466810), for tools/verify.py run.

usage: usleep_wrapper_cases.py OUT_DIR

The function multiplies its argument by 1000 and calls libc usleep with the product, then returns
1. Its only observable effect is that one call, so the cases pin down the nanosecond count the
stub receives: the microsecond-to-nanosecond conversion, its 32-bit wrap (which the zero-extension
into the stub's argument register does not undo), and the return value 1, which is the game's
convention and not libc's 0.

The game only ever calls this with a constant 10 (0x00719aa0, 0x00719d6e), so the wrap cases are
extrapolation beyond any input the game produces; they are here because the multiplication is the
whole function.
"""
import json
import os
import sys

ADDRESS = '0x00466810'
USLEEP = 'usleep'

NS_PER_US = 1000
MAX_UNWRAPPED_US = 0xFFFFFFFF // NS_PER_US


def case(cid, microseconds):
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i32',                    # MOV EAX,0x1: the whole register, not just AL
        'args': {'rdi': f'0x{microseconds & 0xffffffff:x}'},
        'buffers': {},
        'memory': [],
        'imports': [{'name': USLEEP, 'argc': 1, 'ret': 0}],
    }


CASES = [
    # The argument the game passes, and the ordinary range around it.
    case('zero', 0),
    case('one_us', 1),
    case('game_argument', 10),
    case('hundred_us', 100),
    case('just_below_second', 999999),
    case('one_second', 1000000),
    # The wrap boundary: the last argument whose nanosecond count survives 32 bits, and the first
    # that does not.
    case('last_unwrapped', MAX_UNWRAPPED_US),
    case('first_wrapped', MAX_UNWRAPPED_US + 1),
    case('wrap_to_small', MAX_UNWRAPPED_US + 100),
    # 2**32 us is exactly one full turn of the 32-bit product, so the stub sees 0 ns.
    case('full_turn_to_zero', 0x1000000),
    case('two_turns', 0x2000000),
    # The extremes of the 32-bit argument.
    case('high_bit', 0x80000000),
    case('max_argument', 0xFFFFFFFF),
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
