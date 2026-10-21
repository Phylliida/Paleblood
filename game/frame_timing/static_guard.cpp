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
//   0x014405b0  guard 0x05ac59b8  pointer 0x05ac59b0  storage base 0x056b4840
//   0x014405e0  guard 0x05ac59c8  pointer 0x05ac59c0  storage base 0x056b4890
//   0x01440610  guard 0x05ac59d8  pointer 0x05ac59d0  storage base 0x056b47f0
//
// The storage *base* is what the LEA names; the value stored is `base + 0x10`, because the original
// adds 0x10 before storing. Reading the LEA as the value stored is the easy mistake here, and it is
// invisible unless a case checks the pointer's bytes rather than only that it changed.
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

constexpr std::uint32_t guard_of_0135bde0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0135bde0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0135bde0 = 0x056b4840;

constexpr std::uint32_t guard_of_0135be10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0135be10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0135be10 = 0x056b4890;

constexpr std::uint32_t guard_of_0135be40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0135be40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0135be40 = 0x056b47f0;

constexpr std::uint32_t guard_of_0135c780 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0135c780 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0135c780 = 0x056b4840;

constexpr std::uint32_t guard_of_0135c7b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0135c7b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0135c7b0 = 0x056b4890;

constexpr std::uint32_t guard_of_0135c7e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0135c7e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0135c7e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0135c9b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0135c9b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0135c9b0 = 0x056b4840;

constexpr std::uint32_t guard_of_0135c9e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0135c9e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0135c9e0 = 0x056b4890;

constexpr std::uint32_t guard_of_0135ca10 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0135ca10 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0135ca10 = 0x056b47f0;

constexpr std::uint32_t guard_of_0135cca0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0135cca0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0135cca0 = 0x056b4840;

constexpr std::uint32_t guard_of_0135ccd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0135ccd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0135ccd0 = 0x056b4890;

constexpr std::uint32_t guard_of_0135cd00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0135cd00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0135cd00 = 0x056b47f0;

constexpr std::uint32_t guard_of_0135d370 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0135d370 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0135d370 = 0x056b4840;

constexpr std::uint32_t guard_of_0135d3a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0135d3a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0135d3a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0135d3d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0135d3d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0135d3d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0135e1a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0135e1a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0135e1a0 = 0x056b4840;

constexpr std::uint32_t guard_of_0135e1d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0135e1d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0135e1d0 = 0x056b4890;

constexpr std::uint32_t guard_of_0135e200 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0135e200 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0135e200 = 0x056b47f0;

constexpr std::uint32_t guard_of_01364050 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01364050 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01364050 = 0x056b4840;

constexpr std::uint32_t guard_of_01364080 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01364080 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01364080 = 0x056b4890;

constexpr std::uint32_t guard_of_013640b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013640b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013640b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013642c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013642c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013642c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013642f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013642f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013642f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01364320 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01364320 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01364320 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136ad40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136ad40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136ad40 = 0x056b4840;

constexpr std::uint32_t guard_of_0136ad70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136ad70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136ad70 = 0x056b4890;

constexpr std::uint32_t guard_of_0136ada0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136ada0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136ada0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136af00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136af00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136af00 = 0x056b4840;

constexpr std::uint32_t guard_of_0136af30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136af30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136af30 = 0x056b4890;

constexpr std::uint32_t guard_of_0136af60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136af60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136af60 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136b2f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136b2f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136b2f0 = 0x056b4840;

constexpr std::uint32_t guard_of_0136b320 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136b320 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136b320 = 0x056b4890;

constexpr std::uint32_t guard_of_0136b350 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136b350 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136b350 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136ccb0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136ccb0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136ccb0 = 0x056b4840;

constexpr std::uint32_t guard_of_0136cce0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136cce0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136cce0 = 0x056b4890;

constexpr std::uint32_t guard_of_0136cd10 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136cd10 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136cd10 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136d550 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136d550 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136d550 = 0x056b4840;

constexpr std::uint32_t guard_of_0136d580 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136d580 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136d580 = 0x056b4890;

constexpr std::uint32_t guard_of_0136d5b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136d5b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136d5b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136de90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136de90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136de90 = 0x056b4840;

constexpr std::uint32_t guard_of_0136dec0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136dec0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136dec0 = 0x056b4890;

constexpr std::uint32_t guard_of_0136def0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136def0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136def0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136e0b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136e0b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136e0b0 = 0x056b4840;

constexpr std::uint32_t guard_of_0136e0e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136e0e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136e0e0 = 0x056b4890;

constexpr std::uint32_t guard_of_0136e110 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136e110 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136e110 = 0x056b47f0;

constexpr std::uint32_t guard_of_0136e4e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0136e4e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0136e4e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0136e510 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0136e510 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0136e510 = 0x056b4890;

constexpr std::uint32_t guard_of_0136e540 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0136e540 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0136e540 = 0x056b47f0;

constexpr std::uint32_t guard_of_01370770 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01370770 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01370770 = 0x056b4840;

constexpr std::uint32_t guard_of_013707a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013707a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013707a0 = 0x056b4890;

constexpr std::uint32_t guard_of_013707d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013707d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013707d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01370920 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01370920 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01370920 = 0x056b4840;

constexpr std::uint32_t guard_of_01370950 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01370950 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01370950 = 0x056b4890;

constexpr std::uint32_t guard_of_01370980 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01370980 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01370980 = 0x056b47f0;

constexpr std::uint32_t guard_of_01370ea0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01370ea0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01370ea0 = 0x056b4840;

constexpr std::uint32_t guard_of_01370ed0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01370ed0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01370ed0 = 0x056b4890;

constexpr std::uint32_t guard_of_01370f00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01370f00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01370f00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013711b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013711b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013711b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013711e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013711e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013711e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01371210 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01371210 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01371210 = 0x056b47f0;

constexpr std::uint32_t guard_of_01371810 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01371810 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01371810 = 0x056b4840;

constexpr std::uint32_t guard_of_01371840 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01371840 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01371840 = 0x056b4890;

constexpr std::uint32_t guard_of_01371870 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01371870 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01371870 = 0x056b47f0;

constexpr std::uint32_t guard_of_01371b20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01371b20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01371b20 = 0x056b4840;

constexpr std::uint32_t guard_of_01371b50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01371b50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01371b50 = 0x056b4890;

constexpr std::uint32_t guard_of_01371b80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01371b80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01371b80 = 0x056b47f0;

constexpr std::uint32_t guard_of_01372140 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01372140 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01372140 = 0x056b4840;

constexpr std::uint32_t guard_of_01372170 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01372170 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01372170 = 0x056b4890;

constexpr std::uint32_t guard_of_013721a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013721a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013721a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01372400 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01372400 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01372400 = 0x056b4840;

constexpr std::uint32_t guard_of_01372430 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01372430 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01372430 = 0x056b4890;

constexpr std::uint32_t guard_of_01372460 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01372460 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01372460 = 0x056b47f0;

constexpr std::uint32_t guard_of_01372620 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01372620 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01372620 = 0x056b4840;

constexpr std::uint32_t guard_of_01372650 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01372650 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01372650 = 0x056b4890;

constexpr std::uint32_t guard_of_01372680 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01372680 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01372680 = 0x056b47f0;

constexpr std::uint32_t guard_of_01372fd0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01372fd0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01372fd0 = 0x056b4840;

constexpr std::uint32_t guard_of_01373000 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01373000 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01373000 = 0x056b4890;

constexpr std::uint32_t guard_of_01373030 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01373030 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01373030 = 0x056b47f0;

constexpr std::uint32_t guard_of_01373d60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01373d60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01373d60 = 0x056b4840;

constexpr std::uint32_t guard_of_01373d90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01373d90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01373d90 = 0x056b4890;

constexpr std::uint32_t guard_of_01373dc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01373dc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01373dc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01373f60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01373f60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01373f60 = 0x056b4840;

constexpr std::uint32_t guard_of_01373f90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01373f90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01373f90 = 0x056b4890;

constexpr std::uint32_t guard_of_01373fc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01373fc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01373fc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01374a80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01374a80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01374a80 = 0x056b4840;

constexpr std::uint32_t guard_of_01374ab0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01374ab0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01374ab0 = 0x056b4890;

constexpr std::uint32_t guard_of_01374ae0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01374ae0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01374ae0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013784a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013784a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013784a0 = 0x056b4840;

constexpr std::uint32_t guard_of_013784d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013784d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013784d0 = 0x056b4890;

constexpr std::uint32_t guard_of_01378500 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01378500 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01378500 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137a460 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137a460 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137a460 = 0x056b4840;

constexpr std::uint32_t guard_of_0137a490 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137a490 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137a490 = 0x056b4890;

constexpr std::uint32_t guard_of_0137a4c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137a4c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137a4c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137ac00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137ac00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137ac00 = 0x056b4840;

constexpr std::uint32_t guard_of_0137ac30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137ac30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137ac30 = 0x056b4890;

constexpr std::uint32_t guard_of_0137ac60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137ac60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137ac60 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137af50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137af50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137af50 = 0x056b4840;

constexpr std::uint32_t guard_of_0137af80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137af80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137af80 = 0x056b4890;

constexpr std::uint32_t guard_of_0137afb0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137afb0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137afb0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137b490 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137b490 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137b490 = 0x056b4840;

constexpr std::uint32_t guard_of_0137b4c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137b4c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137b4c0 = 0x056b4890;

constexpr std::uint32_t guard_of_0137b4f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137b4f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137b4f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137b7e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137b7e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137b7e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0137b810 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137b810 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137b810 = 0x056b4890;

constexpr std::uint32_t guard_of_0137b840 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137b840 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137b840 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137d670 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137d670 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137d670 = 0x056b4840;

constexpr std::uint32_t guard_of_0137d6a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137d6a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137d6a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0137d6d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137d6d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137d6d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137d930 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137d930 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137d930 = 0x056b4840;

constexpr std::uint32_t guard_of_0137d960 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137d960 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137d960 = 0x056b4890;

constexpr std::uint32_t guard_of_0137d990 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137d990 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137d990 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137df20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137df20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137df20 = 0x056b4840;

constexpr std::uint32_t guard_of_0137df50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137df50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137df50 = 0x056b4890;

constexpr std::uint32_t guard_of_0137df80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137df80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137df80 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137e2b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137e2b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137e2b0 = 0x056b4840;

constexpr std::uint32_t guard_of_0137e2e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137e2e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137e2e0 = 0x056b4890;

constexpr std::uint32_t guard_of_0137e310 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137e310 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137e310 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137e5c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137e5c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137e5c0 = 0x056b4840;

constexpr std::uint32_t guard_of_0137e5f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137e5f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137e5f0 = 0x056b4890;

constexpr std::uint32_t guard_of_0137e620 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137e620 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137e620 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137e7e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137e7e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137e7e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0137e810 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137e810 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137e810 = 0x056b4890;

constexpr std::uint32_t guard_of_0137e840 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137e840 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137e840 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137ea10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137ea10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137ea10 = 0x056b4840;

constexpr std::uint32_t guard_of_0137ea40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137ea40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137ea40 = 0x056b4890;

constexpr std::uint32_t guard_of_0137ea70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137ea70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137ea70 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137ec90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137ec90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137ec90 = 0x056b4840;

constexpr std::uint32_t guard_of_0137ecc0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137ecc0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137ecc0 = 0x056b4890;

constexpr std::uint32_t guard_of_0137ecf0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137ecf0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137ecf0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137f270 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137f270 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137f270 = 0x056b4840;

constexpr std::uint32_t guard_of_0137f2a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137f2a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137f2a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0137f2d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137f2d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137f2d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0137f5e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0137f5e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0137f5e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0137f610 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0137f610 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0137f610 = 0x056b4890;

constexpr std::uint32_t guard_of_0137f640 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0137f640 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0137f640 = 0x056b47f0;

constexpr std::uint32_t guard_of_01382360 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01382360 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01382360 = 0x056b4840;

constexpr std::uint32_t guard_of_01382390 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01382390 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01382390 = 0x056b4890;

constexpr std::uint32_t guard_of_013823c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013823c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013823c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013828c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013828c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013828c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013828f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013828f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013828f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01382920 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01382920 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01382920 = 0x056b47f0;

constexpr std::uint32_t guard_of_01382c40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01382c40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01382c40 = 0x056b4840;

constexpr std::uint32_t guard_of_01382c70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01382c70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01382c70 = 0x056b4890;

constexpr std::uint32_t guard_of_01382ca0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01382ca0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01382ca0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01382f50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01382f50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01382f50 = 0x056b4840;

constexpr std::uint32_t guard_of_01382f80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01382f80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01382f80 = 0x056b4890;

constexpr std::uint32_t guard_of_01382fb0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01382fb0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01382fb0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01383300 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01383300 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01383300 = 0x056b4840;

constexpr std::uint32_t guard_of_01383330 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01383330 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01383330 = 0x056b4890;

constexpr std::uint32_t guard_of_01383360 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01383360 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01383360 = 0x056b47f0;

constexpr std::uint32_t guard_of_01383610 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01383610 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01383610 = 0x056b4840;

constexpr std::uint32_t guard_of_01383640 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01383640 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01383640 = 0x056b4890;

constexpr std::uint32_t guard_of_01383670 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01383670 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01383670 = 0x056b47f0;

constexpr std::uint32_t guard_of_01383920 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01383920 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01383920 = 0x056b4840;

constexpr std::uint32_t guard_of_01383950 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01383950 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01383950 = 0x056b4890;

constexpr std::uint32_t guard_of_01383980 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01383980 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01383980 = 0x056b47f0;

constexpr std::uint32_t guard_of_01383e10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01383e10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01383e10 = 0x056b4840;

constexpr std::uint32_t guard_of_01383e40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01383e40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01383e40 = 0x056b4890;

constexpr std::uint32_t guard_of_01383e70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01383e70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01383e70 = 0x056b47f0;

constexpr std::uint32_t guard_of_01384100 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01384100 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01384100 = 0x056b4840;

constexpr std::uint32_t guard_of_01384130 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01384130 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01384130 = 0x056b4890;

constexpr std::uint32_t guard_of_01384160 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01384160 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01384160 = 0x056b47f0;

constexpr std::uint32_t guard_of_013843f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013843f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013843f0 = 0x056b4840;

constexpr std::uint32_t guard_of_01384420 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01384420 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01384420 = 0x056b4890;

constexpr std::uint32_t guard_of_01384450 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01384450 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01384450 = 0x056b47f0;

constexpr std::uint32_t guard_of_01384760 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01384760 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01384760 = 0x056b4840;

constexpr std::uint32_t guard_of_01384790 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01384790 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01384790 = 0x056b4890;

constexpr std::uint32_t guard_of_013847c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013847c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013847c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01384a70 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01384a70 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01384a70 = 0x056b4840;

constexpr std::uint32_t guard_of_01384aa0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01384aa0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01384aa0 = 0x056b4890;

constexpr std::uint32_t guard_of_01384ad0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01384ad0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01384ad0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01384f10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01384f10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01384f10 = 0x056b4840;

constexpr std::uint32_t guard_of_01384f40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01384f40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01384f40 = 0x056b4890;

constexpr std::uint32_t guard_of_01384f70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01384f70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01384f70 = 0x056b47f0;

constexpr std::uint32_t guard_of_013852b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013852b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013852b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013852e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013852e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013852e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01385310 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01385310 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01385310 = 0x056b47f0;

constexpr std::uint32_t guard_of_01385610 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01385610 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01385610 = 0x056b4840;

constexpr std::uint32_t guard_of_01385640 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01385640 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01385640 = 0x056b4890;

constexpr std::uint32_t guard_of_01385670 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01385670 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01385670 = 0x056b47f0;

constexpr std::uint32_t guard_of_01385980 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01385980 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01385980 = 0x056b4840;

constexpr std::uint32_t guard_of_013859b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013859b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013859b0 = 0x056b4890;

constexpr std::uint32_t guard_of_013859e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013859e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013859e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01385c90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01385c90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01385c90 = 0x056b4840;

constexpr std::uint32_t guard_of_01385cc0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01385cc0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01385cc0 = 0x056b4890;

constexpr std::uint32_t guard_of_01385cf0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01385cf0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01385cf0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01386180 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01386180 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01386180 = 0x056b4840;

constexpr std::uint32_t guard_of_013861b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013861b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013861b0 = 0x056b4890;

constexpr std::uint32_t guard_of_013861e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013861e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013861e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013864e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013864e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013864e0 = 0x056b4840;

constexpr std::uint32_t guard_of_01386510 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01386510 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01386510 = 0x056b4890;

constexpr std::uint32_t guard_of_01386540 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01386540 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01386540 = 0x056b47f0;

constexpr std::uint32_t guard_of_01386610 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01386610 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01386610 = 0x056b4840;

constexpr std::uint32_t guard_of_01386640 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01386640 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01386640 = 0x056b4890;

constexpr std::uint32_t guard_of_01386670 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01386670 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01386670 = 0x056b47f0;

constexpr std::uint32_t guard_of_01386740 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01386740 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01386740 = 0x056b4840;

constexpr std::uint32_t guard_of_01386770 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01386770 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01386770 = 0x056b4890;

constexpr std::uint32_t guard_of_013867a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013867a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013867a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01386860 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01386860 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01386860 = 0x056b4840;

constexpr std::uint32_t guard_of_01386890 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01386890 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01386890 = 0x056b4890;

constexpr std::uint32_t guard_of_013868c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013868c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013868c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01387410 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01387410 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01387410 = 0x056b4840;

constexpr std::uint32_t guard_of_01387440 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01387440 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01387440 = 0x056b4890;

constexpr std::uint32_t guard_of_01387470 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01387470 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01387470 = 0x056b47f0;

constexpr std::uint32_t guard_of_013884a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013884a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013884a0 = 0x056b4840;

constexpr std::uint32_t guard_of_013884d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013884d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013884d0 = 0x056b4890;

constexpr std::uint32_t guard_of_01388500 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01388500 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01388500 = 0x056b47f0;

constexpr std::uint32_t guard_of_01389560 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01389560 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01389560 = 0x056b4840;

constexpr std::uint32_t guard_of_01389590 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01389590 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01389590 = 0x056b4890;

constexpr std::uint32_t guard_of_013895c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013895c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013895c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01389750 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01389750 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01389750 = 0x056b4840;

constexpr std::uint32_t guard_of_01389780 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01389780 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01389780 = 0x056b4890;

constexpr std::uint32_t guard_of_013897b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013897b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013897b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01389ed0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01389ed0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01389ed0 = 0x056b4840;

constexpr std::uint32_t guard_of_01389f00 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01389f00 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01389f00 = 0x056b4890;

constexpr std::uint32_t guard_of_01389f30 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01389f30 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01389f30 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138a5c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138a5c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138a5c0 = 0x056b4840;

constexpr std::uint32_t guard_of_0138a5f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138a5f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138a5f0 = 0x056b4890;

constexpr std::uint32_t guard_of_0138a620 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138a620 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138a620 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138a9e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138a9e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138a9e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0138aa10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138aa10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138aa10 = 0x056b4890;

constexpr std::uint32_t guard_of_0138aa40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138aa40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138aa40 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138acf0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138acf0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138acf0 = 0x056b4840;

constexpr std::uint32_t guard_of_0138ad20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138ad20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138ad20 = 0x056b4890;

constexpr std::uint32_t guard_of_0138ad50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138ad50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138ad50 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138bf20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138bf20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138bf20 = 0x056b4840;

constexpr std::uint32_t guard_of_0138bf50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138bf50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138bf50 = 0x056b4890;

constexpr std::uint32_t guard_of_0138bf80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138bf80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138bf80 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138bff0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138bff0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138bff0 = 0x056b4840;

constexpr std::uint32_t guard_of_0138c020 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138c020 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138c020 = 0x056b4890;

constexpr std::uint32_t guard_of_0138c050 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138c050 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138c050 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138c770 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138c770 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138c770 = 0x056b4840;

constexpr std::uint32_t guard_of_0138c7a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138c7a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138c7a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0138c7d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138c7d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138c7d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0138ca20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0138ca20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0138ca20 = 0x056b4840;

constexpr std::uint32_t guard_of_0138ca50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0138ca50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0138ca50 = 0x056b4890;

constexpr std::uint32_t guard_of_0138ca80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0138ca80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0138ca80 = 0x056b47f0;

constexpr std::uint32_t guard_of_01391300 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01391300 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01391300 = 0x056b4840;

constexpr std::uint32_t guard_of_01391330 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01391330 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01391330 = 0x056b4890;

constexpr std::uint32_t guard_of_01391360 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01391360 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01391360 = 0x056b47f0;

constexpr std::uint32_t guard_of_01393740 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01393740 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01393740 = 0x056b4840;

constexpr std::uint32_t guard_of_01393770 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01393770 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01393770 = 0x056b4890;

constexpr std::uint32_t guard_of_013937a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013937a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013937a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01395780 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01395780 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01395780 = 0x056b4840;

constexpr std::uint32_t guard_of_013957b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013957b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013957b0 = 0x056b4890;

constexpr std::uint32_t guard_of_013957e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013957e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013957e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01395960 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01395960 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01395960 = 0x056b4840;

constexpr std::uint32_t guard_of_01395990 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01395990 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01395990 = 0x056b4890;

constexpr std::uint32_t guard_of_013959c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013959c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013959c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01396090 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01396090 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01396090 = 0x056b4840;

constexpr std::uint32_t guard_of_013960c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013960c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013960c0 = 0x056b4890;

constexpr std::uint32_t guard_of_013960f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013960f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013960f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013984b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013984b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013984b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013984e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013984e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013984e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01398510 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01398510 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01398510 = 0x056b47f0;

constexpr std::uint32_t guard_of_013988d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013988d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013988d0 = 0x056b4840;

constexpr std::uint32_t guard_of_01398900 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01398900 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01398900 = 0x056b4890;

constexpr std::uint32_t guard_of_01398930 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01398930 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01398930 = 0x056b47f0;

constexpr std::uint32_t guard_of_01399550 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01399550 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01399550 = 0x056b4840;

constexpr std::uint32_t guard_of_01399580 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01399580 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01399580 = 0x056b4890;

constexpr std::uint32_t guard_of_013995b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013995b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013995b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01399fa0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01399fa0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01399fa0 = 0x056b4840;

constexpr std::uint32_t guard_of_01399fd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01399fd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01399fd0 = 0x056b4890;

constexpr std::uint32_t guard_of_0139a000 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139a000 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139a000 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139ae00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139ae00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139ae00 = 0x056b4840;

constexpr std::uint32_t guard_of_0139ae30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139ae30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139ae30 = 0x056b4890;

constexpr std::uint32_t guard_of_0139ae60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139ae60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139ae60 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139b410 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139b410 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139b410 = 0x056b4840;

constexpr std::uint32_t guard_of_0139b440 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139b440 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139b440 = 0x056b4890;

constexpr std::uint32_t guard_of_0139b470 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139b470 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139b470 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139b500 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139b500 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139b500 = 0x056b4840;

constexpr std::uint32_t guard_of_0139b530 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139b530 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139b530 = 0x056b4890;

constexpr std::uint32_t guard_of_0139b560 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139b560 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139b560 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139bce0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139bce0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139bce0 = 0x056b4840;

constexpr std::uint32_t guard_of_0139bd10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139bd10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139bd10 = 0x056b4890;

constexpr std::uint32_t guard_of_0139bd40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139bd40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139bd40 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139c0d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139c0d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139c0d0 = 0x056b4840;

constexpr std::uint32_t guard_of_0139c100 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139c100 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139c100 = 0x056b4890;

constexpr std::uint32_t guard_of_0139c130 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139c130 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139c130 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139c310 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139c310 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139c310 = 0x056b4840;

constexpr std::uint32_t guard_of_0139c340 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139c340 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139c340 = 0x056b4890;

constexpr std::uint32_t guard_of_0139c370 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139c370 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139c370 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139c620 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139c620 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139c620 = 0x056b4840;

constexpr std::uint32_t guard_of_0139c650 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139c650 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139c650 = 0x056b4890;

constexpr std::uint32_t guard_of_0139c680 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139c680 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139c680 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139c770 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139c770 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139c770 = 0x056b4840;

constexpr std::uint32_t guard_of_0139c7a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139c7a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139c7a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0139c7d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139c7d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139c7d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139cba0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139cba0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139cba0 = 0x056b4840;

constexpr std::uint32_t guard_of_0139cbd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139cbd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139cbd0 = 0x056b4890;

constexpr std::uint32_t guard_of_0139cc00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139cc00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139cc00 = 0x056b47f0;

constexpr std::uint32_t guard_of_0139f6d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0139f6d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0139f6d0 = 0x056b4840;

constexpr std::uint32_t guard_of_0139f700 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0139f700 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0139f700 = 0x056b4890;

constexpr std::uint32_t guard_of_0139f730 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0139f730 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0139f730 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a4bd0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a4bd0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a4bd0 = 0x056b4840;

constexpr std::uint32_t guard_of_013a4c00 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a4c00 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a4c00 = 0x056b4890;

constexpr std::uint32_t guard_of_013a4c30 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a4c30 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a4c30 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a5030 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a5030 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a5030 = 0x056b4840;

constexpr std::uint32_t guard_of_013a5060 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a5060 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a5060 = 0x056b4890;

constexpr std::uint32_t guard_of_013a5090 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a5090 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a5090 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a6380 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a6380 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a6380 = 0x056b4840;

constexpr std::uint32_t guard_of_013a63b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a63b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a63b0 = 0x056b4890;

constexpr std::uint32_t guard_of_013a63e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a63e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a63e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a6580 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a6580 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a6580 = 0x056b4840;

constexpr std::uint32_t guard_of_013a65b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a65b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a65b0 = 0x056b4890;

constexpr std::uint32_t guard_of_013a65e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a65e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a65e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a74a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a74a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a74a0 = 0x056b4840;

constexpr std::uint32_t guard_of_013a74d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a74d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a74d0 = 0x056b4890;

constexpr std::uint32_t guard_of_013a7500 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a7500 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a7500 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a79e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a79e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a79e0 = 0x056b4840;

constexpr std::uint32_t guard_of_013a7a10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a7a10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a7a10 = 0x056b4890;

constexpr std::uint32_t guard_of_013a7a40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a7a40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a7a40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a8080 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a8080 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a8080 = 0x056b4840;

constexpr std::uint32_t guard_of_013a80b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a80b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a80b0 = 0x056b4890;

constexpr std::uint32_t guard_of_013a80e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a80e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a80e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013a9b50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013a9b50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013a9b50 = 0x056b4840;

constexpr std::uint32_t guard_of_013a9b80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013a9b80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013a9b80 = 0x056b4890;

constexpr std::uint32_t guard_of_013a9bb0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013a9bb0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013a9bb0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013aa960 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013aa960 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013aa960 = 0x056b4840;

constexpr std::uint32_t guard_of_013aa990 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013aa990 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013aa990 = 0x056b4890;

constexpr std::uint32_t guard_of_013aa9c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013aa9c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013aa9c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ab530 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ab530 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ab530 = 0x056b4840;

constexpr std::uint32_t guard_of_013ab560 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ab560 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ab560 = 0x056b4890;

constexpr std::uint32_t guard_of_013ab590 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ab590 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ab590 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ad0b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ad0b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ad0b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013ad0e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ad0e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ad0e0 = 0x056b4890;

constexpr std::uint32_t guard_of_013ad110 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ad110 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ad110 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ae990 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ae990 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ae990 = 0x056b4840;

constexpr std::uint32_t guard_of_013ae9c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ae9c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ae9c0 = 0x056b4890;

constexpr std::uint32_t guard_of_013ae9f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ae9f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ae9f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013af330 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013af330 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013af330 = 0x056b4840;

constexpr std::uint32_t guard_of_013af360 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013af360 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013af360 = 0x056b4890;

constexpr std::uint32_t guard_of_013af390 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013af390 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013af390 = 0x056b47f0;

constexpr std::uint32_t guard_of_013af7c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013af7c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013af7c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013af7f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013af7f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013af7f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013af820 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013af820 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013af820 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b0090 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b0090 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b0090 = 0x056b4840;

constexpr std::uint32_t guard_of_013b00c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b00c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b00c0 = 0x056b4890;

constexpr std::uint32_t guard_of_013b00f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b00f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b00f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b1b60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b1b60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b1b60 = 0x056b4840;

constexpr std::uint32_t guard_of_013b1b90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b1b90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b1b90 = 0x056b4890;

constexpr std::uint32_t guard_of_013b1bc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b1bc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b1bc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b2e20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b2e20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b2e20 = 0x056b4840;

constexpr std::uint32_t guard_of_013b2e50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b2e50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b2e50 = 0x056b4890;

constexpr std::uint32_t guard_of_013b2e80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b2e80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b2e80 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b3430 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b3430 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b3430 = 0x056b4840;

constexpr std::uint32_t guard_of_013b3460 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b3460 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b3460 = 0x056b4890;

constexpr std::uint32_t guard_of_013b3490 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b3490 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b3490 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b4730 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b4730 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b4730 = 0x056b4840;

constexpr std::uint32_t guard_of_013b4760 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b4760 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b4760 = 0x056b4890;

constexpr std::uint32_t guard_of_013b4790 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b4790 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b4790 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b4d50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b4d50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b4d50 = 0x056b4840;

constexpr std::uint32_t guard_of_013b4d80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b4d80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b4d80 = 0x056b4890;

constexpr std::uint32_t guard_of_013b4db0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b4db0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b4db0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b4fb0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b4fb0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b4fb0 = 0x056b4840;

constexpr std::uint32_t guard_of_013b4fe0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b4fe0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b4fe0 = 0x056b4890;

constexpr std::uint32_t guard_of_013b5010 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b5010 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b5010 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b5370 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b5370 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b5370 = 0x056b4840;

constexpr std::uint32_t guard_of_013b53a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b53a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b53a0 = 0x056b4890;

constexpr std::uint32_t guard_of_013b53d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b53d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b53d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b5fd0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b5fd0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b5fd0 = 0x056b4840;

constexpr std::uint32_t guard_of_013b6000 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b6000 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b6000 = 0x056b4890;

constexpr std::uint32_t guard_of_013b6030 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b6030 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b6030 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b8920 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b8920 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b8920 = 0x056b4840;

constexpr std::uint32_t guard_of_013b8950 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b8950 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b8950 = 0x056b4890;

constexpr std::uint32_t guard_of_013b8980 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b8980 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b8980 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b9220 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b9220 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b9220 = 0x056b4840;

constexpr std::uint32_t guard_of_013b9250 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b9250 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b9250 = 0x056b4890;

constexpr std::uint32_t guard_of_013b9280 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b9280 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b9280 = 0x056b47f0;

constexpr std::uint32_t guard_of_013b97f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013b97f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013b97f0 = 0x056b4840;

constexpr std::uint32_t guard_of_013b9820 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013b9820 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013b9820 = 0x056b4890;

constexpr std::uint32_t guard_of_013b9850 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013b9850 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013b9850 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ba550 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ba550 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ba550 = 0x056b4840;

constexpr std::uint32_t guard_of_013ba580 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ba580 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ba580 = 0x056b4890;

constexpr std::uint32_t guard_of_013ba5b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ba5b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ba5b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bbfc0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bbfc0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bbfc0 = 0x056b4840;

constexpr std::uint32_t guard_of_013bbff0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bbff0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bbff0 = 0x056b4890;

constexpr std::uint32_t guard_of_013bc020 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bc020 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bc020 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bc100 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bc100 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bc100 = 0x056b4840;

constexpr std::uint32_t guard_of_013bc130 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bc130 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bc130 = 0x056b4890;

constexpr std::uint32_t guard_of_013bc160 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bc160 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bc160 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bc220 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bc220 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bc220 = 0x056b4840;

constexpr std::uint32_t guard_of_013bc250 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bc250 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bc250 = 0x056b4890;

constexpr std::uint32_t guard_of_013bc280 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bc280 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bc280 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bc660 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bc660 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bc660 = 0x056b4840;

constexpr std::uint32_t guard_of_013bc690 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bc690 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bc690 = 0x056b4890;

constexpr std::uint32_t guard_of_013bc6c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bc6c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bc6c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bde80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bde80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bde80 = 0x056b4840;

constexpr std::uint32_t guard_of_013bdeb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bdeb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bdeb0 = 0x056b4890;

constexpr std::uint32_t guard_of_013bdee0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bdee0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bdee0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013be8b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013be8b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013be8b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013be8e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013be8e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013be8e0 = 0x056b4890;

constexpr std::uint32_t guard_of_013be910 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013be910 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013be910 = 0x056b47f0;

constexpr std::uint32_t guard_of_013beba0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013beba0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013beba0 = 0x056b4840;

constexpr std::uint32_t guard_of_013bebd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bebd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bebd0 = 0x056b4890;

constexpr std::uint32_t guard_of_013bec00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bec00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bec00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bece0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bece0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bece0 = 0x056b4840;

constexpr std::uint32_t guard_of_013bed10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bed10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bed10 = 0x056b4890;

constexpr std::uint32_t guard_of_013bed40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bed40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bed40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013beea0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013beea0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013beea0 = 0x056b4840;

constexpr std::uint32_t guard_of_013beed0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013beed0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013beed0 = 0x056b4890;

constexpr std::uint32_t guard_of_013bef00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bef00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bef00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bf9a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bf9a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bf9a0 = 0x056b4840;

constexpr std::uint32_t guard_of_013bf9d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bf9d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bf9d0 = 0x056b4890;

constexpr std::uint32_t guard_of_013bfa00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bfa00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bfa00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013bfe60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013bfe60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013bfe60 = 0x056b4840;

constexpr std::uint32_t guard_of_013bfe90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013bfe90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013bfe90 = 0x056b4890;

constexpr std::uint32_t guard_of_013bfec0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013bfec0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013bfec0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c18a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c18a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c18a0 = 0x056b4840;

constexpr std::uint32_t guard_of_013c18d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c18d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c18d0 = 0x056b4890;

constexpr std::uint32_t guard_of_013c1900 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c1900 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c1900 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c2fe0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c2fe0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c2fe0 = 0x056b4840;

constexpr std::uint32_t guard_of_013c3010 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c3010 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c3010 = 0x056b4890;

constexpr std::uint32_t guard_of_013c3040 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c3040 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c3040 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c3830 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c3830 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c3830 = 0x056b4840;

constexpr std::uint32_t guard_of_013c3860 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c3860 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c3860 = 0x056b4890;

constexpr std::uint32_t guard_of_013c3890 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c3890 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c3890 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c3da0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c3da0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c3da0 = 0x056b4840;

constexpr std::uint32_t guard_of_013c3dd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c3dd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c3dd0 = 0x056b4890;

constexpr std::uint32_t guard_of_013c3e00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c3e00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c3e00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c5000 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c5000 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c5000 = 0x056b4840;

constexpr std::uint32_t guard_of_013c5030 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c5030 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c5030 = 0x056b4890;

constexpr std::uint32_t guard_of_013c5060 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c5060 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c5060 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c55c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c55c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c55c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013c55f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c55f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c55f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013c5620 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c5620 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c5620 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c6e60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c6e60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c6e60 = 0x056b4840;

constexpr std::uint32_t guard_of_013c6e90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c6e90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c6e90 = 0x056b4890;

constexpr std::uint32_t guard_of_013c6ec0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c6ec0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c6ec0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c7330 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c7330 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c7330 = 0x056b4840;

