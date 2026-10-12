#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for the debug print wrapper, for tools/verify.py run.

usage: print_wrapper_cases.py OUT_DIR

frame_timing_yield_0111a740 (0x0111a740) loads the FILE * out of its own image at 0x057e40c0 and
calls fputs with it, then returns a constant zero. The cases therefore preset that global rather
than scripting it:

  * the stream the kernel sees is exactly the 64 bits that were at 0x057e40c0, so a replacement
    that substituted a real stdout -- or that read the slot as a value instead of as a pointer
    slot -- produces a different argument and the comparison notices;
  * the string is the caller's first argument, forwarded untouched, including when it is null;
  * the return is zero whether fputs succeeded or failed. fputs reports EOF on error and this
    wrapper discards it, so the failing case is the one that proves the result is constant.

The value written to the global is a recognisable non-zero address rather than a real FILE *, so
that a write that silently did not happen cannot pass as a correct read.
"""
import json
import os
import sys

ADDRESS = '0x0111a740'
FPUTS = 'fputs'

# The slot the wrapper reads its stream from, inside the executable's image.
STDOUT_SLOT = 0x057E40C0

# Stand-in for the FILE *: an address nothing in the harness maps. The wrapper never looks through
# it, so it only has to survive being forwarded intact.
STREAM = 0x00007F2A1234ABCD

TEXT_SIZE = 16


def case(cid, text_offset=0, ret=None, stream=STREAM):
    """An fputs of TEXT answered with RET, with STREAM preloaded into the image's stdout slot."""
    imports = {'name': FPUTS, 'argc': 2}
    if ret is not None:
        imports['ret'] = ret
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i32',
        'args': {'rdi': f'buf:text+{text_offset}'},
        'buffers': {'text': {'size': TEXT_SIZE, 'bytes': '4142434445464748494a4b4c4d4e4f50'}},
        'memory': [{'addr': hex(STDOUT_SLOT), 'bytes': stream.to_bytes(8, 'little').hex()}],
        'imports': [imports],
    }


CASES = [
    # A successful write: fputs returns a non-negative count, and the wrapper still returns zero.
    case('print_success', ret=6),
    # A failed write: fputs returns EOF (-1). The wrapper's zero is constant, so this and the
    # success above must look identical from the outside.
    case('print_failed', ret=-1),
    # fputs returned something with the top bit set for another reason.
    case('print_failed_all_ones', ret=0xFFFFFFFF),
    # The string is the caller's: a different offset into the same buffer is a different argument.
    case('print_offset_string', text_offset=4, ret=3),
    # A null string reaches fputs, which this wrapper does not guard against.
    case('print_null_string', ret=-1),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out = os.path.join(sys.argv[1], ADDRESS)
    os.makedirs(out, exist_ok=True)
    for c in CASES:
        if c['id'] == 'print_null_string':
            c['args']['rdi'] = '0x0'
        with open(os.path.join(out, f"{c['id']}.json"), 'w') as f:
            json.dump(c, f, indent=1)
    print(f'{len(CASES)} cases written to {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
