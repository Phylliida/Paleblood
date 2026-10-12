#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for frame_timing_open_and_stat (0x0111a620), for tools/verify.py run.

usage: open_stat_cases.py OUT_DIR

The function has two chained fallible steps and two out parameters, and its contract is about what
it does *not* write as much as what it does:

  * a failed open returns 0x17 and leaves both out pointers untouched;
  * a failed fstat returns 0x21 and likewise leaves both untouched;
  * success returns 0 and writes the status word to *out and the descriptor to *fd.

The cases therefore seed both out buffers with a sentinel pattern: on a success path the whole
8-byte *fd must be overwritten, and on a failure path those bytes must come back exactly as they
were. The status word is the only part of the kernel's stat structure the function reads, from
offset 0x48, so the scripting writes exactly that field and leaves the rest of the structure zero.
"""
import json
import os
import struct
import sys

ADDRESS = '0x0111a620'
OPEN = 'sceKernelOpen'
FSTAT = 'sceKernelFstat'

PATH = '/app0/data/param/param.sfo'
STAT_SIZE = 0x88
STAT_STATUS_OFFSET = 0x48
SENTINEL = 'deadbeefcafebabe'


def case(cid, fd, fstat_ret=None, status=None):
    """An open returning FD, then an fstat returning FSTAT_RET with STATUS at offset 0x48."""
    imports = [{'name': OPEN, 'argc': 3, 'ret': fd}]
    fstat = {'name': FSTAT, 'argc': 2, 'ret': 0 if fstat_ret is None else fstat_ret}
    if status is not None:
        field = struct.pack('<I', status)
        fstat['writes'] = [{'arg': 1, 'offset': STAT_STATUS_OFFSET, 'size': 4, 'bytes': field.hex()}]
    imports.append(fstat)
    return {
        'schema': 1, 'address': ADDRESS, 'id': cid,
        'returns': 'i32',                    # one of 0, 0x17, 0x21
        'args': {'rdi': 'buf:path', 'rsi': 0, 'rdx': 0, 'rcx': 'buf:out', 'r8': 'buf:fd'},
        'buffers': {
            'path': {'size': len(PATH) + 1, 'bytes': (PATH.encode() + b'\0').hex()},
            'out': {'size': 4, 'bytes': SENTINEL[:8]},
            'fd': {'size': 8, 'bytes': SENTINEL},
        },
        'memory': [],
        'imports': imports,
    }


CASES = [
    # Success: the whole 8-byte descriptor is written, sign-extended from the 32-bit value.
    case('success_fd3_status_regular', 3, status=0x81A4),
    case('success_fd_zero', 0, status=0x41ED),
    case('success_fd_high_bit', 0x7FFFFFFF, status=0),
    case('success_status_high_bit', 4, status=0x80000000),
    case('success_status_max', 5, status=0xFFFFFFFF),
    # A failed fstat: 0x21, and neither out parameter may be touched.
    case('fstat_fails', 3, fstat_ret=-1, status=0x81A4),
    case('fstat_fails_einval', 7, fstat_ret=-22),
    case('fstat_fails_positive', 7, fstat_ret=1),
    # A failed open: 0x17, and the fstat must not be reached at all.
    case('open_fails', -1),
    case('open_fails_enoent', -2),
    case('open_fails_eacces', -13),
    # The boundary the sign test turns on: -1 is a failure, 0 is a valid descriptor.
    case('open_returns_minus_one', -1),
    case('open_returns_zero', 0, status=0x2000),
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
