#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_stop_and_accumulate_01448620 (0x01448620), for tools/verify.py run.

usage: stop_and_accumulate_cases.py OUT_DIR

This is the second half of the pair whose first half is 0x01448580 (elapsed_seconds.cpp). It ends
a measurement rather than starting one: the float at 0x38 is the *mark*, and the value it computes
- the same seconds-since-base the sibling latches - is differenced against that mark, the mark is
zeroed, and the difference is added into the floats at 0x3c and 0x54.

Its guard is the opposite polarity to the sibling's, and that is the whole reason the cases split
the way they do. The original compares the mark against 0.0f with VUCOMISS and branches on JBE, so
it accumulates only when the mark is *greater* than zero. The sibling branches on JNZ/JP, which
accepts only an exact positive zero. Both decline a negative zero and both decline every NaN, but
for opposite reasons, and the values in between are what separate the two tests:

  * the guard. Anything not strictly positive - a positive zero, a negative zero, any negative,
    both infinities, every NaN - must take the short path: no clock call, no writes at all. The
    cases that matter most are the ones a `>= 0.0f` or a `!= 0.0f` test would wrongly accept
    (the zero and the negative zero) and the ones an `!(x <= 0.0f)` test would wrongly accept
    (every NaN). The expectation for all of them is *no writes*, so a right-for-the-wrong-reason
    replacement has nowhere to hide.
  * the arithmetic. A live clock, a seeded mark, and two accumulators. The cases walk the mark
    across the clock value so the delta is positive, zero and negative, and separately check that
    both accumulators receive the *same* delta rather than a chained sum: an implementation that
    did `second += (first after adding)` would agree on the first call and diverge once 0x3c and
    0x54 start out holding different values.

The object is a buffer, so its whole 0x60 bytes are compared: the mark, both accumulators, and
everything the function must leave alone.

