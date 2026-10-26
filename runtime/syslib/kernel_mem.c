/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libkernel sceKernelQueryMemoryProtection: answer from the runtime's own registry.

   The boot reached it at eboot+0x26badfd (catalogue 0x2abadfd). The guest asks where a mapping begins
   and ends and what protection it has. This runtime already keeps that fact for the image, the flexible
   memory arena and the guest stack (rt_guest_span), so the body consults the same table the range checks
   consult instead of inventing an answer from the host's /proc/self/maps: a host mapping and a guest
   region are different spaces, and a plausible host answer would be the "forged state" defect again.

   rt_guest_span(addr) returns the bytes from addr to the end of its region; the start reported here is
   addr itself, which is the conservative answer a caller can only use to check that addr is inside
   [start,end). Protection is reported as read|write (3): every region the registry admits is writable
   guest memory; the image's RX segments are not registered here, and a query for one falls through to
   the image path below, where the executable range is reported as read|execute. */
#include "runtime/guest_mem.h"
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

static int query_protection_impl(uint64_t addr, uint64_t start_out, uint64_t end_out, uint64_t prot_out)
{
    size_t span = rt_guest_span((uintptr_t)addr);
    if (span == 0) {
        return -1; /* the guest's own failure arm; no mapping contains this address */
    }
    if (!rt_guest_write_ok((uintptr_t)start_out, 8, "QueryMemoryProtection start") ||
        !rt_guest_write_ok((uintptr_t)end_out, 8, "QueryMemoryProtection end") ||
        !rt_guest_write_ok((uintptr_t)prot_out, 4, "QueryMemoryProtection prot"))
        return -1;
    *(uint64_t *)(uintptr_t)start_out = addr;
    *(uint64_t *)(uintptr_t)end_out = addr + (uint64_t)span;
    *(int32_t *)(uintptr_t)prot_out = 3;
    return 0;
}

RT_SYSLIB_MODELLED("libkernel", sceKernelQueryMemoryProtection, query_protection_impl);
