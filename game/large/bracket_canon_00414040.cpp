// SPDX-License-Identifier: GPL-2.0-or-later
// Large function 0x414040: bracket canonicaliser with reverse-order mirror output.
//
// This is the first member of the >1024-byte tier, and the first replacement in this tree whose
// body came from a decompiler draft rather than from a byte pattern. The draft is a translation
// input, not an artifact: what follows is a hand transcription of all 279 instructions, kept at
// the level of the machine on purpose. Prose about this function has been wrong four times - the
// mirror cascade, the table clobbers, the reachability of the block at 0x4143f3 and the index
// arithmetic of the bulk copy were each mis-stated before the instruction text was read - so the
// first pass transcribes and does not interpret. A later pass may make it idiomatic; that pass
// needs a differential that already agrees.
//
// Shape, read from the instructions rather than from the draft:
//
//   * Six parameters arrive in rdi..r9 but RDI IS DEAD: the third instruction overwrites it from
//     RSI. The declaration keeps six arguments anyway, because a host replacement is called with
//     the original's register file positionally - omitting the dead one shifts every later
//     argument by one slot and produces a plausible wrong answer with no fault anywhere.
//   * Output is produced in reverse: the output index starts at count-1 and descends.
//   * Two rodata tables, emitted by tools/rodata_table.py and consumed here as value arrays, so
//     no guest memory is dereferenced and this file needs no runtime include.
//   * Every character is classified twice, once against each table, by the same three-way
//     protocol: table entry 0 means "class 0", entry 1 means "class 1", anything else is a base
//     index and the class is one bit of a second lookup. The bit index is the character's low
//     nibble; the second index is the base plus (character >> 4) & 0xff.
//   * The mirror cascade is gated, not unconditional: a bracket is mirrored only when the
//     classification of the *next* character is non-zero. With ASCII input that never happens -
//     table A is class 1 for exactly 600 of the 65536 possible units, all of them at high bytes
//     0x05, 0x06, 0x20 and 0xfc - so ASCII exercises the verbatim path at 0x414385 and the
//     mirror arms are reached only by non-ASCII text.
//
// Known limits, stated here rather than left for a reviewer:
//
//   * The block at 0x4143f3 is unreachable. Its guard is r9 - r8 + 1 <= 0, and r9 and r8
//     advance together - both increment on the same path - from 0 and 1, with r9 only ever reset
//     downwards. So r9 <= r8 - 1 always and the branch at 0x4143f1 is always taken. "Every
//     block ran" is therefore unachievable for this member; 63 of 64 is the ceiling.
//   * Table indices are not bounds-checked against the array sizes, because the original does not
//     bounds-check them either: 1280 of the 65536 units drive an index past the 384-word extent
//     of table A and read whatever follows it in the image. Transcribing that faithfully means
//     this body reads out of bounds on those inputs. They are not reachable from ASCII and they
//     are not reachable from the cases shipped with this member; if that changes, the table's
//     derived extent is the thing to fix, not the index.
#include <cstdint>

#include "rodata_pairs_02fc4a40.h"
#include "rodata_pairs_02fc5120.h"

