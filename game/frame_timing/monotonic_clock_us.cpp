// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the game's monotonic microsecond clock.
//
// frame_timing_get_monotonic_us (0x0111a760) reads CLOCK_MONOTONIC and writes the microseconds
// since its first call to *out. The millisecond clock at 0x0111a7f0 is the same function with
// coarser arithmetic, and both keep the seconds of their first call in the shared clock state
// object (monotonic_clock.h). Only the milliseconds differ: their nanoseconds are divided by
// 1,000 here and by 1,000,000 there, so the result is microseconds, not milliseconds.
//
// The game truncates nanoseconds to microseconds rather than rounding, and every piece of the
// arithmetic is 32-bit and wraps, as in the original. The fixed step (BB_TARGET_FPS) does not
// change this function.
#include <cstddef>
#include <cstdint>

#include "monotonic_clock.h"
#include "runtime/original.h"

namespace {

using frame_timing::ClockState;
using frame_timing::clock_error;
using frame_timing::clock_monotonic;
using frame_timing::clock_state_instance;
using frame_timing::kernel_clock_gettime;
using frame_timing::Timespec;

constexpr uint32_t us_per_second = 1000000, ns_per_us = 1000;

}  // namespace

extern "C" int bb_frame_timing_get_monotonic_us(uint32_t *out)
{
    Timespec ts;
    if (kernel_clock_gettime(clock_monotonic, &ts) != 0) return clock_error;
    ClockState *state = clock_state_instance.get();
    const uint32_t seconds = static_cast<uint32_t>(ts.seconds);
    if (state->base_seconds == 0) state->base_seconds = static_cast<int32_t>(seconds);
    const uint32_t elapsed_us = (seconds - static_cast<uint32_t>(state->base_seconds)) * us_per_second;
    *out = elapsed_us + static_cast<uint32_t>(ts.nanoseconds) / ns_per_us;
    return 0;
}
