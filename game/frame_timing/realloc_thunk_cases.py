#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for the realloc thunk, for tools/verify.py run.

usage: realloc_thunk_cases.py OUT_DIR

frame_timing_realloc_thunk_0111a600 (0x0111a600) is MOVSXD RSI,ESI followed by a tail call to
realloc. Two things follow from that shape and the cases pin both:

  * the size is sign-extended from 32 bits, so a size above 0x7FFFFFFF reaches realloc as a
    negative 64-bit count rather than as a large positive one. A replacement that declared the
    size as int64_t would forward 0x00000000FFFFFFFF instead of 0xFFFFFFFFFFFFFFFF, and the
    two are different requests.
  * the call is a tail call, so realloc's result is returned unchanged: NULL on failure, the
    pointer on success, and no adjustment in between.

The kernel side is scripted, so the cases also check that both arguments arrive as the caller
passed them -- the pointer in RDI is not examined by the thunk.
"""
import json
import os
import sys

ADDRESS = '0x0111a600'
REALLOC = 'realloc'

BLOCK_SIZE = 64

# A recognisable address for the kernel to claim it returned.
NEW_BLOCK = 0x900004000


def case(cid, size, block='buf:block', ret=None):
    """A realloc of BLOCK to SIZE that the kernel answers with RET."""
    imports = {'name': REALLOC, 'argc': 2}
    if ret is not None:
        imports['ret'] = ret
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i64',
        'args': {'rdi': block, 'rsi': size},
        'buffers': {'block': {'size': BLOCK_SIZE, 'bytes': '5a' * BLOCK_SIZE}},
        'memory': [],
        'imports': [imports],
    }


CASES = [
    # A size that fits in 32 bits and has its top bit clear: the sign extension is a no-op, so this
    # only checks that the value is forwarded at all.
    case('size_small', 0x20, ret=NEW_BLOCK),
    case('size_one', 1, ret=NEW_BLOCK),
    case('size_zero', 0, ret=NEW_BLOCK),
    case('size_max_positive', 0x7FFFFFFF, ret=NEW_BLOCK),
    # The interesting ones: the top bit of the 32-bit size is set. MOVSXD turns these into
    # negative 64-bit counts, which is a different request from the zero-extended value.
    case('size_top_bit_set', 0x80000000, ret=NEW_BLOCK),
    case('size_all_ones', 0xFFFFFFFF, ret=NEW_BLOCK),
    case('size_high_half_set', 0x1234567800000020, ret=NEW_BLOCK),
    # Failure: realloc's NULL is returned as it stands, with no status word wrapped around it.
    case('realloc_failed', 0x80000000, ret=0),
    case('realloc_failed_small_size', 0x20, ret=0),
    # A null pointer is realloc's malloc, and the thunk passes it through untouched.
    case('null_block', 0x40, block='0x0', ret=NEW_BLOCK),
    # A large pointer that is not one of the harness's buffers: the thunk does not dereference it,
    # so it must reach the kernel unchanged.
    case('block_outside_harness', 0x40, block='0x123456789ABC', ret=NEW_BLOCK),
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
