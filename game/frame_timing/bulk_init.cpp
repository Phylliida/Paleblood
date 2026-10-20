// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the one-shot bulk initializer and the small object constructor beside it.
//
//   0x01440640  copy three 16-byte constants into one 48-byte global
//   0x01440680  write a vtable pointer, a handle and a dword into the caller's object
//
// Neither calls anything and neither branches, so both are pure memory effects and the only thing
// a case has to get right is which bytes move.
//
// 0x01440640 reads its three sources from 0x04ccbb20, 0x04ccbb30 and 0x04ccbb40 and writes them
// to 0x058b7e60, 0x058b7e70 and 0x058b7e80. The three sources are sixteen-byte constants -- the
// third is {0.0f, 1.0f, 0.0f, 1.0f} -- and all six addresses sit in mapped image memory, past the
// file's own LOAD data in the zero-filled tail of the image mapping.
//
// Two details are load-bearing and both were checked against the original's recorded writes:
//
//   * each constant is stored with ONE sixteen-byte store, not as four dwords and not as a
//     memcpy. The harness records the byte extent a store dirties, so a replacement that writes
//     the same values in smaller pieces produces a different record even though the memory ends
//     up identical.
//   * the source is read from the image at run time rather than substituted as a literal. The
//     original loads from 0x04ccbb20; if a case presets that address to something else, the
//     original copies the preset bytes and a literal-copying replacement would not.
//
// 0x01440680 computes its vtable pointer as `0x056fe140 + 0x10` with an LEA followed by an ADD,
// which is the same base-plus-bias shape as the static guards: the value stored is 0x056fe150,
// not the LEA's own target. Reading the LEA as the stored value is the easy mistake, and a case
// that checks the pointer's bytes rather than only that it changed is what exposes it.
//
// The object pointer in the second function is *not* translated: the caller passes a host
// address (a case buffer), which is what rdi already holds on entry. Guest addresses in the
// image are the ones that go through rt_guest.
#include <cstdint>

#include "runtime/guest.h"

namespace {

// One 16-byte copy. A packed struct rather than four separate stores, so the access stays one
// 16-byte load and one 16-byte store as in the original's single VEX pair.
struct alignas(16) block
{
    float lanes[4];
};

static_assert(sizeof(block) == 16, "the constant is sixteen bytes");

template <std::uint32_t Source, std::uint32_t Destination>
void copy_constant()
{
    *rt::ptr<block>(Destination) = *rt::ptr<const block>(Source);
}

constexpr std::uintptr_t vtable_bias = 0x10;

// The three constant sources and their destinations, in the order the original copies them.
constexpr std::uint32_t constant_a_source = 0x04ccbb20;
constexpr std::uint32_t constant_a_destination = 0x058b7e60;
constexpr std::uint32_t constant_b_source = 0x04ccbb30;
constexpr std::uint32_t constant_b_destination = 0x058b7e70;
constexpr std::uint32_t constant_c_source = 0x04ccbb40;
constexpr std::uint32_t constant_c_destination = 0x058b7e80;

// The object constructor's vtable base and the word after the handle that holds the mode.
constexpr std::uint32_t vtable_base = 0x056fe140;
constexpr std::uintptr_t mode_field_index = 2;

}  // namespace

extern "C" void bb_frame_timing_bulk_init_01440640()
{
    copy_constant<constant_a_source, constant_a_destination>();
    copy_constant<constant_b_source, constant_b_destination>();
    copy_constant<constant_c_source, constant_c_destination>();
}

extern "C" void bb_frame_timing_object_ctor_01440680(void *object, std::uint64_t handle, std::uint32_t mode)
{
    auto *fields = static_cast<std::uint64_t *>(object);
    fields[0] = reinterpret_cast<std::uintptr_t>(rt::ptr<unsigned char>(vtable_base)) + vtable_bias;
    fields[1] = handle;
    *reinterpret_cast<std::uint32_t *>(fields + mode_field_index) = mode;
}
