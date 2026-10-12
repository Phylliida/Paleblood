// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: wall-clock microseconds divided by a period carried by the caller's object.
//
// The function at 0x01088550 reads the wall clock through gettimeofday, turns the timeval into
// whole microseconds the same way frame_timing_get_wall_time_us (wall_time.cpp) does, and then
// divides that count by the 64-bit period stored at offset 0x1d8 of the object passed in. The
// quotient is the return value; the remainder is discarded.
//
// The division is unsigned (XOR EDX,EDX before DIV), so a result is never negative, while the
// dividend itself is built with signed loads and an IMUL -- a clock set before 1970 produces a
// negative count that, read as unsigned, divides into a very large quotient. The original does
// exactly that, and so does this: the timeval fields are int64_t here to match.
//
// Read the period with a byte offset rather than a named field. Offset 0x1d8 is what the
// instruction reads (DIV qword ptr [RBX + 0x1d8]); the decompiler prints its own guess of +0x1d0,
// and nothing establishes what the field means or what object this is, so the replacement does not
// name it. Its ten callers all live in 0x0109....-0x010d...., a region with no replaced function
// yet, so the object's type is unknown.
//
// A zero period divides by zero and takes SIGFPE, on both sides: the original faults at the DIV
// before it ever reaches its stack-canary check, so the canary is unobservable here and the
// replacement keeps none.
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

// Microseconds in a second: the original's IMUL RAX,qword ptr [RBP + -0x20],0xf4240.
constexpr int64_t us_per_second = 1000000;

// Where the caller's object carries the period it divides by.
constexpr std::size_t period_offset = 0x1d8;

}  // namespace

extern "C" uint64_t bb_engine_time_over_period(const void *object)
{
    Timeval tv;
    c_gettimeofday(&tv, nullptr);
    const uint64_t counts = static_cast<uint64_t>(tv.seconds * us_per_second + tv.microseconds);
    uint64_t period;
    std::memcpy(&period, static_cast<const unsigned char *>(object) + period_offset, sizeof period);
    return counts / period;
}