constexpr std::uint32_t guard_of_013c7360 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c7360 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c7360 = 0x056b4890;

constexpr std::uint32_t guard_of_013c7390 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c7390 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c7390 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c7a60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c7a60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c7a60 = 0x056b4840;

constexpr std::uint32_t guard_of_013c7a90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c7a90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c7a90 = 0x056b4890;

constexpr std::uint32_t guard_of_013c7ac0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c7ac0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c7ac0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013c7ee0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013c7ee0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013c7ee0 = 0x056b4840;

constexpr std::uint32_t guard_of_013c7f10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013c7f10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013c7f10 = 0x056b4890;

constexpr std::uint32_t guard_of_013c7f40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013c7f40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013c7f40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013cc410 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013cc410 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013cc410 = 0x056b4840;

constexpr std::uint32_t guard_of_013cc440 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cc440 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cc440 = 0x056b4890;

constexpr std::uint32_t guard_of_013cc470 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cc470 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cc470 = 0x056b47f0;

constexpr std::uint32_t guard_of_013cd550 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013cd550 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013cd550 = 0x056b4840;

constexpr std::uint32_t guard_of_013cd580 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cd580 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cd580 = 0x056b4890;

constexpr std::uint32_t guard_of_013cd5b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cd5b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cd5b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ce1b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ce1b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ce1b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013ce1e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ce1e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ce1e0 = 0x056b4890;

constexpr std::uint32_t guard_of_013ce210 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ce210 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ce210 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ce500 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ce500 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ce500 = 0x056b4840;

constexpr std::uint32_t guard_of_013ce530 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ce530 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ce530 = 0x056b4890;

constexpr std::uint32_t guard_of_013ce560 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ce560 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ce560 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ce9e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ce9e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ce9e0 = 0x056b4840;

constexpr std::uint32_t guard_of_013cea10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cea10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cea10 = 0x056b4890;

constexpr std::uint32_t guard_of_013cea40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cea40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cea40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ced30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ced30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ced30 = 0x056b4840;

constexpr std::uint32_t guard_of_013ced60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ced60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ced60 = 0x056b4890;

constexpr std::uint32_t guard_of_013ced90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ced90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ced90 = 0x056b47f0;

constexpr std::uint32_t guard_of_013cf100 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013cf100 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013cf100 = 0x056b4840;

constexpr std::uint32_t guard_of_013cf130 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cf130 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cf130 = 0x056b4890;

constexpr std::uint32_t guard_of_013cf160 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cf160 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cf160 = 0x056b47f0;

constexpr std::uint32_t guard_of_013cf450 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013cf450 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013cf450 = 0x056b4840;

constexpr std::uint32_t guard_of_013cf480 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cf480 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cf480 = 0x056b4890;

constexpr std::uint32_t guard_of_013cf4b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cf4b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cf4b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013cfa10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013cfa10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013cfa10 = 0x056b4840;

constexpr std::uint32_t guard_of_013cfa40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cfa40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cfa40 = 0x056b4890;

constexpr std::uint32_t guard_of_013cfa70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cfa70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cfa70 = 0x056b47f0;

constexpr std::uint32_t guard_of_013cfd60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013cfd60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013cfd60 = 0x056b4840;

constexpr std::uint32_t guard_of_013cfd90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013cfd90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013cfd90 = 0x056b4890;

constexpr std::uint32_t guard_of_013cfdc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013cfdc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013cfdc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d01c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d01c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d01c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d01f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d01f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d01f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d0220 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d0220 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d0220 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d0510 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d0510 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d0510 = 0x056b4840;

constexpr std::uint32_t guard_of_013d0540 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d0540 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d0540 = 0x056b4890;

constexpr std::uint32_t guard_of_013d0570 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d0570 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d0570 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d08d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d08d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d08d0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d0900 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d0900 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d0900 = 0x056b4890;

constexpr std::uint32_t guard_of_013d0930 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d0930 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d0930 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d0bc0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d0bc0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d0bc0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d0bf0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d0bf0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d0bf0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d0c20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d0c20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d0c20 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d1be0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d1be0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d1be0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d1c10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d1c10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d1c10 = 0x056b4890;

constexpr std::uint32_t guard_of_013d1c40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d1c40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d1c40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d1ef0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d1ef0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d1ef0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d1f20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d1f20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d1f20 = 0x056b4890;

constexpr std::uint32_t guard_of_013d1f50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d1f50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d1f50 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d21b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d21b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d21b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d21e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d21e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d21e0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d2210 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d2210 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d2210 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d22c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d22c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d22c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d22f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d22f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d22f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d2320 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d2320 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d2320 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d24a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d24a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d24a0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d24d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d24d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d24d0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d2500 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d2500 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d2500 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d2ce0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d2ce0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d2ce0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d2d10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d2d10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d2d10 = 0x056b4890;

constexpr std::uint32_t guard_of_013d2d40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d2d40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d2d40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d37b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d37b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d37b0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d37e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d37e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d37e0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d3810 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d3810 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d3810 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d4b10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d4b10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d4b10 = 0x056b4840;

constexpr std::uint32_t guard_of_013d4b40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d4b40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d4b40 = 0x056b4890;

constexpr std::uint32_t guard_of_013d4b70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d4b70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d4b70 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d64c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d64c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d64c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013d64f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d64f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d64f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013d6520 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d6520 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d6520 = 0x056b47f0;

constexpr std::uint32_t guard_of_013d6b30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013d6b30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013d6b30 = 0x056b4840;

constexpr std::uint32_t guard_of_013d6b60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013d6b60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013d6b60 = 0x056b4890;

constexpr std::uint32_t guard_of_013d6b90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013d6b90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013d6b90 = 0x056b47f0;

constexpr std::uint32_t guard_of_013da6f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013da6f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013da6f0 = 0x056b4840;

constexpr std::uint32_t guard_of_013da720 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013da720 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013da720 = 0x056b4890;

constexpr std::uint32_t guard_of_013da750 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013da750 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013da750 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dae40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dae40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dae40 = 0x056b4840;

constexpr std::uint32_t guard_of_013dae70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dae70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dae70 = 0x056b4890;

constexpr std::uint32_t guard_of_013daea0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013daea0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013daea0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013db320 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013db320 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013db320 = 0x056b4840;

constexpr std::uint32_t guard_of_013db350 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013db350 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013db350 = 0x056b4890;

constexpr std::uint32_t guard_of_013db380 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013db380 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013db380 = 0x056b47f0;

constexpr std::uint32_t guard_of_013db670 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013db670 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013db670 = 0x056b4840;

constexpr std::uint32_t guard_of_013db6a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013db6a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013db6a0 = 0x056b4890;

constexpr std::uint32_t guard_of_013db6d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013db6d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013db6d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dba90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dba90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dba90 = 0x056b4840;

constexpr std::uint32_t guard_of_013dbac0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dbac0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dbac0 = 0x056b4890;

constexpr std::uint32_t guard_of_013dbaf0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dbaf0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dbaf0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dbde0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dbde0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dbde0 = 0x056b4840;

constexpr std::uint32_t guard_of_013dbe10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dbe10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dbe10 = 0x056b4890;

constexpr std::uint32_t guard_of_013dbe40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dbe40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dbe40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dc0c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dc0c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dc0c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013dc0f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dc0f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dc0f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013dc120 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dc120 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dc120 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dc6d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dc6d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dc6d0 = 0x056b4840;

constexpr std::uint32_t guard_of_013dc700 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dc700 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dc700 = 0x056b4890;

constexpr std::uint32_t guard_of_013dc730 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dc730 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dc730 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dca30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dca30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dca30 = 0x056b4840;

constexpr std::uint32_t guard_of_013dca60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dca60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dca60 = 0x056b4890;

constexpr std::uint32_t guard_of_013dca90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dca90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dca90 = 0x056b47f0;

constexpr std::uint32_t guard_of_013de430 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013de430 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013de430 = 0x056b4840;

constexpr std::uint32_t guard_of_013de460 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013de460 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013de460 = 0x056b4890;

constexpr std::uint32_t guard_of_013de490 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013de490 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013de490 = 0x056b47f0;

constexpr std::uint32_t guard_of_013debf0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013debf0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013debf0 = 0x056b4840;

constexpr std::uint32_t guard_of_013dec20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dec20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dec20 = 0x056b4890;

constexpr std::uint32_t guard_of_013dec50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dec50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dec50 = 0x056b47f0;

constexpr std::uint32_t guard_of_013defd0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013defd0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013defd0 = 0x056b4840;

constexpr std::uint32_t guard_of_013df000 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013df000 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013df000 = 0x056b4890;

constexpr std::uint32_t guard_of_013df030 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013df030 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013df030 = 0x056b47f0;

constexpr std::uint32_t guard_of_013df440 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013df440 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013df440 = 0x056b4840;

constexpr std::uint32_t guard_of_013df470 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013df470 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013df470 = 0x056b4890;

constexpr std::uint32_t guard_of_013df4a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013df4a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013df4a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013df650 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013df650 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013df650 = 0x056b4840;

constexpr std::uint32_t guard_of_013df680 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013df680 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013df680 = 0x056b4890;

constexpr std::uint32_t guard_of_013df6b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013df6b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013df6b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013dfe60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013dfe60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013dfe60 = 0x056b4840;

constexpr std::uint32_t guard_of_013dfe90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013dfe90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013dfe90 = 0x056b4890;

constexpr std::uint32_t guard_of_013dfec0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013dfec0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013dfec0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e0300 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e0300 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e0300 = 0x056b4840;

constexpr std::uint32_t guard_of_013e0330 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e0330 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e0330 = 0x056b4890;

constexpr std::uint32_t guard_of_013e0360 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e0360 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e0360 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e07e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e07e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e07e0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e0810 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e0810 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e0810 = 0x056b4890;

constexpr std::uint32_t guard_of_013e0840 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e0840 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e0840 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e09e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e09e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e09e0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e0a10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e0a10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e0a10 = 0x056b4890;

constexpr std::uint32_t guard_of_013e0a40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e0a40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e0a40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e0b10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e0b10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e0b10 = 0x056b4840;

constexpr std::uint32_t guard_of_013e0b40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e0b40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e0b40 = 0x056b4890;

constexpr std::uint32_t guard_of_013e0b70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e0b70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e0b70 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e1010 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e1010 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e1010 = 0x056b4840;

constexpr std::uint32_t guard_of_013e1040 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e1040 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e1040 = 0x056b4890;

constexpr std::uint32_t guard_of_013e1070 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e1070 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e1070 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e1360 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e1360 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e1360 = 0x056b4840;

constexpr std::uint32_t guard_of_013e1390 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e1390 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e1390 = 0x056b4890;

constexpr std::uint32_t guard_of_013e13c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e13c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e13c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e1a50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e1a50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e1a50 = 0x056b4840;

constexpr std::uint32_t guard_of_013e1a80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e1a80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e1a80 = 0x056b4890;

constexpr std::uint32_t guard_of_013e1ab0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e1ab0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e1ab0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e1da0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e1da0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e1da0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e1dd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e1dd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e1dd0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e1e00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e1e00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e1e00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e1f80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e1f80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e1f80 = 0x056b4840;

constexpr std::uint32_t guard_of_013e1fb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e1fb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e1fb0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e1fe0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e1fe0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e1fe0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e25d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e25d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e25d0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e2600 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e2600 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e2600 = 0x056b4890;

constexpr std::uint32_t guard_of_013e2630 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e2630 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e2630 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e28c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e28c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e28c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e28f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e28f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e28f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e2920 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e2920 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e2920 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e2e80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e2e80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e2e80 = 0x056b4840;

constexpr std::uint32_t guard_of_013e2eb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e2eb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e2eb0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e2ee0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e2ee0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e2ee0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e3830 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e3830 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e3830 = 0x056b4840;

constexpr std::uint32_t guard_of_013e3860 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e3860 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e3860 = 0x056b4890;

constexpr std::uint32_t guard_of_013e3890 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e3890 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e3890 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e39e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e39e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e39e0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e3a10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e3a10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e3a10 = 0x056b4890;

constexpr std::uint32_t guard_of_013e3a40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e3a40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e3a40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e3c80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e3c80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e3c80 = 0x056b4840;

constexpr std::uint32_t guard_of_013e3cb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e3cb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e3cb0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e3ce0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e3ce0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e3ce0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e49c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e49c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e49c0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e49f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e49f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e49f0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e4a20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e4a20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e4a20 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e5b40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e5b40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e5b40 = 0x056b4840;

constexpr std::uint32_t guard_of_013e5b70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e5b70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e5b70 = 0x056b4890;

constexpr std::uint32_t guard_of_013e5ba0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e5ba0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e5ba0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e5c50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e5c50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e5c50 = 0x056b4840;

constexpr std::uint32_t guard_of_013e5c80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e5c80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e5c80 = 0x056b4890;

constexpr std::uint32_t guard_of_013e5cb0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e5cb0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e5cb0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e6700 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e6700 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e6700 = 0x056b4840;

constexpr std::uint32_t guard_of_013e6730 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e6730 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e6730 = 0x056b4890;

constexpr std::uint32_t guard_of_013e6760 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e6760 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e6760 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e6dc0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e6dc0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e6dc0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e6df0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e6df0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e6df0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e6e20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e6e20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e6e20 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e7510 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e7510 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e7510 = 0x056b4840;

constexpr std::uint32_t guard_of_013e7540 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e7540 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e7540 = 0x056b4890;

constexpr std::uint32_t guard_of_013e7570 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e7570 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e7570 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e7b30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e7b30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e7b30 = 0x056b4840;

constexpr std::uint32_t guard_of_013e7b60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e7b60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e7b60 = 0x056b4890;

constexpr std::uint32_t guard_of_013e7b90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e7b90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e7b90 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e7ef0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e7ef0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e7ef0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e7f20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e7f20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e7f20 = 0x056b4890;

constexpr std::uint32_t guard_of_013e7f50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e7f50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e7f50 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e8260 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e8260 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e8260 = 0x056b4840;

constexpr std::uint32_t guard_of_013e8290 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e8290 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e8290 = 0x056b4890;

constexpr std::uint32_t guard_of_013e82c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e82c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e82c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e8940 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e8940 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e8940 = 0x056b4840;

constexpr std::uint32_t guard_of_013e8970 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e8970 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e8970 = 0x056b4890;

constexpr std::uint32_t guard_of_013e89a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e89a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e89a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e9da0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e9da0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e9da0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e9dd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e9dd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e9dd0 = 0x056b4890;

constexpr std::uint32_t guard_of_013e9e00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e9e00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e9e00 = 0x056b47f0;

constexpr std::uint32_t guard_of_013e9ef0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013e9ef0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013e9ef0 = 0x056b4840;

constexpr std::uint32_t guard_of_013e9f20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013e9f20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013e9f20 = 0x056b4890;

constexpr std::uint32_t guard_of_013e9f50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013e9f50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013e9f50 = 0x056b47f0;

constexpr std::uint32_t guard_of_013edf80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013edf80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013edf80 = 0x056b4840;

constexpr std::uint32_t guard_of_013edfb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013edfb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013edfb0 = 0x056b4890;

constexpr std::uint32_t guard_of_013edfe0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013edfe0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013edfe0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f2140 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f2140 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f2140 = 0x056b4840;

constexpr std::uint32_t guard_of_013f2170 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f2170 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f2170 = 0x056b4890;

constexpr std::uint32_t guard_of_013f21a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f21a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f21a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f4af0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f4af0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f4af0 = 0x056b4840;

constexpr std::uint32_t guard_of_013f4b20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f4b20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f4b20 = 0x056b4890;

constexpr std::uint32_t guard_of_013f4b50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f4b50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f4b50 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f4de0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f4de0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f4de0 = 0x056b4840;

constexpr std::uint32_t guard_of_013f4e10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f4e10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f4e10 = 0x056b4890;

constexpr std::uint32_t guard_of_013f4e40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f4e40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f4e40 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f5c30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f5c30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f5c30 = 0x056b4840;

constexpr std::uint32_t guard_of_013f5c60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f5c60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f5c60 = 0x056b4890;

constexpr std::uint32_t guard_of_013f5c90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f5c90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f5c90 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f6a30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f6a30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f6a30 = 0x056b4840;

constexpr std::uint32_t guard_of_013f6a60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f6a60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f6a60 = 0x056b4890;

constexpr std::uint32_t guard_of_013f6a90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f6a90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f6a90 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f8cc0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f8cc0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f8cc0 = 0x056b4840;

constexpr std::uint32_t guard_of_013f8cf0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f8cf0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f8cf0 = 0x056b4890;

constexpr std::uint32_t guard_of_013f8d20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f8d20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f8d20 = 0x056b47f0;

constexpr std::uint32_t guard_of_013f9a00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013f9a00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013f9a00 = 0x056b4840;

constexpr std::uint32_t guard_of_013f9a30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013f9a30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013f9a30 = 0x056b4890;

constexpr std::uint32_t guard_of_013f9a60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013f9a60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013f9a60 = 0x056b47f0;

constexpr std::uint32_t guard_of_013fe5f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013fe5f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013fe5f0 = 0x056b4840;

constexpr std::uint32_t guard_of_013fe620 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013fe620 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013fe620 = 0x056b4890;

constexpr std::uint32_t guard_of_013fe650 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013fe650 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013fe650 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ff290 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ff290 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ff290 = 0x056b4840;

constexpr std::uint32_t guard_of_013ff2c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ff2c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ff2c0 = 0x056b4890;

constexpr std::uint32_t guard_of_013ff2f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ff2f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ff2f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_013ffe50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_013ffe50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_013ffe50 = 0x056b4840;

constexpr std::uint32_t guard_of_013ffe80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_013ffe80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_013ffe80 = 0x056b4890;

constexpr std::uint32_t guard_of_013ffeb0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_013ffeb0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_013ffeb0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01400740 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01400740 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01400740 = 0x056b4840;

constexpr std::uint32_t guard_of_01400770 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01400770 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01400770 = 0x056b4890;

constexpr std::uint32_t guard_of_014007a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014007a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014007a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01400860 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01400860 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01400860 = 0x056b4840;

constexpr std::uint32_t guard_of_01400890 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01400890 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01400890 = 0x056b4890;

constexpr std::uint32_t guard_of_014008c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014008c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014008c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01401500 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01401500 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01401500 = 0x056b4840;

constexpr std::uint32_t guard_of_01401530 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01401530 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01401530 = 0x056b4890;

constexpr std::uint32_t guard_of_01401560 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01401560 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01401560 = 0x056b47f0;

constexpr std::uint32_t guard_of_01401b20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01401b20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01401b20 = 0x056b4840;

constexpr std::uint32_t guard_of_01401b50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01401b50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01401b50 = 0x056b4890;

constexpr std::uint32_t guard_of_01401b80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01401b80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01401b80 = 0x056b47f0;

constexpr std::uint32_t guard_of_01401e30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01401e30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01401e30 = 0x056b4840;

constexpr std::uint32_t guard_of_01401e60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01401e60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01401e60 = 0x056b4890;

constexpr std::uint32_t guard_of_01401e90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01401e90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01401e90 = 0x056b47f0;

constexpr std::uint32_t guard_of_01401fb0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01401fb0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01401fb0 = 0x056b4840;

constexpr std::uint32_t guard_of_01401fe0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01401fe0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01401fe0 = 0x056b4890;

constexpr std::uint32_t guard_of_01402010 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01402010 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01402010 = 0x056b47f0;

constexpr std::uint32_t guard_of_01403810 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01403810 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01403810 = 0x056b4840;

constexpr std::uint32_t guard_of_01403840 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01403840 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01403840 = 0x056b4890;

constexpr std::uint32_t guard_of_01403870 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01403870 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01403870 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140a7a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140a7a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140a7a0 = 0x056b4840;

constexpr std::uint32_t guard_of_0140a7d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140a7d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140a7d0 = 0x056b4890;

constexpr std::uint32_t guard_of_0140a800 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140a800 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140a800 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140b410 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140b410 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140b410 = 0x056b4840;

constexpr std::uint32_t guard_of_0140b440 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140b440 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140b440 = 0x056b4890;

constexpr std::uint32_t guard_of_0140b470 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140b470 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140b470 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140b710 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140b710 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140b710 = 0x056b4840;

constexpr std::uint32_t guard_of_0140b740 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140b740 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140b740 = 0x056b4890;

constexpr std::uint32_t guard_of_0140b770 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140b770 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140b770 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140cd80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140cd80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140cd80 = 0x056b4840;

constexpr std::uint32_t guard_of_0140cdb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140cdb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140cdb0 = 0x056b4890;

constexpr std::uint32_t guard_of_0140cde0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140cde0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140cde0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140ce90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140ce90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140ce90 = 0x056b4840;

constexpr std::uint32_t guard_of_0140cec0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140cec0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140cec0 = 0x056b4890;

constexpr std::uint32_t guard_of_0140cef0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140cef0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140cef0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140d300 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140d300 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140d300 = 0x056b4840;

constexpr std::uint32_t guard_of_0140d330 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140d330 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140d330 = 0x056b4890;

constexpr std::uint32_t guard_of_0140d360 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140d360 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140d360 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140def0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140def0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140def0 = 0x056b4840;

constexpr std::uint32_t guard_of_0140df20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140df20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140df20 = 0x056b4890;

constexpr std::uint32_t guard_of_0140df50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140df50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140df50 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140ea50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140ea50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140ea50 = 0x056b4840;

constexpr std::uint32_t guard_of_0140ea80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140ea80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140ea80 = 0x056b4890;

constexpr std::uint32_t guard_of_0140eab0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140eab0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140eab0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140f090 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140f090 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140f090 = 0x056b4840;

constexpr std::uint32_t guard_of_0140f0c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140f0c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140f0c0 = 0x056b4890;

constexpr std::uint32_t guard_of_0140f0f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140f0f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140f0f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140f5c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140f5c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140f5c0 = 0x056b4840;

constexpr std::uint32_t guard_of_0140f5f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140f5f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140f5f0 = 0x056b4890;

constexpr std::uint32_t guard_of_0140f620 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140f620 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140f620 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140f690 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140f690 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140f690 = 0x056b4840;

constexpr std::uint32_t guard_of_0140f6c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140f6c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140f6c0 = 0x056b4890;

constexpr std::uint32_t guard_of_0140f6f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140f6f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140f6f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0140fd10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0140fd10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0140fd10 = 0x056b4840;

constexpr std::uint32_t guard_of_0140fd40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0140fd40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0140fd40 = 0x056b4890;

constexpr std::uint32_t guard_of_0140fd70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0140fd70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0140fd70 = 0x056b47f0;

constexpr std::uint32_t guard_of_01410030 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01410030 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01410030 = 0x056b4840;

constexpr std::uint32_t guard_of_01410060 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01410060 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01410060 = 0x056b4890;

constexpr std::uint32_t guard_of_01410090 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01410090 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01410090 = 0x056b47f0;

constexpr std::uint32_t guard_of_01410750 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01410750 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01410750 = 0x056b4840;

constexpr std::uint32_t guard_of_01410780 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01410780 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01410780 = 0x056b4890;

constexpr std::uint32_t guard_of_014107b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014107b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014107b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01411490 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01411490 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01411490 = 0x056b4840;

constexpr std::uint32_t guard_of_014114c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014114c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014114c0 = 0x056b4890;

constexpr std::uint32_t guard_of_014114f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014114f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014114f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014119e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014119e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014119e0 = 0x056b4840;

constexpr std::uint32_t guard_of_01411a10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01411a10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01411a10 = 0x056b4890;

constexpr std::uint32_t guard_of_01411a40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01411a40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01411a40 = 0x056b47f0;

constexpr std::uint32_t guard_of_01412430 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01412430 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01412430 = 0x056b4840;

constexpr std::uint32_t guard_of_01412460 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01412460 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01412460 = 0x056b4890;

constexpr std::uint32_t guard_of_01412490 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01412490 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01412490 = 0x056b47f0;

constexpr std::uint32_t guard_of_01412df0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01412df0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01412df0 = 0x056b4840;

constexpr std::uint32_t guard_of_01412e20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01412e20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01412e20 = 0x056b4890;

constexpr std::uint32_t guard_of_01412e50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01412e50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01412e50 = 0x056b47f0;

constexpr std::uint32_t guard_of_01417530 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01417530 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01417530 = 0x056b4840;

constexpr std::uint32_t guard_of_01417560 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01417560 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01417560 = 0x056b4890;

constexpr std::uint32_t guard_of_01417590 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01417590 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01417590 = 0x056b47f0;

constexpr std::uint32_t guard_of_01417a20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01417a20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01417a20 = 0x056b4840;

constexpr std::uint32_t guard_of_01417a50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01417a50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01417a50 = 0x056b4890;

constexpr std::uint32_t guard_of_01417a80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01417a80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01417a80 = 0x056b47f0;

constexpr std::uint32_t guard_of_014181d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014181d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014181d0 = 0x056b4840;

constexpr std::uint32_t guard_of_01418200 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01418200 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01418200 = 0x056b4890;

constexpr std::uint32_t guard_of_01418230 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01418230 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01418230 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141a290 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141a290 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141a290 = 0x056b4840;

constexpr std::uint32_t guard_of_0141a2c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141a2c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141a2c0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141a2f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141a2f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141a2f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141a560 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141a560 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141a560 = 0x056b4840;

constexpr std::uint32_t guard_of_0141a590 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141a590 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141a590 = 0x056b4890;

constexpr std::uint32_t guard_of_0141a5c0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141a5c0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141a5c0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141bb90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141bb90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141bb90 = 0x056b4840;

constexpr std::uint32_t guard_of_0141bbc0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141bbc0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141bbc0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141bbf0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141bbf0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141bbf0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141bd40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141bd40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141bd40 = 0x056b4840;

constexpr std::uint32_t guard_of_0141bd70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141bd70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141bd70 = 0x056b4890;

constexpr std::uint32_t guard_of_0141bda0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141bda0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141bda0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141bfa0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141bfa0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141bfa0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141bfd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141bfd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141bfd0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141c000 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141c000 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141c000 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141c1d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141c1d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141c1d0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141c200 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141c200 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141c200 = 0x056b4890;

constexpr std::uint32_t guard_of_0141c230 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141c230 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141c230 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141c4f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141c4f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141c4f0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141c520 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141c520 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141c520 = 0x056b4890;

constexpr std::uint32_t guard_of_0141c550 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141c550 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141c550 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141c800 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141c800 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141c800 = 0x056b4840;

constexpr std::uint32_t guard_of_0141c830 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141c830 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141c830 = 0x056b4890;

constexpr std::uint32_t guard_of_0141c860 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141c860 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141c860 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141cb20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141cb20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141cb20 = 0x056b4840;

constexpr std::uint32_t guard_of_0141cb50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141cb50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141cb50 = 0x056b4890;

constexpr std::uint32_t guard_of_0141cb80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141cb80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141cb80 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141cf80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141cf80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141cf80 = 0x056b4840;

constexpr std::uint32_t guard_of_0141cfb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141cfb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141cfb0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141cfe0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141cfe0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141cfe0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141d1b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141d1b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141d1b0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141d1e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141d1e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141d1e0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141d210 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141d210 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141d210 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141d4d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141d4d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141d4d0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141d500 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141d500 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141d500 = 0x056b4890;

constexpr std::uint32_t guard_of_0141d530 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141d530 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141d530 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141d7e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141d7e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141d7e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141d810 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141d810 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141d810 = 0x056b4890;

constexpr std::uint32_t guard_of_0141d840 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141d840 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141d840 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141da70 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141da70 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141da70 = 0x056b4840;

constexpr std::uint32_t guard_of_0141daa0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141daa0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141daa0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141dad0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141dad0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141dad0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141dc40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141dc40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141dc40 = 0x056b4840;

constexpr std::uint32_t guard_of_0141dc70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141dc70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141dc70 = 0x056b4890;

constexpr std::uint32_t guard_of_0141dca0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141dca0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141dca0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141e320 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141e320 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141e320 = 0x056b4840;

constexpr std::uint32_t guard_of_0141e350 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141e350 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141e350 = 0x056b4890;

constexpr std::uint32_t guard_of_0141e380 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141e380 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141e380 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141f080 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141f080 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141f080 = 0x056b4840;

constexpr std::uint32_t guard_of_0141f0b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141f0b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141f0b0 = 0x056b4890;

constexpr std::uint32_t guard_of_0141f0e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141f0e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141f0e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0141f4e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0141f4e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0141f4e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0141f510 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0141f510 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0141f510 = 0x056b4890;

constexpr std::uint32_t guard_of_0141f540 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0141f540 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0141f540 = 0x056b47f0;

constexpr std::uint32_t guard_of_01423250 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01423250 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01423250 = 0x056b4840;

constexpr std::uint32_t guard_of_01423280 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01423280 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01423280 = 0x056b4890;

constexpr std::uint32_t guard_of_014232b0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014232b0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014232b0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01425f60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01425f60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01425f60 = 0x056b4840;

constexpr std::uint32_t guard_of_01425f90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01425f90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01425f90 = 0x056b4890;

constexpr std::uint32_t guard_of_01425fc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01425fc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01425fc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01426c20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01426c20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01426c20 = 0x056b4840;

constexpr std::uint32_t guard_of_01426c50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01426c50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01426c50 = 0x056b4890;

constexpr std::uint32_t guard_of_01426c80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01426c80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01426c80 = 0x056b47f0;

constexpr std::uint32_t guard_of_01426da0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01426da0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01426da0 = 0x056b4840;

constexpr std::uint32_t guard_of_01426dd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01426dd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01426dd0 = 0x056b4890;

constexpr std::uint32_t guard_of_01426e00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01426e00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01426e00 = 0x056b47f0;

constexpr std::uint32_t guard_of_01427500 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01427500 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01427500 = 0x056b4840;

constexpr std::uint32_t guard_of_01427530 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01427530 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01427530 = 0x056b4890;

constexpr std::uint32_t guard_of_01427560 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01427560 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01427560 = 0x056b47f0;

constexpr std::uint32_t guard_of_014325f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014325f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014325f0 = 0x056b4840;

constexpr std::uint32_t guard_of_01432620 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01432620 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01432620 = 0x056b4890;

constexpr std::uint32_t guard_of_01432650 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01432650 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01432650 = 0x056b47f0;

constexpr std::uint32_t guard_of_014329c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014329c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014329c0 = 0x056b4840;

constexpr std::uint32_t guard_of_014329f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014329f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014329f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01432a20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01432a20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01432a20 = 0x056b47f0;

constexpr std::uint32_t guard_of_01432ab0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01432ab0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01432ab0 = 0x056b4840;

constexpr std::uint32_t guard_of_01432ae0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01432ae0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01432ae0 = 0x056b4890;

constexpr std::uint32_t guard_of_01432b10 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01432b10 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01432b10 = 0x056b47f0;

constexpr std::uint32_t guard_of_01432c10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01432c10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01432c10 = 0x056b4840;

constexpr std::uint32_t guard_of_01432c40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01432c40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01432c40 = 0x056b4890;

constexpr std::uint32_t guard_of_01432c70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01432c70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01432c70 = 0x056b47f0;

constexpr std::uint32_t guard_of_01432f80 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01432f80 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01432f80 = 0x056b4840;

constexpr std::uint32_t guard_of_01432fb0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01432fb0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01432fb0 = 0x056b4890;

constexpr std::uint32_t guard_of_01432fe0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01432fe0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01432fe0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014332b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014332b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014332b0 = 0x056b4840;

constexpr std::uint32_t guard_of_014332e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014332e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014332e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01433310 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01433310 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01433310 = 0x056b47f0;

constexpr std::uint32_t guard_of_014333b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014333b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014333b0 = 0x056b4840;

constexpr std::uint32_t guard_of_014333e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014333e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014333e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01433410 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01433410 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01433410 = 0x056b47f0;

constexpr std::uint32_t guard_of_01433700 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01433700 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01433700 = 0x056b4840;

constexpr std::uint32_t guard_of_01433730 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01433730 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01433730 = 0x056b4890;

constexpr std::uint32_t guard_of_01433760 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01433760 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01433760 = 0x056b47f0;

constexpr std::uint32_t guard_of_01433a60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01433a60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01433a60 = 0x056b4840;

constexpr std::uint32_t guard_of_01433a90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01433a90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01433a90 = 0x056b4890;

constexpr std::uint32_t guard_of_01433ac0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01433ac0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01433ac0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01434980 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01434980 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01434980 = 0x056b4840;

constexpr std::uint32_t guard_of_014349b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014349b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014349b0 = 0x056b4890;

constexpr std::uint32_t guard_of_014349e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014349e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014349e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01435910 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01435910 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01435910 = 0x056b4840;

constexpr std::uint32_t guard_of_01435940 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01435940 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01435940 = 0x056b4890;

constexpr std::uint32_t guard_of_01435970 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01435970 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01435970 = 0x056b47f0;

constexpr std::uint32_t guard_of_01436930 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01436930 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01436930 = 0x056b4840;

constexpr std::uint32_t guard_of_01436960 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01436960 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01436960 = 0x056b4890;

constexpr std::uint32_t guard_of_01436990 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01436990 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01436990 = 0x056b47f0;

constexpr std::uint32_t guard_of_01436b60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01436b60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01436b60 = 0x056b4840;

constexpr std::uint32_t guard_of_01436b90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01436b90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01436b90 = 0x056b4890;

constexpr std::uint32_t guard_of_01436bc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01436bc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01436bc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01436e50 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01436e50 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01436e50 = 0x056b4840;

constexpr std::uint32_t guard_of_01436e80 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01436e80 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01436e80 = 0x056b4890;

constexpr std::uint32_t guard_of_01436eb0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01436eb0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01436eb0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014371f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014371f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014371f0 = 0x056b4840;

constexpr std::uint32_t guard_of_01437220 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01437220 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01437220 = 0x056b4890;

constexpr std::uint32_t guard_of_01437250 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01437250 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01437250 = 0x056b47f0;

constexpr std::uint32_t guard_of_01437500 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01437500 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01437500 = 0x056b4840;

constexpr std::uint32_t guard_of_01437530 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01437530 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01437530 = 0x056b4890;

constexpr std::uint32_t guard_of_01437560 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01437560 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01437560 = 0x056b47f0;

constexpr std::uint32_t guard_of_01437810 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01437810 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01437810 = 0x056b4840;

constexpr std::uint32_t guard_of_01437840 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01437840 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01437840 = 0x056b4890;

constexpr std::uint32_t guard_of_01437870 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01437870 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01437870 = 0x056b47f0;

constexpr std::uint32_t guard_of_01437b20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01437b20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01437b20 = 0x056b4840;

constexpr std::uint32_t guard_of_01437b50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01437b50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01437b50 = 0x056b4890;

constexpr std::uint32_t guard_of_01437b80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01437b80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01437b80 = 0x056b47f0;

constexpr std::uint32_t guard_of_01437e30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01437e30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01437e30 = 0x056b4840;

constexpr std::uint32_t guard_of_01437e60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01437e60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01437e60 = 0x056b4890;

constexpr std::uint32_t guard_of_01437e90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01437e90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01437e90 = 0x056b47f0;

constexpr std::uint32_t guard_of_01438af0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01438af0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01438af0 = 0x056b4840;

constexpr std::uint32_t guard_of_01438b20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01438b20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01438b20 = 0x056b4890;

constexpr std::uint32_t guard_of_01438b50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01438b50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01438b50 = 0x056b47f0;

