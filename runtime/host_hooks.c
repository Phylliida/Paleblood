/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime/host_hooks.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(__x86_64__)
#error "The version-1 host hook callback requires an x86-64 host"
#endif

enum { ABSOLUTE_JUMP_SIZE = 14 };

static unsigned char *guest_image;
static uint64_t guest_image_size;

/* Once the boot has installed a guest block, the guest's %fs is live, and this jump has no boundary
   stub: the replacement would run on the guest's TCB, where glibc's errno and stack protector are
   not -- the shape that cost seven slices in the import trampoline, one level down. Refuse rather
   than fault later, and say what is missing. Weak, because the differential harness links no TLS,
   has no guest block, and passes an installer that installs nothing. */
extern uint64_t rt_tls_guest_base(void) __attribute__((weak));

static int guest_tls_is_live(void)
{
    return rt_tls_guest_base && rt_tls_guest_base() != 0;
}

static int install_hook(uint64_t offset, uint64_t size, const void *target)
{
    if (!guest_image || !target || size < ABSOLUTE_JUMP_SIZE || offset > guest_image_size ||
        size > guest_image_size - offset)
        return -1;

    if (guest_tls_is_live()) {
        fprintf(stderr,
                "hook: refusing to patch 0x%llx: the guest %%fs is live and this path has no "
                "boundary stub -- it jumps straight into the replacement, which then runs on the "
                "guest's TCB (glibc errno and stack protector are not there). Install a stub that "
                "swaps %%fs (wrfsbase) and gives the body a 16-byte aligned stack first.\n",
                (unsigned long long)offset);
        return -1;
    }

    /* `jmp qword ptr [rip]` followed by the 64-bit destination preserves every argument register,
       including AL for variadic calls. The loader installs hooks before entering guest code. */
    unsigned char jump[ABSOLUTE_JUMP_SIZE] = {0xff, 0x25, 0, 0, 0, 0};
    const uintptr_t destination = (uintptr_t)target;
    memcpy(jump + 6, &destination, sizeof destination);
    memcpy(guest_image + offset, jump, sizeof jump);
    __builtin___clear_cache((char *)guest_image + offset, (char *)guest_image + offset + sizeof jump);

    /* "N installed" counts writes. Prove the bytes the guest will execute are the bytes written, or
       a write that landed somewhere else reads as a working hook. */
    if (memcmp(guest_image + offset, jump, sizeof jump) != 0) {
        fprintf(stderr, "hook: readback at 0x%llx does not match the jump written\n",
                (unsigned long long)offset);
        return -1;
    }
    if (getenv("BB_HOOK_VERBOSE"))
        fprintf(stderr, "hook: 0x%llx size %llu bytes patched with a %u-byte absolute jump to "
                "host 0x%llx (distance %lld bytes), readback ok\n",
                (unsigned long long)offset, (unsigned long long)size, (unsigned)ABSOLUTE_JUMP_SIZE,
                (unsigned long long)destination,
                (long long)((intptr_t)destination -
                            (intptr_t)(uintptr_t)(guest_image + offset)));
    return 0;
}

int rt_host_hooks_initialize(rt_host *host)
{
    if (!host || host->version != RT_HOST_API_VERSION || !host->image ||
        host->image_size < ABSOLUTE_JUMP_SIZE)
        return -1;

    guest_image = host->image;
    guest_image_size = host->image_size;
    host->install_hook = install_hook;
    return 0;
}
