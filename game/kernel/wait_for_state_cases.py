#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for kernel_wait_for_state (0x024bdd40), for tools/verify.py run.

usage: wait_for_state_cases.py OUT_DIR

The function polls the 32-bit word at offset 0x10 of its argument until it reads 2, calling the
microsecond sleep with a fixed 1000 once per poll. Its only means of changing that word is the
sleep call between polls, so each case says what the sleep leaves behind, in order: one scripted
call per poll, and the loop re-reads after every one.

The state word lives in a case buffer, and the scripted write names it with `target`. The earlier
draft of these cases pointed the function at a spare spot in the image and wrote through a
register the stub had left alone. That cannot work, and the reason is a rule rather than a bug: a
scripted write must land in memory the guest may write, and the image's first segment is
read+execute -- it holds the code, so a case writing there is the harness doing something the
game never could. `memory` presets reach it (a preset is the layout, not an access) but a write
during a call does not. A buffer is writable by construction, and `target` means the case no
longer has to arrange for some register to happen to hold the address: which register holds a
pointer is the compiler's choice, and the two sides are allowed to differ.

The delay argument is recorded (`argc: 1`) even though this function's behaviour here is about
which words stop the loop, because it is free and it pins the 1000 the original loads at
0x024bdd50. A replacement that polled at a different interval would diverge on it.
"""
import json
import os
import struct
import sys

ADDRESS = '0x024bdd40'
# The import as the executable names it: 'kernel_usleep' is the repository's RT_ORIGINAL label,
# and the boot table carries salted NIDs, so only the imported library name hashes to one present.
SLEEP = 'sceKernelUsleep'
POLL_INTERVAL_US = 1000

STATE_OFFSET = 0x10     # the polled word: the original's MOV EAX,dword ptr [RBX + 0x10]
STATE_SIZE = 0x20       # offset 0x10 plus the 8 bytes a write covers


def case(cid, state, polls, note, high=0):
    """One case.

    state -- the 32-bit word at offset 0x10 before the call.
    polls -- what the sleep leaves in the low half after each call, in order. One entry is one
             scripted call, and therefore one expected poll.
    high  -- the 32-bit word at offset 0x14, which no poll changes. Only the low half is compared,
             so these separate a 32-bit read from a 64-bit one.
    """
    def word(low):
        return struct.pack('<II', low & 0xffffffff, high & 0xffffffff).hex()

    return {
        'schema': 1,
        'address': ADDRESS,
        'id': cid,
        'returns': 'void',
        'args': {'rdi': 'buf:state'},
        'buffers': {'state': {'size': STATE_SIZE,
                              'bytes': '00' * STATE_OFFSET + word(state)}},
        'memory': [],
        'imports': [{'name': SLEEP, 'argc': 1, 'ret': 0, 'argi': [],
                     'writes': [{'target': f'buf:state+0x{STATE_OFFSET:x}', 'bytes': word(v)}]}
                    for v in polls],
        'stubs': {},
        'note': note,
    }


CASES = [
    # The loop is entered through its test rather than fallen into, so a word already holding 2
    # returns without a single sleep call. This is what the original's JMP to 024bdd5a is for,
    # and a do/while replacement would call the sleep once and diverge on the call count.
    case('already_ready', 2, [], 'state already 2: returns without polling'),
    case('one_poll', 1, [2], 'state 1, one poll leaves 2'),
    case('two_polls', 0, [3, 2], 'state 0, polls leave 3 then 2'),
    case('four_polls', -1, [0, 1, 3, 2], 'state -1, polls leave 0, 1, 3, 2'),
    # A longer run, to pin that every iteration re-reads rather than testing once: nothing here
    # is ready until the ninth poll.
    case('nine_polls', 0, [0, 1, 3, 4, 5, 6, 7, 8, 2], 'state 0, ready only on the ninth poll'),
    # Only the low half is compared. With a high half of 1 a 64-bit read would keep polling.
    case('high_half_ready', 2, [], 'high half 1, low half 2: returns without polling', high=1),
    case('high_half_polling', 3, [2], 'high half 1, low half 3 then 2', high=1),
    # The mirror of the case above: a high half of 2 must not look ready, which a replacement
    # reading offset 0x14 instead of 0x10 would mistake for it.
    case('high_half_two_low_not', 0, [2], 'high half 2, low half 0: polls', high=2),
    # Every value that must not be mistaken for ready, each finished by a poll.
    case('zero_is_not_ready', 0, [2], 'state 0 is not ready'),
    case('one_is_not_ready', 1, [2], 'state 1 is not ready'),
    case('minus_one_is_not_ready', -1, [2], 'state -1 is not ready'),
    case('four_is_not_ready', 4, [2], 'state 4 is not ready'),
    case('high_bit_is_not_ready', 0x80000000, [2], 'state 0x80000000 is negative and not ready'),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    os.makedirs(sys.argv[1], exist_ok=True)
    for c in CASES:
        with open(os.path.join(sys.argv[1], f"{c['id']}.json"), 'w') as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write('\n')
    print(f'{len(CASES)} cases written to {sys.argv[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