constexpr std::uint32_t guard_of_014391a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014391a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014391a0 = 0x056b4840;

constexpr std::uint32_t guard_of_014391d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014391d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014391d0 = 0x056b4890;

constexpr std::uint32_t guard_of_01439200 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01439200 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01439200 = 0x056b47f0;

constexpr std::uint32_t guard_of_014393a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014393a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014393a0 = 0x056b4840;

constexpr std::uint32_t guard_of_014393d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014393d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014393d0 = 0x056b4890;

constexpr std::uint32_t guard_of_01439400 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01439400 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01439400 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143b9d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143b9d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143b9d0 = 0x056b4840;

constexpr std::uint32_t guard_of_0143ba00 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143ba00 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143ba00 = 0x056b4890;

constexpr std::uint32_t guard_of_0143ba30 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143ba30 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143ba30 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143bdf0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143bdf0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143bdf0 = 0x056b4840;

constexpr std::uint32_t guard_of_0143be20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143be20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143be20 = 0x056b4890;

constexpr std::uint32_t guard_of_0143be50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143be50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143be50 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143bf20 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143bf20 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143bf20 = 0x056b4840;

constexpr std::uint32_t guard_of_0143bf50 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143bf50 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143bf50 = 0x056b4890;

constexpr std::uint32_t guard_of_0143bf80 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143bf80 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143bf80 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143ce10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143ce10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143ce10 = 0x056b4840;

constexpr std::uint32_t guard_of_0143ce40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143ce40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143ce40 = 0x056b4890;

constexpr std::uint32_t guard_of_0143ce70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143ce70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143ce70 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143d470 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143d470 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143d470 = 0x056b4840;

constexpr std::uint32_t guard_of_0143d4a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143d4a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143d4a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0143d4d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143d4d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143d4d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143d810 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143d810 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143d810 = 0x056b4840;

constexpr std::uint32_t guard_of_0143d840 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143d840 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143d840 = 0x056b4890;

constexpr std::uint32_t guard_of_0143d870 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143d870 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143d870 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143e0e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143e0e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143e0e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0143e110 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143e110 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143e110 = 0x056b4890;

constexpr std::uint32_t guard_of_0143e140 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143e140 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143e140 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143e540 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143e540 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143e540 = 0x056b4840;

constexpr std::uint32_t guard_of_0143e570 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143e570 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143e570 = 0x056b4890;

constexpr std::uint32_t guard_of_0143e5a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143e5a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143e5a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143eff0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143eff0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143eff0 = 0x056b4840;

constexpr std::uint32_t guard_of_0143f020 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143f020 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143f020 = 0x056b4890;

constexpr std::uint32_t guard_of_0143f050 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143f050 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143f050 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143f8b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143f8b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143f8b0 = 0x056b4840;

constexpr std::uint32_t guard_of_0143f8e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143f8e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143f8e0 = 0x056b4890;

constexpr std::uint32_t guard_of_0143f910 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143f910 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143f910 = 0x056b47f0;

constexpr std::uint32_t guard_of_0143fa30 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0143fa30 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0143fa30 = 0x056b4840;

constexpr std::uint32_t guard_of_0143fa60 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0143fa60 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0143fa60 = 0x056b4890;

constexpr std::uint32_t guard_of_0143fa90 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0143fa90 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0143fa90 = 0x056b47f0;

constexpr std::uint32_t guard_of_01440700 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01440700 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01440700 = 0x056b4840;

constexpr std::uint32_t guard_of_01440730 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01440730 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01440730 = 0x056b4890;

constexpr std::uint32_t guard_of_01440760 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01440760 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01440760 = 0x056b47f0;

constexpr std::uint32_t guard_of_01440d60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01440d60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01440d60 = 0x056b4840;

constexpr std::uint32_t guard_of_01440d90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01440d90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01440d90 = 0x056b4890;

constexpr std::uint32_t guard_of_01440dc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01440dc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01440dc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014412b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014412b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014412b0 = 0x056b4840;

constexpr std::uint32_t guard_of_014412e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014412e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014412e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01441310 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01441310 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01441310 = 0x056b47f0;

constexpr std::uint32_t guard_of_014415a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014415a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014415a0 = 0x056b4840;

constexpr std::uint32_t guard_of_014415d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014415d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014415d0 = 0x056b4890;

constexpr std::uint32_t guard_of_01441600 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01441600 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01441600 = 0x056b47f0;

constexpr std::uint32_t guard_of_01441870 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01441870 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01441870 = 0x056b4840;

constexpr std::uint32_t guard_of_014418a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014418a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014418a0 = 0x056b4890;

constexpr std::uint32_t guard_of_014418d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014418d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014418d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014422c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014422c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014422c0 = 0x056b4840;

constexpr std::uint32_t guard_of_014422f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014422f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014422f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01442320 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01442320 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01442320 = 0x056b47f0;

constexpr std::uint32_t guard_of_01444270 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01444270 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01444270 = 0x056b4840;

constexpr std::uint32_t guard_of_014442a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014442a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014442a0 = 0x056b4890;

constexpr std::uint32_t guard_of_014442d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014442d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014442d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01444a40 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01444a40 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01444a40 = 0x056b4840;

constexpr std::uint32_t guard_of_01444a70 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01444a70 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01444a70 = 0x056b4890;

constexpr std::uint32_t guard_of_01444aa0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01444aa0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01444aa0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01444dd0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01444dd0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01444dd0 = 0x056b4840;

constexpr std::uint32_t guard_of_01444e00 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01444e00 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01444e00 = 0x056b4890;

constexpr std::uint32_t guard_of_01444e30 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01444e30 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01444e30 = 0x056b47f0;

constexpr std::uint32_t guard_of_014452d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014452d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014452d0 = 0x056b4840;

constexpr std::uint32_t guard_of_01445300 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01445300 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01445300 = 0x056b4890;

constexpr std::uint32_t guard_of_01445330 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01445330 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01445330 = 0x056b47f0;

constexpr std::uint32_t guard_of_01445820 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01445820 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01445820 = 0x056b4840;

constexpr std::uint32_t guard_of_01445850 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01445850 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01445850 = 0x056b4890;

constexpr std::uint32_t guard_of_01445880 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01445880 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01445880 = 0x056b47f0;

constexpr std::uint32_t guard_of_014469b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014469b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014469b0 = 0x056b4840;

constexpr std::uint32_t guard_of_014469e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014469e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014469e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01446a10 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01446a10 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01446a10 = 0x056b47f0;

constexpr std::uint32_t guard_of_01447e10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01447e10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01447e10 = 0x056b4840;

constexpr std::uint32_t guard_of_01447e40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01447e40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01447e40 = 0x056b4890;

constexpr std::uint32_t guard_of_01447e70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01447e70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01447e70 = 0x056b47f0;

constexpr std::uint32_t guard_of_01448390 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01448390 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01448390 = 0x056b4840;

constexpr std::uint32_t guard_of_014483c0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014483c0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014483c0 = 0x056b4890;

constexpr std::uint32_t guard_of_014483f0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014483f0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014483f0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014488e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014488e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014488e0 = 0x056b4840;

constexpr std::uint32_t guard_of_01448910 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01448910 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01448910 = 0x056b4890;

constexpr std::uint32_t guard_of_01448940 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01448940 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01448940 = 0x056b47f0;

constexpr std::uint32_t guard_of_014489f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014489f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014489f0 = 0x056b4840;

constexpr std::uint32_t guard_of_01448a20 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01448a20 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01448a20 = 0x056b4890;

constexpr std::uint32_t guard_of_01448a50 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01448a50 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01448a50 = 0x056b47f0;

constexpr std::uint32_t guard_of_01448ce0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01448ce0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01448ce0 = 0x056b4840;

constexpr std::uint32_t guard_of_01448d10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01448d10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01448d10 = 0x056b4890;

constexpr std::uint32_t guard_of_01448d40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01448d40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01448d40 = 0x056b47f0;

constexpr std::uint32_t guard_of_01449120 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01449120 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01449120 = 0x056b4840;

constexpr std::uint32_t guard_of_01449150 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01449150 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01449150 = 0x056b4890;

constexpr std::uint32_t guard_of_01449180 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01449180 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01449180 = 0x056b47f0;

constexpr std::uint32_t guard_of_014493c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014493c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014493c0 = 0x056b4840;

constexpr std::uint32_t guard_of_014493f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014493f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014493f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01449420 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01449420 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01449420 = 0x056b47f0;

constexpr std::uint32_t guard_of_0144a740 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0144a740 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0144a740 = 0x056b4840;

constexpr std::uint32_t guard_of_0144a770 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0144a770 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0144a770 = 0x056b4890;

constexpr std::uint32_t guard_of_0144a7a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0144a7a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0144a7a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0144ae60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0144ae60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0144ae60 = 0x056b4840;

constexpr std::uint32_t guard_of_0144ae90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0144ae90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0144ae90 = 0x056b4890;

constexpr std::uint32_t guard_of_0144aec0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0144aec0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0144aec0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0144ba10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0144ba10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0144ba10 = 0x056b4840;

constexpr std::uint32_t guard_of_0144ba40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0144ba40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0144ba40 = 0x056b4890;

constexpr std::uint32_t guard_of_0144ba70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0144ba70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0144ba70 = 0x056b47f0;

constexpr std::uint32_t guard_of_01450720 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01450720 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01450720 = 0x056b4840;

constexpr std::uint32_t guard_of_01450750 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01450750 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01450750 = 0x056b4890;

constexpr std::uint32_t guard_of_01450780 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01450780 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01450780 = 0x056b47f0;

constexpr std::uint32_t guard_of_01450e10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01450e10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01450e10 = 0x056b4840;

constexpr std::uint32_t guard_of_01450e40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01450e40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01450e40 = 0x056b4890;

constexpr std::uint32_t guard_of_01450e70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01450e70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01450e70 = 0x056b47f0;

constexpr std::uint32_t guard_of_014511b0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014511b0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014511b0 = 0x056b4840;

constexpr std::uint32_t guard_of_014511e0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014511e0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014511e0 = 0x056b4890;

constexpr std::uint32_t guard_of_01451210 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01451210 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01451210 = 0x056b47f0;

constexpr std::uint32_t guard_of_01451c90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01451c90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01451c90 = 0x056b4840;

constexpr std::uint32_t guard_of_01451cc0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01451cc0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01451cc0 = 0x056b4890;

constexpr std::uint32_t guard_of_01451cf0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01451cf0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01451cf0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01455be0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01455be0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01455be0 = 0x056b4840;

constexpr std::uint32_t guard_of_01455c10 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01455c10 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01455c10 = 0x056b4890;

constexpr std::uint32_t guard_of_01455c40 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01455c40 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01455c40 = 0x056b47f0;

constexpr std::uint32_t guard_of_01455cc0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01455cc0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01455cc0 = 0x056b4840;

constexpr std::uint32_t guard_of_01455cf0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01455cf0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01455cf0 = 0x056b4890;

constexpr std::uint32_t guard_of_01455d20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01455d20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01455d20 = 0x056b47f0;

constexpr std::uint32_t guard_of_01456040 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01456040 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01456040 = 0x056b4840;

constexpr std::uint32_t guard_of_01456070 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01456070 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01456070 = 0x056b4890;

constexpr std::uint32_t guard_of_014560a0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014560a0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014560a0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01456a10 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01456a10 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01456a10 = 0x056b4840;

constexpr std::uint32_t guard_of_01456a40 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01456a40 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01456a40 = 0x056b4890;

constexpr std::uint32_t guard_of_01456a70 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01456a70 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01456a70 = 0x056b47f0;

constexpr std::uint32_t guard_of_01456cc0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01456cc0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01456cc0 = 0x056b4840;

constexpr std::uint32_t guard_of_01456cf0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01456cf0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01456cf0 = 0x056b4890;

constexpr std::uint32_t guard_of_01456d20 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01456d20 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01456d20 = 0x056b47f0;

constexpr std::uint32_t guard_of_01457210 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01457210 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01457210 = 0x056b4840;

constexpr std::uint32_t guard_of_01457240 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01457240 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01457240 = 0x056b4890;

constexpr std::uint32_t guard_of_01457270 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01457270 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01457270 = 0x056b47f0;

constexpr std::uint32_t guard_of_01457b70 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01457b70 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01457b70 = 0x056b4840;

constexpr std::uint32_t guard_of_01457ba0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01457ba0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01457ba0 = 0x056b4890;

constexpr std::uint32_t guard_of_01457bd0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01457bd0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01457bd0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01457c60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01457c60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01457c60 = 0x056b4840;

constexpr std::uint32_t guard_of_01457c90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01457c90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01457c90 = 0x056b4890;

constexpr std::uint32_t guard_of_01457cc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01457cc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01457cc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014592a0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014592a0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014592a0 = 0x056b4840;

constexpr std::uint32_t guard_of_014592d0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014592d0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014592d0 = 0x056b4890;

constexpr std::uint32_t guard_of_01459300 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01459300 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01459300 = 0x056b47f0;

constexpr std::uint32_t guard_of_01459d00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01459d00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01459d00 = 0x056b4840;

constexpr std::uint32_t guard_of_01459d30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01459d30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01459d30 = 0x056b4890;

constexpr std::uint32_t guard_of_01459d60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01459d60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01459d60 = 0x056b47f0;

constexpr std::uint32_t guard_of_01459dd0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01459dd0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01459dd0 = 0x056b4840;

constexpr std::uint32_t guard_of_01459e00 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01459e00 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01459e00 = 0x056b4890;

constexpr std::uint32_t guard_of_01459e30 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01459e30 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01459e30 = 0x056b47f0;

constexpr std::uint32_t guard_of_01459f00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01459f00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01459f00 = 0x056b4840;

constexpr std::uint32_t guard_of_01459f30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01459f30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01459f30 = 0x056b4890;

constexpr std::uint32_t guard_of_01459f60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01459f60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01459f60 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145a030 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145a030 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145a030 = 0x056b4840;

constexpr std::uint32_t guard_of_0145a060 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145a060 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145a060 = 0x056b4890;

constexpr std::uint32_t guard_of_0145a090 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145a090 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145a090 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145b5e0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145b5e0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145b5e0 = 0x056b4840;

constexpr std::uint32_t guard_of_0145b610 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145b610 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145b610 = 0x056b4890;

constexpr std::uint32_t guard_of_0145b640 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145b640 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145b640 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145b700 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145b700 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145b700 = 0x056b4840;

constexpr std::uint32_t guard_of_0145b730 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145b730 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145b730 = 0x056b4890;

constexpr std::uint32_t guard_of_0145b760 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145b760 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145b760 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145bb60 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145bb60 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145bb60 = 0x056b4840;

constexpr std::uint32_t guard_of_0145bb90 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145bb90 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145bb90 = 0x056b4890;

constexpr std::uint32_t guard_of_0145bbc0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145bbc0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145bbc0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145c770 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145c770 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145c770 = 0x056b4840;

constexpr std::uint32_t guard_of_0145c7a0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145c7a0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145c7a0 = 0x056b4890;

constexpr std::uint32_t guard_of_0145c7d0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145c7d0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145c7d0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145cb70 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145cb70 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145cb70 = 0x056b4840;

constexpr std::uint32_t guard_of_0145cba0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145cba0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145cba0 = 0x056b4890;

constexpr std::uint32_t guard_of_0145cbd0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145cbd0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145cbd0 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145d020 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145d020 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145d020 = 0x056b4840;

constexpr std::uint32_t guard_of_0145d050 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145d050 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145d050 = 0x056b4890;

constexpr std::uint32_t guard_of_0145d080 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145d080 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145d080 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145da00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145da00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145da00 = 0x056b4840;

constexpr std::uint32_t guard_of_0145da30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145da30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145da30 = 0x056b4890;

constexpr std::uint32_t guard_of_0145da60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145da60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145da60 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145e530 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145e530 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145e530 = 0x056b4840;

constexpr std::uint32_t guard_of_0145e560 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145e560 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145e560 = 0x056b4890;

constexpr std::uint32_t guard_of_0145e590 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145e590 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145e590 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145eaa0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145eaa0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145eaa0 = 0x056b4840;

constexpr std::uint32_t guard_of_0145ead0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145ead0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145ead0 = 0x056b4890;

constexpr std::uint32_t guard_of_0145eb00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145eb00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145eb00 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145edb0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145edb0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145edb0 = 0x056b4840;

constexpr std::uint32_t guard_of_0145ede0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145ede0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145ede0 = 0x056b4890;

constexpr std::uint32_t guard_of_0145ee10 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145ee10 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145ee10 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145f2d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145f2d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145f2d0 = 0x056b4840;

constexpr std::uint32_t guard_of_0145f300 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145f300 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145f300 = 0x056b4890;

constexpr std::uint32_t guard_of_0145f330 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145f330 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145f330 = 0x056b47f0;

constexpr std::uint32_t guard_of_0145fc90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_0145fc90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_0145fc90 = 0x056b4840;

constexpr std::uint32_t guard_of_0145fcc0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_0145fcc0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_0145fcc0 = 0x056b4890;

constexpr std::uint32_t guard_of_0145fcf0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_0145fcf0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_0145fcf0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014624c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014624c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014624c0 = 0x056b4840;

constexpr std::uint32_t guard_of_014624f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014624f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014624f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01462520 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01462520 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01462520 = 0x056b47f0;

constexpr std::uint32_t guard_of_01463300 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01463300 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01463300 = 0x056b4840;

constexpr std::uint32_t guard_of_01463330 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01463330 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01463330 = 0x056b4890;

constexpr std::uint32_t guard_of_01463360 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01463360 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01463360 = 0x056b47f0;

constexpr std::uint32_t guard_of_014644f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014644f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014644f0 = 0x056b4840;

constexpr std::uint32_t guard_of_01464520 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01464520 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01464520 = 0x056b4890;

constexpr std::uint32_t guard_of_01464550 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01464550 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01464550 = 0x056b47f0;

constexpr std::uint32_t guard_of_01464da0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01464da0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01464da0 = 0x056b4840;

constexpr std::uint32_t guard_of_01464dd0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01464dd0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01464dd0 = 0x056b4890;

constexpr std::uint32_t guard_of_01464e00 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01464e00 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01464e00 = 0x056b47f0;

constexpr std::uint32_t guard_of_01464f70 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01464f70 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01464f70 = 0x056b4840;

constexpr std::uint32_t guard_of_01464fa0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01464fa0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01464fa0 = 0x056b4890;

constexpr std::uint32_t guard_of_01464fd0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01464fd0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01464fd0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01466c70 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01466c70 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01466c70 = 0x056b4840;

constexpr std::uint32_t guard_of_01466ca0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01466ca0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01466ca0 = 0x056b4890;

constexpr std::uint32_t guard_of_01466cd0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01466cd0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01466cd0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01466d90 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01466d90 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01466d90 = 0x056b4840;

constexpr std::uint32_t guard_of_01466dc0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01466dc0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01466dc0 = 0x056b4890;

constexpr std::uint32_t guard_of_01466df0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01466df0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01466df0 = 0x056b47f0;

constexpr std::uint32_t guard_of_01466f00 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01466f00 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01466f00 = 0x056b4840;

constexpr std::uint32_t guard_of_01466f30 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01466f30 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01466f30 = 0x056b4890;

constexpr std::uint32_t guard_of_01466f60 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01466f60 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01466f60 = 0x056b47f0;

constexpr std::uint32_t guard_of_014675c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014675c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014675c0 = 0x056b4840;

constexpr std::uint32_t guard_of_014675f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014675f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014675f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01467620 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01467620 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01467620 = 0x056b47f0;

constexpr std::uint32_t guard_of_014677f0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014677f0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014677f0 = 0x056b4840;

constexpr std::uint32_t guard_of_01467820 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01467820 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01467820 = 0x056b4890;

constexpr std::uint32_t guard_of_01467850 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01467850 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01467850 = 0x056b47f0;

constexpr std::uint32_t guard_of_014680c0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014680c0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014680c0 = 0x056b4840;

constexpr std::uint32_t guard_of_014680f0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014680f0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014680f0 = 0x056b4890;

constexpr std::uint32_t guard_of_01468120 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01468120 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01468120 = 0x056b47f0;

constexpr std::uint32_t guard_of_01468380 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_01468380 = 0x05ac59b0;
constexpr std::uint32_t storage_of_01468380 = 0x056b4840;

constexpr std::uint32_t guard_of_014683b0 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_014683b0 = 0x05ac59c0;
constexpr std::uint32_t storage_of_014683b0 = 0x056b4890;

constexpr std::uint32_t guard_of_014683e0 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_014683e0 = 0x05ac59d0;
constexpr std::uint32_t storage_of_014683e0 = 0x056b47f0;

constexpr std::uint32_t guard_of_014684d0 = 0x05ac59b8;
constexpr std::uint32_t pointer_of_014684d0 = 0x05ac59b0;
constexpr std::uint32_t storage_of_014684d0 = 0x056b4840;

constexpr std::uint32_t guard_of_01468500 = 0x05ac59c8;
constexpr std::uint32_t pointer_of_01468500 = 0x05ac59c0;
constexpr std::uint32_t storage_of_01468500 = 0x056b4890;

constexpr std::uint32_t guard_of_01468530 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_01468530 = 0x05ac59d0;
constexpr std::uint32_t storage_of_01468530 = 0x056b47f0;

constexpr std::uint32_t guard_of_02785310 = 0x05ac59d8;
constexpr std::uint32_t pointer_of_02785310 = 0x05ac59d0;
constexpr std::uint32_t storage_of_02785310 = 0x056b47f0;

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

extern "C" void bb_frame_timing_static_guard_0135bde0()
{
    bind_static<guard_of_0135bde0, pointer_of_0135bde0, storage_of_0135bde0>();
}

extern "C" void bb_frame_timing_static_guard_0135be10()
{
    bind_static<guard_of_0135be10, pointer_of_0135be10, storage_of_0135be10>();
}

extern "C" void bb_frame_timing_static_guard_0135be40()
{
    bind_static<guard_of_0135be40, pointer_of_0135be40, storage_of_0135be40>();
}

extern "C" void bb_frame_timing_static_guard_0135c780()
{
    bind_static<guard_of_0135c780, pointer_of_0135c780, storage_of_0135c780>();
}

extern "C" void bb_frame_timing_static_guard_0135c7b0()
{
    bind_static<guard_of_0135c7b0, pointer_of_0135c7b0, storage_of_0135c7b0>();
}

extern "C" void bb_frame_timing_static_guard_0135c7e0()
{
    bind_static<guard_of_0135c7e0, pointer_of_0135c7e0, storage_of_0135c7e0>();
}

extern "C" void bb_frame_timing_static_guard_0135c9b0()
{
    bind_static<guard_of_0135c9b0, pointer_of_0135c9b0, storage_of_0135c9b0>();
}

extern "C" void bb_frame_timing_static_guard_0135c9e0()
{
    bind_static<guard_of_0135c9e0, pointer_of_0135c9e0, storage_of_0135c9e0>();
}

extern "C" void bb_frame_timing_static_guard_0135ca10()
{
    bind_static<guard_of_0135ca10, pointer_of_0135ca10, storage_of_0135ca10>();
}

extern "C" void bb_frame_timing_static_guard_0135cca0()
{
    bind_static<guard_of_0135cca0, pointer_of_0135cca0, storage_of_0135cca0>();
}

extern "C" void bb_frame_timing_static_guard_0135ccd0()
{
    bind_static<guard_of_0135ccd0, pointer_of_0135ccd0, storage_of_0135ccd0>();
}

extern "C" void bb_frame_timing_static_guard_0135cd00()
{
    bind_static<guard_of_0135cd00, pointer_of_0135cd00, storage_of_0135cd00>();
}

extern "C" void bb_frame_timing_static_guard_0135d370()
{
    bind_static<guard_of_0135d370, pointer_of_0135d370, storage_of_0135d370>();
}

extern "C" void bb_frame_timing_static_guard_0135d3a0()
{
    bind_static<guard_of_0135d3a0, pointer_of_0135d3a0, storage_of_0135d3a0>();
}

extern "C" void bb_frame_timing_static_guard_0135d3d0()
{
    bind_static<guard_of_0135d3d0, pointer_of_0135d3d0, storage_of_0135d3d0>();
}

extern "C" void bb_frame_timing_static_guard_0135e1a0()
{
    bind_static<guard_of_0135e1a0, pointer_of_0135e1a0, storage_of_0135e1a0>();
}

extern "C" void bb_frame_timing_static_guard_0135e1d0()
{
    bind_static<guard_of_0135e1d0, pointer_of_0135e1d0, storage_of_0135e1d0>();
}

extern "C" void bb_frame_timing_static_guard_0135e200()
{
    bind_static<guard_of_0135e200, pointer_of_0135e200, storage_of_0135e200>();
}

extern "C" void bb_frame_timing_static_guard_01364050()
{
    bind_static<guard_of_01364050, pointer_of_01364050, storage_of_01364050>();
}

extern "C" void bb_frame_timing_static_guard_01364080()
{
    bind_static<guard_of_01364080, pointer_of_01364080, storage_of_01364080>();
}

extern "C" void bb_frame_timing_static_guard_013640b0()
{
    bind_static<guard_of_013640b0, pointer_of_013640b0, storage_of_013640b0>();
}

extern "C" void bb_frame_timing_static_guard_013642c0()
{
    bind_static<guard_of_013642c0, pointer_of_013642c0, storage_of_013642c0>();
}

extern "C" void bb_frame_timing_static_guard_013642f0()
{
    bind_static<guard_of_013642f0, pointer_of_013642f0, storage_of_013642f0>();
}

extern "C" void bb_frame_timing_static_guard_01364320()
{
    bind_static<guard_of_01364320, pointer_of_01364320, storage_of_01364320>();
}

extern "C" void bb_frame_timing_static_guard_0136ad40()
{
    bind_static<guard_of_0136ad40, pointer_of_0136ad40, storage_of_0136ad40>();
}

extern "C" void bb_frame_timing_static_guard_0136ad70()
{
    bind_static<guard_of_0136ad70, pointer_of_0136ad70, storage_of_0136ad70>();
}

extern "C" void bb_frame_timing_static_guard_0136ada0()
{
    bind_static<guard_of_0136ada0, pointer_of_0136ada0, storage_of_0136ada0>();
}

extern "C" void bb_frame_timing_static_guard_0136af00()
{
    bind_static<guard_of_0136af00, pointer_of_0136af00, storage_of_0136af00>();
}

extern "C" void bb_frame_timing_static_guard_0136af30()
{
    bind_static<guard_of_0136af30, pointer_of_0136af30, storage_of_0136af30>();
}

extern "C" void bb_frame_timing_static_guard_0136af60()
{
    bind_static<guard_of_0136af60, pointer_of_0136af60, storage_of_0136af60>();
}

extern "C" void bb_frame_timing_static_guard_0136b2f0()
{
    bind_static<guard_of_0136b2f0, pointer_of_0136b2f0, storage_of_0136b2f0>();
}

extern "C" void bb_frame_timing_static_guard_0136b320()
{
    bind_static<guard_of_0136b320, pointer_of_0136b320, storage_of_0136b320>();
}

extern "C" void bb_frame_timing_static_guard_0136b350()
{
    bind_static<guard_of_0136b350, pointer_of_0136b350, storage_of_0136b350>();
}

extern "C" void bb_frame_timing_static_guard_0136ccb0()
{
    bind_static<guard_of_0136ccb0, pointer_of_0136ccb0, storage_of_0136ccb0>();
}

extern "C" void bb_frame_timing_static_guard_0136cce0()
{
    bind_static<guard_of_0136cce0, pointer_of_0136cce0, storage_of_0136cce0>();
}

extern "C" void bb_frame_timing_static_guard_0136cd10()
{
    bind_static<guard_of_0136cd10, pointer_of_0136cd10, storage_of_0136cd10>();
}

extern "C" void bb_frame_timing_static_guard_0136d550()
{
    bind_static<guard_of_0136d550, pointer_of_0136d550, storage_of_0136d550>();
}

extern "C" void bb_frame_timing_static_guard_0136d580()
{
    bind_static<guard_of_0136d580, pointer_of_0136d580, storage_of_0136d580>();
}

extern "C" void bb_frame_timing_static_guard_0136d5b0()
{
    bind_static<guard_of_0136d5b0, pointer_of_0136d5b0, storage_of_0136d5b0>();
}

extern "C" void bb_frame_timing_static_guard_0136de90()
{
    bind_static<guard_of_0136de90, pointer_of_0136de90, storage_of_0136de90>();
}

extern "C" void bb_frame_timing_static_guard_0136dec0()
{
    bind_static<guard_of_0136dec0, pointer_of_0136dec0, storage_of_0136dec0>();
}

extern "C" void bb_frame_timing_static_guard_0136def0()
{
    bind_static<guard_of_0136def0, pointer_of_0136def0, storage_of_0136def0>();
}

extern "C" void bb_frame_timing_static_guard_0136e0b0()
{
    bind_static<guard_of_0136e0b0, pointer_of_0136e0b0, storage_of_0136e0b0>();
}

extern "C" void bb_frame_timing_static_guard_0136e0e0()
{
    bind_static<guard_of_0136e0e0, pointer_of_0136e0e0, storage_of_0136e0e0>();
}

extern "C" void bb_frame_timing_static_guard_0136e110()
{
    bind_static<guard_of_0136e110, pointer_of_0136e110, storage_of_0136e110>();
}

extern "C" void bb_frame_timing_static_guard_0136e4e0()
{
    bind_static<guard_of_0136e4e0, pointer_of_0136e4e0, storage_of_0136e4e0>();
}

extern "C" void bb_frame_timing_static_guard_0136e510()
{
    bind_static<guard_of_0136e510, pointer_of_0136e510, storage_of_0136e510>();
}

extern "C" void bb_frame_timing_static_guard_0136e540()
{
    bind_static<guard_of_0136e540, pointer_of_0136e540, storage_of_0136e540>();
}

extern "C" void bb_frame_timing_static_guard_01370770()
{
    bind_static<guard_of_01370770, pointer_of_01370770, storage_of_01370770>();
}

extern "C" void bb_frame_timing_static_guard_013707a0()
{
    bind_static<guard_of_013707a0, pointer_of_013707a0, storage_of_013707a0>();
}

extern "C" void bb_frame_timing_static_guard_013707d0()
{
    bind_static<guard_of_013707d0, pointer_of_013707d0, storage_of_013707d0>();
}

extern "C" void bb_frame_timing_static_guard_01370920()
{
    bind_static<guard_of_01370920, pointer_of_01370920, storage_of_01370920>();
}

extern "C" void bb_frame_timing_static_guard_01370950()
{
    bind_static<guard_of_01370950, pointer_of_01370950, storage_of_01370950>();
}

extern "C" void bb_frame_timing_static_guard_01370980()
{
    bind_static<guard_of_01370980, pointer_of_01370980, storage_of_01370980>();
}

extern "C" void bb_frame_timing_static_guard_01370ea0()
{
    bind_static<guard_of_01370ea0, pointer_of_01370ea0, storage_of_01370ea0>();
}

extern "C" void bb_frame_timing_static_guard_01370ed0()
{
    bind_static<guard_of_01370ed0, pointer_of_01370ed0, storage_of_01370ed0>();
}

extern "C" void bb_frame_timing_static_guard_01370f00()
{
    bind_static<guard_of_01370f00, pointer_of_01370f00, storage_of_01370f00>();
}

extern "C" void bb_frame_timing_static_guard_013711b0()
{
    bind_static<guard_of_013711b0, pointer_of_013711b0, storage_of_013711b0>();
}

extern "C" void bb_frame_timing_static_guard_013711e0()
{
    bind_static<guard_of_013711e0, pointer_of_013711e0, storage_of_013711e0>();
}

extern "C" void bb_frame_timing_static_guard_01371210()
{
    bind_static<guard_of_01371210, pointer_of_01371210, storage_of_01371210>();
}

extern "C" void bb_frame_timing_static_guard_01371810()
{
    bind_static<guard_of_01371810, pointer_of_01371810, storage_of_01371810>();
}

extern "C" void bb_frame_timing_static_guard_01371840()
{
    bind_static<guard_of_01371840, pointer_of_01371840, storage_of_01371840>();
}

extern "C" void bb_frame_timing_static_guard_01371870()
{
    bind_static<guard_of_01371870, pointer_of_01371870, storage_of_01371870>();
}

extern "C" void bb_frame_timing_static_guard_01371b20()
{
    bind_static<guard_of_01371b20, pointer_of_01371b20, storage_of_01371b20>();
}

extern "C" void bb_frame_timing_static_guard_01371b50()
{
    bind_static<guard_of_01371b50, pointer_of_01371b50, storage_of_01371b50>();
}

extern "C" void bb_frame_timing_static_guard_01371b80()
{
    bind_static<guard_of_01371b80, pointer_of_01371b80, storage_of_01371b80>();
}

extern "C" void bb_frame_timing_static_guard_01372140()
{
    bind_static<guard_of_01372140, pointer_of_01372140, storage_of_01372140>();
}

extern "C" void bb_frame_timing_static_guard_01372170()
{
    bind_static<guard_of_01372170, pointer_of_01372170, storage_of_01372170>();
}

extern "C" void bb_frame_timing_static_guard_013721a0()
{
    bind_static<guard_of_013721a0, pointer_of_013721a0, storage_of_013721a0>();
}

extern "C" void bb_frame_timing_static_guard_01372400()
{
    bind_static<guard_of_01372400, pointer_of_01372400, storage_of_01372400>();
}

extern "C" void bb_frame_timing_static_guard_01372430()
{
    bind_static<guard_of_01372430, pointer_of_01372430, storage_of_01372430>();
}

extern "C" void bb_frame_timing_static_guard_01372460()
{
    bind_static<guard_of_01372460, pointer_of_01372460, storage_of_01372460>();
}

extern "C" void bb_frame_timing_static_guard_01372620()
{
    bind_static<guard_of_01372620, pointer_of_01372620, storage_of_01372620>();
}

extern "C" void bb_frame_timing_static_guard_01372650()
{
    bind_static<guard_of_01372650, pointer_of_01372650, storage_of_01372650>();
}

extern "C" void bb_frame_timing_static_guard_01372680()
{
    bind_static<guard_of_01372680, pointer_of_01372680, storage_of_01372680>();
}

extern "C" void bb_frame_timing_static_guard_01372fd0()
{
    bind_static<guard_of_01372fd0, pointer_of_01372fd0, storage_of_01372fd0>();
}

extern "C" void bb_frame_timing_static_guard_01373000()
{
    bind_static<guard_of_01373000, pointer_of_01373000, storage_of_01373000>();
}

extern "C" void bb_frame_timing_static_guard_01373030()
{
    bind_static<guard_of_01373030, pointer_of_01373030, storage_of_01373030>();
}

extern "C" void bb_frame_timing_static_guard_01373d60()
{
    bind_static<guard_of_01373d60, pointer_of_01373d60, storage_of_01373d60>();
}

extern "C" void bb_frame_timing_static_guard_01373d90()
{
    bind_static<guard_of_01373d90, pointer_of_01373d90, storage_of_01373d90>();
}

extern "C" void bb_frame_timing_static_guard_01373dc0()
{
    bind_static<guard_of_01373dc0, pointer_of_01373dc0, storage_of_01373dc0>();
}

extern "C" void bb_frame_timing_static_guard_01373f60()
{
    bind_static<guard_of_01373f60, pointer_of_01373f60, storage_of_01373f60>();
}

