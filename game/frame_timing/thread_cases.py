#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for the thread identity and mutex pair, for tools/verify.py run.

usage: thread_cases.py OUT_DIR

frame_timing_thread_self (0x0111a8a0) stores the import's 64-bit return through its pointer
argument and returns 0. The stored value is the current case's own behaviour: it must be the exact
64-bit word the stub produced, high half included, because the original stores the full RAX. The
stub is scripted with a value whose two halves differ so that a 32-bit store would be visible.

frame_timing_mutex_lock (0x0111acd0) and frame_timing_mutex_unlock (0x0111acf0) each call one stub
and turn its result into the reported word with MOV ECX,EAX / TEST ECX,ECX / MOV EAX,0x21 /
CMOVE EAX,ECX. A successful call (0) therefore keeps the zero, and every nonzero result is
replaced by the fixed 0x21 -- the kernel's specific error code is discarded, not passed through.
Both functions also return 0 for a null mutex without calling anything, so the case that matters
most is the one that separates "0 means the pointer was null so report 0" from "0 means success so
report 0": the null pointer must produce a zero return and no call at all.

The failure paths script the stub returning a nonzero word, covering a small positive, a value
with the high bit set, and 0xffffffff. The comparison is on the low 32 bits only, so a result whose
low word is zero reads as success even when the high word is not -- that case is scripted too.

frame_timing_semaphore_delete (0x0111ad80), _wait (0x0111ada0) and _signal (0x0111adc0) report the
same way as the mutex pair, and unlike it they do not test their handle first: the handle reaches
the stub even when it is zero, so the case that matters here is that a zero handle is *not* short
circuited. _wait scripts need_count and the null timeout the wrapper passes, _signal the count, so a
replacement that dropped or changed them is visible in the recorded call arguments.
"""
import json
import os
import sys

ADDRESS_SELF = '0x0111a8a0'
ADDRESS_LOCK = '0x0111acd0'
ADDRESS_UNLOCK = '0x0111acf0'
ADDRESS_SEMA_DELETE = '0x0111ad80'
ADDRESS_SEMA_WAIT = '0x0111ada0'
ADDRESS_SEMA_SIGNAL = '0x0111adc0'

PTHREAD_SELF = 'scePthreadSelf'
MUTEX_LOCK = 'scePthreadMutexLock'
MUTEX_UNLOCK = 'scePthreadMutexUnlock'
SEMA_DELETE = 'sceKernelDeleteSema'
SEMA_WAIT = 'sceKernelWaitSema'
SEMA_SIGNAL = 'sceKernelSignalSema'

# A return whose halves differ, so a truncated store cannot pass.
SELF_HALVES_DIFFER = 0x1122334455667788
SELF_LOW_ONLY = 0x00000000DEADBEEF
SELF_HIGH_ONLY = 0xCAFEBABE00000000


def case_self(cid, value, note):
    return {
        'schema': 1, 'address': ADDRESS_SELF, 'id': cid,
        'returns': 'i64',                    # XOR EAX,EAX: the caller sees 0
        'args': {'rdi': 'buf:out'},
        'buffers': {'out': {'size': 8, 'bytes': '0000000000000000'}},
        'memory': [],
        'imports': [{'name': PTHREAD_SELF, 'argc': 0, 'ret': value}],
        'note': note,
    }


def case_mutex(address, cid, name, value, note, null=False):
    if null:
        # A null mutex must not reach the stub at all: no script is supplied, so any call is an
        # unscripted-library-call error rather than a silent success.
        args = {'rdi': '0x0'}
        imports = []
    else:
        args = {'rdi': 'buf:mutex'}
        imports = [{'name': name, 'argc': 1, 'ret': value}]
    return {
        'schema': 1, 'address': address, 'id': cid,
        'returns': 'i32',                    # the whole EAX is the result, not just AL
        'args': args,
        'buffers': {} if null else {'mutex': {'size': 8, 'bytes': 'efbeadde00000000'}},
        'memory': [],
        'imports': imports,
        'note': note,
    }


def case_sema(address, cid, name, argc, args, value, note):
    """A wrapper that reports its stub's result as 0 or the fixed 0x21, with no handle test."""
    return {
        'schema': 1, 'address': address, 'id': cid,
        'returns': 'i32',                    # the whole EAX is the result, not just AL
        'args': args,
        'buffers': {} if args['rdi'] == '0x0' else {'sema': {'size': 8, 'bytes': 'efbeadde00000000'}},
        'memory': [],
        'imports': [{'name': name, 'argc': argc, 'ret': value}],
        'note': note,
    }