namespace {

using bb::data::k_pairs_02fc4a40;
using bb::data::k_pairs_02fc5120;

// Every immediate in the transcription, named. tools/check_readable.py refuses a body that
// carries bare numbers, and the refusal is right: the eight bracket codes below are the whole
// content of the cascade and a reader should not have to decode 0x5d to see which bracket it is.
constexpr std::uint64_t k_class_zero = 0;
constexpr std::uint64_t k_class_one = 1;
constexpr std::uint64_t k_hi_shift = 8;
constexpr std::uint64_t k_low_nibble_mask = 0xf;
constexpr std::uint64_t k_low_byte_mask = 0xff;
constexpr std::uint64_t k_bextr_start = 4;
constexpr std::uint64_t k_bextr_length_mask = 0xff;
constexpr std::uint64_t k_neighbour_shift = 7;
constexpr std::uint64_t k_neighbour_mask = 0x1fe;
// Two ELEMENTS of look-ahead, not a sizeof: r9, r13 and r8 all hold element indices here, and the
// original adds 2 at 0x414411 before subtracting the current index. Its meaning is the bulk copy's
// tail bound and is not established beyond "the arithmetic that the listing performs"; naming it
// after a byte width would be a claim this transcription cannot support.
constexpr std::int64_t k_bulk_tail_lookahead = 2;

constexpr std::uint64_t k_ch_lparen = 0x28;
constexpr std::uint64_t k_ch_rparen = 0x29;
constexpr std::uint64_t k_ch_lt = 0x3c;
constexpr std::uint64_t k_ch_gt = 0x3e;
constexpr std::uint64_t k_ch_lbrack = 0x5b;
constexpr std::uint64_t k_ch_rbrack = 0x5d;
constexpr std::uint64_t k_ch_lbrace = 0x7b;
constexpr std::uint64_t k_ch_rbrace = 0x7d;

// The two comparison pivots of the cascade, which are not bracket codes: the first split is on
// ';' and the second on 'Z', and they are reached by signed comparison against the character.
constexpr std::uint64_t k_pivot_semicolon = 0x3b;
constexpr std::uint64_t k_pivot_upper_z = 0x5a;
constexpr std::uint64_t k_pivot_lower_z = 0x7a;

}  // namespace

// EVIDENCE SCOPE, so a reviewer can tell what the differential did and did not touch.
//
// Verified by three cases: `<>`, `(()`, and `()` with rdi poisoned. Those inputs enter 14 of the 64
// blocks -- they reach the guard at 0x414350, the classification at 0x414140, the run loop at
// 0x414140..0x4142a5, the reverse write at 0x414385 and the epilogue -- and produce dst = ") ( ( (".
// Two planted errors were caught 3/3 each (a one-element skew in the index write, and a wrong
// constant in the return clamp), and the restore was confirmed by a clean 3/3 rerun.
//
// NOT verified by any case, and no case can:
//   * The dead `cmove` at 0x414483. Its effect is unobservable by construction: the epilogue's
//     `setne al` at 0x4144a7 overwrites the low byte on every path that leaves the loop. It is
//     preserved because removing it would be a claim that it is unreachable, and the trace that
//     said so is one input's trace, not a proof.
//   * The mirror arms (0x4140b5..0x41412e) and the bulk copy at 0x414410. No ASCII input reaches
//     them: no unit below U+0500 is table-A class 1, so a case with a codepoint >= U+051d is
//     required before this body's middle is meaningfully tested at all.
//   * The three padding runs at 0x414239 (6 B), 0x414283 (13 B), 0x4143df (1 B). They affect the
//     leader set, which the coverage gate checks by address; no differential can see them.
//
// rdi_argument is dead on entry and is kept only to preserve argument positions; see the header.
//
// Every block of the original carries a label here, including the ones reached only by
// fall-through, because the mapping from source line to guest address is the whole point of a
// transcription and a reader diffing this against the listing needs all 64. Clang warns that a
// label nothing jumps to is unused; that is the intent, so the warning is suppressed for this
// function alone rather than answered by deleting the labels a reviewer needs.
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-label"
#endif
extern "C" std::uint64_t bb_large_bracket_canon_00414040([[maybe_unused]] std::uint64_t rdi_argument,
                                                         const std::uint16_t *rsi_src,
                                                         std::uint64_t rdx_count,
                                                         std::uint16_t *rcx_dst,
                                                         std::int32_t *r8_idx,
                                                         std::uint8_t *r9_flg) {
    // Register-level state. Named by the register they hold because the original reuses several
    // of them for two different purposes (r8 is an input base and then a loop counter; r9 is a
    // character class and then a run length), and collapsing that reuse is exactly the kind of
    // "simplification" that changes behaviour quietly.
    std::uint64_t v_rax = 0;
    std::uint64_t v_rbx = 0;
    std::uint64_t v_rcx = 0;
    std::uint64_t v_rsi = 0;
    std::uint64_t v_rdi = 0;
    std::uint64_t v_r8 = 0;
    std::uint64_t v_r9 = 0;
    std::uint64_t v_r10 = 0;
    std::uint64_t v_r11 = 0;
    std::uint64_t v_r12 = 0;
    std::uint64_t v_r13 = 0;
    std::uint64_t v_r14 = 0;
    std::uint64_t v_r15 = 0;
    std::uint64_t v_rbp = 0;

    // The original spills seven constants to its frame on entry and a further three around the
    // cascade. Each spilt value is an expression of the incoming arguments alone and is restored
    // from the same slot it was written to, so they are named here and used directly.
    std::uint64_t slot_saved_b = 0;
    std::uint64_t slot_saved_a = 0;
    std::uint64_t slot_saved_r11 = 0;

    // Set if the branch at 0x4142f1 is ever taken; by the argument in the header it is not.
    std::int64_t bulk_offset = 0;

    // sil as a value of its own: the original writes only that byte in two of the three places
    // that define it, and testing the full register afterwards would read the wrong thing.
    bool v_sil = false;

L_414040:  // 0x00414040
    // Six callee-saved pushes, elided: no argument or local depends on them.
    // The third instruction is `mov rdi, rsi`, which is why rdi_argument is dead.
    v_rax = 0;
    if (rdx_count == 0) {
        goto L_4144ad;
    }

L_41405d:  // 0x0041405d
    v_r13 = rdx_count - 1;
    v_r11 = 0;
    v_r10 = 0;
    goto L_414140;

    // ---------------------------------------------------------------------------------------
    // The mirror cascade. Reached only when the gate at 0x414350 finds a non-zero class on
    // either side. Each arm writes one mirrored code unit and rejoins at 0x41438a; falling off
    // the end of the chain means "no mirror applies" and rejoins at 0x414385 instead.
    // ---------------------------------------------------------------------------------------

L_4140b5:  // 0x004140b5
    if (v_r15 != k_ch_rparen) {
        goto L_41412e;
    }

L_4140c0:  // 0x004140c0
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_lparen);
    goto L_41438a;