extern "C" void bb_frame_timing_static_guard_01373f90()
{
    bind_static<guard_of_01373f90, pointer_of_01373f90, storage_of_01373f90>();
}

extern "C" void bb_frame_timing_static_guard_01373fc0()
{
    bind_static<guard_of_01373fc0, pointer_of_01373fc0, storage_of_01373fc0>();
}

extern "C" void bb_frame_timing_static_guard_01374a80()
{
    bind_static<guard_of_01374a80, pointer_of_01374a80, storage_of_01374a80>();
}

extern "C" void bb_frame_timing_static_guard_01374ab0()
{
    bind_static<guard_of_01374ab0, pointer_of_01374ab0, storage_of_01374ab0>();
}

extern "C" void bb_frame_timing_static_guard_01374ae0()
{
    bind_static<guard_of_01374ae0, pointer_of_01374ae0, storage_of_01374ae0>();
}

extern "C" void bb_frame_timing_static_guard_013784a0()
{
    bind_static<guard_of_013784a0, pointer_of_013784a0, storage_of_013784a0>();
}

extern "C" void bb_frame_timing_static_guard_013784d0()
{
    bind_static<guard_of_013784d0, pointer_of_013784d0, storage_of_013784d0>();
}

extern "C" void bb_frame_timing_static_guard_01378500()
{
    bind_static<guard_of_01378500, pointer_of_01378500, storage_of_01378500>();
}

extern "C" void bb_frame_timing_static_guard_0137a460()
{
    bind_static<guard_of_0137a460, pointer_of_0137a460, storage_of_0137a460>();
}

extern "C" void bb_frame_timing_static_guard_0137a490()
{
    bind_static<guard_of_0137a490, pointer_of_0137a490, storage_of_0137a490>();
}

extern "C" void bb_frame_timing_static_guard_0137a4c0()
{
    bind_static<guard_of_0137a4c0, pointer_of_0137a4c0, storage_of_0137a4c0>();
}

extern "C" void bb_frame_timing_static_guard_0137ac00()
{
    bind_static<guard_of_0137ac00, pointer_of_0137ac00, storage_of_0137ac00>();
}

extern "C" void bb_frame_timing_static_guard_0137ac30()
{
    bind_static<guard_of_0137ac30, pointer_of_0137ac30, storage_of_0137ac30>();
}

extern "C" void bb_frame_timing_static_guard_0137ac60()
{
    bind_static<guard_of_0137ac60, pointer_of_0137ac60, storage_of_0137ac60>();
}

extern "C" void bb_frame_timing_static_guard_0137af50()
{
    bind_static<guard_of_0137af50, pointer_of_0137af50, storage_of_0137af50>();
}

extern "C" void bb_frame_timing_static_guard_0137af80()
{
    bind_static<guard_of_0137af80, pointer_of_0137af80, storage_of_0137af80>();
}

extern "C" void bb_frame_timing_static_guard_0137afb0()
{
    bind_static<guard_of_0137afb0, pointer_of_0137afb0, storage_of_0137afb0>();
}

extern "C" void bb_frame_timing_static_guard_0137b490()
{
    bind_static<guard_of_0137b490, pointer_of_0137b490, storage_of_0137b490>();
}

extern "C" void bb_frame_timing_static_guard_0137b4c0()
{
    bind_static<guard_of_0137b4c0, pointer_of_0137b4c0, storage_of_0137b4c0>();
}

extern "C" void bb_frame_timing_static_guard_0137b4f0()
{
    bind_static<guard_of_0137b4f0, pointer_of_0137b4f0, storage_of_0137b4f0>();
}

extern "C" void bb_frame_timing_static_guard_0137b7e0()
{
    bind_static<guard_of_0137b7e0, pointer_of_0137b7e0, storage_of_0137b7e0>();
}

extern "C" void bb_frame_timing_static_guard_0137b810()
{
    bind_static<guard_of_0137b810, pointer_of_0137b810, storage_of_0137b810>();
}

extern "C" void bb_frame_timing_static_guard_0137b840()
{
    bind_static<guard_of_0137b840, pointer_of_0137b840, storage_of_0137b840>();
}

extern "C" void bb_frame_timing_static_guard_0137d670()
{
    bind_static<guard_of_0137d670, pointer_of_0137d670, storage_of_0137d670>();
}

extern "C" void bb_frame_timing_static_guard_0137d6a0()
{
    bind_static<guard_of_0137d6a0, pointer_of_0137d6a0, storage_of_0137d6a0>();
}

extern "C" void bb_frame_timing_static_guard_0137d6d0()
{
    bind_static<guard_of_0137d6d0, pointer_of_0137d6d0, storage_of_0137d6d0>();
}

extern "C" void bb_frame_timing_static_guard_0137d930()
{
    bind_static<guard_of_0137d930, pointer_of_0137d930, storage_of_0137d930>();
}

extern "C" void bb_frame_timing_static_guard_0137d960()
{
    bind_static<guard_of_0137d960, pointer_of_0137d960, storage_of_0137d960>();
}

extern "C" void bb_frame_timing_static_guard_0137d990()
{
    bind_static<guard_of_0137d990, pointer_of_0137d990, storage_of_0137d990>();
}

extern "C" void bb_frame_timing_static_guard_0137df20()
{
    bind_static<guard_of_0137df20, pointer_of_0137df20, storage_of_0137df20>();
}

extern "C" void bb_frame_timing_static_guard_0137df50()
{
    bind_static<guard_of_0137df50, pointer_of_0137df50, storage_of_0137df50>();
}

extern "C" void bb_frame_timing_static_guard_0137df80()
{
    bind_static<guard_of_0137df80, pointer_of_0137df80, storage_of_0137df80>();
}

extern "C" void bb_frame_timing_static_guard_0137e2b0()
{
    bind_static<guard_of_0137e2b0, pointer_of_0137e2b0, storage_of_0137e2b0>();
}

extern "C" void bb_frame_timing_static_guard_0137e2e0()
{
    bind_static<guard_of_0137e2e0, pointer_of_0137e2e0, storage_of_0137e2e0>();
}

extern "C" void bb_frame_timing_static_guard_0137e310()
{
    bind_static<guard_of_0137e310, pointer_of_0137e310, storage_of_0137e310>();
}

extern "C" void bb_frame_timing_static_guard_0137e5c0()
{
    bind_static<guard_of_0137e5c0, pointer_of_0137e5c0, storage_of_0137e5c0>();
}

extern "C" void bb_frame_timing_static_guard_0137e5f0()
{
    bind_static<guard_of_0137e5f0, pointer_of_0137e5f0, storage_of_0137e5f0>();
}

extern "C" void bb_frame_timing_static_guard_0137e620()
{
    bind_static<guard_of_0137e620, pointer_of_0137e620, storage_of_0137e620>();
}

extern "C" void bb_frame_timing_static_guard_0137e7e0()
{
    bind_static<guard_of_0137e7e0, pointer_of_0137e7e0, storage_of_0137e7e0>();
}

extern "C" void bb_frame_timing_static_guard_0137e810()
{
    bind_static<guard_of_0137e810, pointer_of_0137e810, storage_of_0137e810>();
}

extern "C" void bb_frame_timing_static_guard_0137e840()
{
    bind_static<guard_of_0137e840, pointer_of_0137e840, storage_of_0137e840>();
}

extern "C" void bb_frame_timing_static_guard_0137ea10()
{
    bind_static<guard_of_0137ea10, pointer_of_0137ea10, storage_of_0137ea10>();
}

extern "C" void bb_frame_timing_static_guard_0137ea40()
{
    bind_static<guard_of_0137ea40, pointer_of_0137ea40, storage_of_0137ea40>();
}

extern "C" void bb_frame_timing_static_guard_0137ea70()
{
    bind_static<guard_of_0137ea70, pointer_of_0137ea70, storage_of_0137ea70>();
}

extern "C" void bb_frame_timing_static_guard_0137ec90()
{
    bind_static<guard_of_0137ec90, pointer_of_0137ec90, storage_of_0137ec90>();
}

extern "C" void bb_frame_timing_static_guard_0137ecc0()
{
    bind_static<guard_of_0137ecc0, pointer_of_0137ecc0, storage_of_0137ecc0>();
}

extern "C" void bb_frame_timing_static_guard_0137ecf0()
{
    bind_static<guard_of_0137ecf0, pointer_of_0137ecf0, storage_of_0137ecf0>();
}

extern "C" void bb_frame_timing_static_guard_0137f270()
{
    bind_static<guard_of_0137f270, pointer_of_0137f270, storage_of_0137f270>();
}

extern "C" void bb_frame_timing_static_guard_0137f2a0()
{
    bind_static<guard_of_0137f2a0, pointer_of_0137f2a0, storage_of_0137f2a0>();
}

extern "C" void bb_frame_timing_static_guard_0137f2d0()
{
    bind_static<guard_of_0137f2d0, pointer_of_0137f2d0, storage_of_0137f2d0>();
}

extern "C" void bb_frame_timing_static_guard_0137f5e0()
{
    bind_static<guard_of_0137f5e0, pointer_of_0137f5e0, storage_of_0137f5e0>();
}

extern "C" void bb_frame_timing_static_guard_0137f610()
{
    bind_static<guard_of_0137f610, pointer_of_0137f610, storage_of_0137f610>();
}

extern "C" void bb_frame_timing_static_guard_0137f640()
{
    bind_static<guard_of_0137f640, pointer_of_0137f640, storage_of_0137f640>();
}

extern "C" void bb_frame_timing_static_guard_01382360()
{
    bind_static<guard_of_01382360, pointer_of_01382360, storage_of_01382360>();
}

extern "C" void bb_frame_timing_static_guard_01382390()
{
    bind_static<guard_of_01382390, pointer_of_01382390, storage_of_01382390>();
}

extern "C" void bb_frame_timing_static_guard_013823c0()
{
    bind_static<guard_of_013823c0, pointer_of_013823c0, storage_of_013823c0>();
}

extern "C" void bb_frame_timing_static_guard_013828c0()
{
    bind_static<guard_of_013828c0, pointer_of_013828c0, storage_of_013828c0>();
}

extern "C" void bb_frame_timing_static_guard_013828f0()
{
    bind_static<guard_of_013828f0, pointer_of_013828f0, storage_of_013828f0>();
}

extern "C" void bb_frame_timing_static_guard_01382920()
{
    bind_static<guard_of_01382920, pointer_of_01382920, storage_of_01382920>();
}

extern "C" void bb_frame_timing_static_guard_01382c40()
{
    bind_static<guard_of_01382c40, pointer_of_01382c40, storage_of_01382c40>();
}

extern "C" void bb_frame_timing_static_guard_01382c70()
{
    bind_static<guard_of_01382c70, pointer_of_01382c70, storage_of_01382c70>();
}

extern "C" void bb_frame_timing_static_guard_01382ca0()
{
    bind_static<guard_of_01382ca0, pointer_of_01382ca0, storage_of_01382ca0>();
}

extern "C" void bb_frame_timing_static_guard_01382f50()
{
    bind_static<guard_of_01382f50, pointer_of_01382f50, storage_of_01382f50>();
}

extern "C" void bb_frame_timing_static_guard_01382f80()
{
    bind_static<guard_of_01382f80, pointer_of_01382f80, storage_of_01382f80>();
}

extern "C" void bb_frame_timing_static_guard_01382fb0()
{
    bind_static<guard_of_01382fb0, pointer_of_01382fb0, storage_of_01382fb0>();
}

extern "C" void bb_frame_timing_static_guard_01383300()
{
    bind_static<guard_of_01383300, pointer_of_01383300, storage_of_01383300>();
}

extern "C" void bb_frame_timing_static_guard_01383330()
{
    bind_static<guard_of_01383330, pointer_of_01383330, storage_of_01383330>();
}

extern "C" void bb_frame_timing_static_guard_01383360()
{
    bind_static<guard_of_01383360, pointer_of_01383360, storage_of_01383360>();
}

extern "C" void bb_frame_timing_static_guard_01383610()
{
    bind_static<guard_of_01383610, pointer_of_01383610, storage_of_01383610>();
}

extern "C" void bb_frame_timing_static_guard_01383640()
{
    bind_static<guard_of_01383640, pointer_of_01383640, storage_of_01383640>();
}

extern "C" void bb_frame_timing_static_guard_01383670()
{
    bind_static<guard_of_01383670, pointer_of_01383670, storage_of_01383670>();
}

extern "C" void bb_frame_timing_static_guard_01383920()
{
    bind_static<guard_of_01383920, pointer_of_01383920, storage_of_01383920>();
}

extern "C" void bb_frame_timing_static_guard_01383950()
{
    bind_static<guard_of_01383950, pointer_of_01383950, storage_of_01383950>();
}

extern "C" void bb_frame_timing_static_guard_01383980()
{
    bind_static<guard_of_01383980, pointer_of_01383980, storage_of_01383980>();
}

extern "C" void bb_frame_timing_static_guard_01383e10()
{
    bind_static<guard_of_01383e10, pointer_of_01383e10, storage_of_01383e10>();
}

extern "C" void bb_frame_timing_static_guard_01383e40()
{
    bind_static<guard_of_01383e40, pointer_of_01383e40, storage_of_01383e40>();
}

extern "C" void bb_frame_timing_static_guard_01383e70()
{
    bind_static<guard_of_01383e70, pointer_of_01383e70, storage_of_01383e70>();
}

extern "C" void bb_frame_timing_static_guard_01384100()
{
    bind_static<guard_of_01384100, pointer_of_01384100, storage_of_01384100>();
}

extern "C" void bb_frame_timing_static_guard_01384130()
{
    bind_static<guard_of_01384130, pointer_of_01384130, storage_of_01384130>();
}

extern "C" void bb_frame_timing_static_guard_01384160()
{
    bind_static<guard_of_01384160, pointer_of_01384160, storage_of_01384160>();
}

extern "C" void bb_frame_timing_static_guard_013843f0()
{
    bind_static<guard_of_013843f0, pointer_of_013843f0, storage_of_013843f0>();
}

extern "C" void bb_frame_timing_static_guard_01384420()
{
    bind_static<guard_of_01384420, pointer_of_01384420, storage_of_01384420>();
}

extern "C" void bb_frame_timing_static_guard_01384450()
{
    bind_static<guard_of_01384450, pointer_of_01384450, storage_of_01384450>();
}

extern "C" void bb_frame_timing_static_guard_01384760()
{
    bind_static<guard_of_01384760, pointer_of_01384760, storage_of_01384760>();
}

extern "C" void bb_frame_timing_static_guard_01384790()
{
    bind_static<guard_of_01384790, pointer_of_01384790, storage_of_01384790>();
}

extern "C" void bb_frame_timing_static_guard_013847c0()
{
    bind_static<guard_of_013847c0, pointer_of_013847c0, storage_of_013847c0>();
}

extern "C" void bb_frame_timing_static_guard_01384a70()
{
    bind_static<guard_of_01384a70, pointer_of_01384a70, storage_of_01384a70>();
}

extern "C" void bb_frame_timing_static_guard_01384aa0()
{
    bind_static<guard_of_01384aa0, pointer_of_01384aa0, storage_of_01384aa0>();
}

extern "C" void bb_frame_timing_static_guard_01384ad0()
{
    bind_static<guard_of_01384ad0, pointer_of_01384ad0, storage_of_01384ad0>();
}

extern "C" void bb_frame_timing_static_guard_01384f10()
{
    bind_static<guard_of_01384f10, pointer_of_01384f10, storage_of_01384f10>();
}

extern "C" void bb_frame_timing_static_guard_01384f40()
{
    bind_static<guard_of_01384f40, pointer_of_01384f40, storage_of_01384f40>();
}

extern "C" void bb_frame_timing_static_guard_01384f70()
{
    bind_static<guard_of_01384f70, pointer_of_01384f70, storage_of_01384f70>();
}

extern "C" void bb_frame_timing_static_guard_013852b0()
{
    bind_static<guard_of_013852b0, pointer_of_013852b0, storage_of_013852b0>();
}

extern "C" void bb_frame_timing_static_guard_013852e0()
{
    bind_static<guard_of_013852e0, pointer_of_013852e0, storage_of_013852e0>();
}

extern "C" void bb_frame_timing_static_guard_01385310()
{
    bind_static<guard_of_01385310, pointer_of_01385310, storage_of_01385310>();
}

extern "C" void bb_frame_timing_static_guard_01385610()
{
    bind_static<guard_of_01385610, pointer_of_01385610, storage_of_01385610>();
}

extern "C" void bb_frame_timing_static_guard_01385640()
{
    bind_static<guard_of_01385640, pointer_of_01385640, storage_of_01385640>();
}

extern "C" void bb_frame_timing_static_guard_01385670()
{
    bind_static<guard_of_01385670, pointer_of_01385670, storage_of_01385670>();
}

extern "C" void bb_frame_timing_static_guard_01385980()
{
    bind_static<guard_of_01385980, pointer_of_01385980, storage_of_01385980>();
}

extern "C" void bb_frame_timing_static_guard_013859b0()
{
    bind_static<guard_of_013859b0, pointer_of_013859b0, storage_of_013859b0>();
}

extern "C" void bb_frame_timing_static_guard_013859e0()
{
    bind_static<guard_of_013859e0, pointer_of_013859e0, storage_of_013859e0>();
}

extern "C" void bb_frame_timing_static_guard_01385c90()
{
    bind_static<guard_of_01385c90, pointer_of_01385c90, storage_of_01385c90>();
}

extern "C" void bb_frame_timing_static_guard_01385cc0()
{
    bind_static<guard_of_01385cc0, pointer_of_01385cc0, storage_of_01385cc0>();
}

extern "C" void bb_frame_timing_static_guard_01385cf0()
{
    bind_static<guard_of_01385cf0, pointer_of_01385cf0, storage_of_01385cf0>();
}

extern "C" void bb_frame_timing_static_guard_01386180()
{
    bind_static<guard_of_01386180, pointer_of_01386180, storage_of_01386180>();
}

extern "C" void bb_frame_timing_static_guard_013861b0()
{
    bind_static<guard_of_013861b0, pointer_of_013861b0, storage_of_013861b0>();
}

extern "C" void bb_frame_timing_static_guard_013861e0()
{
    bind_static<guard_of_013861e0, pointer_of_013861e0, storage_of_013861e0>();
}

extern "C" void bb_frame_timing_static_guard_013864e0()
{
    bind_static<guard_of_013864e0, pointer_of_013864e0, storage_of_013864e0>();
}

extern "C" void bb_frame_timing_static_guard_01386510()
{
    bind_static<guard_of_01386510, pointer_of_01386510, storage_of_01386510>();
}

extern "C" void bb_frame_timing_static_guard_01386540()
{
    bind_static<guard_of_01386540, pointer_of_01386540, storage_of_01386540>();
}

extern "C" void bb_frame_timing_static_guard_01386610()
{
    bind_static<guard_of_01386610, pointer_of_01386610, storage_of_01386610>();
}

extern "C" void bb_frame_timing_static_guard_01386640()
{
    bind_static<guard_of_01386640, pointer_of_01386640, storage_of_01386640>();
}

extern "C" void bb_frame_timing_static_guard_01386670()
{
    bind_static<guard_of_01386670, pointer_of_01386670, storage_of_01386670>();
}

extern "C" void bb_frame_timing_static_guard_01386740()
{
    bind_static<guard_of_01386740, pointer_of_01386740, storage_of_01386740>();
}

extern "C" void bb_frame_timing_static_guard_01386770()
{
    bind_static<guard_of_01386770, pointer_of_01386770, storage_of_01386770>();
}

extern "C" void bb_frame_timing_static_guard_013867a0()
{
    bind_static<guard_of_013867a0, pointer_of_013867a0, storage_of_013867a0>();
}

extern "C" void bb_frame_timing_static_guard_01386860()
{
    bind_static<guard_of_01386860, pointer_of_01386860, storage_of_01386860>();
}

extern "C" void bb_frame_timing_static_guard_01386890()
{
    bind_static<guard_of_01386890, pointer_of_01386890, storage_of_01386890>();
}

extern "C" void bb_frame_timing_static_guard_013868c0()
{
    bind_static<guard_of_013868c0, pointer_of_013868c0, storage_of_013868c0>();
}

extern "C" void bb_frame_timing_static_guard_01387410()
{
    bind_static<guard_of_01387410, pointer_of_01387410, storage_of_01387410>();
}

extern "C" void bb_frame_timing_static_guard_01387440()
{
    bind_static<guard_of_01387440, pointer_of_01387440, storage_of_01387440>();
}

extern "C" void bb_frame_timing_static_guard_01387470()
{
    bind_static<guard_of_01387470, pointer_of_01387470, storage_of_01387470>();
}

extern "C" void bb_frame_timing_static_guard_013884a0()
{
    bind_static<guard_of_013884a0, pointer_of_013884a0, storage_of_013884a0>();
}

extern "C" void bb_frame_timing_static_guard_013884d0()
{
    bind_static<guard_of_013884d0, pointer_of_013884d0, storage_of_013884d0>();
}

extern "C" void bb_frame_timing_static_guard_01388500()
{
    bind_static<guard_of_01388500, pointer_of_01388500, storage_of_01388500>();
}

extern "C" void bb_frame_timing_static_guard_01389560()
{
    bind_static<guard_of_01389560, pointer_of_01389560, storage_of_01389560>();
}

extern "C" void bb_frame_timing_static_guard_01389590()
{
    bind_static<guard_of_01389590, pointer_of_01389590, storage_of_01389590>();
}

extern "C" void bb_frame_timing_static_guard_013895c0()
{
    bind_static<guard_of_013895c0, pointer_of_013895c0, storage_of_013895c0>();
}

extern "C" void bb_frame_timing_static_guard_01389750()
{
    bind_static<guard_of_01389750, pointer_of_01389750, storage_of_01389750>();
}

extern "C" void bb_frame_timing_static_guard_01389780()
{
    bind_static<guard_of_01389780, pointer_of_01389780, storage_of_01389780>();
}

extern "C" void bb_frame_timing_static_guard_013897b0()
{
    bind_static<guard_of_013897b0, pointer_of_013897b0, storage_of_013897b0>();
}

extern "C" void bb_frame_timing_static_guard_01389ed0()
{
    bind_static<guard_of_01389ed0, pointer_of_01389ed0, storage_of_01389ed0>();
}

extern "C" void bb_frame_timing_static_guard_01389f00()
{
    bind_static<guard_of_01389f00, pointer_of_01389f00, storage_of_01389f00>();
}

extern "C" void bb_frame_timing_static_guard_01389f30()
{
    bind_static<guard_of_01389f30, pointer_of_01389f30, storage_of_01389f30>();
}

extern "C" void bb_frame_timing_static_guard_0138a5c0()
{
    bind_static<guard_of_0138a5c0, pointer_of_0138a5c0, storage_of_0138a5c0>();
}

extern "C" void bb_frame_timing_static_guard_0138a5f0()
{
    bind_static<guard_of_0138a5f0, pointer_of_0138a5f0, storage_of_0138a5f0>();
}

extern "C" void bb_frame_timing_static_guard_0138a620()
{
    bind_static<guard_of_0138a620, pointer_of_0138a620, storage_of_0138a620>();
}

extern "C" void bb_frame_timing_static_guard_0138a9e0()
{
    bind_static<guard_of_0138a9e0, pointer_of_0138a9e0, storage_of_0138a9e0>();
}

extern "C" void bb_frame_timing_static_guard_0138aa10()
{
    bind_static<guard_of_0138aa10, pointer_of_0138aa10, storage_of_0138aa10>();
}

extern "C" void bb_frame_timing_static_guard_0138aa40()
{
    bind_static<guard_of_0138aa40, pointer_of_0138aa40, storage_of_0138aa40>();
}

extern "C" void bb_frame_timing_static_guard_0138acf0()
{
    bind_static<guard_of_0138acf0, pointer_of_0138acf0, storage_of_0138acf0>();
}

extern "C" void bb_frame_timing_static_guard_0138ad20()
{
    bind_static<guard_of_0138ad20, pointer_of_0138ad20, storage_of_0138ad20>();
}

extern "C" void bb_frame_timing_static_guard_0138ad50()
{
    bind_static<guard_of_0138ad50, pointer_of_0138ad50, storage_of_0138ad50>();
}

extern "C" void bb_frame_timing_static_guard_0138bf20()
{
    bind_static<guard_of_0138bf20, pointer_of_0138bf20, storage_of_0138bf20>();
}

extern "C" void bb_frame_timing_static_guard_0138bf50()
{
    bind_static<guard_of_0138bf50, pointer_of_0138bf50, storage_of_0138bf50>();
}

extern "C" void bb_frame_timing_static_guard_0138bf80()
{
    bind_static<guard_of_0138bf80, pointer_of_0138bf80, storage_of_0138bf80>();
}

extern "C" void bb_frame_timing_static_guard_0138bff0()
{
    bind_static<guard_of_0138bff0, pointer_of_0138bff0, storage_of_0138bff0>();
}

extern "C" void bb_frame_timing_static_guard_0138c020()
{
    bind_static<guard_of_0138c020, pointer_of_0138c020, storage_of_0138c020>();
}

extern "C" void bb_frame_timing_static_guard_0138c050()
{
    bind_static<guard_of_0138c050, pointer_of_0138c050, storage_of_0138c050>();
}

extern "C" void bb_frame_timing_static_guard_0138c770()
{
    bind_static<guard_of_0138c770, pointer_of_0138c770, storage_of_0138c770>();
}

extern "C" void bb_frame_timing_static_guard_0138c7a0()
{
    bind_static<guard_of_0138c7a0, pointer_of_0138c7a0, storage_of_0138c7a0>();
}

extern "C" void bb_frame_timing_static_guard_0138c7d0()
{
    bind_static<guard_of_0138c7d0, pointer_of_0138c7d0, storage_of_0138c7d0>();
}

extern "C" void bb_frame_timing_static_guard_0138ca20()
{
    bind_static<guard_of_0138ca20, pointer_of_0138ca20, storage_of_0138ca20>();
}

extern "C" void bb_frame_timing_static_guard_0138ca50()
{
    bind_static<guard_of_0138ca50, pointer_of_0138ca50, storage_of_0138ca50>();
}

extern "C" void bb_frame_timing_static_guard_0138ca80()
{
    bind_static<guard_of_0138ca80, pointer_of_0138ca80, storage_of_0138ca80>();
}

extern "C" void bb_frame_timing_static_guard_01391300()
{
    bind_static<guard_of_01391300, pointer_of_01391300, storage_of_01391300>();
}

extern "C" void bb_frame_timing_static_guard_01391330()
{
    bind_static<guard_of_01391330, pointer_of_01391330, storage_of_01391330>();
}

extern "C" void bb_frame_timing_static_guard_01391360()
{
    bind_static<guard_of_01391360, pointer_of_01391360, storage_of_01391360>();
}

extern "C" void bb_frame_timing_static_guard_01393740()
{
    bind_static<guard_of_01393740, pointer_of_01393740, storage_of_01393740>();
}

extern "C" void bb_frame_timing_static_guard_01393770()
{
    bind_static<guard_of_01393770, pointer_of_01393770, storage_of_01393770>();
}

extern "C" void bb_frame_timing_static_guard_013937a0()
{
    bind_static<guard_of_013937a0, pointer_of_013937a0, storage_of_013937a0>();
}

extern "C" void bb_frame_timing_static_guard_01395780()
{
    bind_static<guard_of_01395780, pointer_of_01395780, storage_of_01395780>();
}

extern "C" void bb_frame_timing_static_guard_013957b0()
{
    bind_static<guard_of_013957b0, pointer_of_013957b0, storage_of_013957b0>();
}

extern "C" void bb_frame_timing_static_guard_013957e0()
{
    bind_static<guard_of_013957e0, pointer_of_013957e0, storage_of_013957e0>();
}

extern "C" void bb_frame_timing_static_guard_01395960()
{
    bind_static<guard_of_01395960, pointer_of_01395960, storage_of_01395960>();
}

extern "C" void bb_frame_timing_static_guard_01395990()
{
    bind_static<guard_of_01395990, pointer_of_01395990, storage_of_01395990>();
}

extern "C" void bb_frame_timing_static_guard_013959c0()
{
    bind_static<guard_of_013959c0, pointer_of_013959c0, storage_of_013959c0>();
}

extern "C" void bb_frame_timing_static_guard_01396090()
{
    bind_static<guard_of_01396090, pointer_of_01396090, storage_of_01396090>();
}

extern "C" void bb_frame_timing_static_guard_013960c0()
{
    bind_static<guard_of_013960c0, pointer_of_013960c0, storage_of_013960c0>();
}

extern "C" void bb_frame_timing_static_guard_013960f0()
{
    bind_static<guard_of_013960f0, pointer_of_013960f0, storage_of_013960f0>();
}

extern "C" void bb_frame_timing_static_guard_013984b0()
{
    bind_static<guard_of_013984b0, pointer_of_013984b0, storage_of_013984b0>();
}

extern "C" void bb_frame_timing_static_guard_013984e0()
{
    bind_static<guard_of_013984e0, pointer_of_013984e0, storage_of_013984e0>();
}

extern "C" void bb_frame_timing_static_guard_01398510()
{
    bind_static<guard_of_01398510, pointer_of_01398510, storage_of_01398510>();
}

extern "C" void bb_frame_timing_static_guard_013988d0()
{
    bind_static<guard_of_013988d0, pointer_of_013988d0, storage_of_013988d0>();
}

extern "C" void bb_frame_timing_static_guard_01398900()
{
    bind_static<guard_of_01398900, pointer_of_01398900, storage_of_01398900>();
}

extern "C" void bb_frame_timing_static_guard_01398930()
{
    bind_static<guard_of_01398930, pointer_of_01398930, storage_of_01398930>();
}

extern "C" void bb_frame_timing_static_guard_01399550()
{
    bind_static<guard_of_01399550, pointer_of_01399550, storage_of_01399550>();
}

extern "C" void bb_frame_timing_static_guard_01399580()
{
    bind_static<guard_of_01399580, pointer_of_01399580, storage_of_01399580>();
}

extern "C" void bb_frame_timing_static_guard_013995b0()
{
    bind_static<guard_of_013995b0, pointer_of_013995b0, storage_of_013995b0>();
}

extern "C" void bb_frame_timing_static_guard_01399fa0()
{
    bind_static<guard_of_01399fa0, pointer_of_01399fa0, storage_of_01399fa0>();
}

extern "C" void bb_frame_timing_static_guard_01399fd0()
{
    bind_static<guard_of_01399fd0, pointer_of_01399fd0, storage_of_01399fd0>();
}

extern "C" void bb_frame_timing_static_guard_0139a000()
{
    bind_static<guard_of_0139a000, pointer_of_0139a000, storage_of_0139a000>();
}

extern "C" void bb_frame_timing_static_guard_0139ae00()
{
    bind_static<guard_of_0139ae00, pointer_of_0139ae00, storage_of_0139ae00>();
}

extern "C" void bb_frame_timing_static_guard_0139ae30()
{
    bind_static<guard_of_0139ae30, pointer_of_0139ae30, storage_of_0139ae30>();
}

extern "C" void bb_frame_timing_static_guard_0139ae60()
{
    bind_static<guard_of_0139ae60, pointer_of_0139ae60, storage_of_0139ae60>();
}

extern "C" void bb_frame_timing_static_guard_0139b410()
{
    bind_static<guard_of_0139b410, pointer_of_0139b410, storage_of_0139b410>();
}

extern "C" void bb_frame_timing_static_guard_0139b440()
{
    bind_static<guard_of_0139b440, pointer_of_0139b440, storage_of_0139b440>();
}

extern "C" void bb_frame_timing_static_guard_0139b470()
{
    bind_static<guard_of_0139b470, pointer_of_0139b470, storage_of_0139b470>();
}

extern "C" void bb_frame_timing_static_guard_0139b500()
{
    bind_static<guard_of_0139b500, pointer_of_0139b500, storage_of_0139b500>();
}

extern "C" void bb_frame_timing_static_guard_0139b530()
{
    bind_static<guard_of_0139b530, pointer_of_0139b530, storage_of_0139b530>();
}

extern "C" void bb_frame_timing_static_guard_0139b560()
{
    bind_static<guard_of_0139b560, pointer_of_0139b560, storage_of_0139b560>();
}

extern "C" void bb_frame_timing_static_guard_0139bce0()
{
    bind_static<guard_of_0139bce0, pointer_of_0139bce0, storage_of_0139bce0>();
}

extern "C" void bb_frame_timing_static_guard_0139bd10()
{
    bind_static<guard_of_0139bd10, pointer_of_0139bd10, storage_of_0139bd10>();
}

extern "C" void bb_frame_timing_static_guard_0139bd40()
{
    bind_static<guard_of_0139bd40, pointer_of_0139bd40, storage_of_0139bd40>();
}

extern "C" void bb_frame_timing_static_guard_0139c0d0()
{
    bind_static<guard_of_0139c0d0, pointer_of_0139c0d0, storage_of_0139c0d0>();
}

extern "C" void bb_frame_timing_static_guard_0139c100()
{
    bind_static<guard_of_0139c100, pointer_of_0139c100, storage_of_0139c100>();
}

extern "C" void bb_frame_timing_static_guard_0139c130()
{
    bind_static<guard_of_0139c130, pointer_of_0139c130, storage_of_0139c130>();
}

extern "C" void bb_frame_timing_static_guard_0139c310()
{
    bind_static<guard_of_0139c310, pointer_of_0139c310, storage_of_0139c310>();
}

extern "C" void bb_frame_timing_static_guard_0139c340()
{
    bind_static<guard_of_0139c340, pointer_of_0139c340, storage_of_0139c340>();
}

extern "C" void bb_frame_timing_static_guard_0139c370()
{
    bind_static<guard_of_0139c370, pointer_of_0139c370, storage_of_0139c370>();
}

extern "C" void bb_frame_timing_static_guard_0139c620()
{
    bind_static<guard_of_0139c620, pointer_of_0139c620, storage_of_0139c620>();
}

extern "C" void bb_frame_timing_static_guard_0139c650()
{
    bind_static<guard_of_0139c650, pointer_of_0139c650, storage_of_0139c650>();
}

extern "C" void bb_frame_timing_static_guard_0139c680()
{
    bind_static<guard_of_0139c680, pointer_of_0139c680, storage_of_0139c680>();
}

extern "C" void bb_frame_timing_static_guard_0139c770()
{
    bind_static<guard_of_0139c770, pointer_of_0139c770, storage_of_0139c770>();
}

extern "C" void bb_frame_timing_static_guard_0139c7a0()
{
    bind_static<guard_of_0139c7a0, pointer_of_0139c7a0, storage_of_0139c7a0>();
}

extern "C" void bb_frame_timing_static_guard_0139c7d0()
{
    bind_static<guard_of_0139c7d0, pointer_of_0139c7d0, storage_of_0139c7d0>();
}

extern "C" void bb_frame_timing_static_guard_0139cba0()
{
    bind_static<guard_of_0139cba0, pointer_of_0139cba0, storage_of_0139cba0>();
}

extern "C" void bb_frame_timing_static_guard_0139cbd0()
{
    bind_static<guard_of_0139cbd0, pointer_of_0139cbd0, storage_of_0139cbd0>();
}