CASES = [
    # --- thread identity ---
    case_self('self_halves_differ', SELF_HALVES_DIFFER,
              'both halves nonzero: a 32-bit store would pass the low half only'),
    case_self('self_low_only', SELF_LOW_ONLY, 'the high half zero'),
    case_self('self_high_only', SELF_HIGH_ONLY, 'the low half zero'),
    case_self('self_all_ones', 0xFFFFFFFFFFFFFFFF, 'the whole word set'),

    # --- mutex lock ---
    case_mutex(ADDRESS_LOCK, 'lock_success', MUTEX_LOCK, 0,
               'a zero result means the lock was taken, so the wrapper reports 0'),
    case_mutex(ADDRESS_LOCK, 'lock_null_mutex', MUTEX_LOCK, 0,
               'a null mutex returns 0 and must not call the stub', null=True),
    case_mutex(ADDRESS_LOCK, 'lock_small_error', MUTEX_LOCK, 0x0B,
               'a nonzero result is replaced by the fixed 0x21, not passed through'),
    case_mutex(ADDRESS_LOCK, 'lock_high_bit_error', MUTEX_LOCK, 0x80000016,
               'a negative kernel error still reports 0x21, not its low 32 bits'),
    case_mutex(ADDRESS_LOCK, 'lock_all_ones', MUTEX_LOCK, 0xFFFFFFFF,
               'the largest nonzero result, which must not leak through as 0xffffffff'),

    # --- mutex unlock ---
    case_mutex(ADDRESS_UNLOCK, 'unlock_success', MUTEX_UNLOCK, 0,
               'a zero result means the unlock succeeded, so the wrapper reports 0'),
    case_mutex(ADDRESS_UNLOCK, 'unlock_null_mutex', MUTEX_UNLOCK, 0,
               'a null mutex returns 0 and must not call the stub', null=True),
    case_mutex(ADDRESS_UNLOCK, 'unlock_small_error', MUTEX_UNLOCK, 0x01,
               'a nonzero result is replaced by the fixed 0x21, not passed through'),
    case_mutex(ADDRESS_UNLOCK, 'unlock_high_bit_error', MUTEX_UNLOCK, 0xFFFFFFF7,
               'a negative kernel error still reports 0x21, not its low 32 bits'),
    case_mutex(ADDRESS_UNLOCK, 'unlock_all_ones', MUTEX_UNLOCK, 0xFFFFFFFF,
               'the largest nonzero result, which must not leak through as 0xffffffff'),

    # --- semaphore delete ---
    case_sema(ADDRESS_SEMA_DELETE, 'sema_delete_success', SEMA_DELETE, 1, {'rdi': 'buf:sema'}, 0,
              'a zero result means the semaphore was deleted, so the wrapper reports 0'),
    case_sema(ADDRESS_SEMA_DELETE, 'sema_delete_zero_handle', SEMA_DELETE, 1, {'rdi': '0x0'}, 0,
              'there is no null test: a zero handle still reaches the stub, and 0 is reported'),
    case_sema(ADDRESS_SEMA_DELETE, 'sema_delete_small_error', SEMA_DELETE, 1, {'rdi': 'buf:sema'},
              0x80020016, 'a nonzero result is replaced by the fixed 0x21, not passed through'),
    case_sema(ADDRESS_SEMA_DELETE, 'sema_delete_all_ones', SEMA_DELETE, 1, {'rdi': 'buf:sema'},
              0xFFFFFFFF, 'the largest nonzero result, which must not leak through as 0xffffffff'),

    # --- semaphore wait ---
    case_sema(ADDRESS_SEMA_WAIT, 'sema_wait_success', SEMA_WAIT, 3,
              {'rdi': 'buf:sema', 'rsi': '0x1', 'rdx': '0x0'}, 0,
              'one unit and a null timeout, which is the wait the wrapper asks for'),
    case_sema(ADDRESS_SEMA_WAIT, 'sema_wait_zero_handle', SEMA_WAIT, 3,
              {'rdi': '0x0', 'rsi': '0x1', 'rdx': '0x0'}, 0,
              'there is no null test: a zero handle still reaches the stub, and 0 is reported'),
    case_sema(ADDRESS_SEMA_WAIT, 'sema_wait_timeout', SEMA_WAIT, 3,
              {'rdi': 'buf:sema', 'rsi': '0x1', 'rdx': '0x0'}, 0x8002003C,
              'EAGAIN from a null timeout is impossible, but a nonzero result still reports 0x21'),
    case_sema(ADDRESS_SEMA_WAIT, 'sema_wait_all_ones', SEMA_WAIT, 3,
              {'rdi': 'buf:sema', 'rsi': '0x1', 'rdx': '0x0'}, 0xFFFFFFFF,
              'the largest nonzero result, which must not leak through as 0xffffffff'),

    # --- semaphore signal ---
    case_sema(ADDRESS_SEMA_SIGNAL, 'sema_signal_success', SEMA_SIGNAL, 2,
              {'rdi': 'buf:sema', 'rsi': '0x1'}, 0,
              'one unit is posted, and a zero result is reported as 0'),
    case_sema(ADDRESS_SEMA_SIGNAL, 'sema_signal_zero_handle', SEMA_SIGNAL, 2,
              {'rdi': '0x0', 'rsi': '0x1'}, 0,
              'there is no null test: a zero handle still reaches the stub, and 0 is reported'),
    case_sema(ADDRESS_SEMA_SIGNAL, 'sema_signal_small_error', SEMA_SIGNAL, 2,
              {'rdi': 'buf:sema', 'rsi': '0x1'}, 0x80020001,
              'a nonzero result is replaced by the fixed 0x21, not passed through'),
    case_sema(ADDRESS_SEMA_SIGNAL, 'sema_signal_all_ones', SEMA_SIGNAL, 2,
              {'rdi': 'buf:sema', 'rsi': '0x1'}, 0xFFFFFFFF,
              'the largest nonzero result, which must not leak through as 0xffffffff'),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    # One directory per function: verify.py runs a directory against a single address and rejects a
    # case that names another.
    counts = {}
    for c in CASES:
        c.pop('note', None)
        out = os.path.join(sys.argv[1], c['address'])
        os.makedirs(out, exist_ok=True)
        counts[c['address']] = counts.get(c['address'], 0) + 1
        with open(os.path.join(out, f"{c['id']}.json"), 'w') as f:
            json.dump(c, f, indent=1)
    summary = ', '.join(f'{n} at {a}' for a, n in sorted(counts.items()))
    print(f'{len(CASES)} cases written under {sys.argv[1]} ({summary})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