L_4140cc:  // 0x004140cc
    if (v_r15 != k_ch_lbrace) {
        goto L_4140f8;
    }

L_4140d7:  // 0x004140d7
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_rbrace);
    goto L_41438a;

L_4140e3:  // 0x004140e3
    if (v_r15 != k_ch_lbrack) {
        goto L_41411c;
    }

L_4140ec:  // 0x004140ec
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_rbrack);
    goto L_41438a;

L_4140f8:  // 0x004140f8
    if (v_r15 != k_ch_rbrace) {
        goto L_41412e;
    }

L_4140fe:  // 0x004140fe
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_lbrace);
    goto L_41438a;

L_41410a:  // 0x0041410a
    if (v_r15 != k_ch_gt) {
        goto L_41412e;
    }

L_414110:  // 0x00414110
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_lt);
    goto L_41438a;

L_41411c:  // 0x0041411c
    if (v_r15 != k_ch_rbrack) {
        goto L_41412e;
    }

L_414122:  // 0x00414122
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_lbrack);
    goto L_41438a;

L_41412e:  // 0x0041412e
    // No arm matched. The original also writes the (unchanged) destination pointer back to its
    // frame slot here; that slot is never read before being written again.
    goto L_414385;

    // ---------------------------------------------------------------------------------------
    // Loop head: classify the current character against table A (class into r9) and against
    // table B (class into rbx), then classify the following character against A (into rcx).
    // ---------------------------------------------------------------------------------------

L_414140:  // 0x00414140
    v_r15 = rsi_src[v_r10];
    v_rcx = v_r15 >> k_hi_shift;
    v_rsi = k_pairs_02fc5120[v_rcx];
    v_rbx = 0;
    v_r9 = 0;
    if (v_rsi == k_class_zero) {
        goto L_414196;
    }