extern "C" void bb_frame_timing_static_guard_0139cc00()
{
    bind_static<guard_of_0139cc00, pointer_of_0139cc00, storage_of_0139cc00>();
}

extern "C" void bb_frame_timing_static_guard_0139f6d0()
{
    bind_static<guard_of_0139f6d0, pointer_of_0139f6d0, storage_of_0139f6d0>();
}

extern "C" void bb_frame_timing_static_guard_0139f700()
{
    bind_static<guard_of_0139f700, pointer_of_0139f700, storage_of_0139f700>();
}

extern "C" void bb_frame_timing_static_guard_0139f730()
{
    bind_static<guard_of_0139f730, pointer_of_0139f730, storage_of_0139f730>();
}

extern "C" void bb_frame_timing_static_guard_013a4bd0()
{
    bind_static<guard_of_013a4bd0, pointer_of_013a4bd0, storage_of_013a4bd0>();
}

extern "C" void bb_frame_timing_static_guard_013a4c00()
{
    bind_static<guard_of_013a4c00, pointer_of_013a4c00, storage_of_013a4c00>();
}

extern "C" void bb_frame_timing_static_guard_013a4c30()
{
    bind_static<guard_of_013a4c30, pointer_of_013a4c30, storage_of_013a4c30>();
}

extern "C" void bb_frame_timing_static_guard_013a5030()
{
    bind_static<guard_of_013a5030, pointer_of_013a5030, storage_of_013a5030>();
}

extern "C" void bb_frame_timing_static_guard_013a5060()
{
    bind_static<guard_of_013a5060, pointer_of_013a5060, storage_of_013a5060>();
}

extern "C" void bb_frame_timing_static_guard_013a5090()
{
    bind_static<guard_of_013a5090, pointer_of_013a5090, storage_of_013a5090>();
}

extern "C" void bb_frame_timing_static_guard_013a6380()
{
    bind_static<guard_of_013a6380, pointer_of_013a6380, storage_of_013a6380>();
}

extern "C" void bb_frame_timing_static_guard_013a63b0()
{
    bind_static<guard_of_013a63b0, pointer_of_013a63b0, storage_of_013a63b0>();
}

extern "C" void bb_frame_timing_static_guard_013a63e0()
{
    bind_static<guard_of_013a63e0, pointer_of_013a63e0, storage_of_013a63e0>();
}

extern "C" void bb_frame_timing_static_guard_013a6580()
{
    bind_static<guard_of_013a6580, pointer_of_013a6580, storage_of_013a6580>();
}

extern "C" void bb_frame_timing_static_guard_013a65b0()
{
    bind_static<guard_of_013a65b0, pointer_of_013a65b0, storage_of_013a65b0>();
}

extern "C" void bb_frame_timing_static_guard_013a65e0()
{
    bind_static<guard_of_013a65e0, pointer_of_013a65e0, storage_of_013a65e0>();
}

extern "C" void bb_frame_timing_static_guard_013a74a0()
{
    bind_static<guard_of_013a74a0, pointer_of_013a74a0, storage_of_013a74a0>();
}

extern "C" void bb_frame_timing_static_guard_013a74d0()
{
    bind_static<guard_of_013a74d0, pointer_of_013a74d0, storage_of_013a74d0>();
}

extern "C" void bb_frame_timing_static_guard_013a7500()
{
    bind_static<guard_of_013a7500, pointer_of_013a7500, storage_of_013a7500>();
}

extern "C" void bb_frame_timing_static_guard_013a79e0()
{
    bind_static<guard_of_013a79e0, pointer_of_013a79e0, storage_of_013a79e0>();
}

extern "C" void bb_frame_timing_static_guard_013a7a10()
{
    bind_static<guard_of_013a7a10, pointer_of_013a7a10, storage_of_013a7a10>();
}

extern "C" void bb_frame_timing_static_guard_013a7a40()
{
    bind_static<guard_of_013a7a40, pointer_of_013a7a40, storage_of_013a7a40>();
}

extern "C" void bb_frame_timing_static_guard_013a8080()
{
    bind_static<guard_of_013a8080, pointer_of_013a8080, storage_of_013a8080>();
}

extern "C" void bb_frame_timing_static_guard_013a80b0()
{
    bind_static<guard_of_013a80b0, pointer_of_013a80b0, storage_of_013a80b0>();
}

extern "C" void bb_frame_timing_static_guard_013a80e0()
{
    bind_static<guard_of_013a80e0, pointer_of_013a80e0, storage_of_013a80e0>();
}

extern "C" void bb_frame_timing_static_guard_013a9b50()
{
    bind_static<guard_of_013a9b50, pointer_of_013a9b50, storage_of_013a9b50>();
}

extern "C" void bb_frame_timing_static_guard_013a9b80()
{
    bind_static<guard_of_013a9b80, pointer_of_013a9b80, storage_of_013a9b80>();
}

extern "C" void bb_frame_timing_static_guard_013a9bb0()
{
    bind_static<guard_of_013a9bb0, pointer_of_013a9bb0, storage_of_013a9bb0>();
}

extern "C" void bb_frame_timing_static_guard_013aa960()
{
    bind_static<guard_of_013aa960, pointer_of_013aa960, storage_of_013aa960>();
}

extern "C" void bb_frame_timing_static_guard_013aa990()
{
    bind_static<guard_of_013aa990, pointer_of_013aa990, storage_of_013aa990>();
}

extern "C" void bb_frame_timing_static_guard_013aa9c0()
{
    bind_static<guard_of_013aa9c0, pointer_of_013aa9c0, storage_of_013aa9c0>();
}

extern "C" void bb_frame_timing_static_guard_013ab530()
{
    bind_static<guard_of_013ab530, pointer_of_013ab530, storage_of_013ab530>();
}

extern "C" void bb_frame_timing_static_guard_013ab560()
{
    bind_static<guard_of_013ab560, pointer_of_013ab560, storage_of_013ab560>();
}

extern "C" void bb_frame_timing_static_guard_013ab590()
{
    bind_static<guard_of_013ab590, pointer_of_013ab590, storage_of_013ab590>();
}

extern "C" void bb_frame_timing_static_guard_013ad0b0()
{
    bind_static<guard_of_013ad0b0, pointer_of_013ad0b0, storage_of_013ad0b0>();
}

extern "C" void bb_frame_timing_static_guard_013ad0e0()
{
    bind_static<guard_of_013ad0e0, pointer_of_013ad0e0, storage_of_013ad0e0>();
}

extern "C" void bb_frame_timing_static_guard_013ad110()
{
    bind_static<guard_of_013ad110, pointer_of_013ad110, storage_of_013ad110>();
}

extern "C" void bb_frame_timing_static_guard_013ae990()
{
    bind_static<guard_of_013ae990, pointer_of_013ae990, storage_of_013ae990>();
}

extern "C" void bb_frame_timing_static_guard_013ae9c0()
{
    bind_static<guard_of_013ae9c0, pointer_of_013ae9c0, storage_of_013ae9c0>();
}

extern "C" void bb_frame_timing_static_guard_013ae9f0()
{
    bind_static<guard_of_013ae9f0, pointer_of_013ae9f0, storage_of_013ae9f0>();
}

extern "C" void bb_frame_timing_static_guard_013af330()
{
    bind_static<guard_of_013af330, pointer_of_013af330, storage_of_013af330>();
}

extern "C" void bb_frame_timing_static_guard_013af360()
{
    bind_static<guard_of_013af360, pointer_of_013af360, storage_of_013af360>();
}

extern "C" void bb_frame_timing_static_guard_013af390()
{
    bind_static<guard_of_013af390, pointer_of_013af390, storage_of_013af390>();
}

extern "C" void bb_frame_timing_static_guard_013af7c0()
{
    bind_static<guard_of_013af7c0, pointer_of_013af7c0, storage_of_013af7c0>();
}

extern "C" void bb_frame_timing_static_guard_013af7f0()
{
    bind_static<guard_of_013af7f0, pointer_of_013af7f0, storage_of_013af7f0>();
}

extern "C" void bb_frame_timing_static_guard_013af820()
{
    bind_static<guard_of_013af820, pointer_of_013af820, storage_of_013af820>();
}

extern "C" void bb_frame_timing_static_guard_013b0090()
{
    bind_static<guard_of_013b0090, pointer_of_013b0090, storage_of_013b0090>();
}

extern "C" void bb_frame_timing_static_guard_013b00c0()
{
    bind_static<guard_of_013b00c0, pointer_of_013b00c0, storage_of_013b00c0>();
}

extern "C" void bb_frame_timing_static_guard_013b00f0()
{
    bind_static<guard_of_013b00f0, pointer_of_013b00f0, storage_of_013b00f0>();
}

extern "C" void bb_frame_timing_static_guard_013b1b60()
{
    bind_static<guard_of_013b1b60, pointer_of_013b1b60, storage_of_013b1b60>();
}

extern "C" void bb_frame_timing_static_guard_013b1b90()
{
    bind_static<guard_of_013b1b90, pointer_of_013b1b90, storage_of_013b1b90>();
}

extern "C" void bb_frame_timing_static_guard_013b1bc0()
{
    bind_static<guard_of_013b1bc0, pointer_of_013b1bc0, storage_of_013b1bc0>();
}

extern "C" void bb_frame_timing_static_guard_013b2e20()
{
    bind_static<guard_of_013b2e20, pointer_of_013b2e20, storage_of_013b2e20>();
}

extern "C" void bb_frame_timing_static_guard_013b2e50()
{
    bind_static<guard_of_013b2e50, pointer_of_013b2e50, storage_of_013b2e50>();
}

extern "C" void bb_frame_timing_static_guard_013b2e80()
{
    bind_static<guard_of_013b2e80, pointer_of_013b2e80, storage_of_013b2e80>();
}

extern "C" void bb_frame_timing_static_guard_013b3430()
{
    bind_static<guard_of_013b3430, pointer_of_013b3430, storage_of_013b3430>();
}

extern "C" void bb_frame_timing_static_guard_013b3460()
{
    bind_static<guard_of_013b3460, pointer_of_013b3460, storage_of_013b3460>();
}

extern "C" void bb_frame_timing_static_guard_013b3490()
{
    bind_static<guard_of_013b3490, pointer_of_013b3490, storage_of_013b3490>();
}

extern "C" void bb_frame_timing_static_guard_013b4730()
{
    bind_static<guard_of_013b4730, pointer_of_013b4730, storage_of_013b4730>();
}

extern "C" void bb_frame_timing_static_guard_013b4760()
{
    bind_static<guard_of_013b4760, pointer_of_013b4760, storage_of_013b4760>();
}

extern "C" void bb_frame_timing_static_guard_013b4790()
{
    bind_static<guard_of_013b4790, pointer_of_013b4790, storage_of_013b4790>();
}

extern "C" void bb_frame_timing_static_guard_013b4d50()
{
    bind_static<guard_of_013b4d50, pointer_of_013b4d50, storage_of_013b4d50>();
}

extern "C" void bb_frame_timing_static_guard_013b4d80()
{
    bind_static<guard_of_013b4d80, pointer_of_013b4d80, storage_of_013b4d80>();
}

extern "C" void bb_frame_timing_static_guard_013b4db0()
{
    bind_static<guard_of_013b4db0, pointer_of_013b4db0, storage_of_013b4db0>();
}

extern "C" void bb_frame_timing_static_guard_013b4fb0()
{
    bind_static<guard_of_013b4fb0, pointer_of_013b4fb0, storage_of_013b4fb0>();
}

extern "C" void bb_frame_timing_static_guard_013b4fe0()
{
    bind_static<guard_of_013b4fe0, pointer_of_013b4fe0, storage_of_013b4fe0>();
}

extern "C" void bb_frame_timing_static_guard_013b5010()
{
    bind_static<guard_of_013b5010, pointer_of_013b5010, storage_of_013b5010>();
}

extern "C" void bb_frame_timing_static_guard_013b5370()
{
    bind_static<guard_of_013b5370, pointer_of_013b5370, storage_of_013b5370>();
}

extern "C" void bb_frame_timing_static_guard_013b53a0()
{
    bind_static<guard_of_013b53a0, pointer_of_013b53a0, storage_of_013b53a0>();
}

extern "C" void bb_frame_timing_static_guard_013b53d0()
{
    bind_static<guard_of_013b53d0, pointer_of_013b53d0, storage_of_013b53d0>();
}

extern "C" void bb_frame_timing_static_guard_013b5fd0()
{
    bind_static<guard_of_013b5fd0, pointer_of_013b5fd0, storage_of_013b5fd0>();
}

extern "C" void bb_frame_timing_static_guard_013b6000()
{
    bind_static<guard_of_013b6000, pointer_of_013b6000, storage_of_013b6000>();
}

extern "C" void bb_frame_timing_static_guard_013b6030()
{
    bind_static<guard_of_013b6030, pointer_of_013b6030, storage_of_013b6030>();
}

extern "C" void bb_frame_timing_static_guard_013b8920()
{
    bind_static<guard_of_013b8920, pointer_of_013b8920, storage_of_013b8920>();
}

extern "C" void bb_frame_timing_static_guard_013b8950()
{
    bind_static<guard_of_013b8950, pointer_of_013b8950, storage_of_013b8950>();
}

extern "C" void bb_frame_timing_static_guard_013b8980()
{
    bind_static<guard_of_013b8980, pointer_of_013b8980, storage_of_013b8980>();
}

extern "C" void bb_frame_timing_static_guard_013b9220()
{
    bind_static<guard_of_013b9220, pointer_of_013b9220, storage_of_013b9220>();
}

extern "C" void bb_frame_timing_static_guard_013b9250()
{
    bind_static<guard_of_013b9250, pointer_of_013b9250, storage_of_013b9250>();
}

extern "C" void bb_frame_timing_static_guard_013b9280()
{
    bind_static<guard_of_013b9280, pointer_of_013b9280, storage_of_013b9280>();
}

extern "C" void bb_frame_timing_static_guard_013b97f0()
{
    bind_static<guard_of_013b97f0, pointer_of_013b97f0, storage_of_013b97f0>();
}

extern "C" void bb_frame_timing_static_guard_013b9820()
{
    bind_static<guard_of_013b9820, pointer_of_013b9820, storage_of_013b9820>();
}

extern "C" void bb_frame_timing_static_guard_013b9850()
{
    bind_static<guard_of_013b9850, pointer_of_013b9850, storage_of_013b9850>();
}

extern "C" void bb_frame_timing_static_guard_013ba550()
{
    bind_static<guard_of_013ba550, pointer_of_013ba550, storage_of_013ba550>();
}

extern "C" void bb_frame_timing_static_guard_013ba580()
{
    bind_static<guard_of_013ba580, pointer_of_013ba580, storage_of_013ba580>();
}

extern "C" void bb_frame_timing_static_guard_013ba5b0()
{
    bind_static<guard_of_013ba5b0, pointer_of_013ba5b0, storage_of_013ba5b0>();
}

extern "C" void bb_frame_timing_static_guard_013bbfc0()
{
    bind_static<guard_of_013bbfc0, pointer_of_013bbfc0, storage_of_013bbfc0>();
}

extern "C" void bb_frame_timing_static_guard_013bbff0()
{
    bind_static<guard_of_013bbff0, pointer_of_013bbff0, storage_of_013bbff0>();
}

extern "C" void bb_frame_timing_static_guard_013bc020()
{
    bind_static<guard_of_013bc020, pointer_of_013bc020, storage_of_013bc020>();
}

extern "C" void bb_frame_timing_static_guard_013bc100()
{
    bind_static<guard_of_013bc100, pointer_of_013bc100, storage_of_013bc100>();
}

extern "C" void bb_frame_timing_static_guard_013bc130()
{
    bind_static<guard_of_013bc130, pointer_of_013bc130, storage_of_013bc130>();
}

extern "C" void bb_frame_timing_static_guard_013bc160()
{
    bind_static<guard_of_013bc160, pointer_of_013bc160, storage_of_013bc160>();
}

extern "C" void bb_frame_timing_static_guard_013bc220()
{
    bind_static<guard_of_013bc220, pointer_of_013bc220, storage_of_013bc220>();
}

extern "C" void bb_frame_timing_static_guard_013bc250()
{
    bind_static<guard_of_013bc250, pointer_of_013bc250, storage_of_013bc250>();
}

extern "C" void bb_frame_timing_static_guard_013bc280()
{
    bind_static<guard_of_013bc280, pointer_of_013bc280, storage_of_013bc280>();
}

extern "C" void bb_frame_timing_static_guard_013bc660()
{
    bind_static<guard_of_013bc660, pointer_of_013bc660, storage_of_013bc660>();
}

extern "C" void bb_frame_timing_static_guard_013bc690()
{
    bind_static<guard_of_013bc690, pointer_of_013bc690, storage_of_013bc690>();
}

extern "C" void bb_frame_timing_static_guard_013bc6c0()
{
    bind_static<guard_of_013bc6c0, pointer_of_013bc6c0, storage_of_013bc6c0>();
}

extern "C" void bb_frame_timing_static_guard_013bde80()
{
    bind_static<guard_of_013bde80, pointer_of_013bde80, storage_of_013bde80>();
}

extern "C" void bb_frame_timing_static_guard_013bdeb0()
{
    bind_static<guard_of_013bdeb0, pointer_of_013bdeb0, storage_of_013bdeb0>();
}

extern "C" void bb_frame_timing_static_guard_013bdee0()
{
    bind_static<guard_of_013bdee0, pointer_of_013bdee0, storage_of_013bdee0>();
}

extern "C" void bb_frame_timing_static_guard_013be8b0()
{
    bind_static<guard_of_013be8b0, pointer_of_013be8b0, storage_of_013be8b0>();
}

extern "C" void bb_frame_timing_static_guard_013be8e0()
{
    bind_static<guard_of_013be8e0, pointer_of_013be8e0, storage_of_013be8e0>();
}

extern "C" void bb_frame_timing_static_guard_013be910()
{
    bind_static<guard_of_013be910, pointer_of_013be910, storage_of_013be910>();
}

extern "C" void bb_frame_timing_static_guard_013beba0()
{
    bind_static<guard_of_013beba0, pointer_of_013beba0, storage_of_013beba0>();
}

extern "C" void bb_frame_timing_static_guard_013bebd0()
{
    bind_static<guard_of_013bebd0, pointer_of_013bebd0, storage_of_013bebd0>();
}

extern "C" void bb_frame_timing_static_guard_013bec00()
{
    bind_static<guard_of_013bec00, pointer_of_013bec00, storage_of_013bec00>();
}

extern "C" void bb_frame_timing_static_guard_013bece0()
{
    bind_static<guard_of_013bece0, pointer_of_013bece0, storage_of_013bece0>();
}

extern "C" void bb_frame_timing_static_guard_013bed10()
{
    bind_static<guard_of_013bed10, pointer_of_013bed10, storage_of_013bed10>();
}

extern "C" void bb_frame_timing_static_guard_013bed40()
{
    bind_static<guard_of_013bed40, pointer_of_013bed40, storage_of_013bed40>();
}

extern "C" void bb_frame_timing_static_guard_013beea0()
{
    bind_static<guard_of_013beea0, pointer_of_013beea0, storage_of_013beea0>();
}

extern "C" void bb_frame_timing_static_guard_013beed0()
{
    bind_static<guard_of_013beed0, pointer_of_013beed0, storage_of_013beed0>();
}

extern "C" void bb_frame_timing_static_guard_013bef00()
{
    bind_static<guard_of_013bef00, pointer_of_013bef00, storage_of_013bef00>();
}

extern "C" void bb_frame_timing_static_guard_013bf9a0()
{
    bind_static<guard_of_013bf9a0, pointer_of_013bf9a0, storage_of_013bf9a0>();
}

extern "C" void bb_frame_timing_static_guard_013bf9d0()
{
    bind_static<guard_of_013bf9d0, pointer_of_013bf9d0, storage_of_013bf9d0>();
}

extern "C" void bb_frame_timing_static_guard_013bfa00()
{
    bind_static<guard_of_013bfa00, pointer_of_013bfa00, storage_of_013bfa00>();
}

extern "C" void bb_frame_timing_static_guard_013bfe60()
{
    bind_static<guard_of_013bfe60, pointer_of_013bfe60, storage_of_013bfe60>();
}

extern "C" void bb_frame_timing_static_guard_013bfe90()
{
    bind_static<guard_of_013bfe90, pointer_of_013bfe90, storage_of_013bfe90>();
}

extern "C" void bb_frame_timing_static_guard_013bfec0()
{
    bind_static<guard_of_013bfec0, pointer_of_013bfec0, storage_of_013bfec0>();
}

extern "C" void bb_frame_timing_static_guard_013c18a0()
{
    bind_static<guard_of_013c18a0, pointer_of_013c18a0, storage_of_013c18a0>();
}

extern "C" void bb_frame_timing_static_guard_013c18d0()
{
    bind_static<guard_of_013c18d0, pointer_of_013c18d0, storage_of_013c18d0>();
}

extern "C" void bb_frame_timing_static_guard_013c1900()
{
    bind_static<guard_of_013c1900, pointer_of_013c1900, storage_of_013c1900>();
}

extern "C" void bb_frame_timing_static_guard_013c2fe0()
{
    bind_static<guard_of_013c2fe0, pointer_of_013c2fe0, storage_of_013c2fe0>();
}

extern "C" void bb_frame_timing_static_guard_013c3010()
{
    bind_static<guard_of_013c3010, pointer_of_013c3010, storage_of_013c3010>();
}

extern "C" void bb_frame_timing_static_guard_013c3040()
{
    bind_static<guard_of_013c3040, pointer_of_013c3040, storage_of_013c3040>();
}

extern "C" void bb_frame_timing_static_guard_013c3830()
{
    bind_static<guard_of_013c3830, pointer_of_013c3830, storage_of_013c3830>();
}

extern "C" void bb_frame_timing_static_guard_013c3860()
{
    bind_static<guard_of_013c3860, pointer_of_013c3860, storage_of_013c3860>();
}

extern "C" void bb_frame_timing_static_guard_013c3890()
{
    bind_static<guard_of_013c3890, pointer_of_013c3890, storage_of_013c3890>();
}

extern "C" void bb_frame_timing_static_guard_013c3da0()
{
    bind_static<guard_of_013c3da0, pointer_of_013c3da0, storage_of_013c3da0>();
}

extern "C" void bb_frame_timing_static_guard_013c3dd0()
{
    bind_static<guard_of_013c3dd0, pointer_of_013c3dd0, storage_of_013c3dd0>();
}

extern "C" void bb_frame_timing_static_guard_013c3e00()
{
    bind_static<guard_of_013c3e00, pointer_of_013c3e00, storage_of_013c3e00>();
}

extern "C" void bb_frame_timing_static_guard_013c5000()
{
    bind_static<guard_of_013c5000, pointer_of_013c5000, storage_of_013c5000>();
}

extern "C" void bb_frame_timing_static_guard_013c5030()
{
    bind_static<guard_of_013c5030, pointer_of_013c5030, storage_of_013c5030>();
}

extern "C" void bb_frame_timing_static_guard_013c5060()
{
    bind_static<guard_of_013c5060, pointer_of_013c5060, storage_of_013c5060>();
}

extern "C" void bb_frame_timing_static_guard_013c55c0()
{
    bind_static<guard_of_013c55c0, pointer_of_013c55c0, storage_of_013c55c0>();
}

extern "C" void bb_frame_timing_static_guard_013c55f0()
{
    bind_static<guard_of_013c55f0, pointer_of_013c55f0, storage_of_013c55f0>();
}

extern "C" void bb_frame_timing_static_guard_013c5620()
{
    bind_static<guard_of_013c5620, pointer_of_013c5620, storage_of_013c5620>();
}

extern "C" void bb_frame_timing_static_guard_013c6e60()
{
    bind_static<guard_of_013c6e60, pointer_of_013c6e60, storage_of_013c6e60>();
}

extern "C" void bb_frame_timing_static_guard_013c6e90()
{
    bind_static<guard_of_013c6e90, pointer_of_013c6e90, storage_of_013c6e90>();
}

extern "C" void bb_frame_timing_static_guard_013c6ec0()
{
    bind_static<guard_of_013c6ec0, pointer_of_013c6ec0, storage_of_013c6ec0>();
}

extern "C" void bb_frame_timing_static_guard_013c7330()
{
    bind_static<guard_of_013c7330, pointer_of_013c7330, storage_of_013c7330>();
}

extern "C" void bb_frame_timing_static_guard_013c7360()
{
    bind_static<guard_of_013c7360, pointer_of_013c7360, storage_of_013c7360>();
}

extern "C" void bb_frame_timing_static_guard_013c7390()
{
    bind_static<guard_of_013c7390, pointer_of_013c7390, storage_of_013c7390>();
}

extern "C" void bb_frame_timing_static_guard_013c7a60()
{
    bind_static<guard_of_013c7a60, pointer_of_013c7a60, storage_of_013c7a60>();
}

extern "C" void bb_frame_timing_static_guard_013c7a90()
{
    bind_static<guard_of_013c7a90, pointer_of_013c7a90, storage_of_013c7a90>();
}

extern "C" void bb_frame_timing_static_guard_013c7ac0()
{
    bind_static<guard_of_013c7ac0, pointer_of_013c7ac0, storage_of_013c7ac0>();
}

extern "C" void bb_frame_timing_static_guard_013c7ee0()
{
    bind_static<guard_of_013c7ee0, pointer_of_013c7ee0, storage_of_013c7ee0>();
}

extern "C" void bb_frame_timing_static_guard_013c7f10()
{
    bind_static<guard_of_013c7f10, pointer_of_013c7f10, storage_of_013c7f10>();
}

extern "C" void bb_frame_timing_static_guard_013c7f40()
{
    bind_static<guard_of_013c7f40, pointer_of_013c7f40, storage_of_013c7f40>();
}

extern "C" void bb_frame_timing_static_guard_013cc410()
{
    bind_static<guard_of_013cc410, pointer_of_013cc410, storage_of_013cc410>();
}

extern "C" void bb_frame_timing_static_guard_013cc440()
{
    bind_static<guard_of_013cc440, pointer_of_013cc440, storage_of_013cc440>();
}

extern "C" void bb_frame_timing_static_guard_013cc470()
{
    bind_static<guard_of_013cc470, pointer_of_013cc470, storage_of_013cc470>();
}

extern "C" void bb_frame_timing_static_guard_013cd550()
{
    bind_static<guard_of_013cd550, pointer_of_013cd550, storage_of_013cd550>();
}

extern "C" void bb_frame_timing_static_guard_013cd580()
{
    bind_static<guard_of_013cd580, pointer_of_013cd580, storage_of_013cd580>();
}

extern "C" void bb_frame_timing_static_guard_013cd5b0()
{
    bind_static<guard_of_013cd5b0, pointer_of_013cd5b0, storage_of_013cd5b0>();
}

extern "C" void bb_frame_timing_static_guard_013ce1b0()
{
    bind_static<guard_of_013ce1b0, pointer_of_013ce1b0, storage_of_013ce1b0>();
}

extern "C" void bb_frame_timing_static_guard_013ce1e0()
{
    bind_static<guard_of_013ce1e0, pointer_of_013ce1e0, storage_of_013ce1e0>();
}

extern "C" void bb_frame_timing_static_guard_013ce210()
{
    bind_static<guard_of_013ce210, pointer_of_013ce210, storage_of_013ce210>();
}

extern "C" void bb_frame_timing_static_guard_013ce500()
{
    bind_static<guard_of_013ce500, pointer_of_013ce500, storage_of_013ce500>();
}

extern "C" void bb_frame_timing_static_guard_013ce530()
{
    bind_static<guard_of_013ce530, pointer_of_013ce530, storage_of_013ce530>();
}

extern "C" void bb_frame_timing_static_guard_013ce560()
{
    bind_static<guard_of_013ce560, pointer_of_013ce560, storage_of_013ce560>();
}

extern "C" void bb_frame_timing_static_guard_013ce9e0()
{
    bind_static<guard_of_013ce9e0, pointer_of_013ce9e0, storage_of_013ce9e0>();
}

extern "C" void bb_frame_timing_static_guard_013cea10()
{
    bind_static<guard_of_013cea10, pointer_of_013cea10, storage_of_013cea10>();
}

extern "C" void bb_frame_timing_static_guard_013cea40()
{
    bind_static<guard_of_013cea40, pointer_of_013cea40, storage_of_013cea40>();
}

extern "C" void bb_frame_timing_static_guard_013ced30()
{
    bind_static<guard_of_013ced30, pointer_of_013ced30, storage_of_013ced30>();
}

extern "C" void bb_frame_timing_static_guard_013ced60()
{
    bind_static<guard_of_013ced60, pointer_of_013ced60, storage_of_013ced60>();
}

extern "C" void bb_frame_timing_static_guard_013ced90()
{
    bind_static<guard_of_013ced90, pointer_of_013ced90, storage_of_013ced90>();
}

extern "C" void bb_frame_timing_static_guard_013cf100()
{
    bind_static<guard_of_013cf100, pointer_of_013cf100, storage_of_013cf100>();
}

extern "C" void bb_frame_timing_static_guard_013cf130()
{
    bind_static<guard_of_013cf130, pointer_of_013cf130, storage_of_013cf130>();
}

extern "C" void bb_frame_timing_static_guard_013cf160()
{
    bind_static<guard_of_013cf160, pointer_of_013cf160, storage_of_013cf160>();
}

extern "C" void bb_frame_timing_static_guard_013cf450()
{
    bind_static<guard_of_013cf450, pointer_of_013cf450, storage_of_013cf450>();
}

extern "C" void bb_frame_timing_static_guard_013cf480()
{
    bind_static<guard_of_013cf480, pointer_of_013cf480, storage_of_013cf480>();
}

extern "C" void bb_frame_timing_static_guard_013cf4b0()
{
    bind_static<guard_of_013cf4b0, pointer_of_013cf4b0, storage_of_013cf4b0>();
}

extern "C" void bb_frame_timing_static_guard_013cfa10()
{
    bind_static<guard_of_013cfa10, pointer_of_013cfa10, storage_of_013cfa10>();
}

extern "C" void bb_frame_timing_static_guard_013cfa40()
{
    bind_static<guard_of_013cfa40, pointer_of_013cfa40, storage_of_013cfa40>();
}

extern "C" void bb_frame_timing_static_guard_013cfa70()
{
    bind_static<guard_of_013cfa70, pointer_of_013cfa70, storage_of_013cfa70>();
}

extern "C" void bb_frame_timing_static_guard_013cfd60()
{
    bind_static<guard_of_013cfd60, pointer_of_013cfd60, storage_of_013cfd60>();
}

extern "C" void bb_frame_timing_static_guard_013cfd90()
{
    bind_static<guard_of_013cfd90, pointer_of_013cfd90, storage_of_013cfd90>();
}

extern "C" void bb_frame_timing_static_guard_013cfdc0()
{
    bind_static<guard_of_013cfdc0, pointer_of_013cfdc0, storage_of_013cfdc0>();
}

extern "C" void bb_frame_timing_static_guard_013d01c0()
{
    bind_static<guard_of_013d01c0, pointer_of_013d01c0, storage_of_013d01c0>();
}

extern "C" void bb_frame_timing_static_guard_013d01f0()
{
    bind_static<guard_of_013d01f0, pointer_of_013d01f0, storage_of_013d01f0>();
}

extern "C" void bb_frame_timing_static_guard_013d0220()
{
    bind_static<guard_of_013d0220, pointer_of_013d0220, storage_of_013d0220>();
}

extern "C" void bb_frame_timing_static_guard_013d0510()
{
    bind_static<guard_of_013d0510, pointer_of_013d0510, storage_of_013d0510>();
}

extern "C" void bb_frame_timing_static_guard_013d0540()
{
    bind_static<guard_of_013d0540, pointer_of_013d0540, storage_of_013d0540>();
}

extern "C" void bb_frame_timing_static_guard_013d0570()
{
    bind_static<guard_of_013d0570, pointer_of_013d0570, storage_of_013d0570>();
}

extern "C" void bb_frame_timing_static_guard_013d08d0()
{
    bind_static<guard_of_013d08d0, pointer_of_013d08d0, storage_of_013d08d0>();
}

extern "C" void bb_frame_timing_static_guard_013d0900()
{
    bind_static<guard_of_013d0900, pointer_of_013d0900, storage_of_013d0900>();
}

extern "C" void bb_frame_timing_static_guard_013d0930()
{
    bind_static<guard_of_013d0930, pointer_of_013d0930, storage_of_013d0930>();
}

extern "C" void bb_frame_timing_static_guard_013d0bc0()
{
    bind_static<guard_of_013d0bc0, pointer_of_013d0bc0, storage_of_013d0bc0>();
}

extern "C" void bb_frame_timing_static_guard_013d0bf0()
{
    bind_static<guard_of_013d0bf0, pointer_of_013d0bf0, storage_of_013d0bf0>();
}

extern "C" void bb_frame_timing_static_guard_013d0c20()
{
    bind_static<guard_of_013d0c20, pointer_of_013d0c20, storage_of_013d0c20>();
}

extern "C" void bb_frame_timing_static_guard_013d1be0()
{
    bind_static<guard_of_013d1be0, pointer_of_013d1be0, storage_of_013d1be0>();
}

extern "C" void bb_frame_timing_static_guard_013d1c10()
{
    bind_static<guard_of_013d1c10, pointer_of_013d1c10, storage_of_013d1c10>();
}

extern "C" void bb_frame_timing_static_guard_013d1c40()
{
    bind_static<guard_of_013d1c40, pointer_of_013d1c40, storage_of_013d1c40>();
}

extern "C" void bb_frame_timing_static_guard_013d1ef0()
{
    bind_static<guard_of_013d1ef0, pointer_of_013d1ef0, storage_of_013d1ef0>();
}

extern "C" void bb_frame_timing_static_guard_013d1f20()
{
    bind_static<guard_of_013d1f20, pointer_of_013d1f20, storage_of_013d1f20>();
}

extern "C" void bb_frame_timing_static_guard_013d1f50()
{
    bind_static<guard_of_013d1f50, pointer_of_013d1f50, storage_of_013d1f50>();
}

extern "C" void bb_frame_timing_static_guard_013d21b0()
{
    bind_static<guard_of_013d21b0, pointer_of_013d21b0, storage_of_013d21b0>();
}

extern "C" void bb_frame_timing_static_guard_013d21e0()
{
    bind_static<guard_of_013d21e0, pointer_of_013d21e0, storage_of_013d21e0>();
}

extern "C" void bb_frame_timing_static_guard_013d2210()
{
    bind_static<guard_of_013d2210, pointer_of_013d2210, storage_of_013d2210>();
}

extern "C" void bb_frame_timing_static_guard_013d22c0()
{
    bind_static<guard_of_013d22c0, pointer_of_013d22c0, storage_of_013d22c0>();
}

extern "C" void bb_frame_timing_static_guard_013d22f0()
{
    bind_static<guard_of_013d22f0, pointer_of_013d22f0, storage_of_013d22f0>();
}

extern "C" void bb_frame_timing_static_guard_013d2320()
{
    bind_static<guard_of_013d2320, pointer_of_013d2320, storage_of_013d2320>();
}

extern "C" void bb_frame_timing_static_guard_013d24a0()
{
    bind_static<guard_of_013d24a0, pointer_of_013d24a0, storage_of_013d24a0>();
}

