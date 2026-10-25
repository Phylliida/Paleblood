/* Guest thread-local storage, one block per host thread.

   Measured before anything here was written: the guest uses %fs 16,854 times across the 157,757-entry
   catalog, at exactly one displacement -- fs:[0], the TCB self-pointer. gs: zero. And wrfsbase is usable
   here: CPUID leaf 7 EBX bit 0 set, and a write/read-back round trip landed on this CPU.

   So the guest block needs to be aligned, its first eight bytes must point at itself, and the swap is two
   instructions. The architecture is checked at init rather than assumed, so pbboot does not become a binary
   that only runs on CPUs with FSGSBASE: without it the same swap costs an arch_prctl.

   The C state is reached through %gs, not %fs. That is the whole per-thread correction: while a thread is
   running guest code its %fs is the guest TCB, so any `_Thread_local` host variable would be read at a
   guest offset -- the host FS base itself would be looked up through the guest block. %gs is unused by the
   guest (measured zero) and stays pointing at this thread's state across both swaps. */
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

typedef struct rt_tls_thread {
    struct rt_tls_thread *self;  /* at %gs:0, so a thread can find its own state without %fs */
    unsigned char *guest_block;  /* == guest %fs, the TCB: self-pointer at offset 0 */
    unsigned char *guest_alloc_base; /* the pointer actually returned by posix_memalign */
    size_t guest_alloc;
    unsigned guest_memsz;
    unsigned long host_fsbase;   /* this thread's own host FS, never the main thread's */
    unsigned long host_gsbase;   /* the GS base to restore when this thread ends */
    int is_main;
} rt_tls_thread;

static rt_tls_thread main_state = {.self = &main_state, .guest_memsz = 0x4a0u, .is_main = 1};

/* Off unless the environment asks: a mirror is an experiment, not a design. */
static int rt_mirror_host_tls;

/* Read by the assembly stubs that cannot call a C helper without eating caller-saved arguments. Only the
   main thread publishes these; the child-side selector reads its own state through %gs. */
uint64_t rt_tls_guest_base_v;
uint64_t rt_tls_host_base_v;
static int have_wrfsbase;
static int have_wrgsbase;

static void set_gs_base(const void *p)
{
    __asm__ volatile("wrgsbase %0" ::"r"((unsigned long)p));
}

static unsigned long get_gs_base(void)
{
    unsigned long v = 0;
    __asm__ volatile("rdgsbase %0" : "=r"(v));
    return v;
}

/* %gs is installed by rt_tls_init on the main thread and by rt_tls_thread_begin on a child; the boot calls
   rt_tls_layout once before init, when the GS base is still the host's (normally zero), and that call must
   land on the main state rather than dereference 0. */
static rt_tls_thread *tls_state(void)
{
    /* Before the CPU probe there is no safe way to read %gs on a machine without FSGSBASE; the one
       pre-init caller is boot.c's main-thread layout, which belongs to main_state by definition. */
    if (!have_wrgsbase) return &main_state;
    const unsigned long gs = get_gs_base();
    return gs ? (rt_tls_thread *)(uintptr_t)gs : &main_state;
}

static void set_fs_base(unsigned long v)
{
    __asm__ volatile("wrfsbase %0" ::"r"(v));
}

/* Asking the CPU and not the documentation: FSGSBASE is advertised in leaf 7 EBX bit 0, but the feature
   only works if the kernel enables it, so the round trip is the check that matters. GS is probed too: it
   carries this file's per-thread state across the guest swap. */
