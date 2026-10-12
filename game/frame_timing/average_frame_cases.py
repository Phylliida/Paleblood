#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_average_frame_014486d0 (0x014486d0), for tools/verify.py run.

usage: average_frame_cases.py OUT_DIR

The object is the one the timer pair writes, so its whole 0x60 bytes are compared: the smoothed
fields, the accumulators, both peaks and the counter, plus everything the function must leave alone.

Three groups of cases exist because three things in this function are easy to write plausibly and
get wrong.

  * The average period. The counter at 0x5c is incremented first and the *old* value is tested
    against 29, so the average closes on the tick that takes it from 29 to 30 and the divisor is the
    new count. The cases pin the boundary from below (28 -> 29: no average), at it (29 -> 30: average,
    divisor 30, counter back to 0), and above it (30 -> 31: an average with divisor 31, which the
    shipped function can never actually reach because it zeroes the counter, but a replacement that
    resets in the wrong place would show up here). The counter value left in the buffer separates a
    replacement that resets it from one that does not.
  * The type of each field. The first numerator at 0x3c is a float load; the second at 0x44 is a
    VCVTSI2SS of the same bytes read as a *signed 32-bit integer*. The bit patterns '000000bf' and
    '0000c0bf' are ordinary small floats (-0.5f, -1.5f) but are huge negative integers, so a
    replacement that treats both fields as floats produces a completely different 0x48.
  * The peak roll. The integers use CMOVGE, which is signed: a negative low never beats a positive
    high however large it is. The floats use VMAXSS, which returns its *source* operand when the
    comparison is equal or unordered, so low = -0.0f with high = +0.0f keeps the +0.0f and NaN
    behaves differently in the two positions. Each of those gets its own case, with a NaN in the low
    field and a NaN in the high field separately.

