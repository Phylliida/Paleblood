// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: open a file descriptor and read back its size and status.
//
// frame_timing_open_and_stat (0x0111a620) opens a path, asks the kernel to stat the descriptor it
// got, and hands two things back to the caller: the file's status word in *out, and the
// descriptor itself in *fd. It is the "open and size this file" helper of the middleware's asset
// path, and the caller (0x011a40b0) is the same function that calls the read helper
// (io_wrapper.cpp), so the two are a pair: open, stat, then read exactly the size that was
// returned.
//
// The status codes are the game libc's own, and each failure is distinct:
//
//   * the open fails (negative descriptor) -> return 0x17, and neither out parameter is written
//   * the fstat fails                      -> return 0x21, and neither out parameter is written
//   * both succeed                         -> *out = the status word, *fd = the descriptor, return 0
//
// Both out parameters are left untouched on every failure path, so a caller must check the return
// before reading them. They arrive in RCX and R8 and are the fourth and fifth arguments; the two
// words between the path and *out are unused by this caller but are part of the signature, since
// the registers holding them are where the out pointers would otherwise land. The descriptor is written sign-extended (MOVSXD RAX,EBX): a negative
// descriptor would be stored as a negative 64-bit value, but that path is unreachable because
// open has already been rejected by then.
//
// The status word is read at offset 0x48 of the kernel's stat structure. The structure itself is
// 0x88 bytes here; only that one field is consumed, so the replacement keeps it as raw bytes
// rather than declaring a layout the other 0x84 bytes would have to be guessed for.
#include <cstddef>
#include <cstdint>

#include "runtime/original.h"

namespace {

// The executable's call stub for sceKernelOpen at 0x02fbf3f8: a 16-byte entry, `ff 25 <disp32>`
// jumping through its GOT slot, then `68 <imm32>` and `e9 <rel32>` to the lazy binder. The
// immediate is a small number (244 here, 409 for fstat below) that indexes this executable's own
// import table, not the loader's import list; the two numberings differ, so do not read it as a
// loader index. The name comes from the harness, which resolves the callee by NID.
// Path in RDI, flags and mode both zero in this caller.
RT_ORIGINAL(0x02fbf3f8, kernel_open, int64_t(const char *path, uint32_t flags, uint32_t mode));

// The executable's call stub for sceKernelFstat at 0x02fbfe48; same 16-byte entry shape.
RT_ORIGINAL(0x02fbfe48, kernel_fstat, int32_t(uint32_t fd, void *stat_buffer));

constexpr uint32_t open_failed = 0x17, stat_failed = 0x21;

// Bytes the kernel's stat structure occupies, and the offset of the status word inside it.
constexpr size_t stat_size = 0x88, stat_status_offset = 0x48;

}  // namespace

extern "C" uint32_t bb_frame_timing_open_and_stat(const char *path, uint32_t, uint32_t, uint32_t *out, uint64_t *fd)
{
    const int32_t descriptor = static_cast<int32_t>(kernel_open(path, 0, 0));
    if (descriptor < 0) return open_failed;
    alignas(8) uint8_t stat_buffer[stat_size] = {};
    if (kernel_fstat(static_cast<uint32_t>(descriptor), stat_buffer) != 0) return stat_failed;
    uint32_t status = 0;
    __builtin_memcpy(&status, stat_buffer + stat_status_offset, sizeof status);
    *out = status;
    *fd = static_cast<uint64_t>(static_cast<int64_t>(descriptor));
    return 0;
}
