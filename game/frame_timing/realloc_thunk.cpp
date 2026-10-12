// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the realloc thunk.
//
// frame_timing_realloc_thunk_0111a600 (0x0111a600) is eight bytes and two instructions:
//
//     MOVSXD RSI,ESI     ; sign-extend the size
//     JMP 0x02fbfe38     ; tail call to realloc
//
// It is a tail call, not a call: there is no frame, no saved return address and no adjustment of
// the result, so realloc's return value (and realloc's failure path, including the NULL it
// returns for a refused request) reaches the caller untouched. The parameter registers are the
// caller's own, so the pointer in RDI is not examined here either.
//
// The one transformation is MOVSXD: a 32-bit *signed* size is widened into the 64-bit argument.
// A size whose top bit is set therefore becomes a negative 64-bit count rather than a large
// positive one, and realloc sees a request it cannot satisfy. The declared parameter is int32_t
// rather than int64_t for exactly that reason -- taking the size as int64_t would leave the upper
// half of the caller's register in the value, where the original discards it.
#include <cstdint>

#include "runtime/original.h"

namespace {

// The executable's call stub for realloc. Unlike the I/O wrappers this one really is a tail call,
// so its result is this function's result.
RT_ORIGINAL(0x02fbfe38, c_realloc, void *(void *block, uint64_t size));

}  // namespace

extern "C" void *bb_frame_timing_realloc_thunk_0111a600(void *block, int32_t size)
{
    return c_realloc(block, static_cast<uint64_t>(static_cast<int64_t>(size)));
}
