// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: sleep for a number of microseconds (sceKernelUsleep wrapper).
//
// frame_timing_sleep (0x0111a880) is the game's sleep-for-microseconds helper: it multiplies its
// argument by 1000 and passes the result to sceKernelUsleep, which takes nanoseconds, then
// returns 0 whatever the kernel call returned. The multiplication is 32-bit and wraps, and the
// stub takes a 32-bit argument, so the zero-extended wrapped product is what the kernel sees: a
// caller asking for more than about 4295 seconds of sleep gets a short sleep instead.
//
// Its 20 callers are all in 0x0110e...-0x0121b..., the region the two monotonic clock helpers
// live in (monotonic_clock.cpp, monotonic_clock_us.cpp), so this is the same layer: the back-off
// sleeps of that middleware's timing path. It is the microsecond counterpart of the frame
// limiter's kernel_usleep call, which passes nanoseconds to the same stub directly.
#include <cstdint>

#include "runtime/original.h"

namespace {

// The executable's call stub for sceKernelUsleep (nanoseconds).
RT_ORIGINAL(0x02fbfe68, kernel_usleep, int(uint32_t nanoseconds));

// Nanoseconds in a microsecond: the original's IMUL EDI,EDI,0x3e8.
constexpr uint32_t ns_per_us = 1000;

}  // namespace

extern "C" uint64_t bb_frame_timing_sleep(uint32_t microseconds)
{
    kernel_usleep(microseconds * ns_per_us);
    return 0;
}
