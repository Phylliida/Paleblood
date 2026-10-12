#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cases for 0x024bd150, the kernel's wait-then-advance walk.

Every structure the function dereferences lives in a sandbox *buffer*, and every pointer between
them is written with the "pointer" memory form. That is the only way the original can walk them:
guest code dereferences a pointer as-is, so the word it follows has to be a real mapped host
address, and the harness hands one out only through "pointer" (which stores a buffer's host
address). Two forms that look like they would do the job do not. A plain hex "args" value is
passed through verbatim -- the guest gets the literal, not the address -- and "guest" takes an
in-image address, which is bounds-checked against the image and, once stored, is not the host
address of anything, so the first load through it faults. Buffers are laid out at SANDBOX, which
the harness maps, so a host buffer address is an address the guest can load from.

The one exception is the two vtable slots: those hold *stub* addresses, which really are image
addresses, and "guest" is the right form for them. A stub is a trampoline the harness installs at
the address itself, so nothing dereferences it on the guest's side.

The lock is reached through a global (0x05aa4578) whose own word *is* the vtable -- the original
loads the global once and calls through [rax+0x18] -- with slot +0x18 taking the lock and slot
+0x28 releasing it. Both slots are scripted as stubs, so a case states what the function calls and
in what order: modes 0 and 1 make a lock/unlock pair before the wait, and every mode makes one
around the advance. A stub queue is popped in call order, so a case that takes two pairs supplies
two entries per slot.

