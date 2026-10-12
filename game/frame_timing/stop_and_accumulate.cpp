// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: stops the running latch, keeps the delta, accumulates it into two counters.
//
// The function at 0x01448620 is the other half of the pair whose first half lives in
// elapsed_seconds.cpp (0x01448580). It reads the same wall clock, subtracts the same base at
// 0x05940660 and divides by 1000000, so it arrives at the same number -- but instead of latching
// it, it treats it as "now", differences it against the float the object already carries at
// offset 0x38, zeroes that field and adds the difference into the floats at 0x3c and 0x54. Where
// 0x01448580 starts a measurement, this ends one: 0x38 holds the mark, 0x3c and 0x54 accumulate
// the spans between marks.
//
// The guard is a positive test, not a zero test. The original loads the float, compares it
// against 0.0f with VUCOMISS and branches on JBE, so it takes the accumulate path only when the
// field is greater than zero and returns early for a positive zero, a negative zero, every
// negative value and every NaN -- VUCOMISS leaves CF set for both "below" and "unordered".
// Because the whole body sits under `> 0.0f`, an object that was never marked accumulates
// nothing, which is what makes this safe to call on a timer that is not running.
//
// Both accumulators get the same single-precision difference: the original computes
// VSUBSS xmm0, xmm0, [RBX+0x38] once and then does two VADDSS from that one register, so the
// subtraction is rounded to float before it is added. The two stores are therefore independent
// accumulators fed one rounded delta, not two chained sums. The conversion of the microsecond
// count to float goes through the same double as in elapsed_seconds.cpp; only the final
// narrowing differs, VCVTSD2SS here against the sibling's store of an already-narrowed value.
//
// The canary the original uses is the cookie behind 0x057e3be0. The guard branch jumps to the
// canary check rather than past it, so both the accumulate path and the early return check it --
// the comparison at 0x14486b1 is the target of the JBE at 0x14486a9. This replacement keeps no
// cookie: it writes only through the caller's object, and the case suite runs both sides with a
// valid cookie, so the failure path is reached on neither.
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "runtime/original.h"

namespace {

struct Timeval {
    int64_t seconds;
    int64_t microseconds;
};

// The executable's call stub for gettimeofday.
RT_ORIGINAL(0x02fbe728, c_gettimeofday, int(Timeval *, void *timezone));

// The base the elapsed calculation subtracts, shared with 0x01448580.
RT_GLOBAL(0x05940660, clock_base_us, uint64_t);

// Microseconds in a second: the original's IMUL RAX,qword ptr [RBP + -0x28],0xf4240.
constexpr int64_t us_per_second = 1000000;

// The mark this function differences against, and the two accumulators it feeds.
constexpr std::size_t mark_offset = 0x38;
constexpr std::size_t first_accumulator_offset = 0x3c;
constexpr std::size_t second_accumulator_offset = 0x54;

}  // namespace

extern "C" void bb_frame_timing_stop_and_accumulate_01448620(void *object)
{
    auto *base = static_cast<unsigned char *>(object);

    float mark;
    std::memcpy(&mark, base + mark_offset, sizeof mark);
    if (!(mark > 0.0f)) {
        return;
    }

    Timeval tv;
    c_gettimeofday(&tv, nullptr);
    const uint64_t counts = static_cast<uint64_t>(tv.seconds) * us_per_second +
                            static_cast<uint64_t>(tv.microseconds);
    const uint64_t seconds_since_base = counts - clock_base_us.get();

    const float now = static_cast<float>(seconds_since_base / static_cast<double>(us_per_second));
    const float delta = now - mark;

    const float cleared = 0.0f;
    std::memcpy(base + mark_offset, &cleared, sizeof cleared);

    float first;
    std::memcpy(&first, base + first_accumulator_offset, sizeof first);
    first += delta;
    std::memcpy(base + first_accumulator_offset, &first, sizeof first);

    float second;
    std::memcpy(&second, base + second_accumulator_offset, sizeof second);
    second += delta;
    std::memcpy(base + second_accumulator_offset, &second, sizeof second);
}