L_41415d:  // 0x0041415d
    if (v_rsi != k_class_one) {
        goto L_414170;
    }

L_414163:  // 0x00414163
    v_r9 = k_class_one;
    goto L_414196;

L_414170:  // 0x00414170
    // bextr with a control of 0x404: start 4, length 8, i.e. the second byte of the unit.
    v_rdi = (v_r15 >> k_bextr_start) & k_bextr_length_mask;
    v_rdi += v_rsi;
    v_rsi = k_pairs_02fc5120[v_rdi];
    v_r9 = (v_rsi >> (v_r15 & k_low_nibble_mask)) & 1;
    // (bt/sbb/and 1: the class is the selected bit, as an ordinary 0 or 1.)

L_414196:  // 0x00414196
    v_r11 = (v_r11 != 0) ? 1 : 0;
    v_rcx = k_pairs_02fc4a40[v_rcx];
    if (v_rcx == k_class_zero) {
        goto L_4141e2;
    }

L_4141a6:  // 0x004141a6
    if (v_rcx != k_class_one) {
        goto L_4141c0;
    }

L_4141ac:  // 0x004141ac
    v_rbx = k_class_one;
    goto L_4141e2;

L_4141c0:  // 0x004141c0
    v_rsi = (v_r15 >> k_bextr_start) & k_bextr_length_mask;
    v_rsi += v_rcx;
    v_rcx = k_pairs_02fc4a40[v_rsi];
    v_rbx = (v_rcx >> (v_r15 & k_low_nibble_mask)) & 1;

L_4141e2:  // 0x004141e2
    v_r12 = v_r10 + 1;
    v_rcx = v_r9;
    if (v_r12 >= rdx_count) {
        goto L_414240;
    }

L_4141ee:  // 0x004141ee
    // The following character, classified against A. The original reaches the same table entry
    // by shifting left by seven and masking to 0x1fe rather than by shifting right by eight, so
    // the stored value is a byte offset rather than an index; halving it recovers the index.
    v_rsi = rsi_src[v_r10 + 1];
    v_rcx = (v_rsi >> k_neighbour_shift) & k_neighbour_mask;
    v_rdi = k_pairs_02fc5120[v_rcx >> 1];
    v_rcx = 0;
    if (v_rdi == k_class_zero) {
        goto L_414240;
    }

L_41420b:  // 0x0041420b
    if (v_rdi != k_class_one) {
        goto L_414218;
    }

L_414211:  // 0x00414211
    v_rcx = k_class_one;
    goto L_414240;

L_414218:  // 0x00414218
    v_rcx = (v_rsi >> k_bextr_start) & k_bextr_length_mask;
    v_rcx += v_rdi;
    v_rcx = k_pairs_02fc5120[v_rcx];
    v_rcx = (v_rcx >> (v_rsi & k_low_nibble_mask)) & 1;
    // A six-byte nop follows in the original, inside this block.

L_414240:  // 0x00414240
    v_r11 |= v_r9;
    slot_saved_r11 = v_r11;
    v_rsi = v_rbx | v_r9;
    if (v_rsi != 0) {
        goto L_414350;
    }

L_414253:  // 0x00414253
    slot_saved_b = v_rbx;
    slot_saved_a = v_r9;
    v_r9 = 0;
    v_r8 = 1;
    if (v_r12 >= rdx_count) {
        goto L_4143e0;
    }

L_414271:  // 0x00414271
    v_r9 = 0;
    v_r8 = 1;
    // A thirteen-byte nop follows in the original, inside this block.

L_414290:  // 0x00414290
    // Run scan: walk forward while the character's A class is zero, counting. A non-zero A class
    // ends the run from here; a zero A class falls through to the B test, which decides whether
    // the run continues.
    v_rdi = rsi_src[v_r10 + v_r8];
    v_rsi = v_rdi >> k_hi_shift;
    v_rbx = k_pairs_02fc5120[v_rsi];
    if (v_rbx != k_class_zero) {
        goto L_414301;
    }