The poll body is out of reach, and not only for the reason it first appeared. A stub *can* write
to the node -- "writes" with a buffer name reaches the state word -- but the loop only leaves when
the word reads exactly 2, so the number of sleep calls before it leaves depends on when the stub
writes, and a case file cannot state a call sequence that is the same on both sides. Every case
here therefore leaves the state word reading 2, satisfying the test at the top of the loop so the
body never runs. What stays uncovered is that body: the usleep at 0x02fbfe68, and the re-read of
the state word. A state that is never set to 2 does not converge either; both sides spin until the
harness's runaway guard stops them, which is a fact about the guard and not about the function.
"""

import json
import os
import struct
import sys

ADDRESS = '0x024bd150'

HEAD_OFFSET = 0x8
STATE_OFFSET = 0x10
NEXT_OFFSET = 0x18
ADVANCE_COUNT_OFFSET = 0x30
IS_RELEASED_OFFSET = 0x31
CHAIN_OFFSET = 0x80
CHAIN_GUARD_OFFSET = 0x88

# The global whose word points at the lockable, and the two vtable slots that are called on it.
LOCK_GLOBAL = 0x05aa4578
LOCK_SLOT = 0x18
UNLOCK_SLOT = 0x28
LOCK_STUB = 0x00500000
UNLOCK_STUB = 0x00500100

MODE_NO_WAIT = 2
STATE_READY = 2
BUFFER_SIZE = 0x200

LOCK_ONLY = {'address': hex(LOCK_STUB), 'argc': 2, 'returns': 'void'}
UNLOCK_ONLY = {'address': hex(UNLOCK_STUB), 'argc': 1, 'returns': 'void'}


def u32(v):
    """A little-endian word, as the guest reads it."""
    return struct.pack('<I', v).hex()


class Case:
    """One call: the registry in a buffer, the lock chain behind it, the node to walk to."""

    def __init__(self, cid, mode, head_null=False, state=STATE_READY, release_byte=0,
                 count=0, chain=None, chain_guard=False):
        self.cid, self.mode = cid, mode
        self.buffers = {'registry': {'size': BUFFER_SIZE, 'bytes': '00' * BUFFER_SIZE},
                        'vt': {'size': BUFFER_SIZE, 'bytes': '00' * BUFFER_SIZE},
                        'node': {'size': BUFFER_SIZE, 'bytes': '00' * BUFFER_SIZE},
                        'next': {'size': BUFFER_SIZE, 'bytes': '00' * BUFFER_SIZE}}
        self.memory = [
            # The global's own word *is* the vtable: the original loads the global once and calls
            # through [rax+0x18], so a buffer in between would be dereferenced as the vtable.
            {'addr': hex(LOCK_GLOBAL), 'pointer': 'vt'},
            {'addr': f'buf:vt+{LOCK_SLOT:#x}', 'guest': hex(LOCK_STUB)},
            {'addr': f'buf:vt+{UNLOCK_SLOT:#x}', 'guest': hex(UNLOCK_STUB)},
        ]
        # One entry per call the function makes: both slots are popped from their queue in order,
        # so a mode that takes two lock/unlock pairs needs two of each. An exhausted queue is
        # reported as an unscripted call.
        pairs = 1 if mode == MODE_NO_WAIT else 2
        self.stubs = [dict(LOCK_ONLY) for _ in range(pairs)] + \
                     [dict(UNLOCK_ONLY) for _ in range(pairs)]
        if not head_null:
            # The walk always follows one of the two outgoing pointers, so each has to reach a
            # buffer: a null or in-image value faults the guest on the next load.
            self.memory += [
                {'addr': f'buf:registry+{HEAD_OFFSET:#x}', 'pointer': 'node'},
                {'addr': f'buf:node+{STATE_OFFSET:#x}', 'bytes': u32(state)},
                {'addr': f'buf:node+{NEXT_OFFSET:#x}', 'pointer': 'next'},
                {'addr': f'buf:node+{ADVANCE_COUNT_OFFSET:#x}', 'bytes': u32(count)[:2]},
                {'addr': f'buf:node+{IS_RELEASED_OFFSET:#x}', 'bytes': f'{release_byte:02x}'},
            ]
        if chain is not None:
            # +0x80 is a *pointer to* a container, and the walk loads three times to leave it:
            # [node+0x80] -> the container, [container+0x0] -> a second word, [that+0x10] -> the
            # node to move to. Every one of those has to be a mapped host address, so the container
            # points at a buffer of its own rather than at itself.
            self.buffers['container'] = {'size': BUFFER_SIZE, 'bytes': '00' * BUFFER_SIZE}
            self.buffers['holder'] = {'size': BUFFER_SIZE, 'bytes': '00' * BUFFER_SIZE}
            self.memory += [
                {'addr': f'buf:node+{CHAIN_OFFSET:#x}', 'pointer': 'container'},
                {'addr': 'buf:container+0x0', 'pointer': 'holder'},
                {'addr': 'buf:holder+0x10', 'pointer': chain},
            ]
        if chain_guard:
            self.memory += [{'addr': f'buf:node+{CHAIN_GUARD_OFFSET:#x}', 'bytes': '01'}]

    def write(self, out_dir):
        case = {'schema': 1, 'address': ADDRESS, 'id': self.cid,
                'args': {'rdi': 'buf:registry', 'rsi': hex(self.mode)},
                'returns': 'void', 'buffers': self.buffers, 'memory': self.memory,
                'stubs': self.stubs}
        with open(os.path.join(out_dir, f'{self.cid}.json'), 'w') as f:
            json.dump(case, f)
            f.write('\n')


def cases():
    yield Case('001_null_registry_returns_zero', MODE_NO_WAIT, head_null=True)
    yield Case('002_null_registry_mode_zero_returns_zero', 0, head_null=True)
    yield Case('003_mode_two_advances_without_the_lock', MODE_NO_WAIT, state=0)
    yield Case('004_mode_two_ignores_the_released_bit', MODE_NO_WAIT,
               state=0, release_byte=0x01)
    yield Case('005_mode_two_advances_a_node_already_ready', MODE_NO_WAIT)
    # mode 1 waits for the state word; the cases satisfy it at the top of the loop.
    yield Case('006_mode_one_when_not_released', 1, state=STATE_READY)
    yield Case('007_mode_one_when_released_still_advances', 1, release_byte=0x01)
    # mode 1 reads *bit 0* of the released byte before the advance, so the value 2 is not released.
    # The poll body itself is out of reach -- see the note at the top of this file -- which is why
    # the byte is the thing varied here rather than the state word.
    yield Case('008_mode_one_release_bit_zero_clear_still_advances', 1, release_byte=0x02)
    # mode 0 returns 0 when bit 0 is set and advances when it is clear, which is the opposite of
    # what a bare truth test on the byte would do.
    yield Case('009_mode_zero_when_not_released_returns_zero', 0, state=0)
    yield Case('010_mode_zero_when_released_advances', 0, state=0, release_byte=0x01)
    yield Case('011_mode_zero_masks_the_released_byte_to_bit_zero', 0, state=0, release_byte=0x02)
    # the counter and the released bit are read independently.
    yield Case('012_counter_is_bumped_from_a_high_value', MODE_NO_WAIT, count=0x7f)
    # the direct route and the chain route.
    yield Case('013_next_at_plus_0x18_is_taken_when_the_guard_is_clear', MODE_NO_WAIT, state=0)
    yield Case('014_chain_guard_set_takes_the_container_route', MODE_NO_WAIT, state=0,
               chain='next', chain_guard=True)
    yield Case('015_chain_guard_clear_ignores_the_container', MODE_NO_WAIT, state=0,
               chain='next')
    yield Case('016_chain_guard_set_in_mode_one', 1, state=STATE_READY, chain='next',
               chain_guard=True)
    yield Case('017_mode_zero_released_still_advances_through_the_chain', 0, state=0,
               release_byte=0x01, chain='next', chain_guard=True)


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        print('usage: wait_for_release_cases.py OUT_DIR', file=sys.stderr)
        return 2
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for case in cases():
        case.write(out_dir)
        n += 1
    print(f'{n} cases in {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
