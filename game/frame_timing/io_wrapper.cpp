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

// The seek and close wrappers report the same code for "the kernel refused", so the one name
// covers both.
constexpr uint32_t seek_failed = 0x13;

}  // namespace

// The executable's call stub for sceKernelLseek (0x02fbf428) and sceKernelClose (0x02fbf438).
// Both return zero on success or a negative errno, and both wrappers below collapse that to a
// single 0x13 rather than passing the kernel's own error through.
RT_ORIGINAL(0x02fbf428, kernel_lseek, int64_t(uint64_t fd, uint64_t offset, int whence));
RT_ORIGINAL(0x02fbf438, kernel_close, int32_t(uint64_t fd));

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

// Frame timing: the seek and close wrappers, from the same little I/O family as the read probe.
//
// frame_timing_seek_0111a720 (0x0111a720) is `kernel_lseek(fd, (uint32_t)offset, SEEK_SET)` with
// a sign test on the 64-bit result:
//
//   * the kernel returns a negative value -> return 0x13 (seek_failed)
//   * the kernel returns zero or more    -> return 0
//
// The tail is SAR RAX,63 then AND EAX,0x13, which is the negative-result test written without a
// branch: the shift leaves 0 for a non-negative result and all-ones for a negative one, and the
// mask turns those into 0 and 0x13. The offset is narrowed by MOV ESI,ESI before the call, so the
// parameter is 32-bit and the upper half of the caller's register is discarded -- a 64-bit caller
// seeking past 4 GiB would be truncated. The kernel's result is not returned, and its error is not
// passed through: a lseek against a closed descriptor reports 0x13 here, not the kernel's errno.
//
// frame_timing_close_0111a6b0 (0x0111a6b0) is `kernel_close(fd)` with the mirror-image test. Its
// tail is MOV ECX,0x13 / TEST EAX,EAX / CMOVE ECX,EAX, which fires on ZF=1: a kernel result of
// zero stays zero, and any non-zero result becomes 0x13 whatever it was. Only the low 32 bits are
// examined, so an error whose low word happened to be zero would read as success.
extern "C" uint32_t bb_frame_timing_seek_0111a720(uint64_t fd, uint32_t offset)
{
    return kernel_lseek(fd, offset, 0) < 0 ? seek_failed : 0;
}

extern "C" uint32_t bb_frame_timing_close_0111a6b0(uint64_t fd)
{
    const uint32_t result = static_cast<uint32_t>(kernel_close(fd));
    return result == 0 ? 0 : seek_failed;
}
