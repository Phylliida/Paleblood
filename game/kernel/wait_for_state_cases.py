#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Differential cases for kernel_wait_for_state (0x024bdd40).

The function polls the 32-bit word at offset 0x10 of its argument until it reads 2, calling the
microsecond sleep with a fixed 1000 once per poll. Every case therefore has to say how the word
changes between polls, or the loop never ends.

Reaching that word takes some care. The only code that runs between polls is the sleep call, so the
only way to change the word is the scripted import's `writes`, which stores through `args[arg] +
offset`. `args` are the registers as the stub sees them, and arg 0 is the delay -- the original
always passes 1000 there, so arg 0 could only reach the low ELF-header page, which is not part of
any load segment and is unmapped. The registers after the delay are free, and the stub's native
wrapper forwards all six, so arg 1 (rsi) is seeded from the case to point at the structure and the
state word is written through that. Nothing about the delay changes: the function still passes
whatever it passes, and these cases neither record nor check that value (its unit is covered by the
committed sleep and frame-limiter suites; these cases are about which words stop the loop).

The structure therefore lives in the mapped image rather than in a case buffer, at an address the
loop reads and nothing else touches.

Usage: wait_for_state_cases.py [output directory]
"""
import json
import os
import struct
import sys

ADDRESS = '0x024bdd40'
# The import as the executable actually names it. 'kernel_usleep' is the repo's local RT_ORIGINAL
# label (see game/frame_timing/sleep_wrapper.cpp); the boot table carries salted NIDs, and only the
# imported library name hashes to one that is present.
SLEEP = 'sceKernelUsleep'

# 0x700000 sits well past every replaced function and every global these cases touch, while still
# inside the first load segment (vaddr 0, memsz 0x50d96dc), so both the polling read and the 8-byte
# store are mapped.
STATE_ADDR = 0x700010             # the 32-bit state word the loop polls: STRUCT_ADDR + 0x10
STRUCT_ADDR = STATE_ADDR - 0x10   # 0x700000: what the function's only argument points at
ARG_INDEX = 1                     # rsi, seeded by the case to STRUCT_ADDR
STATE_WRITE_OFFSET = 0x10         # STATE_ADDR - STRUCT_ADDR

cases = []


def case(name, state, polls, note, high=0):
    """One case.

    state -- the 32-bit word at offset 0x10 before the call.
    polls -- the 32-bit word the sleep stub leaves behind after each call, in order. Each entry
             becomes one scripted sleep call; the loop re-reads the word after every call, so the
             sequence decides how many times it goes round. One `polls` entry is one expected call.
    high  -- the value of the four bytes above the state word, unchanged by the polls.
    """
    imports = [{
        'name': SLEEP,
        'argc': 1,
        'ret': 0,
        'argi': [],
        'writes': [{'arg': ARG_INDEX,
                    'offset': STATE_WRITE_OFFSET,
                    'bytes': struct.pack('<Q', (high << 32) | (value & 0xffffffff)).hex()}],
    } for value in polls]
    cases.append({
        'file': f'{name}.json',
        'schema': 1,
        'name': name,
        'address': ADDRESS,
        'args': {'rdi': f'guest:{STRUCT_ADDR:#x}', 'rsi': f'guest:{STRUCT_ADDR:#x}'},
        'memory': [{'addr': f'{STATE_ADDR:#x}',
                    'bytes': struct.pack('<Q', (high << 32) | (state & 0xffffffff)).hex()}],
        'returns': 'void',
        'imports': imports,
        'stubs': {},
        'note': note,
    })


# The word already holds 2. The loop is entered through its test rather than fallen into, so this
# returns without a single sleep call: the case that shows it is not a do/while.
case('already_ready', 2, [], 'state already 2: returns without polling')
# One poll: the sleep leaves 2 behind, so the loop goes round exactly once.
case('one_poll', 1, [2], 'state 1, one poll leaves 2')
# A value that is not 2 after the first poll keeps the loop going.
case('two_polls', 0, [3, 2], 'state 0, polls leave 3 then 2')
case('four_polls', -1, [0, 1, 3, 2], 'state -1, polls leave 0, 1, 3, 2')
# Only the low 32 bits are compared. With a high half of 1 and a low half of 2 the loop must
# still leave at once; a replacement that read 64 bits would keep polling and diverge.
case('high_half_ready', 2, [], 'high half 1, low half 2: returns without polling', high=1)
# The same high half, but the low half is not ready: the loop polls, and the poll writes 2 into
# the low half while leaving the high half at 1.
case('high_half_polling', 3, [2], 'high half 1, low half 3 then 2', high=1)
# Every value that must not be mistaken for ready, checked with a poll that then does finish it.
case('zero_is_not_ready', 0, [2], 'state 0 is not ready')
case('one_is_not_ready', 1, [2], 'state 1 is not ready')
case('minus_one_is_not_ready', -1, [2], 'state -1 is not ready')
case('four_is_not_ready', 4, [2], 'state 4 is not ready')
case('high_bit_is_not_ready', -2147483648, [2], 'state 0x80000000 is negative and not ready')

out = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(out, exist_ok=True)
for c in cases:
    path = os.path.join(out, c.pop('file'))
    with open(path, 'w') as f:
        json.dump(c, f, indent=2, sort_keys=True)
        f.write('\n')

print(f'{len(cases)} cases written to {out}')
