/* SPDX-License-Identifier: GPL-2.0-or-later */
/* The one place a system call checks guest memory before writing it.

   This started in clock.c because gettimeofday was the first syscall here that wrote guest memory at
   all. A check with one caller is a habit; the second caller is what makes it an interface, so it lives
   here now and every later writer routes through it. It refuses with the address and the image bounds
   instead of taking a signal: a range outside the image is a caller bug worth naming. */
#include "runtime/guest_mem.h"

#include "runtime/process.h"

#include <stdio.h>

int rt_guest_write_ok(uintptr_t addr, size_t len, const char *call)
{
    uintptr_t base = (uintptr_t)rt_process.image;
    uintptr_t end = base + (uintptr_t)rt_process.image_size;
    if (len == 0) return 1;
    if (addr < base || end < base || len > end - addr) {
        fprintf(stderr, "pbboot: %s: refused write of %zu bytes at %p, outside the image [%p,%p)\n", call,
                len, (void *)addr, (void *)base, (void *)end);
        return 0;
    }
    return 1;
}