static void probe_fsgsbase(void)
{
    unsigned a = 0, b = 0, c = 0, d = 0;
    if (!__get_cpuid_count(7, 0, &a, &b, &c, &d) || (b & 1u) == 0) return;
    unsigned long before = 0, after = 0;
    __asm__ volatile("rdfsbase %0" : "=r"(before));
    /* Write a DIFFERENT canonical value and restore: writing back the value just read is equal whether the
       instruction worked or was ignored, which made this probe unable to fail. */
    const unsigned long probe = before ^ (1UL << 8);
    __asm__ volatile("wrfsbase %0" ::"r"(probe));
    __asm__ volatile("rdfsbase %0" : "=r"(after));
    __asm__ volatile("wrfsbase %0" ::"r"(before));
    if (after == probe) have_wrfsbase = 1;

    unsigned long gbefore = 0, gafter = 0;
    __asm__ volatile("rdgsbase %0" : "=r"(gbefore));
    const unsigned long gprobe = gbefore ^ (1UL << 8);
    __asm__ volatile("wrgsbase %0" ::"r"(gprobe));
    __asm__ volatile("rdgsbase %0" : "=r"(gafter));
    __asm__ volatile("wrgsbase %0" ::"r"(gbefore));
    if (gafter == gprobe) have_wrgsbase = 1;

    /* One stub, one ABI. The trampoline inlines wrfsbase because a C call between the guest's jump and
       the target would eat every caller-saved argument register; a second stub for the arch_prctl path
       would be a code path that only runs on some machines. So absence is a refusal at startup. */
    if (!have_wrfsbase || !have_wrgsbase)
        rt_fatal("FSGSBASE", "this CPU or kernel does not allow user-mode wrfsbase/wrgsbase, so guest %fs "
                             "cannot be swapped between guest and host code at syslib call boundaries");
}

/* The one read that proves the install. A C pointer into the block proves the bytes were written;
   wrfsbase returning cleanly proves nothing about which register it wrote -- 0xdb is wrgsbase, legal,
   silent and wrong, and it cost seven slices. Reading through %fs ITSELF is the only check that both
   the bytes and the base are what the guest's 16,854 fs:[0] reads will find. */
static int fs0_reads_self(uint64_t fs)
{
    if (!have_wrfsbase) return -1; /* the arch_prctl path has never run; it is not proved here */
    uint64_t seen = 0;
    const unsigned long host = tls_state()->host_fsbase;
    set_fs_base((unsigned long)fs);
    __asm__ volatile("movq %%fs:0, %0" : "=r"(seen));
    set_fs_base(host);
    fprintf(stderr, "pbboot: tls: fs:[0] reads 0x%llx, base is 0x%llx -- %s\n", (unsigned long long)seen,
            (unsigned long long)fs, seen == fs ? "self-pointer" : "MISMATCH");
    return seen == fs ? 0 : 1;
}

void rt_tls_init(void)
{
    probe_fsgsbase();
    main_state.self = &main_state;
    main_state.is_main = 1;
    /* boot.c lays out the real PT_TLS before rt_tls_init, because the trampolines bake the guest base.
       Do not overwrite that memsz with the default: the block is already sized and fs is already derived
       from 0x750, and printing 0x4a0 here was a false statement about the block it just accepted. */
    if (!main_state.guest_memsz) main_state.guest_memsz = 0x4a0u;
    __asm__ volatile("rdfsbase %0" : "=r"(main_state.host_fsbase));
    main_state.host_gsbase = get_gs_base();
    set_gs_base(&main_state);
    rt_tls_host_base_v = (uint64_t)main_state.host_fsbase;
    rt_mirror_host_tls = getenv("BB_TLS_MIRROR") != NULL;

    /* EXPERIMENT, one build: seed the guest block with the process's own TCB so the guest sees byte-for-byte
       what it saw before the swap, and only the self-pointer's identity differs. If the boot returns to
       called 66 the guest reads TCB fields and this block must become a declared layout; if it still faults at
       1 the guest does arithmetic on the pointer (variant II) and the block needs a static image before it.
       The copy is a stopgap: it is the host's TCB, whose contents are glibc's business, so it must not survive
       past threads. */
    if (!main_state.guest_block) rt_tls_layout(NULL, 0, main_state.guest_memsz);
    fprintf(stderr, "pbboot: tls: guest block at %p, modelled memsz 0x%x, swap via %s\n",
            (void *)main_state.guest_block, main_state.guest_memsz, have_wrfsbase ? "wrfsbase" : "arch_prctl");
    /* Written is not verified: the guest reads this slot 16,854 times and a zero here is a null TCB base
       for every one of them. Reread it through the register the guest will use and refuse if it differs. */
    if (fs0_reads_self((uint64_t)(uintptr_t)main_state.guest_block) == 1)
        rt_fatal("TLS", "%%fs:[0] does not read back as the TCB base, so every guest fs:[0] read would find "
                        "something else; the boot cannot be interpreted past this point");
    if (getenv("BB_TLS_TRACE")) rt_tls_trace("init");
}

