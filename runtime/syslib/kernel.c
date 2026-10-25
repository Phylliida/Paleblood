/* SPDX-License-Identifier: GPL-2.0-or-later */
/* System call group: kernel, threads and memory (libkernel, libScePosix, libSceSysmodule,
   libSceLibcInternal). */
#include "runtime/guest_mem.h"
#include "runtime/process.h"

#include <stdio.h>
#include <stdlib.h>
#include "runtime/syslib.h"

#include <string.h>

/* The process parameter block: the executable's PT_SCE_PROCPARAM segment as mapped. */
static void *kernel_get_proc_param(void)
{
    /* Probe, before anything else in this boot touches the heap: is glibc's allocator healthy this early? */
    {
        uint64_t live = 0;
        __asm__ volatile("rdfsbase %0" : "=r"(live));
        fprintf(stderr, "pbboot: in-body fs %#llx (compare with the fs line in the report)\n",
                (unsigned long long)live);
        void *p = malloc(48);
        fprintf(stderr, "pbboot: heap probe (before #23): malloc(48) = %p\n", p);
        free(p);
    }
    if (!rt_process.proc_param) rt_fatal("sceKernelGetProcParam", "the executable has no process parameter segment");
    if (!rt_guest_ptr_ok((uintptr_t)rt_process.proc_param, 4, "sceKernelGetProcParam")) {
        fprintf(stderr, "pbboot: sceKernelGetProcParam: proc_param %p, image %p\n", rt_process.proc_param,
                (void *)rt_process.image);
        rt_fatal("sceKernelGetProcParam", "the process parameter pointer is not inside the mapped image");
    }
    return rt_process.proc_param;
}
RT_SYSLIB("libkernel", sceKernelGetProcParam, kernel_get_proc_param);

/* The C library registers its heap functions (a table of function pointers, its own or the
   application's replacements) so that system code allocates from the application's heap. Called
   once while the C library starts; the result is not used by the caller. */
static void kernel_rtld_set_application_heap_api(void **heap_api)
{
    if (!heap_api) rt_fatal("_sceKernelRtldSetApplicationHeapAPI", "no table");
    rt_process.heap_api = heap_api;
}
RT_SYSLIB("libkernel", _sceKernelRtldSetApplicationHeapAPI, kernel_rtld_set_application_heap_api);

/* getpagesize, imported by eboot from libScePosix and by libc.elf from libkernel
   (symbols/imports.csv, two rows naming one call): the loader binds an import by library and NID
   (runtime/boot.c), so each library needs its own entry, both pointing here.

   The PS4's system page size is not established by any evidence we can cite. The target's ELF
   headers bound it at best, and only under assumptions about the PS4 loader; the guest itself just
   rejects a non-power-of-two and caches whatever it gets, so it never states the number. The full
   record - what is observed, what is inferred and on which premise, and what remains open - is in
   docs/runtime-syscalls.md, section "getpagesize: observed, inferred, unknown".

   So the call fails loudly instead of returning an invented number or the host's page size. It is
   registered with RT_SYSLIB_UNRESOLVED: the boot gets a named diagnostic if it reaches this, and
   coverage leaves the import unchecked, since a diagnostic is not an implementation. */
static void kernel_getpagesize(void)
{
    rt_fatal("getpagesize", "the PS4 system page size is not established by public evidence");
}
RT_SYSLIB_UNRESOLVED("libScePosix", getpagesize, kernel_getpagesize);
RT_SYSLIB_UNRESOLVED("libkernel", getpagesize, kernel_getpagesize);

/* memcpy and memset, imported by libSceFios2.elf from libSceLibcInternal (symbols/imports.csv). ISO C
   (7.24.2.1 and 7.24.6.1) fixes their whole result for valid arguments: memcpy copies n bytes from
   the source to the destination, memset writes c converted to unsigned char into the first n bytes,
   and both return the destination. No target-specific value is involved, so the host's own functions
   carry out the same contract. What the standard leaves undefined (overlapping memcpy regions, null
   pointers) is not modelled: no PS4-specific behaviour for those cases is established. */
static void *libc_memcpy(void *dest, const void *src, size_t n)
{
    /* A null destination is a guest bug on the real machine too -- but there it kills the guest, and here it
       kills host glibc inside our body, which presents as our fault. Name it instead: the guest's address
       space is the guest's business, the diagnostic is ours. */
    if (!rt_guest_ptr_ok((uintptr_t)dest, n, "memcpy dest")) return dest;
    if (!rt_guest_ptr_ok((uintptr_t)src, n, "memcpy src")) return dest;
    return memcpy(dest, src, n);
}
RT_SYSLIB("libSceLibcInternal", memcpy, libc_memcpy);
/* The SAME two C contracts, imported by eboot from `libc` (symbols/imports.csv:522/524) while this table
   only carried them for libSceFios2. An alias row asserts a shared CONTRACT, not a shared implementation:
   `memcpy` is ISO C 7.24.2.1 for valid arguments and undefined for overlapping regions on both providers,
   so no target-specific value distinguishes them, and the alias cannot hide a difference the standard
   leaves open. A wildcard over libraries would hide exactly that; a row with a stated contract can be
   falsified by any caller that relies on what the standard leaves undefined. */
RT_SYSLIB("libc", memcpy, libc_memcpy);

static void *libc_memset(void *dest, int c, size_t n)
{
    if (!rt_guest_ptr_ok((uintptr_t)dest, n, "memset dest")) return dest;
    return memset(dest, c, n);
}
RT_SYSLIB("libSceLibcInternal", memset, libc_memset);
/* Same contract claim as memcpy's alias above: ISO C 7.24.6.1, imported by eboot from `libc`. */
RT_SYSLIB("libc", memset, libc_memset);

/* sceKernelGetDirectMemorySize: the size of the direct memory region the guest may address.
   The runtime maps exactly the executable's image (runtime/boot.c: rt_process.image /
   image_size, one mapping sized by the loader), so the only figure it can vouch for is that
   mapping -- this returns a FLOOR, not the console's value. The console figure is not sourced
   here: it is not in the process parameter block this runtime reads, and I have no citation for
   it, so it is not written down. Residual, stated as the affinity constant's is: a caller that
   needs more than the image gets the truth about what is mapped instead of a plausible round
   number, and the value is checked, not asserted in a comment. */
static unsigned long kernel_get_direct_memory_size(void)
{
    unsigned long mapped = rt_process.image_size;
    if (mapped == 0) rt_fatal("sceKernelGetDirectMemorySize", "the image is not mapped");
    /* image_size is the last segment's vaddr + memsz, so it is not page-aligned by construction --
       the first run fataled here, which is the check doing its job on my assumption rather than on
       the runtime. The mapping is a page mapping, so the bytes the guest can address are this
       figure rounded up; returning the unrounded one would understate what is readable. */
    return (mapped + 0xfff) & ~0xfffUL;
}
RT_SYSLIB("libkernel", sceKernelGetDirectMemorySize, kernel_get_direct_memory_size);
