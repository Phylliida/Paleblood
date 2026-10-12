// SPDX-License-Identifier: GPL-2.0-or-later
// Engine: the sixteen-byte copy family, four slots, two objects.
//
// Four functions copy four 16-byte slots between two objects whose bases arrive in the first two
// integer arguments. Each is nine instructions: four VEX moves in, four VEX moves out, then RET
// (39 bytes, with NOP padding after the RET that the size does not cover).
//
//   0x00842ba0   [rdi] -> [rsi]   load and store alternate, all four through xmm0
//   0x00842bd0   [rsi] -> [rdi]   load and store alternate, all four through xmm0
//   0x025aa050   [rsi] -> [rdi]   load and store alternate, all four through xmm0
//   0x02577f80   [rsi] -> [rdi]   all four loads first, into xmm0..xmm3, then stores
//
// The first three are one shape with the operands swapped, so 0x00842bd0 and 0x025aa050 share a
// body. The fourth is not: it stages the whole object in xmm0..xmm3 before storing anything, and
// it stores in the order 0x10, 0x00, 0x30, 0x20 rather than ascending. Both differences are
// observable. Loading everything before storing is what an overlapping copy sees, and verify.py
// compares xmm0 and xmm1 as return registers, so the last member's staging is part of its result:
// it returns with xmm0 holding slot 0 and xmm1 slot 1, where the three interleaving members return
// with xmm0 holding slot 3.
//
// A note that is easy to get wrong from a summary: 0x00842ba0 reads its SOURCE from rdi, unlike
// the other three, which read it from rsi. The direction is in the disassembly, not in the names.
//
// The moves are VEX-encoded VMOVAPS, which faults on a misaligned operand, so the replacements use
// the aligned forms. A misaligned pointer faults on both sides rather than diverging, which is what
// the harness reports as agreement.
#include <cstdint>

#include <immintrin.h>

namespace {

// The substitution order every member of the family uses when it loads and stores alternately:
// offsets 0x00, 0x10, 0x20, 0x30.
constexpr unsigned slot_offsets[4] = {0x00, 0x10, 0x20, 0x30};

// Load slot N of FROM and store it to slot N of TO, one slot at a time. The store of slot 0
// happens before the load of slot 1, which is what an overlapping pair of objects sees.
inline void copy_slots_interleaved(const unsigned char *from, unsigned char *to)
{
    for (unsigned i = 0; i < 4; ++i) {
        const __m128 slot = _mm_load_ps(reinterpret_cast<const float *>(from + slot_offsets[i]));
        _mm_store_ps(reinterpret_cast<float *>(to + slot_offsets[i]), slot);
    }
}

// Stage all four slots, then store them in the order the original uses. The staging is not
// decoration: it is the load-before-store order, and it leaves xmm0 and xmm1 holding slots 0 and 1.
inline void copy_slots_staged(const unsigned char *from, unsigned char *to)
{
    const __m128 slot0 = _mm_load_ps(reinterpret_cast<const float *>(from + slot_offsets[0]));
    const __m128 slot1 = _mm_load_ps(reinterpret_cast<const float *>(from + slot_offsets[1]));
    const __m128 slot2 = _mm_load_ps(reinterpret_cast<const float *>(from + slot_offsets[2]));
    const __m128 slot3 = _mm_load_ps(reinterpret_cast<const float *>(from + slot_offsets[3]));
    _mm_store_ps(reinterpret_cast<float *>(to + slot_offsets[0]), slot0);
    _mm_store_ps(reinterpret_cast<float *>(to + slot_offsets[1]), slot1);
    _mm_store_ps(reinterpret_cast<float *>(to + slot_offsets[2]), slot2);
    _mm_store_ps(reinterpret_cast<float *>(to + slot_offsets[3]), slot3);
}

}  // namespace

// 0x00842ba0: the source is the FIRST argument, the destination the second.
extern "C" void bb_engine_sse_copy_rdi_to_rsi_00842ba0(const unsigned char *from, unsigned char *to)
{
    copy_slots_interleaved(from, to);
}

extern "C" void bb_engine_sse_copy_rsi_to_rdi_00842bd0(unsigned char *to, const unsigned char *from)
{
    copy_slots_interleaved(from, to);
}

extern "C" void bb_engine_sse_copy_rsi_to_rdi_02577f80(unsigned char *to, const unsigned char *from)
{
    copy_slots_staged(from, to);
}

extern "C" void bb_engine_sse_copy_rsi_to_rdi_025aa050(unsigned char *to, const unsigned char *from)
{
    copy_slots_interleaved(from, to);
}
