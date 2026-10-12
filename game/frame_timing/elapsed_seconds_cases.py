#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_elapsed_seconds_01448580 (0x01448580), for tools/verify.py run.

usage: elapsed_seconds_cases.py OUT_DIR

The function latches a value into a float at offset 0x38 of its argument, and the whole of its
control flow hangs on one comparison of that float against zero. So the cases divide into two
groups:

  * the guard. A value that is not zero must take the short path: no clock call, no writes at all.
    The interesting members are the ones a `!(x != 0.0f)` test would wrongly accept -- a negative
    zero and every NaN -- because the original's two branches (JNZ then JP) accept neither. Those
    cases are the ones that would fail if the replacement were written with `if (elapsed == 0.0f)`
    in the wrong direction, so the expectation is that they write *nothing*.
  * the arithmetic. Two timeval fields, a 64-bit base global, a multiplication by 1000000, an
    unsigned subtraction, a division by 1000000.0 and a narrowing to float. The cases walk the
    clock across zero, across a second, into the negative range that the v2.00 update's own
    callers can reach, and past 2**63 where the unsigned reading of the difference stops being the
    mathematical one.

Both counters in the object are seeded with a sentinel far from wrap, and the object is a buffer
so its whole 0x60 bytes are compared: the float, both counters, and everything the function must
leave alone.

The clock is scripted through the name the executable imports (gettimeofday), not the name the
replacement calls it by. The base global is a `memory` entry addressed with `addr` and carrying
raw `bytes`: in a memory entry `addr` is where the write goes, while `guest` and `pointer` are the
*kind of value* a pointer-shaped entry writes there (a translated guest address, or a sandbox
address), not a way to address it. In the shipped image the base already holds 8, and one case
overrides it to show the subtraction is real.
"""
import json
import os
import struct
import sys

ADDRESS = '0x01448580'
GETTIMEOFDAY = 'gettimeofday'

BASE_ADDRESS = 0x05940660
BASE_SHIPPED = 8

ELAPSED_OFFSET = 0x38
FIRST_COUNTER_OFFSET = 0x44
SECOND_COUNTER_OFFSET = 0x4c
OBJECT_SIZE = 0x60

# Far from any wrap: an increment must show up as sentinel+1, not as the sentinel.
COUNTER_SENTINEL = 0x11111111

# Every bit pattern the guard has to get right, as the raw 4 bytes of the float field.
FLOATS = {
    'zero': '00000000',                 # +0.0f: the only value that reaches the clock
    'zero_negative': '00000080',        # -0.0f: compares equal to 0.0f, but not to the original's test
    'one': '0000803f',                  # 1.0f
    'tiny_subnormal': '01000000',       # 1.4e-45f: nonzero, so not the clock path
    'infinity': '0000807f',
    'infinity_negative': '000080ff',
    'nan_quiet': '0000c07f',
    'nan_negative': '0000c0ff',
    'nan_payload': '0100c07f',
    'nan_signalling': '0100807f',
}


def object_bytes(float_bits, first=COUNTER_SENTINEL, second=COUNTER_SENTINEL):
    """A 0x60-byte object: float at 0x38, counters at 0x44 and 0x4c, zeros everywhere else."""
    buf = bytearray(OBJECT_SIZE)
    struct.pack_into('<I', buf, ELAPSED_OFFSET, int(float_bits, 16))
    struct.pack_into('<I', buf, FIRST_COUNTER_OFFSET, first)
    struct.pack_into('<I', buf, SECOND_COUNTER_OFFSET, second)
    return bytes(buf).hex()


def case(cid, float_bits, seconds, microseconds, base=None, note=None):
    """One call, with the clock scripted to SECONDS/MICROSECONDS."""
    tv = struct.pack('<qq', seconds, microseconds)
    entry = {
        'schema': 1,
        'address': ADDRESS,
        'id': cid,
        'returns': 'void',
        'args': {'rdi': 'buf:object'},
        'buffers': {'object': {'size': OBJECT_SIZE, 'bytes': object_bytes(float_bits)}},
        'memory': [{'addr': hex(BASE_ADDRESS),
                    'bytes': struct.pack('<Q', BASE_SHIPPED if base is None else base).hex()}],
        'imports': [{'name': GETTIMEOFDAY, 'argc': 2, 'ret': 0,
                     'writes': [{'arg': 0, 'offset': 0, 'size': 16, 'bytes': tv.hex()}]}],
    }
    if note:
        entry['note'] = note
    return entry


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: elapsed_seconds_cases.py OUT_DIR')
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)

    cases = []

    # -- the guard: not zero, so nothing happens at all. --------------------------------
    for name, bits in FLOATS.items():
        if name == 'zero':
            continue
        cases.append(case('guard_' + name, bits, 0x1000, 0x2000,
                          note='not zero: the clock must not be called and nothing written'))

    # -- the clock path: the latched value and both counters. ---------------------------
    clock = [
        ('base_exact', 0, BASE_SHIPPED, None, 'counts == the base: the quotient is 0.0f'),
        ('one_us', 0, BASE_SHIPPED + 1, None, 'one microsecond over the base: 1e-6 rounds to a float'),
        ('one_second', 0, BASE_SHIPPED + 1000000, None, 'exactly one second'),
        ('half_second', 0, BASE_SHIPPED + 500000, None, '0.5 s, exact in a float'),
        ('ten_seconds', 12, 345678, None, 'ten seconds and a fraction'),
        ('with_microseconds', 1, BASE_SHIPPED + 1, None,
         'the microseconds field carries past a whole second, as a raw timeval may'),
        ('under_base', 0, BASE_SHIPPED - 1000000, None,
         'counts < base: the subtraction wraps and the unsigned conversion stays unsigned'),
        ('far_under_base', 0, 0, None, 'epoch clock against base 8: the largest ordinary wrap'),
        ('seconds_30bit', 0x7fffffff, 999999, None, 'the largest seconds a 32-bit field holds'),
        ('huge_seconds', 0x7fffffffffffffff, 999999, None,
         'seconds*1000000 overflows the signed 64-bit product; the sum is read as unsigned'),
        ('base_override', 0, 5000000, 0,
         'base is not the shipped 8: the subtraction must use whatever the global holds'),
        ('base_high_bit', 0, 1000000, 1 << 63,
         'a base with the top bit set, so the difference wraps into the low range'),
    ]
    for cid, sec, usec, base, note in clock:
        cases.append(case(cid, FLOATS['zero'], sec, usec, base=base, note=note))

    # -- a nonzero float with a live clock: still nothing written. ----------------------
    cases.append(case('nonzero_ignores_clock', FLOATS['one'], 12345, 67890,
                      note='the clock is scripted but must not be called'))

    for entry in cases:
        with open(os.path.join(out_dir, entry['id'] + '.json'), 'w') as f:
            json.dump(entry, f, indent=2)
            f.write('\n')

    print(f'{len(cases)} cases written to {out_dir}')


if __name__ == '__main__':
    main()