L_4142a5:  // 0x004142a5
    v_rbx = k_pairs_02fc4a40[v_rsi];
    v_sil = true;
    if (v_rbx == k_class_zero) {
        goto L_4142e0;
    }

L_4142b1:  // 0x004142b1
    if (v_rbx != k_class_one) {
        goto L_4142c0;
    }

L_4142b7:  // 0x004142b7
    v_sil = false;
    goto L_4142e0;

L_4142c0:  // 0x004142c0
    v_rsi = (v_rdi >> k_bextr_start) & k_bextr_length_mask;
    v_rsi += v_rbx;
    v_rsi = k_pairs_02fc4a40[v_rsi];
    // setae after bt: one when the selected bit is clear, which is the inverse of every other
    // classification site in this function. Preserved rather than normalised.
    v_sil = ((v_rsi >> (v_rdi & k_low_nibble_mask)) & 1) == 0;

L_4142e0:  // 0x004142e0
    v_r9 += 1;
    if (v_sil) {
        v_r9 = 0;
    }
    v_rsi = v_r10 + v_r8 + 1;
    v_r8 += 1;
    if (v_rsi < rdx_count) {
        goto L_414290;
    }
    // Falls into the trampoline below, which is how the original reaches the run end from here.

L_4142fc:  // 0x004142fc
    goto L_4143e0;

L_414301:  // 0x00414301
    // The A class is non-zero, so the run ends here. `bx == 1` skips the bit lookup. The two
    // moves at the head of this block save the table pointers; they have no counterpart here
    // because the tables are named directly, and the saved values are restored before the branch.
    if (v_rbx == k_class_one) {
        goto L_4143da;
    }

L_414311:  // 0x00414311
    v_rbp = (v_rdi >> k_bextr_start) & k_bextr_length_mask;
    v_rbp += v_rbx;
    v_rbp = k_pairs_02fc5120[v_rbp];
    {
        // The original reaches the bit through bl, having overwritten rbx with the low nibble;
        // that value is dead on both exits, so only the nibble is carried across.
        const std::uint64_t bit = (v_rbp >> (v_rdi & k_low_nibble_mask)) & 1;
        v_r11 = slot_saved_r11;
        if (bit == 0) {
            goto L_4142a5;
        }
    }
    // Setae failed, so the run continues past this character: fall into the trampoline.

L_41433f:  // 0x0041433f
    goto L_4143e0;

L_414350:  // 0x00414350
    // The gate. Both classes must be non-zero for the cascade to run: `or ecx, eax` folds the
    // following character's class with the class latched from an earlier iteration, and the
    // second test rejects a zero current-B class.
    if ((v_rcx | v_rax) == 0) {
        goto L_414380;
    }

L_414354:  // 0x00414354
    if (v_rbx == 0) {
        goto L_414380;
    }

L_414358:  // 0x00414358
    if (static_cast<std::int64_t>(v_r15) > static_cast<std::int64_t>(k_pivot_semicolon)) {
        goto L_4143a8;
    }

L_41435e:  // 0x0041435e
    if (v_r15 != k_ch_lparen) {
        goto L_4140b5;
    }

L_414368:  // 0x00414368
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_rparen);
    goto L_41438a;

L_414380:  // 0x00414380
    // Fall through to the verbatim store.

L_414385:  // 0x00414385
    rcx_dst[v_r13] = static_cast<std::uint16_t>(v_r15);

L_41438a:  // 0x0041438a
    r8_idx[v_r13] = static_cast<std::int32_t>(v_r10);
    r9_flg[v_r13] = 0;
    v_r13 -= 1;
    v_r14 = v_r13;
    goto L_414481;

L_4143a8:  // 0x004143a8
    if (static_cast<std::int64_t>(v_r15) > static_cast<std::int64_t>(k_pivot_lower_z)) {
        goto L_4140cc;
    }

