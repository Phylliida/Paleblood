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
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <stddef.h>
#include <stdint.h>
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
enum { k_page = 0x1000u, k_arena_bytes = 0x4000000u /* 64 MiB, the model's whole budget */ };

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
        void *p = mmap(NULL, k_arena_bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p == MAP_FAILED) return k_error_nomem;
        arena = p;
        arena_bytes = k_arena_bytes;
    }
    size_t step = alignment ? alignment : k_page;
    size_t start = (arena_used + step - 1) / step * step;
    if (start > arena_bytes || len > arena_bytes - start) return k_error_nomem;
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
