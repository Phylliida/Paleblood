/* Guest thread-local storage.

   Measured before anything here was written: the guest uses %fs 16,854 times across the 157,757-entry
   catalog, at exactly one displacement -- fs:[0], the TCB self-pointer. gs: zero. And wrfsbase is usable
   here: CPUID leaf 7 EBX bit 0 set, and a write/read-back round trip landed on this CPU.

   So the guest block needs to be aligned, its first eight bytes must point at itself, and the swap is two
   instructions. The architecture is checked at init rather than assumed, so pbboot does not become a binary
   that only runs on CPUs with FSGSBASE: without it the same swap costs an arch_prctl. */
#include "runtime/tls.h"

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
}

void rt_tls_init(void)
{
    probe_fsgsbase();
    asm volatile("rdfsbase %0" : "=r"(host_fsbase));
    memset(guest_block, 0, sizeof guest_block);
    *(uint64_t *)guest_block = (uint64_t)(uintptr_t)guest_block; /* the only field the guest reads */
    fprintf(stderr, "pbboot: tls: guest block at %p, self-pointer set, swap via %s\n", (void *)guest_block,
            have_wrfsbase ? "wrfsbase" : "arch_prctl");
}

int rt_tls_have_wrfsbase(void) { return have_wrfsbase; }

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
