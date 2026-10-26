/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Flexible memory. The guest asked for 0x3000000 bytes with prot 3 (read/write), and its caller uses the
   returned pointer as a structure: a refusal that left the out pointer zero would take the failure arm,
   so a model that returns a real mapping is the honest way to let the guest continue. The mapping is
   registered with guest_mem.c, because the image is not the whole of guest memory and a bounds check that
   knows only the image refuses a pointer the guest can legitimately write.

   Flags are not modelled beyond anonymous private RW; a guest that asks for aliased or executable
   flexible memory gets the data mapping and a printed line. No release path exists yet: a guest that
   calls sceKernelReleaseFlexibleMemory will stop by name at that import, which is the next slice. */
#include "runtime/guest_mem.h"
#include "runtime/syslib.h"

#include <stdio.h>
#include <stdint.h>
#include <sys/mman.h>

enum { k_err_inval = (int)0x80020016u, k_err_nomem = (int)0x8002000cu };

static int map_flexible_memory(void **addr, size_t size, int prot, int flags)
{
    (void)flags;
    if (!addr || size == 0)
        return k_err_inval;
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED)
        return k_err_nomem;
    if (!rt_guest_register_mapping((uintptr_t)p, size)) {
        munmap(p, size);
        fprintf(stderr, "pbboot: sceKernelMapFlexibleMemory: the guest mapping table is full; refusing %zu bytes\n",
                size);
        return k_err_nomem;
    }
    *addr = p;
    static unsigned reported;
    if (!reported++)
        fprintf(stderr, "pbboot: libkernel sceKernelMapFlexibleMemory: MODELLED %zu bytes prot=0x%x -> %p "
                        "(anonymous RW, registered as guest memory; flags=0x%x not modelled)\n",
                size, prot, p, flags);
    return 0;
}

RT_SYSLIB("libkernel", sceKernelMapFlexibleMemory, map_flexible_memory);