The clock is scripted through the name the executable imports (gettimeofday), not the name the
replacement calls it by. The base global is a `memory` entry addressed with `addr` and carrying raw
`bytes`: in a memory entry `addr` is where the write goes, while `guest` and `pointer` are the kind
of value a pointer-shaped entry writes there, not a way to address it. The shipped image already
holds 8 at the base, and one case overrides it to show the subtraction is real.
"""
import json
import os
import struct
import sys

ADDRESS = '0x01448620'
GETTIMEOFDAY = 'gettimeofday'

BASE_ADDRESS = 0x05940660
BASE_SHIPPED = 8

MARK_OFFSET = 0x38
FIRST_ACCUMULATOR_OFFSET = 0x3c
SECOND_ACCUMULATOR_OFFSET = 0x54
OBJECT_SIZE = 0x60

# Deliberately different from each other: two accumulators that happen to hold the same value
# cannot show whether the second one was fed the delta or the first one's new total. These are the
# four bytes as they sit in memory, little-endian: 50.0f packed little-endian is 00 00 48 42.
FIRST_SENTINEL_BITS = '00004842'    # 50.0f
SECOND_SENTINEL_BITS = '0000c842'   # 100.0f

# Every bit pattern the guard has to get right, as the raw 4 bytes of the mark in memory order.
# A float written as the bits 0x3f800000 is stored as 00 00 80 3f, so these literals are the
# little-endian forms of the values named.
FLOATS = {
    'one': '0000803f',                  # 1.0f: the ordinary marked case
    'half': '0000003f',                 # 0.5f
    'ten': '00002041',                  # 10.0f
    'zero': '00000000',                 # +0.0f: not greater than zero, so no accumulation
    'zero_negative': '00000080',        # -0.0f: not greater than zero either
    'negative_one': '000080bf',         # -1.0f
    'negative_tiny': '01000080',        # -1.4e-45f: the smallest negative, still not > 0
    'tiny_subnormal': '01000000',       # +1.4e-45f: positive, so it does accumulate
    'infinity': '0000807f',             # +inf is positive: it accumulates, and now - inf = -inf
    'infinity_negative': '000080ff',    # -inf is not greater than zero
    'nan_quiet': '0000c07f',
    'nan_negative': '0000c0ff',
    'nan_payload': '0100c07f',
    'nan_signalling': '0100807f',
}

# The clock the cases script, as seconds/microseconds around the base. The base is the shipped 8,
# so a clock of 8_000_000 us puts the computed value at exactly 0.0.
def clock_us(us):
    return us // 1000000, us % 1000000


def object_bytes(mark_bits, first=FIRST_SENTINEL_BITS, second=SECOND_SENTINEL_BITS):
    """A 0x60-byte object: the mark at 0x38, accumulators at 0x3c and 0x54, zeros elsewhere.

    Each field is written as the four bytes it occupies, so a literal here is read back by the
    guest as a little-endian float -- '0000803f' is 1.0f, not 0x0000803f.
    """
    buf = bytearray(OBJECT_SIZE)
    buf[MARK_OFFSET:MARK_OFFSET + 4] = bytes.fromhex(mark_bits)
    buf[FIRST_ACCUMULATOR_OFFSET:FIRST_ACCUMULATOR_OFFSET + 4] = bytes.fromhex(first)
    buf[SECOND_ACCUMULATOR_OFFSET:SECOND_ACCUMULATOR_OFFSET + 4] = bytes.fromhex(second)
    return bytes(buf).hex()


def case(cid, mark_bits, seconds, microseconds, base=None, sentinels=None, note=None):
    """One call, with the clock scripted to SECONDS/MICROSECONDS."""
    first, second = sentinels or (FIRST_SENTINEL_BITS, SECOND_SENTINEL_BITS)
    tv = struct.pack('<qq', seconds, microseconds)
    entry = {
        'schema': 1,
        'address': ADDRESS,
        'id': cid,
        'returns': 'void',
        'args': {'rdi': 'buf:object'},
        'buffers': {'object': {'size': OBJECT_SIZE,
                               'bytes': object_bytes(mark_bits, first, second)}},
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
        raise SystemExit('usage: stop_and_accumulate_cases.py OUT_DIR')
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)

    cases = []

    # -- the guard: not strictly positive, so nothing happens at all. --------------------
    for name, bits in FLOATS.items():
        if name in ('one', 'half', 'ten', 'tiny_subnormal', 'infinity'):
            continue
        cases.append(case('guard_' + name, bits, 12, 345678,
                          note='not greater than zero: the clock must not be called and nothing '
                               'written'))

    # -- the accumulate path: a positive mark against a scripted clock. ------------------
    # BASE_SHIPPED is 8, so the clock value in seconds is (us - 8) / 1e6.
    accumulate = [
        ('delta_one_second', FLOATS['one'], 8 + 1000000, 0,
         'now = 1.0, mark = 1.0: the delta is exactly zero and both accumulators keep their value'),
        ('delta_two_seconds', FLOATS['one'], 8 + 2000000, 0,
         'now = 2.0, mark = 1.0: delta +1.0 into both accumulators'),
        ('delta_fraction', FLOATS['half'], 8 + 1500000, 0,
         'now = 1.5, mark = 0.5: delta +1.0, an exact float'),
        ('mark_above_clock', FLOATS['ten'], 8 + 1000000, 0,
         'now = 1.0, mark = 10.0: a negative delta, which the guard still admits'),
        ('mark_equal_clock', FLOATS['one'], 8 + 1000000, 0,
         'the boundary: now == mark, so the delta is 0.0 and the mark is still zeroed'),
        ('subnormal_rounds', FLOATS['tiny_subnormal'], 8 + 1000000, 0,
         'the smallest positive mark: 1.0 - 1.4e-45 rounds to 1.0 in float'),
        ('infinity_mark', FLOATS['infinity'], 8 + 1000000, 0,
         'an infinite mark: now - inf = -inf, which both accumulators absorb'),
        ('tiny_clock_delta', FLOATS['one'], 8 + 1000001, 0,
         'one microsecond past the mark: the delta is at the edge of float precision'),
        ('large_clock', FLOATS['one'], 8 + 86400 * 1000000, 0,
         'a day of uptime: now = 86400.0, so the delta lands exactly on a float'),
        ('mark_near_float_max', 'ffff7f7f', 8 + 1000000, 0,
         'a mark near FLT_MAX: now - mark is hugely negative but finite'),
    ]
    for cid, mark, us, base, note in accumulate:
        sec, usec = clock_us(us)
        cases.append(case(cid, mark, sec, usec, base=base, note=note))

    # -- the accumulators: same delta, not a chained sum. -------------------------------
    cases.append(case('accumulators_equal', FLOATS['one'], *clock_us(8 + 3000000),
                      sentinels=(FIRST_SENTINEL_BITS, FIRST_SENTINEL_BITS),
                      note='both accumulators start equal, so a chained sum could still pass'))
    cases.append(case('accumulators_wide_apart', FLOATS['one'], *clock_us(8 + 3000000),
                      sentinels=(FIRST_SENTINEL_BITS, SECOND_SENTINEL_BITS),
                      note='the two accumulators differ: each must receive the same delta'))
    cases.append(case('accumulators_swapped', FLOATS['one'], *clock_us(8 + 3000000),
                      sentinels=(SECOND_SENTINEL_BITS, FIRST_SENTINEL_BITS),
                      note='the sentinels swapped, so a transposed pair of stores shows up'))

    # -- the base global: the subtraction must read it, not a constant. -----------------
    cases.append(case('base_override', FLOATS['one'], *clock_us(5000000), base=0,
                      note='base is not the shipped 8: the subtraction must use the global'))
    cases.append(case('base_high_bit', FLOATS['one'], *clock_us(1000000), base=1 << 63,
                      note='a base with the top bit set, so the difference wraps low'))

    for entry in cases:
        with open(os.path.join(out_dir, entry['id'] + '.json'), 'w') as f:
            json.dump(entry, f, indent=2)
            f.write('\n')

    print(f'{len(cases)} cases written to {out_dir}')


if __name__ == '__main__':
    main()
