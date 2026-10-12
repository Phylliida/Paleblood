#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_failed_read (0x0111a6e0), for tools/verify.py run.

usage: io_wrapper_cases.py OUT_DIR

The function reads into a buffer and reports through two channels at once: the count in *out and a
status word as the return. The cases pin down each path and the priority between them:

  * a negative kernel result sets *out to 0 and returns 0x13, whatever the count was;
  * a short read returns 0x16 but still writes the count it got;
  * a full read returns 0 and writes the count;
  * the count written to *out is the kernel's value truncated to 32 bits, not a re-derivation;
  * *out is written on every path, so a caller ignoring the return cannot see a stale count.

The count is truncated to 32 bits on the way in, so the request size is 32-bit here.
"""
import json
import os
import sys

ADDRESS = '0x0111a6e0'
READ = 'sceKernelRead'

BUFFER_SIZE = 64


def case(cid, count, got=None, ret=None, fd=7):
    """A read of COUNT bytes that the kernel answers with GOT bytes or a negative RET."""
    imports = {'name': READ, 'argc': 3}
    if ret is not None:
        imports['ret'] = ret
    write = {}
    if got:
        write = {'arg': 1, 'offset': 0, 'size': got, 'bytes': bytes((0x40 + i) & 0xff for i in range(got)).hex()}
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i32',                    # the status word; the count itself lands in *out
        'args': {'rdi': hex(fd), 'rsi': 'buf:data', 'rdx': hex(count), 'rcx': 'buf:out'},
        'buffers': {
            'data': {'size': BUFFER_SIZE, 'bytes': '5a' * BUFFER_SIZE},
            'out': {'size': 8, 'bytes': 'a5a5a5a5a5a5a5a5'},
        },
        'memory': [],
        'imports': [dict(imports, **({'writes': [write]} if write else {}))],
    }


CASES = [
    # A full read: the kernel answers with exactly the count asked for.
    case('full_read', 16, got=16),
    case('full_read_one_byte', 1, got=1),
    # A short read: the kernel has fewer bytes than asked for.
    case('short_read', 16, got=7),
    case('short_read_by_one', 16, got=15),
    case('count_one_got_zero', 1, got=0),
    # A zero-byte request: the kernel returns 0, which equals the count, so this is a full read.
    case('zero_count', 0, got=0),
    # A failed read: the kernel returns a negative errno. *out must be zeroed, not left alone.
    case('read_failed', 16, ret=-1),
    case('read_failed_einval', 16, ret=-22),
    case('read_failed_with_zero_count', 0, ret=-9),
    # The count is 32-bit on the way in and the kernel's answer is truncated on the way out: a
    # negative-looking 32-bit count is a large positive one here.
    case('count_high_bit', 0x80000000, got=4),
    case('count_max', 0xFFFFFFFF, got=8),
    case('fd_negative', 16, got=16, fd=-1),
    case('fd_zero', 16, got=16, fd=0),
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
