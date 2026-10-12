// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: seconds since a base, latched once into a float carried by the caller's object.
//
// The function at 0x01448580 reads the wall clock through gettimeofday, turns the timeval into
// whole microseconds the same way frame_timing_get_wall_time_us (wall_time.cpp) does, subtracts
// the base at 0x05940660, and divides by 1000000 to get seconds. The quotient is stored as a float
// at offset 0x38 of the object, and two 32-bit counters in the same object are bumped.
//
// The latch: the object's float is left alone unless it is *exactly* zero, and the counters are
// bumped only on the same path. The test the original uses is two branches -- JNZ and JP, the
// idiom `x == 0.0f`, which is true for a positive zero but false for a negative zero and false for
// any NaN. It is not `!(x != 0.0f)`, which would also be true for -0.0f. This replacement keeps one
// comparison so that every other value takes the same path, NaN included.
//
// The stored value is a float: the original computes in double and narrows with VCVTSD2SS before
// the store. The microsecond count reaches that double through the unsigned 64-bit conversion,
// which clang (the original's compiler, -O2) emits as VPUNPCKLDQ against 0x4530000043300000,
// VSUBPD against 0x4330000000000000 and VHADDPD. The count and the base are uint64_t here because
// that operand type is what the original compiled from: a signed operand takes a different route
// even on clang. The conversion itself is left to the compiler rather than restated as bit
// manipulation, because this tree builds with g++ at -g -O0 (no optimisation flags), and g++
// lowers an unsigned 64-bit to double through CVTSI2SD and an ADDSD under a sign test. The two
// lowerings agree on the value they produce -- the same standard rounding, exactly representable
// in the one case that matters here, a quotient of microseconds by 1000000.0 -- and the case
// suite compares that value, not the instruction sequence.
//
// The base at 0x05940660 is a plain 64-bit global read in place (MOV RAX,[RCX]); nothing in the
// tree names it yet, so it is named here for what it does to this function. Its shipped value is
// 8, which makes a first call on a stock clock produce 0.0f -- but nothing establishes that the
// loader does not rewrite it, and the value is not what makes the function correct either way.
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

// Seconds since the base, as the object carries it.
RT_GLOBAL(0x05940660, clock_base_us, uint64_t);

// Microseconds in a second: the original's IMUL RAX,qword ptr [RBP + -0x28],0xf4240.
constexpr int64_t us_per_second = 1000000;

constexpr std::size_t elapsed_seconds_offset = 0x38;
constexpr std::size_t first_counter_offset = 0x44;
constexpr std::size_t second_counter_offset = 0x4c;

}  // namespace

extern "C" void bb_frame_timing_elapsed_seconds_01448580(void *object)
{
    auto *base = static_cast<unsigned char *>(object);

    float elapsed;
    std::memcpy(&elapsed, base + elapsed_seconds_offset, sizeof elapsed);
    if (elapsed != 0.0f) {
        return;
    }

    Timeval tv;
    c_gettimeofday(&tv, nullptr);
    const uint64_t counts = static_cast<uint64_t>(tv.seconds) * us_per_second +
                            static_cast<uint64_t>(tv.microseconds);
    const uint64_t seconds_since_base = counts - clock_base_us.get();

    elapsed = static_cast<float>(seconds_since_base / static_cast<double>(us_per_second));
    std::memcpy(base + elapsed_seconds_offset, &elapsed, sizeof elapsed);

    uint32_t counter;
    std::memcpy(&counter, base + first_counter_offset, sizeof counter);
    std::memcpy(base + first_counter_offset, &++counter, sizeof counter);
    std::memcpy(&counter, base + second_counter_offset, sizeof counter);
    std::memcpy(base + second_counter_offset, &++counter, sizeof counter);
}
