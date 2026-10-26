/* SPDX-License-Identifier: GPL-2.0-or-later */
/* The one place a system call checks guest memory before writing it.

   This started in clock.c because gettimeofday was the first syscall here that wrote guest memory at
   all. A check with one caller is a habit; the second caller is what makes it an interface, so it lives
   here now and every later writer routes through it. It refuses with the address and the image bounds
   instead of taking a signal: a range outside the image is a caller bug worth naming. */
#include "runtime/guest_mem.h"

#include "runtime/process.h"

#include <stdio.h>

/* The outbound direction. An address this runtime hands to the guest is the same hazard as one the guest
   hands to us, with the failure deferred: a bad value does not fault here, it faults later inside a module
   we do not own, which is how the missing bias on the process parameter presented. Same check, same
   sentence, other direction. */
int rt_guest_ptr_ok(uintptr_t addr, size_t len, const char *call)
{
    return rt_guest_write_ok(addr, len, call);
}

/* Guest mappings created after the image (sceKernelMapFlexibleMemory). The image is not the whole of
   guest memory: a pointer into a registered mapping is a guest pointer, and the image-range check is the
   wrong instrument for it. One table, because there is one writer of these mappings. */
#define RT_GUEST_MAPPINGS 64
static struct { uintptr_t base, end; } g_guest_mappings[RT_GUEST_MAPPINGS];
static unsigned g_guest_mapping_count;

int rt_guest_register_mapping(uintptr_t base, size_t len)
{
    if (!base || len == 0 || len > UINTPTR_MAX - base)
        return 0;
    if (g_guest_mapping_count >= RT_GUEST_MAPPINGS)
        return 0;
    g_guest_mappings[g_guest_mapping_count].base = base;
    g_guest_mappings[g_guest_mapping_count].end = base + len;
    g_guest_mapping_count++;
    return 1;
}

static int guest_mapping_contains(uintptr_t addr, size_t len)
{
    for (unsigned i = 0; i < g_guest_mapping_count; i++) {
        const uintptr_t b = g_guest_mappings[i].base, e = g_guest_mappings[i].end;
        if (addr >= b && addr < e && len <= e - addr)
            return 1;
    }
    return 0;
}

int rt_guest_write_ok(uintptr_t addr, size_t len, const char *call)
{
    uintptr_t base = (uintptr_t)rt_process.image;
    uintptr_t end = base + (uintptr_t)rt_process.image_size;
    if (len == 0) return 1;
    if (guest_mapping_contains(addr, len)) return 1;
    /* rt_process.image is set in exactly one place, boot.c, so on the plugin path it is NULL and this
       function used to admit EVERY address: with base == end == 0, `end - addr` underflows to a huge
       unsigned value and `len > huge` is false. A bounds check whose subject was never initialised is
       a licence, not a guard, so an unset image is now a refusal that says so -- and an image size of
       zero is the same state by another route. */
    if (!base || !end || end < base) {
        fprintf(stderr, "pbboot: %s: refused %zu bytes at %p: the guest image bounds are unset "
                "(rt_process.image is only initialised by boot.c)\n", call, len, (void *)addr);
        return 0;
    }
    if (addr < base || len > end - addr) {
        fprintf(stderr, "pbboot: %s: refused write of %zu bytes at %p, outside the image [%p,%p)\n", call,
                len, (void *)addr, (void *)base, (void *)end);
        return 0;
    }
    return 1;
}