extern "C" void bb_frame_timing_static_guard_013d24d0()
{
    bind_static<guard_of_013d24d0, pointer_of_013d24d0, storage_of_013d24d0>();
}

extern "C" void bb_frame_timing_static_guard_013d2500()
{
    bind_static<guard_of_013d2500, pointer_of_013d2500, storage_of_013d2500>();
}

extern "C" void bb_frame_timing_static_guard_013d2ce0()
{
    bind_static<guard_of_013d2ce0, pointer_of_013d2ce0, storage_of_013d2ce0>();
}

extern "C" void bb_frame_timing_static_guard_013d2d10()
{
    bind_static<guard_of_013d2d10, pointer_of_013d2d10, storage_of_013d2d10>();
}

extern "C" void bb_frame_timing_static_guard_013d2d40()
{
    bind_static<guard_of_013d2d40, pointer_of_013d2d40, storage_of_013d2d40>();
}

extern "C" void bb_frame_timing_static_guard_013d37b0()
{
    bind_static<guard_of_013d37b0, pointer_of_013d37b0, storage_of_013d37b0>();
}

extern "C" void bb_frame_timing_static_guard_013d37e0()
{
    bind_static<guard_of_013d37e0, pointer_of_013d37e0, storage_of_013d37e0>();
}

extern "C" void bb_frame_timing_static_guard_013d3810()
{
    bind_static<guard_of_013d3810, pointer_of_013d3810, storage_of_013d3810>();
}

extern "C" void bb_frame_timing_static_guard_013d4b10()
{
    bind_static<guard_of_013d4b10, pointer_of_013d4b10, storage_of_013d4b10>();
}

extern "C" void bb_frame_timing_static_guard_013d4b40()
{
    bind_static<guard_of_013d4b40, pointer_of_013d4b40, storage_of_013d4b40>();
}

extern "C" void bb_frame_timing_static_guard_013d4b70()
{
    bind_static<guard_of_013d4b70, pointer_of_013d4b70, storage_of_013d4b70>();
}

extern "C" void bb_frame_timing_static_guard_013d64c0()
{
    bind_static<guard_of_013d64c0, pointer_of_013d64c0, storage_of_013d64c0>();
}

extern "C" void bb_frame_timing_static_guard_013d64f0()
{
    bind_static<guard_of_013d64f0, pointer_of_013d64f0, storage_of_013d64f0>();
}

extern "C" void bb_frame_timing_static_guard_013d6520()
{
    bind_static<guard_of_013d6520, pointer_of_013d6520, storage_of_013d6520>();
}

extern "C" void bb_frame_timing_static_guard_013d6b30()
{
    bind_static<guard_of_013d6b30, pointer_of_013d6b30, storage_of_013d6b30>();
}

extern "C" void bb_frame_timing_static_guard_013d6b60()
{
    bind_static<guard_of_013d6b60, pointer_of_013d6b60, storage_of_013d6b60>();
}

extern "C" void bb_frame_timing_static_guard_013d6b90()
{
    bind_static<guard_of_013d6b90, pointer_of_013d6b90, storage_of_013d6b90>();
}

extern "C" void bb_frame_timing_static_guard_013da6f0()
{
    bind_static<guard_of_013da6f0, pointer_of_013da6f0, storage_of_013da6f0>();
}

extern "C" void bb_frame_timing_static_guard_013da720()
{
    bind_static<guard_of_013da720, pointer_of_013da720, storage_of_013da720>();
}

extern "C" void bb_frame_timing_static_guard_013da750()
{
    bind_static<guard_of_013da750, pointer_of_013da750, storage_of_013da750>();
}

extern "C" void bb_frame_timing_static_guard_013dae40()
{
    bind_static<guard_of_013dae40, pointer_of_013dae40, storage_of_013dae40>();
}

extern "C" void bb_frame_timing_static_guard_013dae70()
{
    bind_static<guard_of_013dae70, pointer_of_013dae70, storage_of_013dae70>();
}

extern "C" void bb_frame_timing_static_guard_013daea0()
{
    bind_static<guard_of_013daea0, pointer_of_013daea0, storage_of_013daea0>();
}

extern "C" void bb_frame_timing_static_guard_013db320()
{
    bind_static<guard_of_013db320, pointer_of_013db320, storage_of_013db320>();
}

extern "C" void bb_frame_timing_static_guard_013db350()
{
    bind_static<guard_of_013db350, pointer_of_013db350, storage_of_013db350>();
}

extern "C" void bb_frame_timing_static_guard_013db380()
{
    bind_static<guard_of_013db380, pointer_of_013db380, storage_of_013db380>();
}

extern "C" void bb_frame_timing_static_guard_013db670()
{
    bind_static<guard_of_013db670, pointer_of_013db670, storage_of_013db670>();
}

extern "C" void bb_frame_timing_static_guard_013db6a0()
{
    bind_static<guard_of_013db6a0, pointer_of_013db6a0, storage_of_013db6a0>();
}

extern "C" void bb_frame_timing_static_guard_013db6d0()
{
    bind_static<guard_of_013db6d0, pointer_of_013db6d0, storage_of_013db6d0>();
}

extern "C" void bb_frame_timing_static_guard_013dba90()
{
    bind_static<guard_of_013dba90, pointer_of_013dba90, storage_of_013dba90>();
}

extern "C" void bb_frame_timing_static_guard_013dbac0()
{
    bind_static<guard_of_013dbac0, pointer_of_013dbac0, storage_of_013dbac0>();
}

extern "C" void bb_frame_timing_static_guard_013dbaf0()
{
    bind_static<guard_of_013dbaf0, pointer_of_013dbaf0, storage_of_013dbaf0>();
}

extern "C" void bb_frame_timing_static_guard_013dbde0()
{
    bind_static<guard_of_013dbde0, pointer_of_013dbde0, storage_of_013dbde0>();
}

extern "C" void bb_frame_timing_static_guard_013dbe10()
{
    bind_static<guard_of_013dbe10, pointer_of_013dbe10, storage_of_013dbe10>();
}

extern "C" void bb_frame_timing_static_guard_013dbe40()
{
    bind_static<guard_of_013dbe40, pointer_of_013dbe40, storage_of_013dbe40>();
}

extern "C" void bb_frame_timing_static_guard_013dc0c0()
{
    bind_static<guard_of_013dc0c0, pointer_of_013dc0c0, storage_of_013dc0c0>();
}

extern "C" void bb_frame_timing_static_guard_013dc0f0()
{
    bind_static<guard_of_013dc0f0, pointer_of_013dc0f0, storage_of_013dc0f0>();
}

extern "C" void bb_frame_timing_static_guard_013dc120()
{
    bind_static<guard_of_013dc120, pointer_of_013dc120, storage_of_013dc120>();
}

extern "C" void bb_frame_timing_static_guard_013dc6d0()
{
    bind_static<guard_of_013dc6d0, pointer_of_013dc6d0, storage_of_013dc6d0>();
}

extern "C" void bb_frame_timing_static_guard_013dc700()
{
    bind_static<guard_of_013dc700, pointer_of_013dc700, storage_of_013dc700>();
}

extern "C" void bb_frame_timing_static_guard_013dc730()
{
    bind_static<guard_of_013dc730, pointer_of_013dc730, storage_of_013dc730>();
}

extern "C" void bb_frame_timing_static_guard_013dca30()
{
    bind_static<guard_of_013dca30, pointer_of_013dca30, storage_of_013dca30>();
}

extern "C" void bb_frame_timing_static_guard_013dca60()
{
    bind_static<guard_of_013dca60, pointer_of_013dca60, storage_of_013dca60>();
}

extern "C" void bb_frame_timing_static_guard_013dca90()
{
    bind_static<guard_of_013dca90, pointer_of_013dca90, storage_of_013dca90>();
}

extern "C" void bb_frame_timing_static_guard_013de430()
{
    bind_static<guard_of_013de430, pointer_of_013de430, storage_of_013de430>();
}

extern "C" void bb_frame_timing_static_guard_013de460()
{
    bind_static<guard_of_013de460, pointer_of_013de460, storage_of_013de460>();
}

extern "C" void bb_frame_timing_static_guard_013de490()
{
    bind_static<guard_of_013de490, pointer_of_013de490, storage_of_013de490>();
}

extern "C" void bb_frame_timing_static_guard_013debf0()
{
    bind_static<guard_of_013debf0, pointer_of_013debf0, storage_of_013debf0>();
}

extern "C" void bb_frame_timing_static_guard_013dec20()
{
    bind_static<guard_of_013dec20, pointer_of_013dec20, storage_of_013dec20>();
}

extern "C" void bb_frame_timing_static_guard_013dec50()
{
    bind_static<guard_of_013dec50, pointer_of_013dec50, storage_of_013dec50>();
}

extern "C" void bb_frame_timing_static_guard_013defd0()
{
    bind_static<guard_of_013defd0, pointer_of_013defd0, storage_of_013defd0>();
}

extern "C" void bb_frame_timing_static_guard_013df000()
{
    bind_static<guard_of_013df000, pointer_of_013df000, storage_of_013df000>();
}

extern "C" void bb_frame_timing_static_guard_013df030()
{
    bind_static<guard_of_013df030, pointer_of_013df030, storage_of_013df030>();
}

extern "C" void bb_frame_timing_static_guard_013df440()
{
    bind_static<guard_of_013df440, pointer_of_013df440, storage_of_013df440>();
}

extern "C" void bb_frame_timing_static_guard_013df470()
{
    bind_static<guard_of_013df470, pointer_of_013df470, storage_of_013df470>();
}

extern "C" void bb_frame_timing_static_guard_013df4a0()
{
    bind_static<guard_of_013df4a0, pointer_of_013df4a0, storage_of_013df4a0>();
}

extern "C" void bb_frame_timing_static_guard_013df650()
{
    bind_static<guard_of_013df650, pointer_of_013df650, storage_of_013df650>();
}

extern "C" void bb_frame_timing_static_guard_013df680()
{
    bind_static<guard_of_013df680, pointer_of_013df680, storage_of_013df680>();
}

extern "C" void bb_frame_timing_static_guard_013df6b0()
{
    bind_static<guard_of_013df6b0, pointer_of_013df6b0, storage_of_013df6b0>();
}

extern "C" void bb_frame_timing_static_guard_013dfe60()
{
    bind_static<guard_of_013dfe60, pointer_of_013dfe60, storage_of_013dfe60>();
}

extern "C" void bb_frame_timing_static_guard_013dfe90()
{
    bind_static<guard_of_013dfe90, pointer_of_013dfe90, storage_of_013dfe90>();
}

extern "C" void bb_frame_timing_static_guard_013dfec0()
{
    bind_static<guard_of_013dfec0, pointer_of_013dfec0, storage_of_013dfec0>();
}

extern "C" void bb_frame_timing_static_guard_013e0300()
{
    bind_static<guard_of_013e0300, pointer_of_013e0300, storage_of_013e0300>();
}

extern "C" void bb_frame_timing_static_guard_013e0330()
{
    bind_static<guard_of_013e0330, pointer_of_013e0330, storage_of_013e0330>();
}

extern "C" void bb_frame_timing_static_guard_013e0360()
{
    bind_static<guard_of_013e0360, pointer_of_013e0360, storage_of_013e0360>();
}

extern "C" void bb_frame_timing_static_guard_013e07e0()
{
    bind_static<guard_of_013e07e0, pointer_of_013e07e0, storage_of_013e07e0>();
}

extern "C" void bb_frame_timing_static_guard_013e0810()
{
    bind_static<guard_of_013e0810, pointer_of_013e0810, storage_of_013e0810>();
}

extern "C" void bb_frame_timing_static_guard_013e0840()
{
    bind_static<guard_of_013e0840, pointer_of_013e0840, storage_of_013e0840>();
}

extern "C" void bb_frame_timing_static_guard_013e09e0()
{
    bind_static<guard_of_013e09e0, pointer_of_013e09e0, storage_of_013e09e0>();
}

extern "C" void bb_frame_timing_static_guard_013e0a10()
{
    bind_static<guard_of_013e0a10, pointer_of_013e0a10, storage_of_013e0a10>();
}

extern "C" void bb_frame_timing_static_guard_013e0a40()
{
    bind_static<guard_of_013e0a40, pointer_of_013e0a40, storage_of_013e0a40>();
}

extern "C" void bb_frame_timing_static_guard_013e0b10()
{
    bind_static<guard_of_013e0b10, pointer_of_013e0b10, storage_of_013e0b10>();
}

extern "C" void bb_frame_timing_static_guard_013e0b40()
{
    bind_static<guard_of_013e0b40, pointer_of_013e0b40, storage_of_013e0b40>();
}

extern "C" void bb_frame_timing_static_guard_013e0b70()
{
    bind_static<guard_of_013e0b70, pointer_of_013e0b70, storage_of_013e0b70>();
}

extern "C" void bb_frame_timing_static_guard_013e1010()
{
    bind_static<guard_of_013e1010, pointer_of_013e1010, storage_of_013e1010>();
}

extern "C" void bb_frame_timing_static_guard_013e1040()
{
    bind_static<guard_of_013e1040, pointer_of_013e1040, storage_of_013e1040>();
}

extern "C" void bb_frame_timing_static_guard_013e1070()
{
    bind_static<guard_of_013e1070, pointer_of_013e1070, storage_of_013e1070>();
}

extern "C" void bb_frame_timing_static_guard_013e1360()
{
    bind_static<guard_of_013e1360, pointer_of_013e1360, storage_of_013e1360>();
}

extern "C" void bb_frame_timing_static_guard_013e1390()
{
    bind_static<guard_of_013e1390, pointer_of_013e1390, storage_of_013e1390>();
}

extern "C" void bb_frame_timing_static_guard_013e13c0()
{
    bind_static<guard_of_013e13c0, pointer_of_013e13c0, storage_of_013e13c0>();
}

extern "C" void bb_frame_timing_static_guard_013e1a50()
{
    bind_static<guard_of_013e1a50, pointer_of_013e1a50, storage_of_013e1a50>();
}

extern "C" void bb_frame_timing_static_guard_013e1a80()
{
    bind_static<guard_of_013e1a80, pointer_of_013e1a80, storage_of_013e1a80>();
}

extern "C" void bb_frame_timing_static_guard_013e1ab0()
{
    bind_static<guard_of_013e1ab0, pointer_of_013e1ab0, storage_of_013e1ab0>();
}

extern "C" void bb_frame_timing_static_guard_013e1da0()
{
    bind_static<guard_of_013e1da0, pointer_of_013e1da0, storage_of_013e1da0>();
}

extern "C" void bb_frame_timing_static_guard_013e1dd0()
{
    bind_static<guard_of_013e1dd0, pointer_of_013e1dd0, storage_of_013e1dd0>();
}

extern "C" void bb_frame_timing_static_guard_013e1e00()
{
    bind_static<guard_of_013e1e00, pointer_of_013e1e00, storage_of_013e1e00>();
}

extern "C" void bb_frame_timing_static_guard_013e1f80()
{
    bind_static<guard_of_013e1f80, pointer_of_013e1f80, storage_of_013e1f80>();
}

extern "C" void bb_frame_timing_static_guard_013e1fb0()
{
    bind_static<guard_of_013e1fb0, pointer_of_013e1fb0, storage_of_013e1fb0>();
}

extern "C" void bb_frame_timing_static_guard_013e1fe0()
{
    bind_static<guard_of_013e1fe0, pointer_of_013e1fe0, storage_of_013e1fe0>();
}

extern "C" void bb_frame_timing_static_guard_013e25d0()
{
    bind_static<guard_of_013e25d0, pointer_of_013e25d0, storage_of_013e25d0>();
}

extern "C" void bb_frame_timing_static_guard_013e2600()
{
    bind_static<guard_of_013e2600, pointer_of_013e2600, storage_of_013e2600>();
}

extern "C" void bb_frame_timing_static_guard_013e2630()
{
    bind_static<guard_of_013e2630, pointer_of_013e2630, storage_of_013e2630>();
}

extern "C" void bb_frame_timing_static_guard_013e28c0()
{
    bind_static<guard_of_013e28c0, pointer_of_013e28c0, storage_of_013e28c0>();
}

extern "C" void bb_frame_timing_static_guard_013e28f0()
{
    bind_static<guard_of_013e28f0, pointer_of_013e28f0, storage_of_013e28f0>();
}

extern "C" void bb_frame_timing_static_guard_013e2920()
{
    bind_static<guard_of_013e2920, pointer_of_013e2920, storage_of_013e2920>();
}

extern "C" void bb_frame_timing_static_guard_013e2e80()
{
    bind_static<guard_of_013e2e80, pointer_of_013e2e80, storage_of_013e2e80>();
}

extern "C" void bb_frame_timing_static_guard_013e2eb0()
{
    bind_static<guard_of_013e2eb0, pointer_of_013e2eb0, storage_of_013e2eb0>();
}

extern "C" void bb_frame_timing_static_guard_013e2ee0()
{
    bind_static<guard_of_013e2ee0, pointer_of_013e2ee0, storage_of_013e2ee0>();
}

extern "C" void bb_frame_timing_static_guard_013e3830()
{
    bind_static<guard_of_013e3830, pointer_of_013e3830, storage_of_013e3830>();
}

extern "C" void bb_frame_timing_static_guard_013e3860()
{
    bind_static<guard_of_013e3860, pointer_of_013e3860, storage_of_013e3860>();
}

extern "C" void bb_frame_timing_static_guard_013e3890()
{
    bind_static<guard_of_013e3890, pointer_of_013e3890, storage_of_013e3890>();
}

extern "C" void bb_frame_timing_static_guard_013e39e0()
{
    bind_static<guard_of_013e39e0, pointer_of_013e39e0, storage_of_013e39e0>();
}

extern "C" void bb_frame_timing_static_guard_013e3a10()
{
    bind_static<guard_of_013e3a10, pointer_of_013e3a10, storage_of_013e3a10>();
}

extern "C" void bb_frame_timing_static_guard_013e3a40()
{
    bind_static<guard_of_013e3a40, pointer_of_013e3a40, storage_of_013e3a40>();
}

extern "C" void bb_frame_timing_static_guard_013e3c80()
{
    bind_static<guard_of_013e3c80, pointer_of_013e3c80, storage_of_013e3c80>();
}

extern "C" void bb_frame_timing_static_guard_013e3cb0()
{
    bind_static<guard_of_013e3cb0, pointer_of_013e3cb0, storage_of_013e3cb0>();
}

extern "C" void bb_frame_timing_static_guard_013e3ce0()
{
    bind_static<guard_of_013e3ce0, pointer_of_013e3ce0, storage_of_013e3ce0>();
}

extern "C" void bb_frame_timing_static_guard_013e49c0()
{
    bind_static<guard_of_013e49c0, pointer_of_013e49c0, storage_of_013e49c0>();
}

extern "C" void bb_frame_timing_static_guard_013e49f0()
{
    bind_static<guard_of_013e49f0, pointer_of_013e49f0, storage_of_013e49f0>();
}

extern "C" void bb_frame_timing_static_guard_013e4a20()
{
    bind_static<guard_of_013e4a20, pointer_of_013e4a20, storage_of_013e4a20>();
}

extern "C" void bb_frame_timing_static_guard_013e5b40()
{
    bind_static<guard_of_013e5b40, pointer_of_013e5b40, storage_of_013e5b40>();
}

extern "C" void bb_frame_timing_static_guard_013e5b70()
{
    bind_static<guard_of_013e5b70, pointer_of_013e5b70, storage_of_013e5b70>();
}

extern "C" void bb_frame_timing_static_guard_013e5ba0()
{
    bind_static<guard_of_013e5ba0, pointer_of_013e5ba0, storage_of_013e5ba0>();
}

extern "C" void bb_frame_timing_static_guard_013e5c50()
{
    bind_static<guard_of_013e5c50, pointer_of_013e5c50, storage_of_013e5c50>();
}

extern "C" void bb_frame_timing_static_guard_013e5c80()
{
    bind_static<guard_of_013e5c80, pointer_of_013e5c80, storage_of_013e5c80>();
}

extern "C" void bb_frame_timing_static_guard_013e5cb0()
{
    bind_static<guard_of_013e5cb0, pointer_of_013e5cb0, storage_of_013e5cb0>();
}

extern "C" void bb_frame_timing_static_guard_013e6700()
{
    bind_static<guard_of_013e6700, pointer_of_013e6700, storage_of_013e6700>();
}

extern "C" void bb_frame_timing_static_guard_013e6730()
{
    bind_static<guard_of_013e6730, pointer_of_013e6730, storage_of_013e6730>();
}

extern "C" void bb_frame_timing_static_guard_013e6760()
{
    bind_static<guard_of_013e6760, pointer_of_013e6760, storage_of_013e6760>();
}

extern "C" void bb_frame_timing_static_guard_013e6dc0()
{
    bind_static<guard_of_013e6dc0, pointer_of_013e6dc0, storage_of_013e6dc0>();
}

extern "C" void bb_frame_timing_static_guard_013e6df0()
{
    bind_static<guard_of_013e6df0, pointer_of_013e6df0, storage_of_013e6df0>();
}

extern "C" void bb_frame_timing_static_guard_013e6e20()
{
    bind_static<guard_of_013e6e20, pointer_of_013e6e20, storage_of_013e6e20>();
}

extern "C" void bb_frame_timing_static_guard_013e7510()
{
    bind_static<guard_of_013e7510, pointer_of_013e7510, storage_of_013e7510>();
}

extern "C" void bb_frame_timing_static_guard_013e7540()
{
    bind_static<guard_of_013e7540, pointer_of_013e7540, storage_of_013e7540>();
}

extern "C" void bb_frame_timing_static_guard_013e7570()
{
    bind_static<guard_of_013e7570, pointer_of_013e7570, storage_of_013e7570>();
}

extern "C" void bb_frame_timing_static_guard_013e7b30()
{
    bind_static<guard_of_013e7b30, pointer_of_013e7b30, storage_of_013e7b30>();
}

extern "C" void bb_frame_timing_static_guard_013e7b60()
{
    bind_static<guard_of_013e7b60, pointer_of_013e7b60, storage_of_013e7b60>();
}

extern "C" void bb_frame_timing_static_guard_013e7b90()
{
    bind_static<guard_of_013e7b90, pointer_of_013e7b90, storage_of_013e7b90>();
}

extern "C" void bb_frame_timing_static_guard_013e7ef0()
{
    bind_static<guard_of_013e7ef0, pointer_of_013e7ef0, storage_of_013e7ef0>();
}

extern "C" void bb_frame_timing_static_guard_013e7f20()
{
    bind_static<guard_of_013e7f20, pointer_of_013e7f20, storage_of_013e7f20>();
}

extern "C" void bb_frame_timing_static_guard_013e7f50()
{
    bind_static<guard_of_013e7f50, pointer_of_013e7f50, storage_of_013e7f50>();
}

extern "C" void bb_frame_timing_static_guard_013e8260()
{
    bind_static<guard_of_013e8260, pointer_of_013e8260, storage_of_013e8260>();
}

extern "C" void bb_frame_timing_static_guard_013e8290()
{
    bind_static<guard_of_013e8290, pointer_of_013e8290, storage_of_013e8290>();
}

extern "C" void bb_frame_timing_static_guard_013e82c0()
{
    bind_static<guard_of_013e82c0, pointer_of_013e82c0, storage_of_013e82c0>();
}

extern "C" void bb_frame_timing_static_guard_013e8940()
{
    bind_static<guard_of_013e8940, pointer_of_013e8940, storage_of_013e8940>();
}

extern "C" void bb_frame_timing_static_guard_013e8970()
{
    bind_static<guard_of_013e8970, pointer_of_013e8970, storage_of_013e8970>();
}

extern "C" void bb_frame_timing_static_guard_013e89a0()
{
    bind_static<guard_of_013e89a0, pointer_of_013e89a0, storage_of_013e89a0>();
}

extern "C" void bb_frame_timing_static_guard_013e9da0()
{
    bind_static<guard_of_013e9da0, pointer_of_013e9da0, storage_of_013e9da0>();
}

extern "C" void bb_frame_timing_static_guard_013e9dd0()
{
    bind_static<guard_of_013e9dd0, pointer_of_013e9dd0, storage_of_013e9dd0>();
}

extern "C" void bb_frame_timing_static_guard_013e9e00()
{
    bind_static<guard_of_013e9e00, pointer_of_013e9e00, storage_of_013e9e00>();
}

extern "C" void bb_frame_timing_static_guard_013e9ef0()
{
    bind_static<guard_of_013e9ef0, pointer_of_013e9ef0, storage_of_013e9ef0>();
}

extern "C" void bb_frame_timing_static_guard_013e9f20()
{
    bind_static<guard_of_013e9f20, pointer_of_013e9f20, storage_of_013e9f20>();
}

extern "C" void bb_frame_timing_static_guard_013e9f50()
{
    bind_static<guard_of_013e9f50, pointer_of_013e9f50, storage_of_013e9f50>();
}

extern "C" void bb_frame_timing_static_guard_013edf80()
{
    bind_static<guard_of_013edf80, pointer_of_013edf80, storage_of_013edf80>();
}

extern "C" void bb_frame_timing_static_guard_013edfb0()
{
    bind_static<guard_of_013edfb0, pointer_of_013edfb0, storage_of_013edfb0>();
}

extern "C" void bb_frame_timing_static_guard_013edfe0()
{
    bind_static<guard_of_013edfe0, pointer_of_013edfe0, storage_of_013edfe0>();
}

extern "C" void bb_frame_timing_static_guard_013f2140()
{
    bind_static<guard_of_013f2140, pointer_of_013f2140, storage_of_013f2140>();
}

extern "C" void bb_frame_timing_static_guard_013f2170()
{
    bind_static<guard_of_013f2170, pointer_of_013f2170, storage_of_013f2170>();
}

extern "C" void bb_frame_timing_static_guard_013f21a0()
{
    bind_static<guard_of_013f21a0, pointer_of_013f21a0, storage_of_013f21a0>();
}

extern "C" void bb_frame_timing_static_guard_013f4af0()
{
    bind_static<guard_of_013f4af0, pointer_of_013f4af0, storage_of_013f4af0>();
}

extern "C" void bb_frame_timing_static_guard_013f4b20()
{
    bind_static<guard_of_013f4b20, pointer_of_013f4b20, storage_of_013f4b20>();
}

extern "C" void bb_frame_timing_static_guard_013f4b50()
{
    bind_static<guard_of_013f4b50, pointer_of_013f4b50, storage_of_013f4b50>();
}

extern "C" void bb_frame_timing_static_guard_013f4de0()
{
    bind_static<guard_of_013f4de0, pointer_of_013f4de0, storage_of_013f4de0>();
}

extern "C" void bb_frame_timing_static_guard_013f4e10()
{
    bind_static<guard_of_013f4e10, pointer_of_013f4e10, storage_of_013f4e10>();
}

extern "C" void bb_frame_timing_static_guard_013f4e40()
{
    bind_static<guard_of_013f4e40, pointer_of_013f4e40, storage_of_013f4e40>();
}

extern "C" void bb_frame_timing_static_guard_013f5c30()
{
    bind_static<guard_of_013f5c30, pointer_of_013f5c30, storage_of_013f5c30>();
}

extern "C" void bb_frame_timing_static_guard_013f5c60()
{
    bind_static<guard_of_013f5c60, pointer_of_013f5c60, storage_of_013f5c60>();
}

extern "C" void bb_frame_timing_static_guard_013f5c90()
{
    bind_static<guard_of_013f5c90, pointer_of_013f5c90, storage_of_013f5c90>();
}

extern "C" void bb_frame_timing_static_guard_013f6a30()
{
    bind_static<guard_of_013f6a30, pointer_of_013f6a30, storage_of_013f6a30>();
}

extern "C" void bb_frame_timing_static_guard_013f6a60()
{
    bind_static<guard_of_013f6a60, pointer_of_013f6a60, storage_of_013f6a60>();
}

extern "C" void bb_frame_timing_static_guard_013f6a90()
{
    bind_static<guard_of_013f6a90, pointer_of_013f6a90, storage_of_013f6a90>();
}

extern "C" void bb_frame_timing_static_guard_013f8cc0()
{
    bind_static<guard_of_013f8cc0, pointer_of_013f8cc0, storage_of_013f8cc0>();
}

extern "C" void bb_frame_timing_static_guard_013f8cf0()
{
    bind_static<guard_of_013f8cf0, pointer_of_013f8cf0, storage_of_013f8cf0>();
}

extern "C" void bb_frame_timing_static_guard_013f8d20()
{
    bind_static<guard_of_013f8d20, pointer_of_013f8d20, storage_of_013f8d20>();
}

extern "C" void bb_frame_timing_static_guard_013f9a00()
{
    bind_static<guard_of_013f9a00, pointer_of_013f9a00, storage_of_013f9a00>();
}

extern "C" void bb_frame_timing_static_guard_013f9a30()
{
    bind_static<guard_of_013f9a30, pointer_of_013f9a30, storage_of_013f9a30>();
}

extern "C" void bb_frame_timing_static_guard_013f9a60()
{
    bind_static<guard_of_013f9a60, pointer_of_013f9a60, storage_of_013f9a60>();
}

extern "C" void bb_frame_timing_static_guard_013fe5f0()
{
    bind_static<guard_of_013fe5f0, pointer_of_013fe5f0, storage_of_013fe5f0>();
}

extern "C" void bb_frame_timing_static_guard_013fe620()
{
    bind_static<guard_of_013fe620, pointer_of_013fe620, storage_of_013fe620>();
}

extern "C" void bb_frame_timing_static_guard_013fe650()
{
    bind_static<guard_of_013fe650, pointer_of_013fe650, storage_of_013fe650>();
}

extern "C" void bb_frame_timing_static_guard_013ff290()
{
    bind_static<guard_of_013ff290, pointer_of_013ff290, storage_of_013ff290>();
}

extern "C" void bb_frame_timing_static_guard_013ff2c0()
{
    bind_static<guard_of_013ff2c0, pointer_of_013ff2c0, storage_of_013ff2c0>();
}

extern "C" void bb_frame_timing_static_guard_013ff2f0()
{
    bind_static<guard_of_013ff2f0, pointer_of_013ff2f0, storage_of_013ff2f0>();
}

extern "C" void bb_frame_timing_static_guard_013ffe50()
{
    bind_static<guard_of_013ffe50, pointer_of_013ffe50, storage_of_013ffe50>();
}

extern "C" void bb_frame_timing_static_guard_013ffe80()
{
    bind_static<guard_of_013ffe80, pointer_of_013ffe80, storage_of_013ffe80>();
}

extern "C" void bb_frame_timing_static_guard_013ffeb0()
{
    bind_static<guard_of_013ffeb0, pointer_of_013ffeb0, storage_of_013ffeb0>();
}

extern "C" void bb_frame_timing_static_guard_01400740()
{
    bind_static<guard_of_01400740, pointer_of_01400740, storage_of_01400740>();
}

extern "C" void bb_frame_timing_static_guard_01400770()
{
    bind_static<guard_of_01400770, pointer_of_01400770, storage_of_01400770>();
}

extern "C" void bb_frame_timing_static_guard_014007a0()
{
    bind_static<guard_of_014007a0, pointer_of_014007a0, storage_of_014007a0>();
}

extern "C" void bb_frame_timing_static_guard_01400860()
{
    bind_static<guard_of_01400860, pointer_of_01400860, storage_of_01400860>();
}

extern "C" void bb_frame_timing_static_guard_01400890()
{
    bind_static<guard_of_01400890, pointer_of_01400890, storage_of_01400890>();
}

extern "C" void bb_frame_timing_static_guard_014008c0()
{
    bind_static<guard_of_014008c0, pointer_of_014008c0, storage_of_014008c0>();
}

extern "C" void bb_frame_timing_static_guard_01401500()
{
    bind_static<guard_of_01401500, pointer_of_01401500, storage_of_01401500>();
}

extern "C" void bb_frame_timing_static_guard_01401530()
{
    bind_static<guard_of_01401530, pointer_of_01401530, storage_of_01401530>();
}

extern "C" void bb_frame_timing_static_guard_01401560()
{
    bind_static<guard_of_01401560, pointer_of_01401560, storage_of_01401560>();
}

extern "C" void bb_frame_timing_static_guard_01401b20()
{
    bind_static<guard_of_01401b20, pointer_of_01401b20, storage_of_01401b20>();
}

extern "C" void bb_frame_timing_static_guard_01401b50()
{
    bind_static<guard_of_01401b50, pointer_of_01401b50, storage_of_01401b50>();
}

extern "C" void bb_frame_timing_static_guard_01401b80()
{
    bind_static<guard_of_01401b80, pointer_of_01401b80, storage_of_01401b80>();
}

extern "C" void bb_frame_timing_static_guard_01401e30()
{
    bind_static<guard_of_01401e30, pointer_of_01401e30, storage_of_01401e30>();
}

extern "C" void bb_frame_timing_static_guard_01401e60()
{
    bind_static<guard_of_01401e60, pointer_of_01401e60, storage_of_01401e60>();
}

extern "C" void bb_frame_timing_static_guard_01401e90()
{
    bind_static<guard_of_01401e90, pointer_of_01401e90, storage_of_01401e90>();
}

extern "C" void bb_frame_timing_static_guard_01401fb0()
{
    bind_static<guard_of_01401fb0, pointer_of_01401fb0, storage_of_01401fb0>();
}

extern "C" void bb_frame_timing_static_guard_01401fe0()
{
    bind_static<guard_of_01401fe0, pointer_of_01401fe0, storage_of_01401fe0>();
}

extern "C" void bb_frame_timing_static_guard_01402010()
{
    bind_static<guard_of_01402010, pointer_of_01402010, storage_of_01402010>();
}

extern "C" void bb_frame_timing_static_guard_01403810()
{
    bind_static<guard_of_01403810, pointer_of_01403810, storage_of_01403810>();
}

extern "C" void bb_frame_timing_static_guard_01403840()
{
    bind_static<guard_of_01403840, pointer_of_01403840, storage_of_01403840>();
}

extern "C" void bb_frame_timing_static_guard_01403870()
{
    bind_static<guard_of_01403870, pointer_of_01403870, storage_of_01403870>();
}

extern "C" void bb_frame_timing_static_guard_0140a7a0()
{
    bind_static<guard_of_0140a7a0, pointer_of_0140a7a0, storage_of_0140a7a0>();
}

extern "C" void bb_frame_timing_static_guard_0140a7d0()
{
    bind_static<guard_of_0140a7d0, pointer_of_0140a7d0, storage_of_0140a7d0>();
}

extern "C" void bb_frame_timing_static_guard_0140a800()
{
    bind_static<guard_of_0140a800, pointer_of_0140a800, storage_of_0140a800>();
}

extern "C" void bb_frame_timing_static_guard_0140b410()
{
    bind_static<guard_of_0140b410, pointer_of_0140b410, storage_of_0140b410>();
}

extern "C" void bb_frame_timing_static_guard_0140b440()
{
    bind_static<guard_of_0140b440, pointer_of_0140b440, storage_of_0140b440>();
}

extern "C" void bb_frame_timing_static_guard_0140b470()
{
    bind_static<guard_of_0140b470, pointer_of_0140b470, storage_of_0140b470>();
}

extern "C" void bb_frame_timing_static_guard_0140b710()
{
    bind_static<guard_of_0140b710, pointer_of_0140b710, storage_of_0140b710>();
}