/* Called once on a host thread that will execute guest code. Captures that thread's own host FS and GS
   before any guest block is installed; inheriting the main thread's values is the defect this removes. */
void rt_tls_thread_begin(void)
{
    rt_tls_thread *st = calloc(1, sizeof *st);
    if (!st) rt_fatal("TLS", "cannot allocate per-thread TLS state");
    st->self = st;
    st->guest_memsz = 0x4a0u;
    __asm__ volatile("rdfsbase %0" : "=r"(st->host_fsbase));
    st->host_gsbase = get_gs_base();
    set_gs_base(st);
    rt_tls_layout(NULL, 0, st->guest_memsz);
}

/* Drops this thread's guest block after restoring its host FS and GS. A freed block left installed as %fs
   is a dangling TCB for the next libc call. */
void rt_tls_thread_end(void)
{
    rt_tls_thread *st = tls_state();
    if (!st) return;
    if (st->guest_block) rt_tls_enter_host();
    const unsigned long restore_gs = st->host_gsbase;
    free(st->guest_alloc_base);
    st->guest_block = NULL;
    st->guest_alloc_base = NULL;
    st->guest_alloc = 0;
    set_gs_base((const void *)restore_gs);
    free(st);
}

/* Places the image and the TCB inside this thread's region and sets %fs to the TCB. Idempotent: later calls
   with a real image replace the zeros a thread would see on the real machine anyway. */
void rt_tls_layout(const void *image, unsigned filesz, unsigned memsz)
{
    rt_tls_thread *st = tls_state();
    if (!st) rt_fatal("TLS", "layout called on a thread with no TLS state");
    if (memsz) st->guest_memsz = memsz;
    if (st->guest_memsz > RT_TLS_AREA_BYTES)
        rt_fatal("TLS", "the module's TLS memsz exceeds the per-thread block budget");
    /* The block must hold [fs - memsz, fs + TCB), and `fs` may be up to 63 bytes above base + memsz + TCB:
       budget memsz + 2*TCB + 64, not memsz + TCB + 64. The short allocation was a real out-of-bounds memset. */
    const size_t need = (size_t)st->guest_memsz + 2u * RT_TCB_BYTES + 64u;
    if (!st->guest_alloc_base || st->guest_alloc < need) {
        free(st->guest_alloc_base);
        void *fresh = NULL;
        if (posix_memalign(&fresh, 64u, need) != 0)
            rt_fatal("TLS", "cannot allocate a per-thread guest block");
        st->guest_alloc_base = fresh;
        st->guest_alloc = need;
    }
    const uintptr_t base = (uintptr_t)st->guest_alloc_base;
    const uintptr_t fs = (base + st->guest_memsz + RT_TCB_BYTES + 63u) & ~(uintptr_t)63u;
    memset((void *)(fs - st->guest_memsz), 0, st->guest_memsz + RT_TCB_BYTES);
    if (image && filesz)
        memcpy((void *)(fs - st->guest_memsz), image,
               filesz < st->guest_memsz ? filesz : st->guest_memsz);
    /* EXPERIMENT: mirror the host's static TLS area -- the bytes below glibc's TCB -- so the guest sees
       byte-for-byte what it saw before the swap, at the correct relative offsets. Reaches 66 calls => the
       guest reads TLS *content* and the question narrows to which variable; still faults at 1 => the guest
       is sensitive to the base ADDRESS, and no content work can fix it. */
    if (rt_mirror_host_tls && st->host_fsbase > st->guest_memsz)
        memcpy((void *)(fs - st->guest_memsz), (const void *)(st->host_fsbase - st->guest_memsz),
               st->guest_memsz);
    st->guest_block = (unsigned char *)fs;
    *(uint64_t *)st->guest_block = (uint64_t)fs;
    /* The assembly call helper still reads these globals; only the main thread publishes them. A child
       must not write them, or two threads race the value the main thread's rt_boot_call will use. The
       child-side selector is a separate change (todo/047). */
    if (st->is_main) {
        rt_tls_guest_base_v = (uint64_t)fs;
        rt_tls_host_base_v = (uint64_t)st->host_fsbase;
    }
}

