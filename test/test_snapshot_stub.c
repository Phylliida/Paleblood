/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Commit A's gate: the hook-only snapshot wrapper is a 5-byte `e9 rel32` and nothing else, and every
   refusal happens before the first store. Proved by the sentinel, not by the absence of a write. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "runtime/boundary_stub.h"
#include "runtime/tls.h"

/* NOT CHECK(): this binary is built in a configuration that defines NDEBUG, where every assertion
   compiles to nothing and the test passes by measuring no code at all. A guard that cannot fail is the
   defect this suite exists to catch, so the checks exit non-zero themselves. */
#define CHECK(cond)                                                                     \
    do {                                                                                \
        if (!(cond)) {                                                                  \
            fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond);   \
            return 1;                                                                   \
        }                                                                               \
    } while (0)

static int test_sizes(void)
{
    CHECK(rt_snapshot_stub_size(0, 0, 0) == 5u);
    CHECK(rt_snapshot_stub_size(0, 1, 0) == 5u);   /* the empty form does not carry a selector */
    /* The capture form exists in two selector shapes: baked bases (the harness's, 88) and the
       per-thread %gs form the product emits (86). */
    CHECK(rt_snapshot_stub_size(1, 0, 0) == 88u);   /* 75 + 13 entry counter */
    CHECK(rt_snapshot_stub_size(1, 1, 0) == 0u);    /* unemittable: no checker, no form */
    CHECK(rt_snapshot_stub_size(1, 1, 0x1000) == 91u); /* 86 + 5 checker call */
    return 0;
}

static int test_emit_and_target(void)
{
    unsigned char buf[16];
    memset(buf, 0xcc, sizeof buf);
    const uint64_t self = 0x10000, stub = 0x10100 + 0x40;
    const size_t n = rt_write_snapshot_stub(buf, sizeof buf, self, stub, 0, 0, 0, 0, 0, 0);
    CHECK(n == 5);
    CHECK(buf[0] == 0xe9);
    int32_t rel;
    memcpy(&rel, buf + 1, 4);
    CHECK((uint64_t)((int64_t)(self + n) + rel) == stub); /* the jump lands where it says */
    CHECK(buf[5] == 0xcc);                                /* writes five bytes, not six */
    return 0;
}

static int test_refusals_leave_the_page_alone(void)
{
    unsigned char buf[16];
    memset(buf, 0xcc, sizeof buf);

    /* too small: refuse before the first store */
    CHECK(rt_write_snapshot_stub(buf, 4, 0x1000, 0x1010, 0, 0, 0, 0, 0, 0) == 0);
    /* a far target silently needs the 14-byte absolute form, so it is refused instead. The edge is
       exactly INT32_MAX from the byte AFTER the opcode: self + 5 + INT32_MAX is the last reachable
       target, one byte further is not. Stated as the edge, because "1<<31" is *inside* the range and my
       first version of this line asserted a refusal that should not happen. */
    CHECK(rt_write_snapshot_stub(buf, sizeof buf, 0x1000, 0x1000 + 5 + (uint64_t)INT32_MAX, 0, 0, 0, 0, 0, 0) == 5);
    CHECK(rt_write_snapshot_stub(buf, sizeof buf, 0x1000, 0x1000 + 6 + (uint64_t)INT32_MAX, 0, 0, 0, 0, 0, 0) == 0);
    /* the capture form now EXISTS: 75 bytes baked / 73 per-thread, and RT_BOUNDARY_STUB_MAX (96) must take it. A 16-byte buffer
       refuses -- the size is a property of the FORM, and the old failure was reading it off a buffer too small
       to hold what the form needs. */
    {
        unsigned char roomy[96];
        memset(roomy, 0xcc, sizeof roomy);
        CHECK(rt_write_snapshot_stub(roomy, sizeof roomy, 0x1000, 0x1010, 0, 0, (uint64_t)(uintptr_t)roomy, 1, 0, 0) == 88u);
        CHECK(roomy[88] == 0xcc);   /* writes 88 bytes, not 89 */
        CHECK(roomy[0] == 0x49 && roomy[1] == 0xbb);            /* movabs r11, &entered: BEFORE the pushes */
        CHECK(roomy[10] == 0x49 && roomy[12] == 0x03);            /* incq [r11] closes the counter at byte 12 */
        CHECK(roomy[13] == 0x57);   /* push rdi: the first of the six, at byte 13 */
        CHECK(roomy[31] == 0xf3 && roomy[35] == 0xd3);          /* wrfsbase r11 -- F3 present, /2 not /3 */
    }
    /* and one byte short must refuse before the first store */
    {
        unsigned char tight[87];
        memset(tight, 0xcc, sizeof tight);
        CHECK(rt_write_snapshot_stub(tight, sizeof tight, 0x1000, 0x1010, 0, 0, (uint64_t)(uintptr_t)tight, 1, 0, 0) == 0);
        CHECK(tight[0] == 0xcc);
    }
    /* The product's per-thread form: the two base slots are %gs loads, not main's baked movabs, and
       the first instruction sequence after the pushes is the checker call. The call shifts every
       literal below by five: counted from the instruction stream, never from the baked offsets. */
    {
        unsigned char roomy[96];
        unsigned char checker[128];
        memset(roomy, 0xcc, sizeof roomy);
        memset(checker, 0xcc, sizeof checker);
        const size_t cn = rt_write_tls_check(checker, sizeof checker, (uint64_t)(uintptr_t)checker);
        CHECK(cn == rt_tls_check_size());
        CHECK(rt_write_snapshot_stub(roomy, sizeof roomy, 0x1000, 0x1010, 0, 0,
                                     (uint64_t)(uintptr_t)roomy, 1, 1,
                                     (uint64_t)(uintptr_t)checker) == 91u);
        CHECK(roomy[91] == 0xcc);   /* writes 91 bytes, not 92 */
        static const unsigned char host_gs[] = {0x65, 0x4c, 0x8b, 0x1c, 0x25,
                                                RT_TLS_GS_HOST_FSBASE_OFF & 0xffu, 0, 0, 0};
        static const unsigned char guest_gs[] = {0x65, 0x4c, 0x8b, 0x1c, 0x25,
                                                 RT_TLS_GS_GUEST_BLOCK_OFF & 0xffu, 0, 0, 0};
        CHECK(roomy[21] == 0xe8);                                   /* call checker at 21 */
        CHECK(memcmp(roomy + 26, host_gs, sizeof host_gs) == 0);
        CHECK(roomy[35] == 0xf3 && roomy[39] == 0xd3);              /* wrfsbase r11 after the gs load */
        CHECK(memcmp(roomy + 64, guest_gs, sizeof guest_gs) == 0);
        CHECK(roomy[73] == 0xf3 && roomy[77] == 0xd3);              /* wrfsbase r11 before the pops */
        CHECK(roomy[86] == 0xe9);                                   /* jmp rel32 at the tail */
    }
    /* null dst */
    CHECK(rt_write_snapshot_stub(NULL, sizeof buf, 0x1000, 0x1010, 0, 0, 0, 0, 0, 0) == 0);
    memset(buf, 0xcc, sizeof buf); /* re-poison: the edge check above was allowed to write */

    for (size_t i = 0; i < sizeof buf; i++) CHECK(buf[i] == 0xcc);
    return 0;
}

int main(void)
{
    if (test_sizes() || test_emit_and_target() || test_refusals_leave_the_page_alone()) return 1;
    puts("snapshot_stub: ok");
    return 0;
}