extern "C" void bb_frame_timing_static_guard_0140b740()
{
    bind_static<guard_of_0140b740, pointer_of_0140b740, storage_of_0140b740>();
}

extern "C" void bb_frame_timing_static_guard_0140b770()
{
    bind_static<guard_of_0140b770, pointer_of_0140b770, storage_of_0140b770>();
}

extern "C" void bb_frame_timing_static_guard_0140cd80()
{
    bind_static<guard_of_0140cd80, pointer_of_0140cd80, storage_of_0140cd80>();
}

extern "C" void bb_frame_timing_static_guard_0140cdb0()
{
    bind_static<guard_of_0140cdb0, pointer_of_0140cdb0, storage_of_0140cdb0>();
}

extern "C" void bb_frame_timing_static_guard_0140cde0()
{
    bind_static<guard_of_0140cde0, pointer_of_0140cde0, storage_of_0140cde0>();
}

extern "C" void bb_frame_timing_static_guard_0140ce90()
{
    bind_static<guard_of_0140ce90, pointer_of_0140ce90, storage_of_0140ce90>();
}

extern "C" void bb_frame_timing_static_guard_0140cec0()
{
    bind_static<guard_of_0140cec0, pointer_of_0140cec0, storage_of_0140cec0>();
}

extern "C" void bb_frame_timing_static_guard_0140cef0()
{
    bind_static<guard_of_0140cef0, pointer_of_0140cef0, storage_of_0140cef0>();
}

extern "C" void bb_frame_timing_static_guard_0140d300()
{
    bind_static<guard_of_0140d300, pointer_of_0140d300, storage_of_0140d300>();
}

extern "C" void bb_frame_timing_static_guard_0140d330()
{
    bind_static<guard_of_0140d330, pointer_of_0140d330, storage_of_0140d330>();
}

extern "C" void bb_frame_timing_static_guard_0140d360()
{
    bind_static<guard_of_0140d360, pointer_of_0140d360, storage_of_0140d360>();
}

extern "C" void bb_frame_timing_static_guard_0140def0()
{
    bind_static<guard_of_0140def0, pointer_of_0140def0, storage_of_0140def0>();
}

extern "C" void bb_frame_timing_static_guard_0140df20()
{
    bind_static<guard_of_0140df20, pointer_of_0140df20, storage_of_0140df20>();
}

extern "C" void bb_frame_timing_static_guard_0140df50()
{
    bind_static<guard_of_0140df50, pointer_of_0140df50, storage_of_0140df50>();
}

extern "C" void bb_frame_timing_static_guard_0140ea50()
{
    bind_static<guard_of_0140ea50, pointer_of_0140ea50, storage_of_0140ea50>();
}

extern "C" void bb_frame_timing_static_guard_0140ea80()
{
    bind_static<guard_of_0140ea80, pointer_of_0140ea80, storage_of_0140ea80>();
}

extern "C" void bb_frame_timing_static_guard_0140eab0()
{
    bind_static<guard_of_0140eab0, pointer_of_0140eab0, storage_of_0140eab0>();
}

extern "C" void bb_frame_timing_static_guard_0140f090()
{
    bind_static<guard_of_0140f090, pointer_of_0140f090, storage_of_0140f090>();
}

extern "C" void bb_frame_timing_static_guard_0140f0c0()
{
    bind_static<guard_of_0140f0c0, pointer_of_0140f0c0, storage_of_0140f0c0>();
}

extern "C" void bb_frame_timing_static_guard_0140f0f0()
{
    bind_static<guard_of_0140f0f0, pointer_of_0140f0f0, storage_of_0140f0f0>();
}

extern "C" void bb_frame_timing_static_guard_0140f5c0()
{
    bind_static<guard_of_0140f5c0, pointer_of_0140f5c0, storage_of_0140f5c0>();
}

extern "C" void bb_frame_timing_static_guard_0140f5f0()
{
    bind_static<guard_of_0140f5f0, pointer_of_0140f5f0, storage_of_0140f5f0>();
}

extern "C" void bb_frame_timing_static_guard_0140f620()
{
    bind_static<guard_of_0140f620, pointer_of_0140f620, storage_of_0140f620>();
}

extern "C" void bb_frame_timing_static_guard_0140f690()
{
    bind_static<guard_of_0140f690, pointer_of_0140f690, storage_of_0140f690>();
}

extern "C" void bb_frame_timing_static_guard_0140f6c0()
{
    bind_static<guard_of_0140f6c0, pointer_of_0140f6c0, storage_of_0140f6c0>();
}

extern "C" void bb_frame_timing_static_guard_0140f6f0()
{
    bind_static<guard_of_0140f6f0, pointer_of_0140f6f0, storage_of_0140f6f0>();
}

extern "C" void bb_frame_timing_static_guard_0140fd10()
{
    bind_static<guard_of_0140fd10, pointer_of_0140fd10, storage_of_0140fd10>();
}

extern "C" void bb_frame_timing_static_guard_0140fd40()
{
    bind_static<guard_of_0140fd40, pointer_of_0140fd40, storage_of_0140fd40>();
}

extern "C" void bb_frame_timing_static_guard_0140fd70()
{
    bind_static<guard_of_0140fd70, pointer_of_0140fd70, storage_of_0140fd70>();
}

extern "C" void bb_frame_timing_static_guard_01410030()
{
    bind_static<guard_of_01410030, pointer_of_01410030, storage_of_01410030>();
}

extern "C" void bb_frame_timing_static_guard_01410060()
{
    bind_static<guard_of_01410060, pointer_of_01410060, storage_of_01410060>();
}

extern "C" void bb_frame_timing_static_guard_01410090()
{
    bind_static<guard_of_01410090, pointer_of_01410090, storage_of_01410090>();
}

extern "C" void bb_frame_timing_static_guard_01410750()
{
    bind_static<guard_of_01410750, pointer_of_01410750, storage_of_01410750>();
}

extern "C" void bb_frame_timing_static_guard_01410780()
{
    bind_static<guard_of_01410780, pointer_of_01410780, storage_of_01410780>();
}

extern "C" void bb_frame_timing_static_guard_014107b0()
{
    bind_static<guard_of_014107b0, pointer_of_014107b0, storage_of_014107b0>();
}

extern "C" void bb_frame_timing_static_guard_01411490()
{
    bind_static<guard_of_01411490, pointer_of_01411490, storage_of_01411490>();
}

extern "C" void bb_frame_timing_static_guard_014114c0()
{
    bind_static<guard_of_014114c0, pointer_of_014114c0, storage_of_014114c0>();
}

extern "C" void bb_frame_timing_static_guard_014114f0()
{
    bind_static<guard_of_014114f0, pointer_of_014114f0, storage_of_014114f0>();
}

extern "C" void bb_frame_timing_static_guard_014119e0()
{
    bind_static<guard_of_014119e0, pointer_of_014119e0, storage_of_014119e0>();
}

extern "C" void bb_frame_timing_static_guard_01411a10()
{
    bind_static<guard_of_01411a10, pointer_of_01411a10, storage_of_01411a10>();
}

extern "C" void bb_frame_timing_static_guard_01411a40()
{
    bind_static<guard_of_01411a40, pointer_of_01411a40, storage_of_01411a40>();
}

extern "C" void bb_frame_timing_static_guard_01412430()
{
    bind_static<guard_of_01412430, pointer_of_01412430, storage_of_01412430>();
}

extern "C" void bb_frame_timing_static_guard_01412460()
{
    bind_static<guard_of_01412460, pointer_of_01412460, storage_of_01412460>();
}

extern "C" void bb_frame_timing_static_guard_01412490()
{
    bind_static<guard_of_01412490, pointer_of_01412490, storage_of_01412490>();
}

extern "C" void bb_frame_timing_static_guard_01412df0()
{
    bind_static<guard_of_01412df0, pointer_of_01412df0, storage_of_01412df0>();
}

extern "C" void bb_frame_timing_static_guard_01412e20()
{
    bind_static<guard_of_01412e20, pointer_of_01412e20, storage_of_01412e20>();
}

extern "C" void bb_frame_timing_static_guard_01412e50()
{
    bind_static<guard_of_01412e50, pointer_of_01412e50, storage_of_01412e50>();
}

extern "C" void bb_frame_timing_static_guard_01417530()
{
    bind_static<guard_of_01417530, pointer_of_01417530, storage_of_01417530>();
}

extern "C" void bb_frame_timing_static_guard_01417560()
{
    bind_static<guard_of_01417560, pointer_of_01417560, storage_of_01417560>();
}

extern "C" void bb_frame_timing_static_guard_01417590()
{
    bind_static<guard_of_01417590, pointer_of_01417590, storage_of_01417590>();
}

extern "C" void bb_frame_timing_static_guard_01417a20()
{
    bind_static<guard_of_01417a20, pointer_of_01417a20, storage_of_01417a20>();
}

extern "C" void bb_frame_timing_static_guard_01417a50()
{
    bind_static<guard_of_01417a50, pointer_of_01417a50, storage_of_01417a50>();
}

extern "C" void bb_frame_timing_static_guard_01417a80()
{
    bind_static<guard_of_01417a80, pointer_of_01417a80, storage_of_01417a80>();
}

extern "C" void bb_frame_timing_static_guard_014181d0()
{
    bind_static<guard_of_014181d0, pointer_of_014181d0, storage_of_014181d0>();
}

extern "C" void bb_frame_timing_static_guard_01418200()
{
    bind_static<guard_of_01418200, pointer_of_01418200, storage_of_01418200>();
}

extern "C" void bb_frame_timing_static_guard_01418230()
{
    bind_static<guard_of_01418230, pointer_of_01418230, storage_of_01418230>();
}

extern "C" void bb_frame_timing_static_guard_0141a290()
{
    bind_static<guard_of_0141a290, pointer_of_0141a290, storage_of_0141a290>();
}

extern "C" void bb_frame_timing_static_guard_0141a2c0()
{
    bind_static<guard_of_0141a2c0, pointer_of_0141a2c0, storage_of_0141a2c0>();
}

extern "C" void bb_frame_timing_static_guard_0141a2f0()
{
    bind_static<guard_of_0141a2f0, pointer_of_0141a2f0, storage_of_0141a2f0>();
}

extern "C" void bb_frame_timing_static_guard_0141a560()
{
    bind_static<guard_of_0141a560, pointer_of_0141a560, storage_of_0141a560>();
}

extern "C" void bb_frame_timing_static_guard_0141a590()
{
    bind_static<guard_of_0141a590, pointer_of_0141a590, storage_of_0141a590>();
}

extern "C" void bb_frame_timing_static_guard_0141a5c0()
{
    bind_static<guard_of_0141a5c0, pointer_of_0141a5c0, storage_of_0141a5c0>();
}

extern "C" void bb_frame_timing_static_guard_0141bb90()
{
    bind_static<guard_of_0141bb90, pointer_of_0141bb90, storage_of_0141bb90>();
}

extern "C" void bb_frame_timing_static_guard_0141bbc0()
{
    bind_static<guard_of_0141bbc0, pointer_of_0141bbc0, storage_of_0141bbc0>();
}

extern "C" void bb_frame_timing_static_guard_0141bbf0()
{
    bind_static<guard_of_0141bbf0, pointer_of_0141bbf0, storage_of_0141bbf0>();
}

extern "C" void bb_frame_timing_static_guard_0141bd40()
{
    bind_static<guard_of_0141bd40, pointer_of_0141bd40, storage_of_0141bd40>();
}

extern "C" void bb_frame_timing_static_guard_0141bd70()
{
    bind_static<guard_of_0141bd70, pointer_of_0141bd70, storage_of_0141bd70>();
}

extern "C" void bb_frame_timing_static_guard_0141bda0()
{
    bind_static<guard_of_0141bda0, pointer_of_0141bda0, storage_of_0141bda0>();
}

extern "C" void bb_frame_timing_static_guard_0141bfa0()
{
    bind_static<guard_of_0141bfa0, pointer_of_0141bfa0, storage_of_0141bfa0>();
}

extern "C" void bb_frame_timing_static_guard_0141bfd0()
{
    bind_static<guard_of_0141bfd0, pointer_of_0141bfd0, storage_of_0141bfd0>();
}

extern "C" void bb_frame_timing_static_guard_0141c000()
{
    bind_static<guard_of_0141c000, pointer_of_0141c000, storage_of_0141c000>();
}

extern "C" void bb_frame_timing_static_guard_0141c1d0()
{
    bind_static<guard_of_0141c1d0, pointer_of_0141c1d0, storage_of_0141c1d0>();
}

extern "C" void bb_frame_timing_static_guard_0141c200()
{
    bind_static<guard_of_0141c200, pointer_of_0141c200, storage_of_0141c200>();
}

extern "C" void bb_frame_timing_static_guard_0141c230()
{
    bind_static<guard_of_0141c230, pointer_of_0141c230, storage_of_0141c230>();
}

extern "C" void bb_frame_timing_static_guard_0141c4f0()
{
    bind_static<guard_of_0141c4f0, pointer_of_0141c4f0, storage_of_0141c4f0>();
}

extern "C" void bb_frame_timing_static_guard_0141c520()
{
    bind_static<guard_of_0141c520, pointer_of_0141c520, storage_of_0141c520>();
}

extern "C" void bb_frame_timing_static_guard_0141c550()
{
    bind_static<guard_of_0141c550, pointer_of_0141c550, storage_of_0141c550>();
}

extern "C" void bb_frame_timing_static_guard_0141c800()
{
    bind_static<guard_of_0141c800, pointer_of_0141c800, storage_of_0141c800>();
}

extern "C" void bb_frame_timing_static_guard_0141c830()
{
    bind_static<guard_of_0141c830, pointer_of_0141c830, storage_of_0141c830>();
}

extern "C" void bb_frame_timing_static_guard_0141c860()
{
    bind_static<guard_of_0141c860, pointer_of_0141c860, storage_of_0141c860>();
}

extern "C" void bb_frame_timing_static_guard_0141cb20()
{
    bind_static<guard_of_0141cb20, pointer_of_0141cb20, storage_of_0141cb20>();
}

extern "C" void bb_frame_timing_static_guard_0141cb50()
{
    bind_static<guard_of_0141cb50, pointer_of_0141cb50, storage_of_0141cb50>();
}

extern "C" void bb_frame_timing_static_guard_0141cb80()
{
    bind_static<guard_of_0141cb80, pointer_of_0141cb80, storage_of_0141cb80>();
}

extern "C" void bb_frame_timing_static_guard_0141cf80()
{
    bind_static<guard_of_0141cf80, pointer_of_0141cf80, storage_of_0141cf80>();
}

extern "C" void bb_frame_timing_static_guard_0141cfb0()
{
    bind_static<guard_of_0141cfb0, pointer_of_0141cfb0, storage_of_0141cfb0>();
}

extern "C" void bb_frame_timing_static_guard_0141cfe0()
{
    bind_static<guard_of_0141cfe0, pointer_of_0141cfe0, storage_of_0141cfe0>();
}

extern "C" void bb_frame_timing_static_guard_0141d1b0()
{
    bind_static<guard_of_0141d1b0, pointer_of_0141d1b0, storage_of_0141d1b0>();
}

extern "C" void bb_frame_timing_static_guard_0141d1e0()
{
    bind_static<guard_of_0141d1e0, pointer_of_0141d1e0, storage_of_0141d1e0>();
}

extern "C" void bb_frame_timing_static_guard_0141d210()
{
    bind_static<guard_of_0141d210, pointer_of_0141d210, storage_of_0141d210>();
}

extern "C" void bb_frame_timing_static_guard_0141d4d0()
{
    bind_static<guard_of_0141d4d0, pointer_of_0141d4d0, storage_of_0141d4d0>();
}

extern "C" void bb_frame_timing_static_guard_0141d500()
{
    bind_static<guard_of_0141d500, pointer_of_0141d500, storage_of_0141d500>();
}

extern "C" void bb_frame_timing_static_guard_0141d530()
{
    bind_static<guard_of_0141d530, pointer_of_0141d530, storage_of_0141d530>();
}

extern "C" void bb_frame_timing_static_guard_0141d7e0()
{
    bind_static<guard_of_0141d7e0, pointer_of_0141d7e0, storage_of_0141d7e0>();
}

extern "C" void bb_frame_timing_static_guard_0141d810()
{
    bind_static<guard_of_0141d810, pointer_of_0141d810, storage_of_0141d810>();
}

extern "C" void bb_frame_timing_static_guard_0141d840()
{
    bind_static<guard_of_0141d840, pointer_of_0141d840, storage_of_0141d840>();
}

extern "C" void bb_frame_timing_static_guard_0141da70()
{
    bind_static<guard_of_0141da70, pointer_of_0141da70, storage_of_0141da70>();
}

extern "C" void bb_frame_timing_static_guard_0141daa0()
{
    bind_static<guard_of_0141daa0, pointer_of_0141daa0, storage_of_0141daa0>();
}

extern "C" void bb_frame_timing_static_guard_0141dad0()
{
    bind_static<guard_of_0141dad0, pointer_of_0141dad0, storage_of_0141dad0>();
}

extern "C" void bb_frame_timing_static_guard_0141dc40()
{
    bind_static<guard_of_0141dc40, pointer_of_0141dc40, storage_of_0141dc40>();
}

extern "C" void bb_frame_timing_static_guard_0141dc70()
{
    bind_static<guard_of_0141dc70, pointer_of_0141dc70, storage_of_0141dc70>();
}

extern "C" void bb_frame_timing_static_guard_0141dca0()
{
    bind_static<guard_of_0141dca0, pointer_of_0141dca0, storage_of_0141dca0>();
}

extern "C" void bb_frame_timing_static_guard_0141e320()
{
    bind_static<guard_of_0141e320, pointer_of_0141e320, storage_of_0141e320>();
}

extern "C" void bb_frame_timing_static_guard_0141e350()
{
    bind_static<guard_of_0141e350, pointer_of_0141e350, storage_of_0141e350>();
}

extern "C" void bb_frame_timing_static_guard_0141e380()
{
    bind_static<guard_of_0141e380, pointer_of_0141e380, storage_of_0141e380>();
}

extern "C" void bb_frame_timing_static_guard_0141f080()
{
    bind_static<guard_of_0141f080, pointer_of_0141f080, storage_of_0141f080>();
}

extern "C" void bb_frame_timing_static_guard_0141f0b0()
{
    bind_static<guard_of_0141f0b0, pointer_of_0141f0b0, storage_of_0141f0b0>();
}

extern "C" void bb_frame_timing_static_guard_0141f0e0()
{
    bind_static<guard_of_0141f0e0, pointer_of_0141f0e0, storage_of_0141f0e0>();
}

extern "C" void bb_frame_timing_static_guard_0141f4e0()
{
    bind_static<guard_of_0141f4e0, pointer_of_0141f4e0, storage_of_0141f4e0>();
}

extern "C" void bb_frame_timing_static_guard_0141f510()
{
    bind_static<guard_of_0141f510, pointer_of_0141f510, storage_of_0141f510>();
}

extern "C" void bb_frame_timing_static_guard_0141f540()
{
    bind_static<guard_of_0141f540, pointer_of_0141f540, storage_of_0141f540>();
}

extern "C" void bb_frame_timing_static_guard_01423250()
{
    bind_static<guard_of_01423250, pointer_of_01423250, storage_of_01423250>();
}

extern "C" void bb_frame_timing_static_guard_01423280()
{
    bind_static<guard_of_01423280, pointer_of_01423280, storage_of_01423280>();
}

extern "C" void bb_frame_timing_static_guard_014232b0()
{
    bind_static<guard_of_014232b0, pointer_of_014232b0, storage_of_014232b0>();
}

extern "C" void bb_frame_timing_static_guard_01425f60()
{
    bind_static<guard_of_01425f60, pointer_of_01425f60, storage_of_01425f60>();
}

extern "C" void bb_frame_timing_static_guard_01425f90()
{
    bind_static<guard_of_01425f90, pointer_of_01425f90, storage_of_01425f90>();
}

extern "C" void bb_frame_timing_static_guard_01425fc0()
{
    bind_static<guard_of_01425fc0, pointer_of_01425fc0, storage_of_01425fc0>();
}

extern "C" void bb_frame_timing_static_guard_01426c20()
{
    bind_static<guard_of_01426c20, pointer_of_01426c20, storage_of_01426c20>();
}

extern "C" void bb_frame_timing_static_guard_01426c50()
{
    bind_static<guard_of_01426c50, pointer_of_01426c50, storage_of_01426c50>();
}

extern "C" void bb_frame_timing_static_guard_01426c80()
{
    bind_static<guard_of_01426c80, pointer_of_01426c80, storage_of_01426c80>();
}

extern "C" void bb_frame_timing_static_guard_01426da0()
{
    bind_static<guard_of_01426da0, pointer_of_01426da0, storage_of_01426da0>();
}

extern "C" void bb_frame_timing_static_guard_01426dd0()
{
    bind_static<guard_of_01426dd0, pointer_of_01426dd0, storage_of_01426dd0>();
}

extern "C" void bb_frame_timing_static_guard_01426e00()
{
    bind_static<guard_of_01426e00, pointer_of_01426e00, storage_of_01426e00>();
}

extern "C" void bb_frame_timing_static_guard_01427500()
{
    bind_static<guard_of_01427500, pointer_of_01427500, storage_of_01427500>();
}

extern "C" void bb_frame_timing_static_guard_01427530()
{
    bind_static<guard_of_01427530, pointer_of_01427530, storage_of_01427530>();
}

extern "C" void bb_frame_timing_static_guard_01427560()
{
    bind_static<guard_of_01427560, pointer_of_01427560, storage_of_01427560>();
}

extern "C" void bb_frame_timing_static_guard_014325f0()
{
    bind_static<guard_of_014325f0, pointer_of_014325f0, storage_of_014325f0>();
}

extern "C" void bb_frame_timing_static_guard_01432620()
{
    bind_static<guard_of_01432620, pointer_of_01432620, storage_of_01432620>();
}

extern "C" void bb_frame_timing_static_guard_01432650()
{
    bind_static<guard_of_01432650, pointer_of_01432650, storage_of_01432650>();
}

extern "C" void bb_frame_timing_static_guard_014329c0()
{
    bind_static<guard_of_014329c0, pointer_of_014329c0, storage_of_014329c0>();
}

extern "C" void bb_frame_timing_static_guard_014329f0()
{
    bind_static<guard_of_014329f0, pointer_of_014329f0, storage_of_014329f0>();
}

extern "C" void bb_frame_timing_static_guard_01432a20()
{
    bind_static<guard_of_01432a20, pointer_of_01432a20, storage_of_01432a20>();
}

extern "C" void bb_frame_timing_static_guard_01432ab0()
{
    bind_static<guard_of_01432ab0, pointer_of_01432ab0, storage_of_01432ab0>();
}

extern "C" void bb_frame_timing_static_guard_01432ae0()
{
    bind_static<guard_of_01432ae0, pointer_of_01432ae0, storage_of_01432ae0>();
}

extern "C" void bb_frame_timing_static_guard_01432b10()
{
    bind_static<guard_of_01432b10, pointer_of_01432b10, storage_of_01432b10>();
}

extern "C" void bb_frame_timing_static_guard_01432c10()
{
    bind_static<guard_of_01432c10, pointer_of_01432c10, storage_of_01432c10>();
}

extern "C" void bb_frame_timing_static_guard_01432c40()
{
    bind_static<guard_of_01432c40, pointer_of_01432c40, storage_of_01432c40>();
}

extern "C" void bb_frame_timing_static_guard_01432c70()
{
    bind_static<guard_of_01432c70, pointer_of_01432c70, storage_of_01432c70>();
}

extern "C" void bb_frame_timing_static_guard_01432f80()
{
    bind_static<guard_of_01432f80, pointer_of_01432f80, storage_of_01432f80>();
}

extern "C" void bb_frame_timing_static_guard_01432fb0()
{
    bind_static<guard_of_01432fb0, pointer_of_01432fb0, storage_of_01432fb0>();
}

extern "C" void bb_frame_timing_static_guard_01432fe0()
{
    bind_static<guard_of_01432fe0, pointer_of_01432fe0, storage_of_01432fe0>();
}

extern "C" void bb_frame_timing_static_guard_014332b0()
{
    bind_static<guard_of_014332b0, pointer_of_014332b0, storage_of_014332b0>();
}

extern "C" void bb_frame_timing_static_guard_014332e0()
{
    bind_static<guard_of_014332e0, pointer_of_014332e0, storage_of_014332e0>();
}

extern "C" void bb_frame_timing_static_guard_01433310()
{
    bind_static<guard_of_01433310, pointer_of_01433310, storage_of_01433310>();
}

extern "C" void bb_frame_timing_static_guard_014333b0()
{
    bind_static<guard_of_014333b0, pointer_of_014333b0, storage_of_014333b0>();
}

extern "C" void bb_frame_timing_static_guard_014333e0()
{
    bind_static<guard_of_014333e0, pointer_of_014333e0, storage_of_014333e0>();
}

extern "C" void bb_frame_timing_static_guard_01433410()
{
    bind_static<guard_of_01433410, pointer_of_01433410, storage_of_01433410>();
}

extern "C" void bb_frame_timing_static_guard_01433700()
{
    bind_static<guard_of_01433700, pointer_of_01433700, storage_of_01433700>();
}

extern "C" void bb_frame_timing_static_guard_01433730()
{
    bind_static<guard_of_01433730, pointer_of_01433730, storage_of_01433730>();
}

extern "C" void bb_frame_timing_static_guard_01433760()
{
    bind_static<guard_of_01433760, pointer_of_01433760, storage_of_01433760>();
}

extern "C" void bb_frame_timing_static_guard_01433a60()
{
    bind_static<guard_of_01433a60, pointer_of_01433a60, storage_of_01433a60>();
}

extern "C" void bb_frame_timing_static_guard_01433a90()
{
    bind_static<guard_of_01433a90, pointer_of_01433a90, storage_of_01433a90>();
}

extern "C" void bb_frame_timing_static_guard_01433ac0()
{
    bind_static<guard_of_01433ac0, pointer_of_01433ac0, storage_of_01433ac0>();
}

extern "C" void bb_frame_timing_static_guard_01434980()
{
    bind_static<guard_of_01434980, pointer_of_01434980, storage_of_01434980>();
}

extern "C" void bb_frame_timing_static_guard_014349b0()
{
    bind_static<guard_of_014349b0, pointer_of_014349b0, storage_of_014349b0>();
}

extern "C" void bb_frame_timing_static_guard_014349e0()
{
    bind_static<guard_of_014349e0, pointer_of_014349e0, storage_of_014349e0>();
}

extern "C" void bb_frame_timing_static_guard_01435910()
{
    bind_static<guard_of_01435910, pointer_of_01435910, storage_of_01435910>();
}

extern "C" void bb_frame_timing_static_guard_01435940()
{
    bind_static<guard_of_01435940, pointer_of_01435940, storage_of_01435940>();
}

extern "C" void bb_frame_timing_static_guard_01435970()
{
    bind_static<guard_of_01435970, pointer_of_01435970, storage_of_01435970>();
}

extern "C" void bb_frame_timing_static_guard_01436930()
{
    bind_static<guard_of_01436930, pointer_of_01436930, storage_of_01436930>();
}

extern "C" void bb_frame_timing_static_guard_01436960()
{
    bind_static<guard_of_01436960, pointer_of_01436960, storage_of_01436960>();
}

extern "C" void bb_frame_timing_static_guard_01436990()
{
    bind_static<guard_of_01436990, pointer_of_01436990, storage_of_01436990>();
}

extern "C" void bb_frame_timing_static_guard_01436b60()
{
    bind_static<guard_of_01436b60, pointer_of_01436b60, storage_of_01436b60>();
}

extern "C" void bb_frame_timing_static_guard_01436b90()
{
    bind_static<guard_of_01436b90, pointer_of_01436b90, storage_of_01436b90>();
}

extern "C" void bb_frame_timing_static_guard_01436bc0()
{
    bind_static<guard_of_01436bc0, pointer_of_01436bc0, storage_of_01436bc0>();
}

extern "C" void bb_frame_timing_static_guard_01436e50()
{
    bind_static<guard_of_01436e50, pointer_of_01436e50, storage_of_01436e50>();
}

extern "C" void bb_frame_timing_static_guard_01436e80()
{
    bind_static<guard_of_01436e80, pointer_of_01436e80, storage_of_01436e80>();
}

extern "C" void bb_frame_timing_static_guard_01436eb0()
{
    bind_static<guard_of_01436eb0, pointer_of_01436eb0, storage_of_01436eb0>();
}

extern "C" void bb_frame_timing_static_guard_014371f0()
{
    bind_static<guard_of_014371f0, pointer_of_014371f0, storage_of_014371f0>();
}

extern "C" void bb_frame_timing_static_guard_01437220()
{
    bind_static<guard_of_01437220, pointer_of_01437220, storage_of_01437220>();
}

extern "C" void bb_frame_timing_static_guard_01437250()
{
    bind_static<guard_of_01437250, pointer_of_01437250, storage_of_01437250>();
}

extern "C" void bb_frame_timing_static_guard_01437500()
{
    bind_static<guard_of_01437500, pointer_of_01437500, storage_of_01437500>();
}

extern "C" void bb_frame_timing_static_guard_01437530()
{
    bind_static<guard_of_01437530, pointer_of_01437530, storage_of_01437530>();
}

extern "C" void bb_frame_timing_static_guard_01437560()
{
    bind_static<guard_of_01437560, pointer_of_01437560, storage_of_01437560>();
}

extern "C" void bb_frame_timing_static_guard_01437810()
{
    bind_static<guard_of_01437810, pointer_of_01437810, storage_of_01437810>();
}

extern "C" void bb_frame_timing_static_guard_01437840()
{
    bind_static<guard_of_01437840, pointer_of_01437840, storage_of_01437840>();
}

extern "C" void bb_frame_timing_static_guard_01437870()
{
    bind_static<guard_of_01437870, pointer_of_01437870, storage_of_01437870>();
}

extern "C" void bb_frame_timing_static_guard_01437b20()
{
    bind_static<guard_of_01437b20, pointer_of_01437b20, storage_of_01437b20>();
}

extern "C" void bb_frame_timing_static_guard_01437b50()
{
    bind_static<guard_of_01437b50, pointer_of_01437b50, storage_of_01437b50>();
}

extern "C" void bb_frame_timing_static_guard_01437b80()
{
    bind_static<guard_of_01437b80, pointer_of_01437b80, storage_of_01437b80>();
}

extern "C" void bb_frame_timing_static_guard_01437e30()
{
    bind_static<guard_of_01437e30, pointer_of_01437e30, storage_of_01437e30>();
}

extern "C" void bb_frame_timing_static_guard_01437e60()
{
    bind_static<guard_of_01437e60, pointer_of_01437e60, storage_of_01437e60>();
}

extern "C" void bb_frame_timing_static_guard_01437e90()
{
    bind_static<guard_of_01437e90, pointer_of_01437e90, storage_of_01437e90>();
}

extern "C" void bb_frame_timing_static_guard_01438af0()
{
    bind_static<guard_of_01438af0, pointer_of_01438af0, storage_of_01438af0>();
}

extern "C" void bb_frame_timing_static_guard_01438b20()
{
    bind_static<guard_of_01438b20, pointer_of_01438b20, storage_of_01438b20>();
}

extern "C" void bb_frame_timing_static_guard_01438b50()
{
    bind_static<guard_of_01438b50, pointer_of_01438b50, storage_of_01438b50>();
}

extern "C" void bb_frame_timing_static_guard_014391a0()
{
    bind_static<guard_of_014391a0, pointer_of_014391a0, storage_of_014391a0>();
}

extern "C" void bb_frame_timing_static_guard_014391d0()
{
    bind_static<guard_of_014391d0, pointer_of_014391d0, storage_of_014391d0>();
}

extern "C" void bb_frame_timing_static_guard_01439200()
{
    bind_static<guard_of_01439200, pointer_of_01439200, storage_of_01439200>();
}

extern "C" void bb_frame_timing_static_guard_014393a0()
{
    bind_static<guard_of_014393a0, pointer_of_014393a0, storage_of_014393a0>();
}

extern "C" void bb_frame_timing_static_guard_014393d0()
{
    bind_static<guard_of_014393d0, pointer_of_014393d0, storage_of_014393d0>();
}

extern "C" void bb_frame_timing_static_guard_01439400()
{
    bind_static<guard_of_01439400, pointer_of_01439400, storage_of_01439400>();
}

extern "C" void bb_frame_timing_static_guard_0143b9d0()
{
    bind_static<guard_of_0143b9d0, pointer_of_0143b9d0, storage_of_0143b9d0>();
}

extern "C" void bb_frame_timing_static_guard_0143ba00()
{
    bind_static<guard_of_0143ba00, pointer_of_0143ba00, storage_of_0143ba00>();
}

extern "C" void bb_frame_timing_static_guard_0143ba30()
{
    bind_static<guard_of_0143ba30, pointer_of_0143ba30, storage_of_0143ba30>();
}

extern "C" void bb_frame_timing_static_guard_0143bdf0()
{
    bind_static<guard_of_0143bdf0, pointer_of_0143bdf0, storage_of_0143bdf0>();
}

extern "C" void bb_frame_timing_static_guard_0143be20()
{
    bind_static<guard_of_0143be20, pointer_of_0143be20, storage_of_0143be20>();
}

extern "C" void bb_frame_timing_static_guard_0143be50()
{
    bind_static<guard_of_0143be50, pointer_of_0143be50, storage_of_0143be50>();
}

extern "C" void bb_frame_timing_static_guard_0143bf20()
{
    bind_static<guard_of_0143bf20, pointer_of_0143bf20, storage_of_0143bf20>();
}

extern "C" void bb_frame_timing_static_guard_0143bf50()
{
    bind_static<guard_of_0143bf50, pointer_of_0143bf50, storage_of_0143bf50>();
}

extern "C" void bb_frame_timing_static_guard_0143bf80()
{
    bind_static<guard_of_0143bf80, pointer_of_0143bf80, storage_of_0143bf80>();
}

extern "C" void bb_frame_timing_static_guard_0143ce10()
{
    bind_static<guard_of_0143ce10, pointer_of_0143ce10, storage_of_0143ce10>();
}

extern "C" void bb_frame_timing_static_guard_0143ce40()
{
    bind_static<guard_of_0143ce40, pointer_of_0143ce40, storage_of_0143ce40>();
}

extern "C" void bb_frame_timing_static_guard_0143ce70()
{
    bind_static<guard_of_0143ce70, pointer_of_0143ce70, storage_of_0143ce70>();
}

extern "C" void bb_frame_timing_static_guard_0143d470()
{
    bind_static<guard_of_0143d470, pointer_of_0143d470, storage_of_0143d470>();
}

extern "C" void bb_frame_timing_static_guard_0143d4a0()
{
    bind_static<guard_of_0143d4a0, pointer_of_0143d4a0, storage_of_0143d4a0>();
}

extern "C" void bb_frame_timing_static_guard_0143d4d0()
{
    bind_static<guard_of_0143d4d0, pointer_of_0143d4d0, storage_of_0143d4d0>();
}

extern "C" void bb_frame_timing_static_guard_0143d810()
{
    bind_static<guard_of_0143d810, pointer_of_0143d810, storage_of_0143d810>();
}

extern "C" void bb_frame_timing_static_guard_0143d840()
{
    bind_static<guard_of_0143d840, pointer_of_0143d840, storage_of_0143d840>();
}

