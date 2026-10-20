// SPDX-License-Identifier: GPL-2.0-or-later
// Kernel: a two-way state code read out of a caller-owned object.
//
// kernel_pending_code (0x004663f0) is a leaf: it makes no calls and writes nothing. It reads two
// adjacent words of its argument and folds them into one code:
//
//   * the word at +0x34 is a count of something in flight. Tested with JG, so it is *signed*:
//     only a strictly positive value selects the first branch, and a word with the top bit set is
//     not "greater than zero" to this function.
//   * while anything is in flight the result is 2, whatever the other word says.
//   * otherwise the result is bit 0 of the word at +0x30, masked with AND (a 32-bit operation, so
//     the count of set bits matters only through bit 0).
//
// Both branches load through a 32-bit `mov eax` or `mov eax,0x2`, which zero-extends into RAX, so
// the full 64-bit return is the code with a zero high half. The caller's object is only read.
#include <cstdint>

namespace {

struct StateObject {
    uint8_t unknown_00[0x30];
    uint32_t identity;  // +0x30, only bit 0 is used on the fall-through path
    int32_t pending;    // +0x34, signed: tested with JG, so a negative count falls through
};

// The code returned while the object still has work in flight.
constexpr std::int32_t pending_code_in_flight = 2;

}  // namespace

extern "C" uint64_t bb_kernel_pending_code(const StateObject *object)
{
    if (object->pending > 0) {
        return pending_code_in_flight;
    }
    return object->identity & 1u;
}
