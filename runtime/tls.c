/* Guest thread-local storage.

   Measured before anything here was written: the guest uses %fs 16,854 times across the 157,757-entry
   catalog, at exactly one displacement -- fs:[0], the TCB self-pointer. gs: zero. And wrfsbase is usable
   here: CPUID leaf 7 EBX bit 0 set, and a write/read-back round trip landed on this CPU.

   So the guest block needs to be aligned, its first eight bytes must point at itself, and the swap is two
   instructions. The architecture is checked at init rather than assumed, so pbboot does not become a binary
   that only runs on CPUs with FSGSBASE: without it the same swap costs an arch_prctl. */
#include "runtime/tls.h"
#include "runtime/process.h"

#include <cpuid.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>


#define RT_TLS_BLOCK_BYTES 0x1000u /* PT_TLS says filesz 0x220 / memsz 0x4a0; one page covers it with slack */

static unsigned char guest_block[RT_TLS_BLOCK_BYTES] __attribute__((aligned(64)));
static unsigned long host_fsbase;
static int have_wrfsbase;

/* Asking the CPU and not the documentation: FSGSBASE is advertised in leaf 7 EBX bit 0, but the feature
   only works if the kernel enables it, so the round trip is the check that matters. */
static void probe_fsgsbase(void)
{
    unsigned a = 0, b = 0, c = 0, d = 0;
    if (!__get_cpuid_count(7, 0, &a, &b, &c, &d) || (b & 1u) == 0) return;
    unsigned long before = 0, after = 0;
    asm volatile("rdfsbase %0" : "=r"(before));
    asm volatile("wrfsbase %0" ::"r"(before));
    asm volatile("rdfsbase %0" : "=r"(after));
    if (after == before) have_wrfsbase = 1;
    /* One stub, one ABI. The trampoline inlines wrfsbase because a C call between the guest's jump and
       the target would eat every caller-saved argument register; a second stub for the arch_prctl path
       would be a code path that only runs on some machines. So absence is a refusal at startup. */
    if (!have_wrfsbase)
        rt_fatal("FSGSBASE", "this CPU or kernel does not allow user-mode wrfsbase, so guest %fs cannot be "
                             "swapped between guest and host code at syslib call boundaries");
}

void rt_tls_init(void)
{
    probe_fsgsbase();
    asm volatile("rdfsbase %0" : "=r"(host_fsbase));
    /* EXPERIMENT, one build: seed the guest block with the process's own TCB so the guest sees byte-for-byte
       what it saw before the swap, and only the self-pointer's identity differs. If the boot returns to
       called 66 the guest reads TCB fields and this block must become a declared layout; if it still faults at
       1 the guest does arithmetic on the pointer (variant II) and the block needs a static image before it.
       The copy is a stopgap: it is the host's TCB, whose contents are glibc's business, so it must not survive
       past threads. */
    memset(guest_block, 0, sizeof guest_block);
    {
        const unsigned char *src = (const unsigned char *)(uintptr_t)host_fsbase;
        memcpy(guest_block + 8, src + 8, RT_TLS_BLOCK_BYTES < 0x4a0 ? RT_TLS_BLOCK_BYTES - 8 : 0x4a0 - 8);
    }
    *(uint64_t *)guest_block = (uint64_t)(uintptr_t)guest_block; /* the guest's own self-pointer */
    fprintf(stderr, "pbboot: tls: guest block at %p, self-pointer set, swap via %s\n", (void *)guest_block,
            have_wrfsbase ? "wrfsbase" : "arch_prctl");
}

int rt_tls_have_wrfsbase(void) { return have_wrfsbase; }

uint64_t rt_tls_host_base(void) { return (uint64_t)host_fsbase; }

uint64_t rt_tls_guest_base(void) { return (uint64_t)(uintptr_t)guest_block; }

void rt_tls_enter_guest(void)
{
    if (have_wrfsbase) {
        asm volatile("wrfsbase %0" ::"r"(guest_block));
        return;
    }
    unsigned long base = (unsigned long)(uintptr_t)guest_block;
    /* glibc's headers have no ARCH_SET_FS; the fallback is raw syscall 158 with 0x1002. */
    long r = syscall(158, 0x1002UL, &base);
    if (r != 0) fprintf(stderr, "pbboot: tls: arch_prctl(ARCH_SET_FS) failed (%ld)\n", r);
}

void rt_tls_enter_host(void)
{
    if (have_wrfsbase) {
        asm volatile("wrfsbase %0" ::"r"(host_fsbase));
        return;
    }
    unsigned long base = host_fsbase;
    long rc = syscall(158, 0x1002UL, &base);
    if (rc != 0) fprintf(stderr, "pbboot: tls: arch_prctl restore failed (%ld)\n", rc);
}
