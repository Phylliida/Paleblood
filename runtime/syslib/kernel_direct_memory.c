/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Direct memory: one bump arena with four entries in front of it.

   sceKernelAllocateDirectMemory writes an address through its last argument, so a stub that
   returned success without writing would hand the guest garbage it uses on the next instruction.
   A model is testable; a no-op is not.

   The model, and its residual stated as the affinity constant's is:
     - no physical/virtual distinction: the address handed back is host memory, not a console
       physical offset, and nothing here translates between the two;
     - no fragmentation and no reuse: a bump pointer only moves forward;
     - no reclaim: Release checks the range and reports success, but the bytes are not returned to
       the arena, because a later allocation claiming a released range would silently alias.

   Sources for the two values that are not parameters: the arena is one page-aligned mapping and
   the default alignment is a page, both taken from the runtime's own page size rather than a
   round number written here. */
#include "runtime/guest_mem.h"
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>

/* Error values are the model's own, not console codes: I have no citation for the kernel's
   numbers, and inventing them would be indistinguishable from having them. */
enum { k_error_inval = 0x16, k_error_fault = 0x0e, k_error_nomem = 0x0c };

/* INVARIANT, and it is not deferrable: this runtime has one address space. The guest is a single
   mapping, so an address this arena hands out is already guest-dereferenceable and
   sceKernelMapDirectMemory must be the IDENTITY over the arena -- it returns the physical address
   it was given. If Map instead invented a separate virtual range, every range Allocate had
   already handed out would become unreadable the moment anything mapped it, and the failure would
   look like memory corruption in whichever consumer ran second. */
/* Reserve, don't ration: the mapping is anonymous and private, so untouched pages cost nothing and
   the arena's ceiling is address space, not memory. A fixed budget here is a number I invented, and
   the guest asked for 116 MiB against a 64 MiB budget at Ps4RuntimeHeapImpl.cpp(324) -- a refusal
   that the guest reports as a fatal panic, which is how six slices were spent downstream of it. */
enum { k_page = 0x1000u, k_arena_bytes = 0x200000000ull /* 8 GiB reserved, committed on touch */ };

static unsigned char *arena;
static size_t arena_used;
static size_t arena_bytes;

static int kernel_allocate_direct_memory(int64_t search_start, int64_t search_end, size_t len,
                                         size_t alignment, int memory_type, int64_t *physical)
{
    (void)search_start;
    (void)search_end;
    (void)memory_type;
    if (!physical) return k_error_fault;
    if (len == 0) return k_error_inval;
    if (!arena) {
        void *p = mmap(NULL, k_arena_bytes, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
        if (p == MAP_FAILED) return k_error_nomem;
        arena = p;
        arena_bytes = k_arena_bytes;
        /* Direct memory is guest memory. Register the whole arena once: a guest pointer into it is not
           an image pointer, and the checked libc paths ask the registry, not the image. The flexible
           mapping was registered and this arena was not -- two producers, one registry, and the second
           producer forgot until a wcscmp in direct memory refused. */
        if (!rt_guest_register_mapping((uintptr_t)arena, arena_bytes)) {
            munmap(p, k_arena_bytes);
            arena = NULL;
            arena_bytes = 0;
            return k_error_nomem;
        }
    }
    size_t step = alignment ? alignment : k_page;
    size_t start = (arena_used + step - 1) / step * step;
    if (start > arena_bytes || len > arena_bytes - start) {
        /* The refusal must be as loud as the guest's, and in the same units. */
        fprintf(stderr, "pbboot: direct memory: allocation of %zu bytes refused, %zu of %zu used\n", len,
                arena_used, arena_bytes);
        return k_error_nomem;
    }
    *physical = (int64_t)(uintptr_t)(arena + start);
    arena_used = start + len;
    return 0;
}
RT_SYSLIB("libkernel", sceKernelAllocateDirectMemory, kernel_allocate_direct_memory);

/* Whether a range was ever handed out is the only thing this can honestly check: the bytes stay
   in the arena, so success here means "that range was inside the model", not "it is now free". */
static int kernel_release_direct_memory(int64_t start, size_t len)
{
    if (!arena || start < (int64_t)(uintptr_t)arena) return k_error_inval;
    size_t offset = (size_t)(start - (int64_t)(uintptr_t)arena);
    if (offset > arena_bytes || len > arena_bytes - offset) return k_error_inval;
    return 0;
}
RT_SYSLIB("libkernel", sceKernelReleaseDirectMemory, kernel_release_direct_memory);

/* Map is the identity, and that is the whole model: an address this arena handed out is already a host
   address, so mapping it yields the same value. Three consequences, each a refusal rather than a rescue:
     - a non-null hint that differs from the identity is refused, because silently relocating would
       invalidate every range Allocate had already handed out;
     - prot is logged, never obeyed, and mprotect is never called: our pages are already read-write and
       honouring a read-only request would violate the identity at the next writer;
     - a range that does not lie inside the arena is refused, because the identity is only defined over
       memory this model owns. */
static int kernel_map_direct_memory(int64_t addr_out, size_t len, int prot, int flags, int64_t start,
                                    size_t alignment)
{
    (void)alignment;
    if (addr_out == 0) return k_error_fault;
    if (!arena) return k_error_inval; /* no base yet: nothing to be the identity of */
    int64_t *out = (int64_t *)(uintptr_t)addr_out;
    int64_t base = (int64_t)(uintptr_t)arena;
    if (start < base || (size_t)(start - base) > arena_bytes || len > arena_bytes - (size_t)(start - base))
        return k_error_inval;
    if (*out != 0 && *out != start) {
        fprintf(stderr, "pbboot: direct memory: Map refused, hint %p is not the identity %p\n",
                (void *)(uintptr_t)*out, (void *)(uintptr_t)start);
        return k_error_inval;
    }
    if (prot != (PROT_READ | PROT_WRITE) || flags != 0)
        fprintf(stderr, "pbboot: direct memory: Map start=%p len=%zu prot=%d flags=%d (logged, not obeyed)\n",
                (void *)(uintptr_t)start, len, prot, flags);
    *out = start;
    return 0;
}
RT_SYSLIB("libkernel", sceKernelMapDirectMemory, kernel_map_direct_memory);
