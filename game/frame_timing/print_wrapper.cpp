// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the middleware's debug print.
//
// frame_timing_yield_0111a740 (0x0111a740) is a two-instruction wrapper around the C library's
// fputs, and it is not a yield despite the name it carries in the registry:
//
//     MOV RSI,QWORD PTR [RIP+0x46c9975]   ; the FILE * kept at 0x057e40c0
//     CALL 0x02fbf1e8                     ; fputs(string, stream)
//     XOR EAX,EAX
//     RET
//
// The string is the first argument, supplied by the caller in RDI; the function does not touch it.
// The stream is the global pointer at 0x057e40c0, which is libc's stdout. The return value is a
// constant zero, so the caller cannot tell a write that failed from one that succeeded -- fputs
// returns EOF on error and this discards it. There is no check on the string either: a null
// pointer reaches fputs.
//
// The global is read through RIP-relative addressing, i.e. from this image's own memory, and the
// executable's loader binds it: it is not a stack or register value the replacement could invent.
// Cases therefore preset 0x057e40c0 rather than scripting it.
#include <cstdint>

#include "runtime/guest.h"
#include "runtime/original.h"

namespace {

// The executable's call stub for fputs. The first argument is the caller's string and the second
// is the stdout pointer this function loaded out of its own image.
RT_ORIGINAL(0x02fbf1e8, c_fputs, int32_t(const char *text, void *stream));

// libc's stdout, in the executable's image; the loader binds it there. The original reads the
// slot in place -- `mov rsi, [rip+...]`, one access, no pointer arithmetic -- so rt::ptr is the
// whole story, and a raw cast to a pointer would dereference the PS4 address in the host.
constexpr uint32_t stdout_pointer = 0x057e40c0;

}  // namespace

extern "C" uint32_t bb_frame_timing_yield_0111a740(const char *text)
{
    const uint64_t stream = *rt::ptr<const uint64_t>(stdout_pointer);
    (void)c_fputs(text, reinterpret_cast<void *>(stream));
    return 0;
}
