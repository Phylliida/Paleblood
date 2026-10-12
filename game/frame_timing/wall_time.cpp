// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: microseconds from gettimeofday as one 64-bit count.
//
// frame_timing_get_wall_time_us (0x02e61140) reads the wall clock, converts the timeval to whole
// microseconds and returns them as a 64-bit value. Unlike the two monotonic clocks
// (monotonic_clock.cpp, monotonic_clock_us.cpp) it does not subtract a first-call base: it is an
// absolute timestamp, not an elapsed one, and it keeps no state between calls.
//
// Both halves of the conversion are 64-bit, so nothing truncates: seconds*1000000 + microseconds
// wraps only past 292471 years, and a negative seconds value (a clock set before 1970) stays
// negative rather than becoming a huge positive count. The frame limiter divides this kind of
// timestamp by a period to get a frame index, which is why the width matters.
//
// The function carries a stack canary (the cookie at *0x057e3be0, checked before every return).
// The replacement keeps no locals that could overrun, so there is no cookie to check; both sides
// read the same valid cookie in the harness, so the failure path runs on neither.
#include <cstdint>

#include "runtime/original.h"

namespace {

struct Timeval {
    int64_t seconds;
    int64_t microseconds;
};

// The executable's call stub for gettimeofday.
RT_ORIGINAL(0x02fbe728, c_gettimeofday, int(Timeval *, void *timezone));

// Microseconds in a second: the original's IMUL RAX,qword ptr [RBP + -0x20],0xf4240.
constexpr int64_t us_per_second = 1000000;

}  // namespace

extern "C" int64_t bb_frame_timing_get_wall_time_us()
{
    Timeval tv;
    c_gettimeofday(&tv, nullptr);
    return tv.seconds * us_per_second + tv.microseconds;
}
