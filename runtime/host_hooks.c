/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime/host_hooks.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

#include "runtime/boundary_stub.h"

#if !defined(__x86_64__)
#error "The version-1 host hook callback requires an x86-64 host"
#endif

enum { ABSOLUTE_JUMP_SIZE = 14 };

static unsigned char *guest_image;
static uint64_t guest_image_size;

/* Once the boot has installed a guest block, the guest's %fs is live, and a bare jump would run the
   replacement on the guest's TCB, where glibc's errno and stack protector are not -- the shape that
   cost seven slices in the import trampoline, one level down. So when TLS is live the 14 bytes point
   at a stub that swaps %fs and aligns the stack; the crossing itself is emitted by
   runtime/boundary_stub.c, the same code the import trampolines use, because a second hand-written
   prologue is how the /3-for-/2 bug survived for days. Weak, because the differential harness links
   no TLS, has no guest block, and passes an installer that installs nothing. */
extern uint64_t rt_tls_guest_base(void) __attribute__((weak));
extern uint64_t rt_tls_host_base(void) __attribute__((weak));

static int guest_tls_is_live(void)
{
    return rt_tls_guest_base && rt_tls_host_base && rt_tls_guest_base() != 0;
}

/* One page of executable memory holds every hook's stub. Bounded and reported, never a silent
   overrun: a hook that cannot get a stub must fail loudly, because a jump to nowhere is a green run
   that executes nothing. */
enum { STUB_PAGE = 4096 };
static unsigned char *stub_area;
static size_t stub_used;

static unsigned char *stub_alloc(size_t n)
{
    if (!stub_area) {
        void *p = mmap(NULL, STUB_PAGE, PROT_READ | PROT_WRITE | PROT_EXEC,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p == MAP_FAILED) return NULL;
        stub_area = p;
    }
    if (n > STUB_PAGE - stub_used) return NULL;
    unsigned char *p = stub_area + stub_used;
    stub_used += n;
    return p;
}

/* A hook written into a page the process cannot execute reads back perfectly and never fires: the
   readback proves the bytes, not the mapping. Ask /proc/self/maps about the page the patch lands in,
   and fail closed if the answer cannot be read. This is the "N installed counts writes" defect one
   level up, and it is cheap here for the same reason it is expensive later. */
static int region_is_executable(const void *address, size_t length)
{
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 0;
    const uintptr_t start = (uintptr_t)address;
    const uintptr_t end = start + length;
    char line[512];
    int executable = 0;
    while (fgets(line, sizeof line, maps)) {
        unsigned long low = 0, high = 0;
        char perms[5] = {0};
        if (sscanf(line, "%lx-%lx %4s", &low, &high, perms) != 3) continue;
        if ((uintptr_t)low <= start && end <= (uintptr_t)high) {
            executable = (perms[2] == 'x');
            break;
        }
    }
    fclose(maps);
    return executable;
}

static int install_hook(uint64_t offset, uint64_t size, const void *target)
{
    if (!guest_image || !target || size < ABSOLUTE_JUMP_SIZE || offset > guest_image_size ||
        size > guest_image_size - offset)
        return -1;

    if (!region_is_executable(guest_image + offset, ABSOLUTE_JUMP_SIZE)) {
        fprintf(stderr, "hook: refusing to patch 0x%llx: the 14 bytes at 0x%llx are not in an "
                "executable mapping, so the patch would read back and never fire\n",
                (unsigned long long)offset, (unsigned long long)(uintptr_t)(guest_image + offset));
        return -1;
    }

    /* With a live guest %fs the jump goes to a boundary stub: swap to the host base, park the guest's
       rsp in rbx, align, call, restore both. Without TLS (the harness) there is nothing to swap and
       the jump goes straight to the target, which is what every existing caller sees. */
    uintptr_t destination = (uintptr_t)target;
    if (guest_tls_is_live()) {
        unsigned char *stub = stub_alloc(RT_BOUNDARY_STUB_MAX);
        if (!stub) {
            fprintf(stderr, "hook: no room for a boundary stub at 0x%llx (page holds %u of %u bytes)\n",
                    (unsigned long long)offset, (unsigned)STUB_PAGE, (unsigned)stub_used);
            return -1;
        }
        size_t n = rt_write_boundary_stub(stub, (uint64_t)(uintptr_t)target,
                                          rt_tls_host_base(), rt_tls_guest_base(), 0);
        __builtin___clear_cache((char *)stub, (char *)stub + n);
        destination = (uintptr_t)stub;
        if (getenv("BB_HOOK_VERBOSE"))
            fprintf(stderr, "hook: 0x%llx -> %zu-byte boundary stub at 0x%llx -> body 0x%llx\n",
                    (unsigned long long)offset, n, (unsigned long long)destination,
                    (unsigned long long)(uintptr_t)target);
    }

    /* `jmp qword ptr [rip]` followed by the 64-bit destination preserves every argument register,
       including AL for variadic calls. The loader installs hooks before entering guest code. */
    unsigned char jump[ABSOLUTE_JUMP_SIZE] = {0xff, 0x25, 0, 0, 0, 0};
    if (destination > (uintptr_t)UINTPTR_MAX) return -1;
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
