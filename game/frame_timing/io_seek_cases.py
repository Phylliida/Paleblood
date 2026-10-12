#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases for the I/O pair, for tools/verify.py run.

usage: io_seek_cases.py OUT_DIR

  * frame_timing_seek_0111a720 (0x0111a720)
  * frame_timing_close_0111a6b0 (0x0111a6b0)

Both ask the kernel for something and collapse its answer to a yes/no: zero on success, 0x13 on
any failure. The kernel's own error is discarded, so the cases check that a success is zero however
it was spelled, that every error shape becomes 0x13, and that the success of one call does not leak
into the other.

Seek narrows its offset to 32 bits (MOV ESI,ESI) before the call, so the offset cases set the high
half of the register to prove it is dropped rather than forwarded. Close examines only the low 32
bits of the kernel's result, so a non-zero answer with a zero low word is included: the original
reads it as success, and the replacement has to agree rather than be more correct.
"""
import json
import os
import sys

SEEK = '0x0111a720'
CLOSE = '0x0111a6b0'

LSEEK = 'sceKernelLseek'
KCLOSE = 'sceKernelClose'

FAILED = 0x13


def seek_case(cid, offset, ret=None, fd=7):
    """A seek on FD to OFFSET that the kernel answers with RET (0 is success)."""
    imports = {'name': LSEEK, 'argc': 3}
    if ret is not None:
        imports['ret'] = ret
    return {
        'schema': 1, 'address': SEEK, 'id': cid,
        'returns': 'i32',
        'args': {'rdi': hex(fd), 'rsi': hex(offset)},
        'buffers': {},
        'memory': [],
        'imports': [imports],
    }


def close_case(cid, ret=None, fd=7):
    """A close of FD that the kernel answers with RET (0 is success)."""
    imports = {'name': KCLOSE, 'argc': 1}
    if ret is not None:
        imports['ret'] = ret
    return {
        'schema': 1, 'address': CLOSE, 'id': cid,
        'returns': 'i32',
        'args': {'rdi': hex(fd)},
        'buffers': {},
        'memory': [],
        'imports': [imports],
    }


CASES = [
    # Seek: the kernel reports the new offset, which is any non-negative value.
    seek_case('seek_start', 0, ret=0),
    seek_case('seek_to_4096', 4096, ret=4096),
    seek_case('seek_to_large_offset', 0x7FFFFFFF, ret=0x7FFFFFFF),
    # Seek: the offset is narrowed to 32 bits before the call, so the high half is discarded. A
    # 64-bit caller seeking past 4 GiB is truncated to the low word here.
    seek_case('seek_offset_high_half_set', 0x1234567890, ret=0x34567890),
    seek_case('seek_offset_top_bit_set', 0x80000000, ret=0x80000000),
    # Seek: the kernel refuses. Every error shape becomes the same 0x13.
    seek_case('seek_failed_ebadf', 0, ret=-9),
    seek_case('seek_failed_einval', 0, ret=-22),
    seek_case('seek_failed_generic', 16, ret=-1),
    # Seek: a negative descriptor still reaches the kernel -- this wrapper runs no null check.
    seek_case('seek_fd_negative', 0, ret=-9, fd=-1),
    seek_case('seek_fd_zero', 0, ret=0, fd=0),
    # Close: zero is the only success, and every non-zero answer is the same 0x13.
    close_case('close_success', ret=0),
    close_case('close_failed_ebadf', ret=-9),
    close_case('close_failed_generic', ret=-1),
    close_case('close_failed_all_ones', ret=0xFFFFFFFF),
    # Close: only the low 32 bits are examined, so an error whose low word is zero reads as
    # success. The replacement has to reproduce that rather than report the error.
    close_case('close_error_low_word_zero', ret=0x100000000),
    close_case('close_fd_zero', ret=0, fd=0),
    close_case('close_fd_negative', ret=-9, fd=-1),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out = sys.argv[1]
    for c in CASES:
        d = os.path.join(out, c['address'])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{c['id']}.json"), 'w') as f:
            json.dump(c, f, indent=1)
    per = {a: sum(1 for c in CASES if c['address'] == a) for a in (SEEK, CLOSE)}
    print(f'{len(CASES)} cases written to {out} ({SEEK}: {per[SEEK]}, {CLOSE}: {per[CLOSE]})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
