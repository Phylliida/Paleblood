// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the one-shot guards that bind three statics to their storage.
//
// Each of these is a function-local static's guard variable compiled through the usual idiom: a
// pointer eight bytes wide followed by the guard, which is also a full eight bytes (the compiler
// clears the whole word), so the two together are sixteen bytes of a twenty-four byte object.
// Once the guard is set the body does nothing at all.
//
// They are three separate statics five instructions apart, all with identical code, and each
// references a different guard, a different pointer and a different storage object. The addresses
// are therefore the entire content of each function:
//
//   0x014405b0  guard 0x05ac59b8  pointer 0x05ac59b0  storage 0x056b4850
//   0x014405e0  guard 0x05ac59c8  pointer 0x05ac59c0  storage 0x056b4890
//   0x01440610  guard 0x05ac59d8  pointer 0x05ac59d0  storage 0x056b47f0
//
// The storage is `base + 0x10`, not `base`: the original loads the base address, adds 0x10, and
// stores that. Reading the LEA as the value stored is the easy mistake here, and it is invisible
// unless a case checks the pointer's bytes rather than only that it changed.
//
// The guard is *read* one byte at a time (CMP BYTE PTR [rax], 0x0) but *written* eight bytes at a
// time, and that asymmetry is load-bearing. The case that catches it presets the guard's upper
// seven bytes to something other than zero: with the low byte clear the original still takes the
// initializing path, and then clears those seven bytes to zero along with setting the low one. An
// implementation that stores a single byte leaves them as they were -- the yes/no answer is
// identical, the memory afterwards is not.
//
// The compiled shape differs from the original's in one respect worth knowing before reading a
// failure: the original materializes each address with LEA RIP-relative, while this one loads the
// PS4 address as a 64-bit immediate and adds the image base at runtime (rt_guest). That is
// constant-folding, not behaviour -- no memory is read to produce the addresses on either side --
// but it means the instruction streams are not byte-identical and the comparison rests on the
// pointer and guard values, which are.
#include <cstdint>

#include "runtime/guest.h"

namespace {

constexpr std::uintptr_t storage_bias = 0x10;

// The guard, the pointer beside it and the storage object each function binds.
constexpr std::uint32_t guard_first = 0x05ac59b8;
constexpr std::uint32_t pointer_first = 0x05ac59b0;
constexpr std::uint32_t storage_first = 0x056b4840;

constexpr std::uint32_t guard_second = 0x05ac59c8;
constexpr std::uint32_t pointer_second = 0x05ac59c0;
constexpr std::uint32_t storage_second = 0x056b4890;

constexpr std::uint32_t guard_third = 0x05ac59d8;
constexpr std::uint32_t pointer_third = 0x05ac59d0;
constexpr std::uint32_t storage_third = 0x056b47f0;

// One guard and the pointer beside it. Both fields are eight bytes wide in the original and both
// are written whole, so both are written whole here.
template <std::uint32_t Guard, std::uint32_t Pointer, std::uint32_t Storage>
void bind_static()
{
    auto *guard = static_cast<std::uint64_t *>(rt_guest(Guard));
    if (static_cast<unsigned char>(*guard) != 0) {
        return;
    }

    *static_cast<void **>(rt_guest(Pointer)) = static_cast<unsigned char *>(rt_guest(Storage)) + storage_bias;
    *guard = 1;
}

}  // namespace

extern "C" void bb_frame_timing_static_guard_014405b0()
{
    bind_static<guard_first, pointer_first, storage_first>();
}

extern "C" void bb_frame_timing_static_guard_014405e0()
{
    bind_static<guard_second, pointer_second, storage_second>();
}

extern "C" void bb_frame_timing_static_guard_01440610()
{
    bind_static<guard_third, pointer_third, storage_third>();
}
