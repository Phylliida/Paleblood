// SPDX-License-Identifier: GPL-2.0-or-later
// Kernel shim: sleep for a number of microseconds (libc usleep wrapper).
//
// kernel_usleep (0x00466810) multiplies its argument by 1000 and passes the result to the libc
// usleep stub, which takes nanoseconds, then returns 1. It is the return value that marks this
// out as the game's own convention rather than libc usleep: libc returns 0, this returns 1, and
// the single function that calls it (0x007199f0) tests the result as a success flag.
//
// The multiplication is 32-bit and wraps before the zero-extension into the stub's 64-bit
// argument register, so an argument above 0x20c49b (about 2.1 seconds) is not a longer sleep but
// a short one. The wrapping is the original's, and is kept.
#include <cstdint>

#include "runtime/original.h"

namespace {

// The executable's call stub for libc usleep (nanoseconds).
RT_ORIGINAL(0x02fbe8d8, c_usleep, int(uint32_t nanoseconds));

// Nanoseconds in a microsecond: the original's IMUL EDI,EDI,0x3e8.
constexpr uint32_t ns_per_us = 1000;

}  // namespace

extern "C" uint8_t bb_kernel_usleep(uint32_t microseconds)
{
    c_usleep(microseconds * ns_per_us);
    return 1;
}
