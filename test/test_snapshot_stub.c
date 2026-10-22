/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Commit A's gate: the hook-only snapshot wrapper is a 5-byte `e9 rel32` and nothing else, and every
   refusal happens before the first store. Proved by the sentinel, not by the absence of a write. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "runtime/boundary_stub.h"

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
    CHECK(rt_snapshot_stub_size(0) == 5u);
    /* The capture form is not emitted yet, and its size refuses rather than guesses: an unsatisfiable
       size is the only value that keeps the capacity check covering a form that has no bytes. */
    CHECK(rt_snapshot_stub_size(1) == SIZE_MAX);
    return 0;
}

static int test_emit_and_target(void)
{
    unsigned char buf[16];
    memset(buf, 0xcc, sizeof buf);
    const uint64_t self = 0x10000, stub = 0x10100 + 0x40;
    const size_t n = rt_write_snapshot_stub(buf, sizeof buf, self, stub, 0);
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
    CHECK(rt_write_snapshot_stub(buf, 4, 0x1000, 0x1010, 0) == 0);
    /* a far target silently needs the 14-byte absolute form, so it is refused instead. The edge is
       exactly INT32_MAX from the byte AFTER the opcode: self + 5 + INT32_MAX is the last reachable
       target, one byte further is not. Stated as the edge, because "1<<31" is *inside* the range and my
       first version of this line asserted a refusal that should not happen. */
    CHECK(rt_write_snapshot_stub(buf, sizeof buf, 0x1000, 0x1000 + 5 + (uint64_t)INT32_MAX, 0) == 5);
    CHECK(rt_write_snapshot_stub(buf, sizeof buf, 0x1000, 0x1000 + 6 + (uint64_t)INT32_MAX, 0) == 0);
    /* the capture form with capacity to spare: refused because its bytes do not exist yet */
    CHECK(rt_write_snapshot_stub(buf, sizeof buf, 0x1000, 0x1010, 1) == 0);
    /* null dst */
    CHECK(rt_write_snapshot_stub(NULL, sizeof buf, 0x1000, 0x1010, 0) == 0);
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
