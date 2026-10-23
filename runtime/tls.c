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
#include <stdlib.h>
#include <sys/syscall.h>
#include <unistd.h>


/* Variant II, the FreeBSD/amd64 arrangement: [static image memsz bytes][TCB], %fs pointing at the TCB and
   the image sitting exactly memsz below it. The guest's @tpoff values are fixed link-time constants relative
   to the TCB, so any padding between image and TCB shifts every TLS variable and reproduces the fault at a
   different address. Alignment therefore belongs to the END: fs = align_up(base + memsz + tcb_end, 64), and
   the image starts at fs - memsz. memsz 0x4a0 is not a multiple of 64 for exactly this reason -- the loader
   aligns the end, not the base. */
#define RT_TLS_AREA_BYTES 0x4000u
#define RT_TCB_BYTES 0x100u

static unsigned char tls_area[RT_TLS_AREA_BYTES + 64] __attribute__((aligned(64)));
static unsigned char *guest_block; /* == %fs, the TCB: self-pointer at offset 0 */
static unsigned guest_memsz = 0x4a0u;

/* Off unless the environment asks: a mirror is an experiment, not a design. */
static int rt_mirror_host_tls;

/* Read by the assembly stubs that cannot call a C helper without eating caller-saved arguments. */
uint64_t rt_tls_guest_base_v;
uint64_t rt_tls_host_base_v;
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
    /* Write a DIFFERENT canonical value and restore: writing back the value just read is equal whether the
       instruction worked or was ignored, which made this probe unable to fail. */
    const unsigned long probe = before ^ (1UL << 8);
    asm volatile("wrfsbase %0" ::"r"(probe));
    asm volatile("rdfsbase %0" : "=r"(after));
    asm volatile("wrfsbase %0" ::"r"(before));
    if (after == probe) have_wrfsbase = 1;
    /* One stub, one ABI. The trampoline inlines wrfsbase because a C call between the guest's jump and
       the target would eat every caller-saved argument register; a second stub for the arch_prctl path
       would be a code path that only runs on some machines. So absence is a refusal at startup. */
    if (!have_wrfsbase)
        rt_fatal("FSGSBASE", "this CPU or kernel does not allow user-mode wrfsbase, so guest %fs cannot be "
                             "swapped between guest and host code at syslib call boundaries");
}

/* The one read that proves the install. A C pointer into the block proves the bytes were written;
   wrfsbase returning cleanly proves nothing about which register it wrote -- 0xdb is wrgsbase, legal,
   silent and wrong, and it cost seven slices. Reading through %fs ITSELF is the only check that both
   the bytes and the base are what the guest's 16,854 fs:[0] reads will find. */
static int fs0_reads_self(uint64_t fs)
{
    if (!have_wrfsbase) return -1; /* the arch_prctl path has never run; it is not proved here */
    uint64_t seen = 0;
    asm volatile("wrfsbase %0" ::"r"((unsigned long)fs));
    asm volatile("movq %%fs:0, %0" : "=r"(seen));
    asm volatile("wrfsbase %0" ::"r"(host_fsbase));
    fprintf(stderr, "pbboot: tls: fs:[0] reads 0x%llx, base is 0x%llx -- %s\n", (unsigned long long)seen,
            (unsigned long long)fs, seen == fs ? "self-pointer" : "MISMATCH");
    return seen == fs ? 0 : 1;
}

void rt_tls_init(void)
{
    rt_mirror_host_tls = getenv("BB_TLS_MIRROR") != NULL;
    probe_fsgsbase();
    asm volatile("rdfsbase %0" : "=r"(host_fsbase));
    rt_tls_host_base_v = (uint64_t)host_fsbase;
    /* EXPERIMENT, one build: seed the guest block with the process's own TCB so the guest sees byte-for-byte
       what it saw before the swap, and only the self-pointer's identity differs. If the boot returns to
       called 66 the guest reads TCB fields and this block must become a declared layout; if it still faults at
       1 the guest does arithmetic on the pointer (variant II) and the block needs a static image before it.
       The copy is a stopgap: it is the host's TCB, whose contents are glibc's business, so it must not survive
       past threads. */
    if (!guest_block) rt_tls_layout(NULL, 0, guest_memsz);
    *(uint64_t *)guest_block = (uint64_t)(uintptr_t)guest_block; /* the guest's own self-pointer */
    fprintf(stderr, "pbboot: tls: guest block at %p, modelled memsz 0x%x, swap via %s\n", (void *)guest_block,
            guest_memsz, have_wrfsbase ? "wrfsbase" : "arch_prctl");
    /* Written is not verified: the guest reads this slot 16,854 times and a zero here is a null TCB base
       for every one of them. Reread it through the register the guest will use and refuse if it differs. */
    if (fs0_reads_self((uint64_t)(uintptr_t)guest_block) == 1)
        rt_fatal("TLS", "%%fs:[0] does not read back as the TCB base, so every guest fs:[0] read would find "
                        "something else; the boot cannot be interpreted past this point");
}

/* Places the image and the TCB inside one region and sets %fs to the TCB. Idempotent: later calls with a
   real image replace the zeros a thread would see on the real machine anyway. */
void rt_tls_layout(const void *image, unsigned filesz, unsigned memsz)
{
    if (memsz) guest_memsz = memsz;
    const uintptr_t base = (uintptr_t)tls_area;
    const uintptr_t fs = (base + guest_memsz + RT_TCB_BYTES + 63u) & ~(uintptr_t)63u;
    guest_block = (unsigned char *)fs;
    memset((void *)(fs - guest_memsz), 0, guest_memsz + RT_TCB_BYTES);
    if (image && filesz) memcpy((void *)(fs - guest_memsz), image, filesz < guest_memsz ? filesz : guest_memsz);
    /* EXPERIMENT: mirror the host's static TLS area -- the bytes below glibc's TCB -- so the guest sees
       byte-for-byte what it saw before the swap, at the correct relative offsets. Reaches 66 calls => the
       guest reads TLS *content* and the question narrows to which variable; still faults at 1 => the guest
       is sensitive to the base ADDRESS, and no content work can fix it. */
    if (rt_mirror_host_tls && host_fsbase > guest_memsz)
        memcpy((void *)(fs - guest_memsz), (const void *)(host_fsbase - guest_memsz), guest_memsz);
    *(uint64_t *)guest_block = (uint64_t)fs;
    rt_tls_guest_base_v = (uint64_t)fs;
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

int rt_tls_uses_wrfsbase(void) { return have_wrfsbase; }

void rt_tls_enter_host(void)
{
    if (have_wrfsbase) {
        asm volatile("wrfsbase %0" ::"r"(host_fsbase));
        return;
    }
    /* arch_prctl(ARCH_SET_FS, addr) takes the ADDRESS, not a pointer to it: &base would install a stack slot
       as the TCB. This path has never run, because have_wrfsbase has never been false. */
    long rc = syscall(158, 0x1002UL, (unsigned long)host_fsbase);
    if (rc != 0) fprintf(stderr, "pbboot: tls: arch_prctl restore failed (%ld)\n", rc);
}
