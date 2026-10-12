// SPDX-License-Identifier: GPL-2.0-or-later
// Kernel helper: wait until a state field reaches 2, sleeping between polls.
//
// The caller passes a structure and 0x024bdd40 spins on the 32-bit word at offset 0x10 until it
// equals 2, calling the plain microsecond sleep (1000 us) once per iteration. The caller does the
// real work; this is only the poll loop around it.
//
// Two details the disassembly fixes and the replacement keeps:
//
//   * The test is on the full 32-bit word and only 2 leaves the loop, so 0, 1, 3, -1 and every
//     larger value keep polling.
//   * The loop is entered through the test, not fallen into: a field already holding 2 returns
//     without sleeping at all. That is what the `JMP` to `024bdd5a` at the top of the original is
//     for.
#include <cstddef>
#include <cstdint>

#include "runtime/original.h"

namespace {

// The executable's call stub for the microsecond sleep, called with a fixed 1000 us per poll
// (`024bdd50`). Declared with the same signature the rest of the game uses for this stub.
RT_ORIGINAL(0x02fbfe68, kernel_usleep, int(uint32_t microseconds));

// One poll interval, in microseconds: the original's MOV EDI,0x3e8.
constexpr uint32_t poll_interval_us = 1000;

// The state word that ends the wait, and its offset in the caller's structure.
constexpr int32_t ready_state = 2;
constexpr size_t state_offset = 0x10;

}  // namespace

extern "C" void bb_kernel_wait_for_state_024bdd40(uint8_t *state)
{
    // Read as a 32-bit word, matching the original's MOV EAX,dword ptr [RBX + 0x10].
    const auto *word = reinterpret_cast<const volatile int32_t *>(state + state_offset);
    while (*word != ready_state) kernel_usleep(poll_interval_us);
}