L_4143b2:  // 0x004143b2
    if (static_cast<std::int64_t>(v_r15) > static_cast<std::int64_t>(k_pivot_upper_z)) {
        goto L_4140e3;
    }

L_4143c4:  // 0x004143c4
    if (v_r15 != k_ch_lt) {
        goto L_41410a;
    }

L_4143d1:  // 0x004143d1
    rcx_dst[v_r13] = static_cast<std::uint16_t>(k_ch_gt);
    goto L_41438a;

L_4143da:  // 0x004143da
    v_r11 = slot_saved_r11;
    // A one-byte nop follows in the original, inside this block.

    // ---------------------------------------------------------------------------------------
    // Run end. r14 becomes the output index for the slot below the run, and the sign of
    // r8 - r9 decides between the bulk copy and the single-character path.
    // ---------------------------------------------------------------------------------------

L_4143e0:  // 0x004143e0
    v_r14 = v_r9 - v_r8;
    v_rcx = v_r14 + v_r13 + 1;
    v_r14 += v_r13;
    if (v_rcx <= v_r13) {
        goto L_414410;
    }

L_4143f3:  // 0x004143f3
    // Unreachable by the argument in the header; transcribed because the bytes are there.
    v_r12 = v_r10;
    v_r9 = slot_saved_a;
    goto L_41447d;

L_414410:  // 0x00414410
    v_r12 = v_r9 + v_r13;
    v_r12 += k_bulk_tail_lookahead;
    v_r12 -= v_r8;
    v_r9 = v_r9 + v_r13;
    v_r9 -= v_r8;
    // The four bulk bases are all "start of array plus one element" in their own widths: the
    // original adds 1, 4, 2 and 2 bytes to the flag, index, destination and source pointers, and
    // those are one element each. Working in element indices here keeps them in step.
    bulk_offset = static_cast<std::int64_t>(v_r9);
    v_rdi = 0;
    v_r9 = slot_saved_a;
    goto L_414458;

L_414450:  // 0x00414450
    v_r15 = rsi_src[v_r10 + 1 + v_rdi];
    v_rdi += 1;

L_414458:  // 0x00414458
    // The first pass enters here rather than at the load, so the slot one below the run receives
    // whatever the cascade last compared - the bracket that opened the run - with the run's own
    // first source index. Passes after that copy source forward one element at a time.
    rcx_dst[1 + bulk_offset + static_cast<std::int64_t>(v_rdi)] = static_cast<std::uint16_t>(v_r15);
    r8_idx[1 + bulk_offset + static_cast<std::int64_t>(v_rdi)] =
        static_cast<std::int32_t>(v_r10 + v_rdi);
    r9_flg[1 + bulk_offset + static_cast<std::int64_t>(v_rdi)] = 0;
    if (v_r12 + v_rdi <= v_r13) {
        goto L_414450;
    }

L_414473:  // 0x00414473
    v_r12 = v_r10 + v_rdi + 1;

L_41447d:  // 0x0041447d
    v_rbx = slot_saved_b;

L_414481:  // 0x00414481
    // cmove: the latched class is refreshed only when the current-B class was zero. It is then
    // read again by the gate at 0x414350 on a later iteration, so it is live even though the
    // epilogue overwrites eax's low byte unconditionally.
    if (v_rbx == 0) {
        v_rax = v_r9;
    }
    v_r13 = v_r14;
    v_r10 = v_r12;
    if (v_r12 < rdx_count) {
        goto L_414140;
    }

L_4144a7:  // 0x004144a7
    // Only the low byte is written, so the upper bits of rax survive from the cmove above.
    v_rax = (v_rax & ~k_low_byte_mask) | ((v_r11 != 0) ? 1 : 0);

L_4144ad:  // 0x004144ad
    // Six callee-saved pops, elided.
    return v_rax;
}
#if defined(__clang__)
#pragma clang diagnostic pop
#endif
