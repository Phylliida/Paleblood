// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: one per-frame tick of the timer that stop_and_accumulate.cpp feeds.
//
// The object is the same one 0x01448580 and 0x01448620 write: floats at 0x3c, 0x40, 0x44, 0x48,
// 0x54 and 0x58, counters at 0x4c, 0x50 and 0x5c. Where those two *sample* the clock, this one
// does the bookkeeping on what they accumulated, and it never calls the clock itself -- the whole
// function is register arithmetic over the caller's struct, with no imports and no calls.
//
// It runs in two stages and the stages are independent. The first is an average that only closes
// every 30th frame: the counter at 0x5c is incremented, and when the value it *held* was >= 29 the
// accumulated floats are divided by the new count into the paired smoothed fields and the
// accumulators are zeroed. The second stage runs on every call: it rolls the low peak at 0x4c into
// the high peak at 0x50, and the low float at 0x54 into the high float at 0x58, zeroing both lows.
//
// Three details of the average stage are easy to get subtly wrong.
//
// The comparison is against 29 with JL, and it tests the *old* count, so the average closes on the
// tick that takes the counter from 29 to 30 and leaves it holding 30. An implementation that
// increments after the test, or that compares the new count against 30, closes one tick late: the
// counter in the buffer and the divisor both give it away, because the divisor is the new count
// (VCVTSI2SS of EAX after the store, not of ECX before it).
//
// Both divisions reuse one divisor register and, more importantly, one XMM register: the original
// computes VCVTSI2SS xmm1 from EAX once, then VCVTSS2SI-free VCVTSI2SS xmm0 for the second numerator
// overwrites only xmm0. The divisors are therefore the same float for both averages.
//
// The second numerator conversion, VCVTSI2SS xmm0, xmm0, DWORD PTR [rdi+0x44], takes the *integer*
// at 0x44 read as a signed 32-bit two's-complement value, not the float that happens to share those
// bytes. The first numerator is a genuine float load (VMOVSS from 0x3c). The two fields next to each
// other are read as different types, which is exactly the kind of thing a plausible rewrite gets
// wrong, so the cases carry bit patterns that are large negatives as integers and ordinary values as
// floats.
//
// The peak stage uses CMOVGE on signed integers and VMAXSS on floats. The integer side is a signed
// comparison, so the "peaks" are ordered in two's complement: a negative low is never above a
// positive high no matter how large its magnitude.
//
// The float side is the one that bites. VMAXSS xmm0, xmm0, [rdi+0x58] computes max(first operand =
// the value at 0x54, second operand = the value at 0x58) and, as MAXSS always has, returns its
// *second* operand on a tie and whenever either operand is NaN. So a NaN at 0x58 is written back
// over itself -- the store executes but the bytes do not move -- while a NaN at 0x54 is discarded in
// favour of 0x58. A C `low > high ? low : high` test looks equivalent and is not: on an unordered
// pair it yields the *low*, so it writes the value from 0x54 into 0x58 where the original wrote the
// NaN. engine::max_of is that same relation and is what the project uses for it, and the cases carry
// a NaN in each position separately for exactly this reason.
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "../engine/scalar.h"

namespace {

// The two stages' field offsets, named for the role each plays in the original's arithmetic.
constexpr std::size_t frame_accumulator = 0x3c;      // float, summed by 0x01448620
constexpr std::size_t frame_average = 0x40;          // float, the smoothed result
constexpr std::size_t byte_accumulator = 0x44;       // int32, converted, never read as a float
constexpr std::size_t byte_average = 0x48;           // float
constexpr std::size_t low_peak_count = 0x4c;         // int32
constexpr std::size_t high_peak_count = 0x50;        // int32, max of the lows
constexpr std::size_t low_peak_float = 0x54;         // float, maxed by 0x01448620
constexpr std::size_t high_peak_float = 0x58;        // float
constexpr std::size_t average_frame_counter = 0x5c;  // int32, wraps at 30

// The average closes on the tick whose *previous* count was >= 29, i.e. on the 30th.
constexpr int32_t average_period_ticks = 29;

template <typename T>
T load(const unsigned char *base, std::size_t offset)
{
    T value;
    std::memcpy(&value, base + offset, sizeof value);
    return value;
}

template <typename T>
void store(unsigned char *base, std::size_t offset, T value)
{
    std::memcpy(base + offset, &value, sizeof value);
}

// VMAXSS xmm0, xmm0, [rdi+0x58] then a 32-bit store back to 0x58: max of the two, taking the second
// operand when they tie or either is NaN. The store is unconditional, as the original's is -- when
// the result is the NaN already sitting there the bytes do not change, which is invisible to a
// write-tracing comparison whether or not the store is conditional, so a conditional store would
// only add machinery that can hide the value actually computed.
void store_max_single(unsigned char *base, float low, float high)
{
    store<float>(base, high_peak_float, engine::max_of(low, high));
}

}  // namespace

extern "C" void bb_frame_timing_average_frame_014486d0(void *object)
{
    auto *base = static_cast<unsigned char *>(object);

    // Stage one: the 30-frame average.
    const int32_t previous = load<int32_t>(base, average_frame_counter);
    const int32_t count = previous + 1;
    store<int32_t>(base, average_frame_counter, count);

    if (previous >= average_period_ticks) {
        const float divisor = static_cast<float>(count);

        const float frames = load<float>(base, frame_accumulator);
        store<float>(base, frame_average, frames / divisor);
        store<float>(base, frame_accumulator, 0.0f);

        const float bytes = static_cast<float>(load<int32_t>(base, byte_accumulator));
        store<float>(base, byte_average, bytes / divisor);
        store<int32_t>(base, byte_accumulator, 0);

        store<int32_t>(base, average_frame_counter, 0);
    }

    // Stage two: roll both peaks, on every call.
    const int32_t count_low = load<int32_t>(base, low_peak_count);
    const int32_t count_high = load<int32_t>(base, high_peak_count);
    store<int32_t>(base, high_peak_count, count_low > count_high ? count_low : count_high);
    store<int32_t>(base, low_peak_count, 0);

    const float float_low = load<float>(base, low_peak_float);
    const float float_high = load<float>(base, high_peak_float);
    store_max_single(base, float_low, float_high);
    store<float>(base, low_peak_float, 0.0f);
}