static unsigned long get_fs_base(void)
{
    unsigned long v = 0;
    __asm__ volatile("rdfsbase %0" : "=r"(v));
    return v;
}

void rt_tls_view_read(rt_tls_view *out)
{
    /* No libc here. This is called while %fs may still be the guest block, and a C library call
       (even memset or fprintf) reaches its own thread state through %fs. Every value below is a
       register read or a field of state reached through %gs, so the capture itself is safe; the
       printing is not, and lives in rt_tls_trace_view. */
    const rt_tls_thread *st = tls_state();
    out->gs = out->state = out->state_self = out->fsbase = out->fs0 = 0;
    out->installer = out->published = out->enter_guest = 0;
    out->memsz = 0;
    out->gs = (uint64_t)get_gs_base();
    out->state = (uint64_t)(uintptr_t)st;
    out->state_self = st ? (uint64_t)(uintptr_t)st->self : 0;
    if (have_wrfsbase) {
        out->fsbase = (uint64_t)get_fs_base();
        if (out->fsbase)
            __asm__ volatile("movq %%fs:0, %0" : "=r"(out->fs0));
    }
    out->installer = st ? (uint64_t)(uintptr_t)st->guest_block : 0;
    out->published = rt_tls_guest_base_v;
    out->enter_guest = st ? (uint64_t)(uintptr_t)st->guest_block : 0;
    out->memsz = st ? st->guest_memsz : 0;
}

void rt_tls_trace_view(const char *where, const rt_tls_view *view)
{
    const rt_tls_view v = *view;
    fprintf(stderr,
            "pbboot: tls trace %s: gs=%#llx state=%#llx state.self=%#llx fsbase=%#llx fs[0]=%#llx "
            "installer=%#llx published=%#llx enter_guest=%#llx memsz=%#x\n",
            where, (unsigned long long)v.gs, (unsigned long long)v.state,
            (unsigned long long)v.state_self, (unsigned long long)v.fsbase, (unsigned long long)v.fs0,
            (unsigned long long)v.installer, (unsigned long long)v.published,
            (unsigned long long)v.enter_guest, v.memsz);
}

void rt_tls_trace(const char *where)
{
    rt_tls_view v;
    rt_tls_view_read(&v);
    rt_tls_trace_view(where, &v);
}

int rt_tls_have_wrfsbase(void) { return have_wrfsbase; }

uint64_t rt_tls_host_base(void)
{
    const rt_tls_thread *st = tls_state();
    return st ? (uint64_t)st->host_fsbase : 0;
}

uint64_t rt_tls_guest_base(void)
{
    const rt_tls_thread *st = tls_state();
    return st ? (uint64_t)(uintptr_t)st->guest_block : 0;
}

void rt_tls_enter_guest(void)
{
    const rt_tls_thread *st = tls_state();
    if (!st || !st->guest_block) rt_fatal("TLS", "no guest block on this thread");
    if (have_wrfsbase) {
        set_fs_base((unsigned long)(uintptr_t)st->guest_block);
        return;
    }
    unsigned long base = (unsigned long)(uintptr_t)st->guest_block;
    /* glibc's headers have no ARCH_SET_FS; the fallback is raw syscall 158 with 0x1002. */
    long r = syscall(158, 0x1002UL, &base);
    if (r != 0) fprintf(stderr, "pbboot: tls: arch_prctl(ARCH_SET_FS) failed (%ld)\n", r);
}

int rt_tls_uses_wrfsbase(void) { return have_wrfsbase; }

void rt_tls_enter_host(void)
{
    const rt_tls_thread *st = tls_state();
    const unsigned long host = st ? st->host_fsbase : 0;
    if (have_wrfsbase) {
        set_fs_base(host);
        return;
    }
    /* arch_prctl(ARCH_SET_FS, addr) takes the ADDRESS, not a pointer to it: &base would install a stack slot
       as the TCB. This path has never run, because have_wrfsbase has never been false. */
    long rc = syscall(158, 0x1002UL, host);
    if (rc != 0) fprintf(stderr, "pbboot: tls: arch_prctl restore failed (%ld)\n", rc);
}
