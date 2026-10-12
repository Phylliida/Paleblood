// SPDX-License-Identifier: GPL-2.0-or-later
// Engine: the wall clock as a 128-bit id, salted with a process-wide counter.
//
// engine_time_id (0x02e61280) reads the wall clock, folds a counter that lives at 0x0570d83c
// into the result, and returns 128 bits in RAX:RDX. Each half packs two 32-bit fields, low field
// first, so neither half is a plain number:
//
//   RAX = uint32(seconds)                   | uint64(uint32(microseconds)) << 32
//   RDX = uint32(seconds + counter)         | uint64(uint32(microseconds + counter + 1)) << 32
//
// The counter is read once, bumped by two, and stored back, so successive calls see 0, 2, 4, ...
// and RDX's second field is one ahead of its first. Both are built as 32-bit sums: the addends
// are the low 32 bits of each timeval field and the arithmetic wraps, so a time past 2106 is
// carried only in its low 32 bits.
//
// One trap in reading the original: it copies the stack cookie into RAX at entry, but RAX is
// overwritten by the microsecond half long before the return, so the cookie is compared but
// never returned. The returned value depends on the clock and the counter only.
//
// The other trap is the addressing: the counter at 0x0570d83c is a plain global read in place,
// while 0x057e3be0 holds the address of the stack cookie. A raw cast to a pointer dereferences
// the PS4 address in the host, which is not where the image is mapped -- it faults. rt::ptr
// applies rt_guest, as every guest access must.
//
// timeval is the 32-bit form described above (see wall_time.cpp for the 64-bit one).
#include <cstdint>

#include "runtime/original.h"

namespace {

struct Timeval {
    int64_t seconds;
    int64_t microseconds;
};

// The two 64-bit halves the original returns in RAX:RDX. A struct of two members is returned in
// exactly those two registers, in this order.
struct TimeId {
    uint64_t low;
    uint64_t high;
};

// The executable's call stub for gettimeofday.
RT_ORIGINAL(0x02fbe728, c_gettimeofday, int(Timeval *, void *timezone));

// The counter the result is salted with. The original loads it with a direct
// `mov edx, [rip+...]` -- one access, no pointer -- so rt::ptr<uint32_t> is the whole story.
constexpr uint32_t counter_address = 0x0570d83c;

// The stack cookie. The original loads the *slot*, `mov rbx, [rip+...]`, then reads the cookie
// through it, `mov rax, [rbx]`, so the slot holds an address and the cookie itself is one more
// indirection away. Only a saved copy and the comparison are used: the microsecond half
// overwrites RAX long before the return, so the cookie never reaches either half of the result.
constexpr uint32_t canary_slot = 0x057e3be0;

// Each half of the result is a 32-bit value, so the packing shift is one half's width.
constexpr unsigned bits_per_half = 32;

// One call advances the counter twice: once on its own, and once more because the second half of
// the result is built from the value the counter would have on the next call.
constexpr uint32_t counter_increment = 2;

}  // namespace

extern "C" TimeId bb_engine_time_id()
{
    Timeval tv;
    c_gettimeofday(&tv, nullptr);

    uint32_t *counter = rt::ptr<uint32_t>(counter_address);
    const uint32_t current = *counter;
    *counter = current + counter_increment;

    const uint32_t seconds = static_cast<uint32_t>(tv.seconds);
    const uint32_t microseconds = static_cast<uint32_t>(tv.microseconds);

    const uint64_t cookie_address = *rt::ptr<uint64_t>(canary_slot);
    const uint32_t cookie = *reinterpret_cast<const volatile uint32_t *>(cookie_address);
    (void)cookie;

    return TimeId{
        static_cast<uint64_t>(seconds) | (static_cast<uint64_t>(microseconds) << bits_per_half),
        static_cast<uint64_t>(current + seconds) | (static_cast<uint64_t>(current + 1 + microseconds) << bits_per_half),
    };
}
