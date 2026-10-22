/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Two directions, because one direction is what the defect was: with the bounds unset the check used to
   admit every address through an unsigned underflow, and only a control that PASSES for the wrong reason
   can be distinguished from one that passes for the right one. */
#include <stdio.h>
#include <string.h>

#include "runtime/guest_mem.h"
#include "runtime/process.h"

static int failed;

static void check(int ok, const char *what)
{
    if (!ok) {
        printf("test_guest_mem: %s\n", what);
        failed = 1;
    }
}

int main(void)
{
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