Every case runs both sides on the same object and the whole buffer is compared, so the expectations
below describe the original's behaviour rather than being asserted against the replacement.
"""
import json
import os
import struct
import sys

ADDRESS = '0x014486d0'

OBJECT_SIZE = 0x60
FRAME_ACCUMULATOR = 0x3c
FRAME_AVERAGE = 0x40
BYTE_ACCUMULATOR = 0x44
BYTE_AVERAGE = 0x48
LOW_PEAK_COUNT = 0x4c
HIGH_PEAK_COUNT = 0x50
LOW_PEAK_FLOAT = 0x54
HIGH_PEAK_FLOAT = 0x58
AVERAGE_FRAME_COUNTER = 0x5c

# Distinguishable values, so a transposed store cannot pass. Written as the four bytes they occupy
# in memory, little-endian, because that is how the guest reads them back.
FRAME_ACCUM_BITS = '0000c842'   # 100.0f
BYTE_ACCUM_BITS = '00000042'    # 2.0f as a float bit pattern; as an int32 this is 0x42000000
FRAME_AVERAGE_BITS = '00007042'  # 60.0f, overwritten only when the average closes
BYTE_AVERAGE_BITS = '0000803f'   # 1.0f, likewise
LOW_PEAK_COUNT_VALUE = 7
HIGH_PEAK_COUNT_VALUE = 3
LOW_PEAK_FLOAT_BITS = '00002041'   # 10.0f
HIGH_PEAK_FLOAT_BITS = '0000c841'  # 25.0f


def object_bytes(counter, frame_accum=FRAME_ACCUM_BITS, byte_accum=BYTE_ACCUM_BITS,
                 frame_average=FRAME_AVERAGE_BITS, byte_average=BYTE_AVERAGE_BITS,
                 low_count=LOW_PEAK_COUNT_VALUE, high_count=HIGH_PEAK_COUNT_VALUE,
                 low_float=LOW_PEAK_FLOAT_BITS, high_float=HIGH_PEAK_FLOAT_BITS):
    buf = bytearray(OBJECT_SIZE)
    buf[FRAME_ACCUMULATOR:FRAME_ACCUMULATOR + 4] = bytes.fromhex(frame_accum)
    buf[FRAME_AVERAGE:FRAME_AVERAGE + 4] = bytes.fromhex(frame_average)
    buf[BYTE_ACCUMULATOR:BYTE_ACCUMULATOR + 4] = bytes.fromhex(byte_accum)
    buf[BYTE_AVERAGE:BYTE_AVERAGE + 4] = bytes.fromhex(byte_average)
    buf[LOW_PEAK_COUNT:LOW_PEAK_COUNT + 4] = struct.pack('<i', low_count)
    buf[HIGH_PEAK_COUNT:HIGH_PEAK_COUNT + 4] = struct.pack('<i', high_count)
    buf[LOW_PEAK_FLOAT:LOW_PEAK_FLOAT + 4] = bytes.fromhex(low_float)
    buf[HIGH_PEAK_FLOAT:HIGH_PEAK_FLOAT + 4] = bytes.fromhex(high_float)
    buf[AVERAGE_FRAME_COUNTER:AVERAGE_FRAME_COUNTER + 4] = struct.pack('<i', counter)
    return bytes(buf).hex()


def case(cid, counter, note=None, **fields):
    entry = {
        'schema': 1,
        'address': ADDRESS,
        'id': cid,
        'returns': 'void',
        'args': {'rdi': 'buf:object'},
        'buffers': {'object': {'size': OBJECT_SIZE,
                               'bytes': object_bytes(counter, **fields)}},
    }
    if note:
        entry['note'] = note
    return entry


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: average_frame_cases.py OUT_DIR')
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)

    cases = []

    # -- the average period: the counter is incremented, then the old value tested. -------
    for counter, note in (
        (0, 'the first tick: counter 0 -> 1, no average, and the peaks still roll'),
        (1, 'the second tick: 1 -> 2, still no average'),
        (27, 'two below the boundary: 27 -> 28, no average'),
        (28, 'one below: 28 -> 29, no average, and the counter is left holding 29'),
        (29, 'the boundary: 29 -> 30, the average closes with divisor 30.0f and the counter resets'),
        (30, 'one above: 30 -> 31, an average with divisor 31.0f. Unreachable in a running timer '
             'because the boundary already reset it, so only a replacement that resets the counter '
             'in the wrong place arrives here'),
        (-1, 'a counter of -1: it increments to 0 and takes the short path'),
        (-29, 'a negative counter far below the boundary: still no average'),
        (100, 'a counter well past the boundary, so the average cannot be a one-shot special case'),
    ):
        cases.append(case(f'period_counter_{counter}'.replace('-', 'negative_'), counter, note=note))

    # -- the type of each numerator. -----------------------------------------------------
    # '000000bf' is -0.5f read as a float and 0xbf000000 = -1090519040 read as an int32.
    cases.append(case('numerator_byte_field_is_int', 29,
                      frame_accum='0000803f',          # 1.0f
                      byte_accum='000000bf',
                      note='0x44 holds bits that are -0.5f as a float and -1090519040 as an int32; '
                           'the divisor is 30.0f, so the two readings differ hugely at 0x48'))
    cases.append(case('numerator_byte_field_large_negative', 29,
                      frame_accum='0000803f',
                      byte_accum='0000c0bf',
                      note='-1.5f as a float, -1077936128 as an int32'))
    cases.append(case('numerator_both_odd_floats', 29,
                      frame_accum='0000c842',          # 100.0f
                      byte_accum='00007042',           # 60.0f as a float; a large int32
                      note='both accumulators carry exact float values that are not exact as '
                           'floats after the conversion from int32'))
    cases.append(case('numerator_zero_accumulators', 29,
                      frame_accum='00000000', byte_accum='00000000',
                      note='both numerators are zero, so both averages become zero and the sign '
                           'comes from the divisor'))
    cases.append(case('numerator_top_bit_set', 29,
                      frame_accum='0000807f',          # +inf
                      byte_accum='ffffffff',           # -1 as int32
                      note='an infinite float numerator and an int32 of -1: inf/30 is inf, and '
                           '-1/30 rounds to -0.0333333f'))

    # -- the peak roll. ------------------------------------------------------------------
    cases.append(case('peak_count_low_above', 1, low_count=9, high_count=3,
                      note='the low integer beats the high: it is copied up and the low is zeroed'))
    cases.append(case('peak_count_low_below', 1, low_count=2, high_count=11,
                      note='the high integer already holds more, so it is kept unchanged'))
    cases.append(case('peak_count_equal', 1, low_count=5, high_count=5,
                      note='equal integers: CMOVGE keeps the high operand either way'))
    cases.append(case('peak_count_negative_low', 1, low_count=-1, high_count=1,
                      note='a signed comparison: -1 is below +1, so the negative low is discarded '
                           'rather than copied up by magnitude'))
    cases.append(case('peak_count_both_negative', 1, low_count=-1, high_count=-9,
                      note='-1 is above -9, so the less negative low is copied up'))
    cases.append(case('peak_count_low_zero', 1, low_count=0, high_count=0,
                      note='both zero: the branch order is unobservable, only the zeroing is'))

    cases.append(case('peak_float_low_above', 1, low_float='00002041', high_float='0000c841',
                      note='10.0f against 25.0f: the high is kept'))
    cases.append(case('peak_float_low_below', 1, low_float='0000a041', high_float='0000c841',
                      note='20.0f against 25.0f: still the high'))
    cases.append(case('peak_float_low_wins', 1, low_float='0000fa43', high_float='0000c841',
                      note='500.0f against 25.0f: the low is copied up'))
    cases.append(case('peak_float_tie_zero_sign', 1, low_float='00000080', high_float='00000000',
                      note='low -0.0f against high +0.0f. VMAXSS returns its source operand when '
                           'the comparison is equal, so the +0.0f at 0x58 survives -- a `low > high` '
                           'test keeps the -0.0f instead'))
    cases.append(case('peak_float_tie_zero_sign_reversed', 1, low_float='00000000', high_float='00000080',
                      note='the same tie the other way up: +0.0f low against -0.0f high, and the '
                           'source is now the -0.0f, so that is what survives'))
    cases.append(case('peak_float_nan_low', 1, low_float='0000c07f', high_float='0000c841',
                      note='a NaN low against 25.0f: unordered, so VMAXSS returns the source, 25.0f'))
    cases.append(case('peak_float_nan_high', 1, low_float='00002041', high_float='0000c07f',
                      note='10.0f low against a NaN high: unordered, so the source operand wins '
                           'again -- the NaN survives in 0x58, which `if (high < low) high = low` '
                           'would not do'))
    cases.append(case('peak_float_nan_both', 1, low_float='0000c07f', high_float='0000c0ff',
                      note='a quiet NaN against a negative quiet NaN: the source is returned, so '
                           'the payload and sign of the high field are preserved'))
    cases.append(case('peak_float_infinities', 1, low_float='0000807f', high_float='000080ff',
                      note='+inf low against -inf high: the low wins and is copied up'))

    # -- every field at once, so nothing is left only partially covered. ------------------
    cases.append(case('all_fields_engaged', 29,
                      frame_accum='0000c842', byte_accum='00002042',
                      frame_average='00007042', byte_average='0000803f',
                      low_count=-3, high_count=-3, low_float='0000c07f', high_float='00000080',
                      note='the average closes, both peaks roll, and the tie and NaN cases are '
                           'combined in one call'))

    for entry in cases:
        with open(os.path.join(out_dir, entry['id'] + '.json'), 'w') as f:
            json.dump(entry, f, indent=2)
            f.write('\n')

    print(f'{len(cases)} cases written to {out_dir}')


if __name__ == '__main__':
    main()
