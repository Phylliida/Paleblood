#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for kernel_index_code (0x004664e0), for tools/verify.py run.

usage: index_code_cases.py OUT_DIR

One argument, one word out, no memory written: every case is a single index passed in RDI, and the
whole point of the suite is the bound. The original tests `cmp edi,0x6; ja`, an *unsigned*
comparison, so the cases cover both sides of that reading:

  * every in-range index, including both ends. Index 6 is the last valid one and its entry (0x2ff)
    is the same as index 5's, so 6 alone would not catch an off-by-one -- 7 is the case that does,
    and it has to answer the default rather than read the byte after the table.
  * negative indices, whose bit patterns are above 6 read unsigned. A signed comparison would send
    these into the table; the original must answer the default for all of them.

The table itself is in the image's read-only data, so these cases read the shipped bytes rather
than a fixture: the suite fails if the replacement's table address is wrong, which a hard-coded
copy of the seven values would hide.

Returns i64, so the high half of RAX is compared: the original's two returns are 32-bit loads and
a 32-bit `mov eax`, all zero-extending.
"""
import json
import os
import sys

ADDRESS = '0x004664e0'

# From the shipped image at 0x02fc5480, for the docstring's benefit; the function reads the real
# table and the expectations below are not computed from a copy of it.
TABLE = (0x00000000, 0x00000001, 0x0000028a, 0x000002bc, 0x000002ee, 0x000002ff, 0x000002ff)
OUT_OF_RANGE = 0x2bc


def case(cid, index):
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid, 'returns': 'i64',
        'args': {'rdi': index & 0xffffffff},
    }


CASES = [
    # In range, both ends.
    case('index_zero', 0),
    case('index_one', 1),
    case('index_two', 2),
    case('index_three', 3),
    case('index_four', 4),
    case('index_five', 5),
    case('index_six_last_valid', 6),
    # The first index past the end. The entry after the table is not part of it, so this has to
    # answer the default.
    case('index_seven_first_invalid', 7),
    case('index_eight', 8),
    case('index_hundred', 100),
    # The largest index the unsigned comparison sees, and one that a signed comparison would read
    # as negative and index backwards with.
    case('index_negative_one', -1),
    case('index_negative_two', -2),
    case('index_int_min', -0x80000000),
    # 2**32 - 7 is exactly one below the table size when read unsigned, so an off-by-one in the
    # bound is visible here even without index 7.
    case('index_at_2_32_minus_7', 0xfffffff9),
    case('index_max_unsigned', 0xffffffff),
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
