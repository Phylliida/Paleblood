// SPDX-License-Identifier: GPL-2.0-or-later
// The monotonic clock both of the game's millisecond and microsecond clock helpers read:
// sceKernelClockGettime(CLOCK_MONOTONIC) plus the clock state object, which keeps the seconds of
// the first call so every later call can subtract it.
//
// The state object is reached through a pointer stored at 0x056d6ae8 (not through an object that
// lives there), which is why the global's type is a pointer to the state. Both helpers share it:
// the first of the two to run fixes the base, so a program that calls the microsecond clock first
// reads milliseconds from the same origin.
//
// monotonic_clock.cpp (the millisecond clock) still declares its own copies of these: pointing it
// at this header would change the source hash its verification.csv rows record, and re-running
// those needs the recorded captures, so the two files are consolidated only when someone can
// re-record the millisecond cases (NEXT.md, readability burn-down).
#pragma once

#include <cstddef>
#include <cstdint>

#include "runtime/original.h"

namespace frame_timing {

struct Timespec {
    int64_t seconds;
    int64_t nanoseconds;
};

struct ClockState {
    uint8_t unknown_0x00[0x10];
    int32_t base_seconds;   // the seconds of the first call; 0 until then
};
static_assert(offsetof(ClockState, base_seconds) == 0x10);

// The executable's call stub for sceKernelClockGettime.
RT_ORIGINAL(0x02fbfe58, kernel_clock_gettime, int(int clock_id, Timespec *ts));
RT_GLOBAL(0x056d6ae8, clock_state_instance, ClockState *);

// CLOCK_MONOTONIC, the id both helpers ask for.
constexpr int clock_monotonic = 4;
// Returned unchanged when the clock call fails (*out is not written).
constexpr int clock_error = 0x21;

}  // namespace frame_timing