extern "C" void bb_frame_timing_static_guard_0143d870()
{
    bind_static<guard_of_0143d870, pointer_of_0143d870, storage_of_0143d870>();
}

extern "C" void bb_frame_timing_static_guard_0143e0e0()
{
    bind_static<guard_of_0143e0e0, pointer_of_0143e0e0, storage_of_0143e0e0>();
}

extern "C" void bb_frame_timing_static_guard_0143e110()
{
    bind_static<guard_of_0143e110, pointer_of_0143e110, storage_of_0143e110>();
}

extern "C" void bb_frame_timing_static_guard_0143e140()
{
    bind_static<guard_of_0143e140, pointer_of_0143e140, storage_of_0143e140>();
}

extern "C" void bb_frame_timing_static_guard_0143e540()
{
    bind_static<guard_of_0143e540, pointer_of_0143e540, storage_of_0143e540>();
}

extern "C" void bb_frame_timing_static_guard_0143e570()
{
    bind_static<guard_of_0143e570, pointer_of_0143e570, storage_of_0143e570>();
}

extern "C" void bb_frame_timing_static_guard_0143e5a0()
{
    bind_static<guard_of_0143e5a0, pointer_of_0143e5a0, storage_of_0143e5a0>();
}

extern "C" void bb_frame_timing_static_guard_0143eff0()
{
    bind_static<guard_of_0143eff0, pointer_of_0143eff0, storage_of_0143eff0>();
}

extern "C" void bb_frame_timing_static_guard_0143f020()
{
    bind_static<guard_of_0143f020, pointer_of_0143f020, storage_of_0143f020>();
}

extern "C" void bb_frame_timing_static_guard_0143f050()
{
    bind_static<guard_of_0143f050, pointer_of_0143f050, storage_of_0143f050>();
}

extern "C" void bb_frame_timing_static_guard_0143f8b0()
{
    bind_static<guard_of_0143f8b0, pointer_of_0143f8b0, storage_of_0143f8b0>();
}

extern "C" void bb_frame_timing_static_guard_0143f8e0()
{
    bind_static<guard_of_0143f8e0, pointer_of_0143f8e0, storage_of_0143f8e0>();
}

extern "C" void bb_frame_timing_static_guard_0143f910()
{
    bind_static<guard_of_0143f910, pointer_of_0143f910, storage_of_0143f910>();
}

extern "C" void bb_frame_timing_static_guard_0143fa30()
{
    bind_static<guard_of_0143fa30, pointer_of_0143fa30, storage_of_0143fa30>();
}

extern "C" void bb_frame_timing_static_guard_0143fa60()
{
    bind_static<guard_of_0143fa60, pointer_of_0143fa60, storage_of_0143fa60>();
}

extern "C" void bb_frame_timing_static_guard_0143fa90()
{
    bind_static<guard_of_0143fa90, pointer_of_0143fa90, storage_of_0143fa90>();
}

extern "C" void bb_frame_timing_static_guard_01440700()
{
    bind_static<guard_of_01440700, pointer_of_01440700, storage_of_01440700>();
}

extern "C" void bb_frame_timing_static_guard_01440730()
{
    bind_static<guard_of_01440730, pointer_of_01440730, storage_of_01440730>();
}

extern "C" void bb_frame_timing_static_guard_01440760()
{
    bind_static<guard_of_01440760, pointer_of_01440760, storage_of_01440760>();
}

extern "C" void bb_frame_timing_static_guard_01440d60()
{
    bind_static<guard_of_01440d60, pointer_of_01440d60, storage_of_01440d60>();
}

extern "C" void bb_frame_timing_static_guard_01440d90()
{
    bind_static<guard_of_01440d90, pointer_of_01440d90, storage_of_01440d90>();
}

extern "C" void bb_frame_timing_static_guard_01440dc0()
{
    bind_static<guard_of_01440dc0, pointer_of_01440dc0, storage_of_01440dc0>();
}

extern "C" void bb_frame_timing_static_guard_014412b0()
{
    bind_static<guard_of_014412b0, pointer_of_014412b0, storage_of_014412b0>();
}

extern "C" void bb_frame_timing_static_guard_014412e0()
{
    bind_static<guard_of_014412e0, pointer_of_014412e0, storage_of_014412e0>();
}

extern "C" void bb_frame_timing_static_guard_01441310()
{
    bind_static<guard_of_01441310, pointer_of_01441310, storage_of_01441310>();
}

extern "C" void bb_frame_timing_static_guard_014415a0()
{
    bind_static<guard_of_014415a0, pointer_of_014415a0, storage_of_014415a0>();
}

extern "C" void bb_frame_timing_static_guard_014415d0()
{
    bind_static<guard_of_014415d0, pointer_of_014415d0, storage_of_014415d0>();
}

extern "C" void bb_frame_timing_static_guard_01441600()
{
    bind_static<guard_of_01441600, pointer_of_01441600, storage_of_01441600>();
}

extern "C" void bb_frame_timing_static_guard_01441870()
{
    bind_static<guard_of_01441870, pointer_of_01441870, storage_of_01441870>();
}

extern "C" void bb_frame_timing_static_guard_014418a0()
{
    bind_static<guard_of_014418a0, pointer_of_014418a0, storage_of_014418a0>();
}

extern "C" void bb_frame_timing_static_guard_014418d0()
{
    bind_static<guard_of_014418d0, pointer_of_014418d0, storage_of_014418d0>();
}

extern "C" void bb_frame_timing_static_guard_014422c0()
{
    bind_static<guard_of_014422c0, pointer_of_014422c0, storage_of_014422c0>();
}

extern "C" void bb_frame_timing_static_guard_014422f0()
{
    bind_static<guard_of_014422f0, pointer_of_014422f0, storage_of_014422f0>();
}

extern "C" void bb_frame_timing_static_guard_01442320()
{
    bind_static<guard_of_01442320, pointer_of_01442320, storage_of_01442320>();
}

extern "C" void bb_frame_timing_static_guard_01444270()
{
    bind_static<guard_of_01444270, pointer_of_01444270, storage_of_01444270>();
}

extern "C" void bb_frame_timing_static_guard_014442a0()
{
    bind_static<guard_of_014442a0, pointer_of_014442a0, storage_of_014442a0>();
}

extern "C" void bb_frame_timing_static_guard_014442d0()
{
    bind_static<guard_of_014442d0, pointer_of_014442d0, storage_of_014442d0>();
}

extern "C" void bb_frame_timing_static_guard_01444a40()
{
    bind_static<guard_of_01444a40, pointer_of_01444a40, storage_of_01444a40>();
}

extern "C" void bb_frame_timing_static_guard_01444a70()
{
    bind_static<guard_of_01444a70, pointer_of_01444a70, storage_of_01444a70>();
}

extern "C" void bb_frame_timing_static_guard_01444aa0()
{
    bind_static<guard_of_01444aa0, pointer_of_01444aa0, storage_of_01444aa0>();
}

extern "C" void bb_frame_timing_static_guard_01444dd0()
{
    bind_static<guard_of_01444dd0, pointer_of_01444dd0, storage_of_01444dd0>();
}

extern "C" void bb_frame_timing_static_guard_01444e00()
{
    bind_static<guard_of_01444e00, pointer_of_01444e00, storage_of_01444e00>();
}

extern "C" void bb_frame_timing_static_guard_01444e30()
{
    bind_static<guard_of_01444e30, pointer_of_01444e30, storage_of_01444e30>();
}

extern "C" void bb_frame_timing_static_guard_014452d0()
{
    bind_static<guard_of_014452d0, pointer_of_014452d0, storage_of_014452d0>();
}

extern "C" void bb_frame_timing_static_guard_01445300()
{
    bind_static<guard_of_01445300, pointer_of_01445300, storage_of_01445300>();
}

extern "C" void bb_frame_timing_static_guard_01445330()
{
    bind_static<guard_of_01445330, pointer_of_01445330, storage_of_01445330>();
}

extern "C" void bb_frame_timing_static_guard_01445820()
{
    bind_static<guard_of_01445820, pointer_of_01445820, storage_of_01445820>();
}

extern "C" void bb_frame_timing_static_guard_01445850()
{
    bind_static<guard_of_01445850, pointer_of_01445850, storage_of_01445850>();
}

extern "C" void bb_frame_timing_static_guard_01445880()
{
    bind_static<guard_of_01445880, pointer_of_01445880, storage_of_01445880>();
}

extern "C" void bb_frame_timing_static_guard_014469b0()
{
    bind_static<guard_of_014469b0, pointer_of_014469b0, storage_of_014469b0>();
}

extern "C" void bb_frame_timing_static_guard_014469e0()
{
    bind_static<guard_of_014469e0, pointer_of_014469e0, storage_of_014469e0>();
}

extern "C" void bb_frame_timing_static_guard_01446a10()
{
    bind_static<guard_of_01446a10, pointer_of_01446a10, storage_of_01446a10>();
}

extern "C" void bb_frame_timing_static_guard_01447e10()
{
    bind_static<guard_of_01447e10, pointer_of_01447e10, storage_of_01447e10>();
}

extern "C" void bb_frame_timing_static_guard_01447e40()
{
    bind_static<guard_of_01447e40, pointer_of_01447e40, storage_of_01447e40>();
}

extern "C" void bb_frame_timing_static_guard_01447e70()
{
    bind_static<guard_of_01447e70, pointer_of_01447e70, storage_of_01447e70>();
}

extern "C" void bb_frame_timing_static_guard_01448390()
{
    bind_static<guard_of_01448390, pointer_of_01448390, storage_of_01448390>();
}

extern "C" void bb_frame_timing_static_guard_014483c0()
{
    bind_static<guard_of_014483c0, pointer_of_014483c0, storage_of_014483c0>();
}

extern "C" void bb_frame_timing_static_guard_014483f0()
{
    bind_static<guard_of_014483f0, pointer_of_014483f0, storage_of_014483f0>();
}

extern "C" void bb_frame_timing_static_guard_014488e0()
{
    bind_static<guard_of_014488e0, pointer_of_014488e0, storage_of_014488e0>();
}

extern "C" void bb_frame_timing_static_guard_01448910()
{
    bind_static<guard_of_01448910, pointer_of_01448910, storage_of_01448910>();
}

extern "C" void bb_frame_timing_static_guard_01448940()
{
    bind_static<guard_of_01448940, pointer_of_01448940, storage_of_01448940>();
}

extern "C" void bb_frame_timing_static_guard_014489f0()
{
    bind_static<guard_of_014489f0, pointer_of_014489f0, storage_of_014489f0>();
}

extern "C" void bb_frame_timing_static_guard_01448a20()
{
    bind_static<guard_of_01448a20, pointer_of_01448a20, storage_of_01448a20>();
}

extern "C" void bb_frame_timing_static_guard_01448a50()
{
    bind_static<guard_of_01448a50, pointer_of_01448a50, storage_of_01448a50>();
}

extern "C" void bb_frame_timing_static_guard_01448ce0()
{
    bind_static<guard_of_01448ce0, pointer_of_01448ce0, storage_of_01448ce0>();
}

extern "C" void bb_frame_timing_static_guard_01448d10()
{
    bind_static<guard_of_01448d10, pointer_of_01448d10, storage_of_01448d10>();
}

extern "C" void bb_frame_timing_static_guard_01448d40()
{
    bind_static<guard_of_01448d40, pointer_of_01448d40, storage_of_01448d40>();
}

extern "C" void bb_frame_timing_static_guard_01449120()
{
    bind_static<guard_of_01449120, pointer_of_01449120, storage_of_01449120>();
}

extern "C" void bb_frame_timing_static_guard_01449150()
{
    bind_static<guard_of_01449150, pointer_of_01449150, storage_of_01449150>();
}

extern "C" void bb_frame_timing_static_guard_01449180()
{
    bind_static<guard_of_01449180, pointer_of_01449180, storage_of_01449180>();
}

extern "C" void bb_frame_timing_static_guard_014493c0()
{
    bind_static<guard_of_014493c0, pointer_of_014493c0, storage_of_014493c0>();
}

extern "C" void bb_frame_timing_static_guard_014493f0()
{
    bind_static<guard_of_014493f0, pointer_of_014493f0, storage_of_014493f0>();
}

extern "C" void bb_frame_timing_static_guard_01449420()
{
    bind_static<guard_of_01449420, pointer_of_01449420, storage_of_01449420>();
}

extern "C" void bb_frame_timing_static_guard_0144a740()
{
    bind_static<guard_of_0144a740, pointer_of_0144a740, storage_of_0144a740>();
}

extern "C" void bb_frame_timing_static_guard_0144a770()
{
    bind_static<guard_of_0144a770, pointer_of_0144a770, storage_of_0144a770>();
}

extern "C" void bb_frame_timing_static_guard_0144a7a0()
{
    bind_static<guard_of_0144a7a0, pointer_of_0144a7a0, storage_of_0144a7a0>();
}

extern "C" void bb_frame_timing_static_guard_0144ae60()
{
    bind_static<guard_of_0144ae60, pointer_of_0144ae60, storage_of_0144ae60>();
}

extern "C" void bb_frame_timing_static_guard_0144ae90()
{
    bind_static<guard_of_0144ae90, pointer_of_0144ae90, storage_of_0144ae90>();
}

extern "C" void bb_frame_timing_static_guard_0144aec0()
{
    bind_static<guard_of_0144aec0, pointer_of_0144aec0, storage_of_0144aec0>();
}

extern "C" void bb_frame_timing_static_guard_0144ba10()
{
    bind_static<guard_of_0144ba10, pointer_of_0144ba10, storage_of_0144ba10>();
}

extern "C" void bb_frame_timing_static_guard_0144ba40()
{
    bind_static<guard_of_0144ba40, pointer_of_0144ba40, storage_of_0144ba40>();
}

extern "C" void bb_frame_timing_static_guard_0144ba70()
{
    bind_static<guard_of_0144ba70, pointer_of_0144ba70, storage_of_0144ba70>();
}

extern "C" void bb_frame_timing_static_guard_01450720()
{
    bind_static<guard_of_01450720, pointer_of_01450720, storage_of_01450720>();
}

extern "C" void bb_frame_timing_static_guard_01450750()
{
    bind_static<guard_of_01450750, pointer_of_01450750, storage_of_01450750>();
}

extern "C" void bb_frame_timing_static_guard_01450780()
{
    bind_static<guard_of_01450780, pointer_of_01450780, storage_of_01450780>();
}

extern "C" void bb_frame_timing_static_guard_01450e10()
{
    bind_static<guard_of_01450e10, pointer_of_01450e10, storage_of_01450e10>();
}

extern "C" void bb_frame_timing_static_guard_01450e40()
{
    bind_static<guard_of_01450e40, pointer_of_01450e40, storage_of_01450e40>();
}

extern "C" void bb_frame_timing_static_guard_01450e70()
{
    bind_static<guard_of_01450e70, pointer_of_01450e70, storage_of_01450e70>();
}

extern "C" void bb_frame_timing_static_guard_014511b0()
{
    bind_static<guard_of_014511b0, pointer_of_014511b0, storage_of_014511b0>();
}

extern "C" void bb_frame_timing_static_guard_014511e0()
{
    bind_static<guard_of_014511e0, pointer_of_014511e0, storage_of_014511e0>();
}

extern "C" void bb_frame_timing_static_guard_01451210()
{
    bind_static<guard_of_01451210, pointer_of_01451210, storage_of_01451210>();
}

extern "C" void bb_frame_timing_static_guard_01451c90()
{
    bind_static<guard_of_01451c90, pointer_of_01451c90, storage_of_01451c90>();
}

extern "C" void bb_frame_timing_static_guard_01451cc0()
{
    bind_static<guard_of_01451cc0, pointer_of_01451cc0, storage_of_01451cc0>();
}

extern "C" void bb_frame_timing_static_guard_01451cf0()
{
    bind_static<guard_of_01451cf0, pointer_of_01451cf0, storage_of_01451cf0>();
}

extern "C" void bb_frame_timing_static_guard_01455be0()
{
    bind_static<guard_of_01455be0, pointer_of_01455be0, storage_of_01455be0>();
}

extern "C" void bb_frame_timing_static_guard_01455c10()
{
    bind_static<guard_of_01455c10, pointer_of_01455c10, storage_of_01455c10>();
}

extern "C" void bb_frame_timing_static_guard_01455c40()
{
    bind_static<guard_of_01455c40, pointer_of_01455c40, storage_of_01455c40>();
}

extern "C" void bb_frame_timing_static_guard_01455cc0()
{
    bind_static<guard_of_01455cc0, pointer_of_01455cc0, storage_of_01455cc0>();
}

extern "C" void bb_frame_timing_static_guard_01455cf0()
{
    bind_static<guard_of_01455cf0, pointer_of_01455cf0, storage_of_01455cf0>();
}

extern "C" void bb_frame_timing_static_guard_01455d20()
{
    bind_static<guard_of_01455d20, pointer_of_01455d20, storage_of_01455d20>();
}

extern "C" void bb_frame_timing_static_guard_01456040()
{
    bind_static<guard_of_01456040, pointer_of_01456040, storage_of_01456040>();
}

extern "C" void bb_frame_timing_static_guard_01456070()
{
    bind_static<guard_of_01456070, pointer_of_01456070, storage_of_01456070>();
}

extern "C" void bb_frame_timing_static_guard_014560a0()
{
    bind_static<guard_of_014560a0, pointer_of_014560a0, storage_of_014560a0>();
}

extern "C" void bb_frame_timing_static_guard_01456a10()
{
    bind_static<guard_of_01456a10, pointer_of_01456a10, storage_of_01456a10>();
}

extern "C" void bb_frame_timing_static_guard_01456a40()
{
    bind_static<guard_of_01456a40, pointer_of_01456a40, storage_of_01456a40>();
}

extern "C" void bb_frame_timing_static_guard_01456a70()
{
    bind_static<guard_of_01456a70, pointer_of_01456a70, storage_of_01456a70>();
}

extern "C" void bb_frame_timing_static_guard_01456cc0()
{
    bind_static<guard_of_01456cc0, pointer_of_01456cc0, storage_of_01456cc0>();
}

extern "C" void bb_frame_timing_static_guard_01456cf0()
{
    bind_static<guard_of_01456cf0, pointer_of_01456cf0, storage_of_01456cf0>();
}

extern "C" void bb_frame_timing_static_guard_01456d20()
{
    bind_static<guard_of_01456d20, pointer_of_01456d20, storage_of_01456d20>();
}

extern "C" void bb_frame_timing_static_guard_01457210()
{
    bind_static<guard_of_01457210, pointer_of_01457210, storage_of_01457210>();
}

extern "C" void bb_frame_timing_static_guard_01457240()
{
    bind_static<guard_of_01457240, pointer_of_01457240, storage_of_01457240>();
}

extern "C" void bb_frame_timing_static_guard_01457270()
{
    bind_static<guard_of_01457270, pointer_of_01457270, storage_of_01457270>();
}

extern "C" void bb_frame_timing_static_guard_01457b70()
{
    bind_static<guard_of_01457b70, pointer_of_01457b70, storage_of_01457b70>();
}

extern "C" void bb_frame_timing_static_guard_01457ba0()
{
    bind_static<guard_of_01457ba0, pointer_of_01457ba0, storage_of_01457ba0>();
}

extern "C" void bb_frame_timing_static_guard_01457bd0()
{
    bind_static<guard_of_01457bd0, pointer_of_01457bd0, storage_of_01457bd0>();
}

extern "C" void bb_frame_timing_static_guard_01457c60()
{
    bind_static<guard_of_01457c60, pointer_of_01457c60, storage_of_01457c60>();
}

extern "C" void bb_frame_timing_static_guard_01457c90()
{
    bind_static<guard_of_01457c90, pointer_of_01457c90, storage_of_01457c90>();
}

extern "C" void bb_frame_timing_static_guard_01457cc0()
{
    bind_static<guard_of_01457cc0, pointer_of_01457cc0, storage_of_01457cc0>();
}

extern "C" void bb_frame_timing_static_guard_014592a0()
{
    bind_static<guard_of_014592a0, pointer_of_014592a0, storage_of_014592a0>();
}

extern "C" void bb_frame_timing_static_guard_014592d0()
{
    bind_static<guard_of_014592d0, pointer_of_014592d0, storage_of_014592d0>();
}

extern "C" void bb_frame_timing_static_guard_01459300()
{
    bind_static<guard_of_01459300, pointer_of_01459300, storage_of_01459300>();
}

extern "C" void bb_frame_timing_static_guard_01459d00()
{
    bind_static<guard_of_01459d00, pointer_of_01459d00, storage_of_01459d00>();
}

extern "C" void bb_frame_timing_static_guard_01459d30()
{
    bind_static<guard_of_01459d30, pointer_of_01459d30, storage_of_01459d30>();
}

extern "C" void bb_frame_timing_static_guard_01459d60()
{
    bind_static<guard_of_01459d60, pointer_of_01459d60, storage_of_01459d60>();
}

extern "C" void bb_frame_timing_static_guard_01459dd0()
{
    bind_static<guard_of_01459dd0, pointer_of_01459dd0, storage_of_01459dd0>();
}

extern "C" void bb_frame_timing_static_guard_01459e00()
{
    bind_static<guard_of_01459e00, pointer_of_01459e00, storage_of_01459e00>();
}

extern "C" void bb_frame_timing_static_guard_01459e30()
{
    bind_static<guard_of_01459e30, pointer_of_01459e30, storage_of_01459e30>();
}

extern "C" void bb_frame_timing_static_guard_01459f00()
{
    bind_static<guard_of_01459f00, pointer_of_01459f00, storage_of_01459f00>();
}

extern "C" void bb_frame_timing_static_guard_01459f30()
{
    bind_static<guard_of_01459f30, pointer_of_01459f30, storage_of_01459f30>();
}

extern "C" void bb_frame_timing_static_guard_01459f60()
{
    bind_static<guard_of_01459f60, pointer_of_01459f60, storage_of_01459f60>();
}

extern "C" void bb_frame_timing_static_guard_0145a030()
{
    bind_static<guard_of_0145a030, pointer_of_0145a030, storage_of_0145a030>();
}

extern "C" void bb_frame_timing_static_guard_0145a060()
{
    bind_static<guard_of_0145a060, pointer_of_0145a060, storage_of_0145a060>();
}

extern "C" void bb_frame_timing_static_guard_0145a090()
{
    bind_static<guard_of_0145a090, pointer_of_0145a090, storage_of_0145a090>();
}

extern "C" void bb_frame_timing_static_guard_0145b5e0()
{
    bind_static<guard_of_0145b5e0, pointer_of_0145b5e0, storage_of_0145b5e0>();
}

extern "C" void bb_frame_timing_static_guard_0145b610()
{
    bind_static<guard_of_0145b610, pointer_of_0145b610, storage_of_0145b610>();
}

extern "C" void bb_frame_timing_static_guard_0145b640()
{
    bind_static<guard_of_0145b640, pointer_of_0145b640, storage_of_0145b640>();
}

extern "C" void bb_frame_timing_static_guard_0145b700()
{
    bind_static<guard_of_0145b700, pointer_of_0145b700, storage_of_0145b700>();
}

extern "C" void bb_frame_timing_static_guard_0145b730()
{
    bind_static<guard_of_0145b730, pointer_of_0145b730, storage_of_0145b730>();
}

extern "C" void bb_frame_timing_static_guard_0145b760()
{
    bind_static<guard_of_0145b760, pointer_of_0145b760, storage_of_0145b760>();
}

extern "C" void bb_frame_timing_static_guard_0145bb60()
{
    bind_static<guard_of_0145bb60, pointer_of_0145bb60, storage_of_0145bb60>();
}

extern "C" void bb_frame_timing_static_guard_0145bb90()
{
    bind_static<guard_of_0145bb90, pointer_of_0145bb90, storage_of_0145bb90>();
}

extern "C" void bb_frame_timing_static_guard_0145bbc0()
{
    bind_static<guard_of_0145bbc0, pointer_of_0145bbc0, storage_of_0145bbc0>();
}

extern "C" void bb_frame_timing_static_guard_0145c770()
{
    bind_static<guard_of_0145c770, pointer_of_0145c770, storage_of_0145c770>();
}

extern "C" void bb_frame_timing_static_guard_0145c7a0()
{
    bind_static<guard_of_0145c7a0, pointer_of_0145c7a0, storage_of_0145c7a0>();
}

extern "C" void bb_frame_timing_static_guard_0145c7d0()
{
    bind_static<guard_of_0145c7d0, pointer_of_0145c7d0, storage_of_0145c7d0>();
}

extern "C" void bb_frame_timing_static_guard_0145cb70()
{
    bind_static<guard_of_0145cb70, pointer_of_0145cb70, storage_of_0145cb70>();
}

extern "C" void bb_frame_timing_static_guard_0145cba0()
{
    bind_static<guard_of_0145cba0, pointer_of_0145cba0, storage_of_0145cba0>();
}

extern "C" void bb_frame_timing_static_guard_0145cbd0()
{
    bind_static<guard_of_0145cbd0, pointer_of_0145cbd0, storage_of_0145cbd0>();
}

extern "C" void bb_frame_timing_static_guard_0145d020()
{
    bind_static<guard_of_0145d020, pointer_of_0145d020, storage_of_0145d020>();
}

extern "C" void bb_frame_timing_static_guard_0145d050()
{
    bind_static<guard_of_0145d050, pointer_of_0145d050, storage_of_0145d050>();
}

extern "C" void bb_frame_timing_static_guard_0145d080()
{
    bind_static<guard_of_0145d080, pointer_of_0145d080, storage_of_0145d080>();
}

extern "C" void bb_frame_timing_static_guard_0145da00()
{
    bind_static<guard_of_0145da00, pointer_of_0145da00, storage_of_0145da00>();
}

extern "C" void bb_frame_timing_static_guard_0145da30()
{
    bind_static<guard_of_0145da30, pointer_of_0145da30, storage_of_0145da30>();
}

extern "C" void bb_frame_timing_static_guard_0145da60()
{
    bind_static<guard_of_0145da60, pointer_of_0145da60, storage_of_0145da60>();
}

extern "C" void bb_frame_timing_static_guard_0145e530()
{
    bind_static<guard_of_0145e530, pointer_of_0145e530, storage_of_0145e530>();
}

extern "C" void bb_frame_timing_static_guard_0145e560()
{
    bind_static<guard_of_0145e560, pointer_of_0145e560, storage_of_0145e560>();
}

extern "C" void bb_frame_timing_static_guard_0145e590()
{
    bind_static<guard_of_0145e590, pointer_of_0145e590, storage_of_0145e590>();
}

extern "C" void bb_frame_timing_static_guard_0145eaa0()
{
    bind_static<guard_of_0145eaa0, pointer_of_0145eaa0, storage_of_0145eaa0>();
}

extern "C" void bb_frame_timing_static_guard_0145ead0()
{
    bind_static<guard_of_0145ead0, pointer_of_0145ead0, storage_of_0145ead0>();
}

extern "C" void bb_frame_timing_static_guard_0145eb00()
{
    bind_static<guard_of_0145eb00, pointer_of_0145eb00, storage_of_0145eb00>();
}

extern "C" void bb_frame_timing_static_guard_0145edb0()
{
    bind_static<guard_of_0145edb0, pointer_of_0145edb0, storage_of_0145edb0>();
}

extern "C" void bb_frame_timing_static_guard_0145ede0()
{
    bind_static<guard_of_0145ede0, pointer_of_0145ede0, storage_of_0145ede0>();
}

extern "C" void bb_frame_timing_static_guard_0145ee10()
{
    bind_static<guard_of_0145ee10, pointer_of_0145ee10, storage_of_0145ee10>();
}

extern "C" void bb_frame_timing_static_guard_0145f2d0()
{
    bind_static<guard_of_0145f2d0, pointer_of_0145f2d0, storage_of_0145f2d0>();
}

extern "C" void bb_frame_timing_static_guard_0145f300()
{
    bind_static<guard_of_0145f300, pointer_of_0145f300, storage_of_0145f300>();
}

extern "C" void bb_frame_timing_static_guard_0145f330()
{
    bind_static<guard_of_0145f330, pointer_of_0145f330, storage_of_0145f330>();
}

extern "C" void bb_frame_timing_static_guard_0145fc90()
{
    bind_static<guard_of_0145fc90, pointer_of_0145fc90, storage_of_0145fc90>();
}

extern "C" void bb_frame_timing_static_guard_0145fcc0()
{
    bind_static<guard_of_0145fcc0, pointer_of_0145fcc0, storage_of_0145fcc0>();
}

extern "C" void bb_frame_timing_static_guard_0145fcf0()
{
    bind_static<guard_of_0145fcf0, pointer_of_0145fcf0, storage_of_0145fcf0>();
}

extern "C" void bb_frame_timing_static_guard_014624c0()
{
    bind_static<guard_of_014624c0, pointer_of_014624c0, storage_of_014624c0>();
}

extern "C" void bb_frame_timing_static_guard_014624f0()
{
    bind_static<guard_of_014624f0, pointer_of_014624f0, storage_of_014624f0>();
}

extern "C" void bb_frame_timing_static_guard_01462520()
{
    bind_static<guard_of_01462520, pointer_of_01462520, storage_of_01462520>();
}

extern "C" void bb_frame_timing_static_guard_01463300()
{
    bind_static<guard_of_01463300, pointer_of_01463300, storage_of_01463300>();
}

extern "C" void bb_frame_timing_static_guard_01463330()
{
    bind_static<guard_of_01463330, pointer_of_01463330, storage_of_01463330>();
}

extern "C" void bb_frame_timing_static_guard_01463360()
{
    bind_static<guard_of_01463360, pointer_of_01463360, storage_of_01463360>();
}

extern "C" void bb_frame_timing_static_guard_014644f0()
{
    bind_static<guard_of_014644f0, pointer_of_014644f0, storage_of_014644f0>();
}

extern "C" void bb_frame_timing_static_guard_01464520()
{
    bind_static<guard_of_01464520, pointer_of_01464520, storage_of_01464520>();
}

extern "C" void bb_frame_timing_static_guard_01464550()
{
    bind_static<guard_of_01464550, pointer_of_01464550, storage_of_01464550>();
}

extern "C" void bb_frame_timing_static_guard_01464da0()
{
    bind_static<guard_of_01464da0, pointer_of_01464da0, storage_of_01464da0>();
}

extern "C" void bb_frame_timing_static_guard_01464dd0()
{
    bind_static<guard_of_01464dd0, pointer_of_01464dd0, storage_of_01464dd0>();
}

extern "C" void bb_frame_timing_static_guard_01464e00()
{
    bind_static<guard_of_01464e00, pointer_of_01464e00, storage_of_01464e00>();
}

extern "C" void bb_frame_timing_static_guard_01464f70()
{
    bind_static<guard_of_01464f70, pointer_of_01464f70, storage_of_01464f70>();
}

extern "C" void bb_frame_timing_static_guard_01464fa0()
{
    bind_static<guard_of_01464fa0, pointer_of_01464fa0, storage_of_01464fa0>();
}

extern "C" void bb_frame_timing_static_guard_01464fd0()
{
    bind_static<guard_of_01464fd0, pointer_of_01464fd0, storage_of_01464fd0>();
}

extern "C" void bb_frame_timing_static_guard_01466c70()
{
    bind_static<guard_of_01466c70, pointer_of_01466c70, storage_of_01466c70>();
}

extern "C" void bb_frame_timing_static_guard_01466ca0()
{
    bind_static<guard_of_01466ca0, pointer_of_01466ca0, storage_of_01466ca0>();
}

extern "C" void bb_frame_timing_static_guard_01466cd0()
{
    bind_static<guard_of_01466cd0, pointer_of_01466cd0, storage_of_01466cd0>();
}

extern "C" void bb_frame_timing_static_guard_01466d90()
{
    bind_static<guard_of_01466d90, pointer_of_01466d90, storage_of_01466d90>();
}

extern "C" void bb_frame_timing_static_guard_01466dc0()
{
    bind_static<guard_of_01466dc0, pointer_of_01466dc0, storage_of_01466dc0>();
}

extern "C" void bb_frame_timing_static_guard_01466df0()
{
    bind_static<guard_of_01466df0, pointer_of_01466df0, storage_of_01466df0>();
}

extern "C" void bb_frame_timing_static_guard_01466f00()
{
    bind_static<guard_of_01466f00, pointer_of_01466f00, storage_of_01466f00>();
}

extern "C" void bb_frame_timing_static_guard_01466f30()
{
    bind_static<guard_of_01466f30, pointer_of_01466f30, storage_of_01466f30>();
}

extern "C" void bb_frame_timing_static_guard_01466f60()
{
    bind_static<guard_of_01466f60, pointer_of_01466f60, storage_of_01466f60>();
}

extern "C" void bb_frame_timing_static_guard_014675c0()
{
    bind_static<guard_of_014675c0, pointer_of_014675c0, storage_of_014675c0>();
}

extern "C" void bb_frame_timing_static_guard_014675f0()
{
    bind_static<guard_of_014675f0, pointer_of_014675f0, storage_of_014675f0>();
}

extern "C" void bb_frame_timing_static_guard_01467620()
{
    bind_static<guard_of_01467620, pointer_of_01467620, storage_of_01467620>();
}

extern "C" void bb_frame_timing_static_guard_014677f0()
{
    bind_static<guard_of_014677f0, pointer_of_014677f0, storage_of_014677f0>();
}

extern "C" void bb_frame_timing_static_guard_01467820()
{
    bind_static<guard_of_01467820, pointer_of_01467820, storage_of_01467820>();
}

extern "C" void bb_frame_timing_static_guard_01467850()
{
    bind_static<guard_of_01467850, pointer_of_01467850, storage_of_01467850>();
}

extern "C" void bb_frame_timing_static_guard_014680c0()
{
    bind_static<guard_of_014680c0, pointer_of_014680c0, storage_of_014680c0>();
}

extern "C" void bb_frame_timing_static_guard_014680f0()
{
    bind_static<guard_of_014680f0, pointer_of_014680f0, storage_of_014680f0>();
}

extern "C" void bb_frame_timing_static_guard_01468120()
{
    bind_static<guard_of_01468120, pointer_of_01468120, storage_of_01468120>();
}

extern "C" void bb_frame_timing_static_guard_01468380()
{
    bind_static<guard_of_01468380, pointer_of_01468380, storage_of_01468380>();
}

extern "C" void bb_frame_timing_static_guard_014683b0()
{
    bind_static<guard_of_014683b0, pointer_of_014683b0, storage_of_014683b0>();
}

extern "C" void bb_frame_timing_static_guard_014683e0()
{
    bind_static<guard_of_014683e0, pointer_of_014683e0, storage_of_014683e0>();
}

extern "C" void bb_frame_timing_static_guard_014684d0()
{
    bind_static<guard_of_014684d0, pointer_of_014684d0, storage_of_014684d0>();
}

extern "C" void bb_frame_timing_static_guard_01468500()
{
    bind_static<guard_of_01468500, pointer_of_01468500, storage_of_01468500>();
}

extern "C" void bb_frame_timing_static_guard_01468530()
{
    bind_static<guard_of_01468530, pointer_of_01468530, storage_of_01468530>();
}

extern "C" void bb_frame_timing_static_guard_02785310()
{
    bind_static<guard_of_02785310, pointer_of_02785310, storage_of_02785310>();
}
