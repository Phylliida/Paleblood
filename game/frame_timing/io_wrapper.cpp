// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the middleware's failed-read probe.
//
// frame_timing_failed_read (0x0111a6e0) asks the kernel for up to count bytes and reports what it
// gets through two separate channels: the byte count in *out, and a status word as the return:
//
//   * the kernel returns a negative value  -> *out = 0, return 0x13 (a failed read)
//   * a short read (fewer bytes than asked) -> *out = got, return 0x16 (an incomplete read)
//   * a full read                           -> *out = got, return 0
//
// The status codes are the ones the game's libc uses for its own errors, and the caller
// (0x011a41a0) tests against them rather than against errno. The count is truncated to 32 bits
// before it reaches the kernel and the kernel's own count is truncated back into *out, so a
// request above 4 GiB could not be satisfied by this function even by a kernel that honoured it:
// the short-read comparison would see the truncated count on both sides.
//
// The write to *out happens in every path, including the failing one, so a caller that ignores
// the return value cannot read a stale count. It is a 32-bit store (MOV dword ptr [R14],EAX), so
// the four bytes above the count are left as they were.
#include <cstdint>

#include "runtime/original.h"

namespace {

// The executable's call stub for sceKernelRead: stub at 0x02fbf408, which carries import
// index 271 in its body half. The kernel returns the byte count, or a negative error.
RT_ORIGINAL(0x02fbf408, kernel_read, int64_t(uint64_t fd, void *buffer, uint32_t count));

constexpr uint32_t read_failed = 0x13, read_incomplete = 0x16;

}  // namespace

extern "C" uint32_t bb_frame_timing_failed_read(uint64_t fd, void *buffer, uint32_t count, uint32_t *out)
{
    const int64_t got = kernel_read(fd, buffer, count);
    if (got < 0) {
        *out = 0;
        return read_failed;
    }
    *out = static_cast<uint32_t>(got);
    return got == static_cast<int64_t>(count) ? 0 : read_incomplete;
}
