/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Two directions, because one direction is what the defect was: with the bounds unset the check used to
   admit every address through an unsigned underflow, and only a control that PASSES for the wrong reason
   can be distinguished from one that passes for the right one. */
#include <stdio.h>
#include <string.h>

#include "runtime/guest_mem.h"
#include "runtime/process.h"
#include "runtime/site_guard.h"

static int failed;

static void check(int ok, const char *what)
{
    if (!ok) {
        printf("test_guest_mem: %s\n", what);
        failed = 1;
    }
}

/* The bias and the prologue: two claims, each cheap to get wrong invisibly. */
static int site_guard_cases(void)
{
    /* check() sets the file-scope flag and returns void: |= here would be a type error, and a local
       flag of the same name would silence every case in this function. */
    /* 1. The image bias is RT_EBOOT_BASE, and it differs from the file bias by exactly p_offset. */
    const uint64_t guest = 0x02418d20u;
    check(rt_image_offset(guest) == guest - 0x400000u, "image offset must use RT_EBOOT_BASE");
    check(rt_image_offset(guest) != guest - 0x3fc000u, "the file bias is not the image bias");
    check((guest - 0x3fc000u) - rt_image_offset(guest) == 0x4000u, "they differ by 0x4000, not by 0");

    /* 2. A prologue at image offset 0x4000 passes; probing at the FILE bias lands 16 KiB lower, where the
          bytes are not the function's, and refuses. That is the shift this guard exists to catch. */
    static unsigned char image[0x10000];
    unsigned char expected[4] = {0x55, 0x48, 0x89, 0xe5};
    const uint64_t probe = 0x400000u + 0x4000u;
    memcpy(image + 0x4000, expected, sizeof expected);
    check(rt_site_matches(image, sizeof image, probe, expected, sizeof expected) == 1,
          "matching prologue at the image offset must pass");
    check(rt_site_matches(image, sizeof image, probe - 0x4000u, expected, sizeof expected) == 0,
          "the same expectation probed at the file bias must fail: 16 KiB is a different function");
    check(rt_site_matches(image, sizeof image, probe, expected, 0) == 0,
          "an empty expectation is not agreement");
    return 0;
}

int main(void)
{
    (void)site_guard_cases();
    unsigned char image[0x1000];

    /* 1. Bounds unset: every address is refused, including a plausible one. This is the plugin path,
          where boot.c never ran. */
    rt_process.image = NULL;
    rt_process.image_size = 0;
    check(!rt_guest_write_ok((uintptr_t)image, 8, "unset"), "unset bounds must refuse a plausible address");
    check(!rt_guest_ptr_ok(0x800000000ULL, 8, "unset"), "unset bounds must refuse a guest address");

    /* 2. Bounds set: inside passes, outside fails, and the last byte of the range is the boundary. */
    rt_process.image = image;
    rt_process.image_size = sizeof image;
    check(rt_guest_write_ok((uintptr_t)image, 8, "set"), "an address inside the image must pass");
    check(rt_guest_write_ok((uintptr_t)image + sizeof image - 8, 8, "last"), "the last 8 bytes must pass");
    check(!rt_guest_write_ok((uintptr_t)image + sizeof image - 7, 8, "overrun"), "a range past the end must fail");
    check(!rt_guest_write_ok((uintptr_t)image - 1, 1, "before"), "an address before the image must fail");
    check(rt_guest_write_ok(0, 0, "empty"), "a zero-length range must pass, as before");

    /* 3. Size zero is the unset state by another route: refuse rather than admit. */
    rt_process.image = image;
    rt_process.image_size = 0;
    check(!rt_guest_write_ok((uintptr_t)image, 8, "zerosize"), "a zero image size must refuse");

    rt_process.image = NULL;
    rt_process.image_size = 0;
    return failed;
}
