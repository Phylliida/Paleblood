#define _GNU_SOURCE 1
/* SPDX-License-Identifier: GPL-2.0-or-later */
/* System call group: kernel, threads and memory. Threads and thread attributes (libkernel,
   libScePosix).

   Facts used: a thread or attribute variable holds a pointer to an object the library allocates
   (FreeBSD libthr, which the PS4's thread library is); the SCE names return 0 or 0x80020000 plus a
   FreeBSD error number, and their POSIX names (libScePosix) return that error number itself. A
   thread handle's WIDTH is part of that fact: the guest's adaptive mutex packs an owner into 40
   bits and compares the truncated word against the full handle (0x20368c0), so a host pointer --
   which has bits above 39 -- can never equal its own tag, and the mutex acquires and then waits
   forever on its own sleep semaphore. Thread objects therefore live in guest memory (thread_alloc),
   not in calloc. An attribute records only what has been set or copied into it; reading a value the
   runtime does not know (one the system would supply) is not implemented, so the boot stops there
   by name instead of guessing. */
#include "runtime/process.h"
#include "runtime/syslib.h"
#include "runtime/guest_mem.h"
#include "runtime/tls.h"

#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

enum { BSD_ENOMEM = 12, BSD_EFAULT = 14, BSD_EINVAL = 22, BSD_EAGAIN = 35 };
#define SCE_KERNEL_ERROR(e) ((int)(0x80020000u + (unsigned)(e)))

/* PTHREAD_CREATE_JOINABLE and PTHREAD_CREATE_DETACHED in FreeBSD's <pthread.h>. The OpenOrbis
   homebrew SDK header (include/orbis/_types/pthread.h) defines ORBIS_PTHREAD_CREATE_JOINABLE and
   ORBIS_PTHREAD_CREATE_DETACHED with the same values; it follows FreeBSD's text, so it corroborates
   them rather than measuring them. */
enum { DETACH_JOINABLE = 0, DETACH_DETACHED = 1 };

typedef struct {
    void *stack;
    uint64_t stack_size;
    pthread_t host;
    int has_host;
    int detached;
    void (*entry)(void *);
    void *arg;
} guest_thread;

/* The arena's handles advance by sizeof(guest_thread), and the boot printed main at 0x980000000 and
   its child at 0x980000030. Pin that stride: thread_handle_ok's alignment clause divides by it, so a
   struct that grows silently would start refusing handles it allocated. Measured, not assumed: the
   fields are 8+8+8+4+4+8+8 = 48 bytes with no padding on this ABI. */
_Static_assert(sizeof(guest_thread) == 0x30, "thread arena stride must stay 0x30 (see boot handles)");

typedef struct {
    int has_stack;
    void *stack;
    uint64_t stack_size;
    int has_detach_state;
    int detach_state;
    int has_affinity;
    uint64_t affinity;
    int has_policy;
    int policy;
} guest_attr;

/* The CPU affinity mask the system supplies when an attribute carries none: the PS4 leaves six of
   its eight cores available (Digital Foundry, "Inside the PlayStation 4", July 2013), so bits 0-5
   are set. What that source does not fix is *which* six; this assumes the OS keeps the top two.
   The game bit-counts the mask to size its worker threads, so a wrong constant changes thread
   topology without failing any call -- which is why the assumption is here, once, in a place a
   reader cannot mistake for a measurement, instead of being invented at a call site. */
enum { PS4_DEFAULT_AFFINITY = 0x3F };

static int sce(int bsd) { return bsd ? SCE_KERNEL_ERROR(bsd) : 0; }

/* Thread objects live in GUEST memory, not in calloc.

   The guest's adaptive mutex packs a thread identity into 40 bits and compares the truncated word
   against the full handle: at 0x20368c0 it does `mov r9,r15; and r9,0xffffffffff`, stores that as the
   owner, then `cmp rdi,r15` after truncating the stored word. A host pointer (`0x5555...`) has bits
   above 39, so the truncated owner can never equal the full handle; the mutex acquires, fails to
   recognise itself, spins out its window, and then waits forever on its own sleep semaphore while
   still holding the lock. That is the deadlock the trace showed, and the defect is the handle's
   space, not the guest's lock order: on the original system the identity is a guest pointer and the
   40-bit tag works.

   A translation table would make `thread_equal` a mapper and turn create-self equality into a
   property maintained by hand. Allocating the objects in guest memory keeps every comparison a
   pointer comparison -- the smallest population that requires the change. The arena is a fixed
   mapping below 2^40, registered with guest_mem.c so a handle is recognisably guest memory. */
enum { kThreadArenaBase = 0x980000000ull, kThreadArenaBytes = 0x10000 };
#define THREAD_ARENA_SLOTS (kThreadArenaBytes / sizeof(guest_thread))

static pthread_once_t thread_arena_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t thread_arena_lock = PTHREAD_MUTEX_INITIALIZER;
static guest_thread *thread_arena;
static guest_thread *thread_arena_free_list;
static size_t thread_arena_used;

static void thread_arena_init(void)
{
    void *p = mmap((void *)(uintptr_t)kThreadArenaBase, kThreadArenaBytes, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (p == MAP_FAILED || (uintptr_t)p != kThreadArenaBase)
        rt_fatal("pthread", "cannot map the guest thread arena at 0x980000000");
    if (!rt_guest_register_mapping((uintptr_t)p, kThreadArenaBytes))
        rt_fatal("pthread", "the guest mapping table is full; cannot register the thread arena");
    thread_arena = p;
}

static guest_thread *thread_alloc(void)
{
    pthread_once(&thread_arena_once, thread_arena_init);
    pthread_mutex_lock(&thread_arena_lock);
    guest_thread *t;
    if (thread_arena_free_list) {
        t = thread_arena_free_list;
        thread_arena_free_list = (guest_thread *)t->stack;
    } else if (thread_arena_used < THREAD_ARENA_SLOTS) {
        t = &thread_arena[thread_arena_used++];
    } else {
        t = NULL;
    }
    if (t) memset(t, 0, sizeof *t);
    pthread_mutex_unlock(&thread_arena_lock);
    return t;
}

static void thread_release(guest_thread *t)
{
    if (!t) return;
    pthread_mutex_lock(&thread_arena_lock);
    t->stack = thread_arena_free_list;
    thread_arena_free_list = t;
    pthread_mutex_unlock(&thread_arena_lock);
}

/* A handle is a pointer into the arena. A value outside it is not a thread, so the join, detach and
   affinity paths refuse it instead of dereferencing guest-supplied garbage: the old test was
   `(thread & 1u) == 0`, true of nearly every even number, which read a random address. The arena has
   not been mapped until the first thread exists, and a handle before that is not one. */
static int thread_handle_ok(const guest_thread *t)
{
    const uintptr_t base = (uintptr_t)thread_arena;
    const uintptr_t h = (uintptr_t)t;
    return thread_arena && h >= base && h - base < (uintptr_t)kThreadArenaBytes &&
           (h - base) % sizeof(guest_thread) == 0;
}

static guest_thread *main_thread;
static _Thread_local guest_thread *current;

void rt_thread_register_main(void *stack, uint64_t stack_size)
{
    if (!main_thread) {
        main_thread = thread_alloc();
        if (!main_thread)
            rt_fatal("pthread", "cannot allocate the main thread object in guest memory");
    }
    main_thread->stack = stack;
    main_thread->stack_size = stack_size;
    current = main_thread;
}

/* No libc after rt_tls_enter_guest: the guest block is %fs, and even fprintf reaches glibc's thread
   state through %fs. The first version of this witness called fprintf here and faulted in libc, which
   looked exactly like a guest fault and was mine. Raw write(2), no TLS, no stack protector. */
static void raw_write2(const char *s, unsigned long n)
{
    long r;
    __asm__ volatile("syscall" : "=a"(r) : "a"(1L), "D"(2L), "S"(s), "d"(n) : "rcx", "r11", "memory");
    (void)r;
}

static void *thread_trampoline(void *p)
{
    guest_thread *t = p;
    fprintf(stderr, "pbboot: thread %p TRAMPOLINE entered host thread\n", (void *)t);
    current = t;
    rt_tls_thread_begin();
    rt_tls_enter_guest();
    raw_write2("pbboot: thread crossed into guest\n", 35);
    t->entry(t->arg);
    raw_write2("pbboot: thread entry RETURNED\n", 30);
    rt_tls_thread_end();
    return NULL;
}

/* A real thread, not a tagged integer: the handle the guest receives is a pointer to this object,
   because a guest_thread* is what Join, Detach, Equal and Self all dereference. The object comes from
   the guest arena above, not calloc, so the handle's value lives in the same space the guest's own
   thread tags do. The child gets its own TLS state and its own %fs through
   rt_tls_thread_begin/enter_guest; those are the two pieces the earlier experiment did not have (it
   shared main's block). The hypothesis is that the pool's continuation needs workers that actually
   run; the falsifier is that the boot still stops at CondWait (or faults earlier) with this branch
   on. */
int rt_thread_create_real(int64_t out, int64_t entry, int64_t arg, uint64_t stack_size, int has_stack)
{
    if (out == 0) return SCE_KERNEL_ERROR(BSD_EINVAL);
    guest_thread *t = thread_alloc();
    if (!t) return SCE_KERNEL_ERROR(BSD_ENOMEM);
    t->entry = (void (*)(void *))(uintptr_t)entry;
    t->arg = (void *)(uintptr_t)arg;
    pthread_attr_t a;
    pthread_attr_init(&a);
    if (has_stack && stack_size >= 0x4000) pthread_attr_setstacksize(&a, (size_t)stack_size);
    const int r = pthread_create(&t->host, &a, thread_trampoline, t);
    pthread_attr_destroy(&a);
    if (r) {
        thread_release(t);
        return SCE_KERNEL_ERROR(r == EAGAIN ? BSD_EAGAIN : BSD_EINVAL);
    }
    t->has_host = 1;
    if (!rt_guest_write_ok((uintptr_t)out, 8, "scePthreadCreate")) {
        pthread_detach(t->host);
        return SCE_KERNEL_ERROR(BSD_EFAULT);
    }
    *(uint64_t *)(uintptr_t)out = (uint64_t)(uintptr_t)t;
    fprintf(stderr, "pbboot: scePthreadCreate: REAL handle %p (host thread, own TLS and %%fs), "
                    "entry %p arg %p, stack %s0x%llx\n",
            (void *)t, (void *)(uintptr_t)entry, (void *)(uintptr_t)arg,
            has_stack ? "" : "not asked ", has_stack ? (unsigned long long)stack_size : 0ull);
    return 0;
}

int rt_thread_join_real(int64_t handle)
{
    guest_thread *t = (guest_thread *)(uintptr_t)handle;
    if (!thread_handle_ok(t) || !t->has_host) return SCE_KERNEL_ERROR(BSD_EINVAL);
    const int r = pthread_join(t->host, NULL);
    if (r) return SCE_KERNEL_ERROR(r == EINVAL ? BSD_EINVAL : r);
    thread_release(t);
    return 0;
}

int rt_thread_detach_real(int64_t handle)
{
    guest_thread *t = (guest_thread *)(uintptr_t)handle;
    if (!thread_handle_ok(t) || !t->has_host || t->detached) return SCE_KERNEL_ERROR(BSD_EINVAL);
    const int r = pthread_detach(t->host);
    if (r) return SCE_KERNEL_ERROR(r == EINVAL ? BSD_EINVAL : r);
    t->detached = 1;
    return 0;
}

static guest_thread *thread_self(void)
{
    if (!current) rt_fatal("scePthreadSelf", "no guest thread registered on this host thread");
    return current;
}

/* Two thread variables name the same thread when they hold the same object pointer. Non-zero when
   equal, zero otherwise, with no error return (FreeBSD pthread_equal(3)). */
/* The experiment switch, read in one place. Empty and "0" mean off; anything else on. */
int rt_thread_modelled_enabled(void)
{
    const char *v = getenv("BB_THREAD_MODELLED");
    return v && *v && strcmp(v, "0") != 0;
}

static int thread_equal(guest_thread *a, guest_thread *b)
{
    return a == b;
}

/* sched_yield: the calling thread gives up the processor and the call returns 0 (POSIX and FreeBSD
   sched_yield(2), which define no error for it). A guest thread runs on a host thread, so the
   host's yield is the same request. A host failure has no FreeBSD error number we could report, so
   it stops by name instead. */
static int kernel_sched_yield(void)
{
    if (sched_yield() != 0) rt_fatal("sched_yield", "the host did not yield the processor");
    return 0;
}

/* scePthreadYield asks for the same yield, but its PS4-visible signature is not established:
   FreeBSD's pthread_yield(3) returns nothing, Linux's returns an int, and no PS4-specific public
   source or guest call site we can cite says which one the guest sees. Returning would leave the
   value a caller might read undefined, so the call stops by name. It is registered with
   RT_SYSLIB_UNRESOLVED: a boot that reaches it names the call, and coverage leaves the import
   unchecked, since a diagnostic is not an implementation. */
static void thread_yield(void)
{
    rt_fatal("scePthreadYield", "the PS4 return behaviour is not established by public evidence");
}

static int attr_init(guest_attr **attr)
{
    if (!attr) return SCE_KERNEL_ERROR(BSD_EINVAL);
    guest_attr *a = calloc(1, sizeof *a);
    if (!a) return SCE_KERNEL_ERROR(BSD_ENOMEM);
    *attr = a;
    return 0;
}

static int attr_destroy(guest_attr **attr)
{
    if (!attr || !*attr) return SCE_KERNEL_ERROR(BSD_EINVAL);
    free(*attr);
    *attr = NULL;
    return 0;
}

/* Copies a running thread's attributes into an initialised attribute object. The copy replaces
   everything the object held (libthr's pthread_attr_get_np copies the whole attribute block), so a
   detach state set on it before is dropped: the thread's own detach state is one the system
   supplies, and the runtime does not know it. */
/* The mask an attribute carries. A fresh attribute holds none -- the system supplies a default at
   creation time, and this runtime has no setter yet -- so the documented default is returned and
   the stored mask wins the moment one exists. Read through this, never the field: a stored zero
   would otherwise read as "no cores", which the system never means. */
static int attr_get_affinity(guest_attr **attr, uint64_t *mask)
{
    const guest_attr *a = attr ? *attr : NULL;
    if (!a || !mask) return SCE_KERNEL_ERROR(BSD_EINVAL);
    *mask = a->has_affinity ? a->affinity : PS4_DEFAULT_AFFINITY;
    return 0;
}

static int attr_get(guest_thread *thread, guest_attr **attr)
{
    if (!thread || !attr || !*attr) return SCE_KERNEL_ERROR(BSD_EINVAL);
    **attr = (guest_attr){.has_stack = 1, .stack = thread->stack, .stack_size = thread->stack_size};
    return 0;
}

/* Whether a thread created with the attribute starts detached or joinable (POSIX
   pthread_attr_setdetachstate). Any other value is EINVAL (POSIX; FreeBSD pthread_attr(3)), and so
   is a variable holding no attribute object (libthr's _pthread_attr_setdetachstate, thr_attr.c). */
static int attr_set_detach_state(guest_attr **attr, int state)
{
    if (!attr || !*attr) return BSD_EINVAL;
    if (state != DETACH_JOINABLE && state != DETACH_DETACHED) return BSD_EINVAL;
    (*attr)->has_detach_state = 1;
    (*attr)->detach_state = state;
    return 0;
}

static int sce_attr_set_detach_state(guest_attr **attr, int state)
{
    return sce(attr_set_detach_state(attr, state));
}

/* scePthreadAttrSetstacksize(attr, size): stores what the guest asked for. The `has_stack` flag is what
   separates "did not ask" from "asked for 0" -- the system's default is not established, and a zero
   stack_size with has_stack set is a request this runtime must not silently replace with a default. */
static int attr_set_stack_size(guest_attr **attr, uint64_t size)
{
    if (!attr || !*attr) return BSD_EINVAL;
    (*attr)->has_stack = 1;
    (*attr)->stack_size = size;
    return 0;
}

static int sce_attr_set_stack_size(guest_attr **attr, uint64_t size)
{
    return sce(attr_set_stack_size(attr, size));
}

/* scePthreadAttrSetschedpolicy(attr, policy): same shape. Policy numbers are the guest's; this runtime
   does not map them to host policies, it records them so a create path can either honour or name them. */
static int attr_set_sched_policy(guest_attr **attr, int policy)
{
    if (!attr || !*attr) return BSD_EINVAL;
    (*attr)->has_policy = 1;
    (*attr)->policy = policy;
    return 0;
}

static int sce_attr_set_sched_policy(guest_attr **attr, int policy)
{
    return sce(attr_set_sched_policy(attr, policy));
}

/* Read the state through this, never from the field: a fresh attribute's detach_state is zero,
   which is the joinable value, so reading the field would assume joinable silently. The two
   messages tell a boot log which unknown the guest reached. */
int rt_thread_attr_detach_state(void *const *attr, const char *caller)
{
    const guest_attr *a = attr ? *attr : NULL;
    if (!a)
        rt_fatal(caller, "no attribute object: the PS4 default detach state is not established");
    if (!a->has_detach_state)
        rt_fatal(caller, "no detach state set: the one the system supplies is not established");
    return a->detach_state;
}

/* 1 = the guest asked, 0 = it did not, -1 = no attribute variable. Never a default substituted for an
   unasked value: the create path prints which of the two it has, and refuses rather than assume. */
int rt_thread_attr_stack_size(void *const *attr, uint64_t *size)
{
    const guest_attr *a = attr ? *attr : NULL;
    if (!a || !size) return -1;
    if (!a->has_stack) return 0;
    *size = a->stack_size;
    return 1;
}

int rt_thread_attr_sched_policy(void *const *attr, int *policy)
{
    const guest_attr *a = attr ? *attr : NULL;
    if (!a || !policy) return -1;
    if (!a->has_policy) return 0;
    *policy = a->policy;
    return 1;
}

/* EXPERIMENT A. scePthreadCreate reports a generic failure and creates nothing, so the guest's own
   error path runs. FreeBSD EAGAIN (35) is "resource temporarily unavailable", the error a real system
   returns when it cannot make a thread; SCE_KERNEL_ERROR(35) = 0x80020023, deliberately NOT 0x805a1001,
   the one code eboot's caller is written to tolerate. Declared MODELLED, not REAL: no thread exists, and
   any guest state that implies one is fabricated. The print goes to stderr because the boot harness
   treats stdout as a JSON map keyed by case id. */
static __attribute__((unused)) int sce_pthread_create_a(void **thread, const char *name, void *entry, void *arg, const void *attr)
{
    (void)thread; (void)name; (void)entry; (void)arg; (void)attr;
    fprintf(stderr, "scePthreadCreate: EXPERIMENT A -- reached, returning 0x80020023 (EAGAIN), "
                    "no thread created, failure modelled\n");
    return SCE_KERNEL_ERROR(35);
}

static int thread_join(int64_t handle) { return rt_thread_join_real(handle); }
static int thread_detach(int64_t handle) { return rt_thread_detach_real(handle); }
RT_SYSLIB("libkernel", scePthreadJoin, thread_join);
RT_SYSLIB("libkernel", scePthreadDetach, thread_detach);
RT_SYSLIB("libkernel", scePthreadSelf, thread_self);
/* NOT registered: `libkernel`/scePthreadCreate is bound by pthread_sema.c's refusal. Until this slice both
   rows existed and THIS one won on section order (index 36 against 88), so every boot ran EXPERIMENT A
   while the tree's later, deliberate policy never executed once. EXPERIMENT A is not pre-registered
   anywhere -- measured: the only occurrences of the name in the tree are the comment above and the print
   below. It produced the guest's Dantelion2 panic (the error path dereferences the unpopulated __sFILE),
   which is why the refusal exists at all. Reproduce it by restoring this line. */
RT_SYSLIB("libkernel", scePthreadEqual, thread_equal);
/* Called only after a modelled create in this experiment. No scheduler state exists, so a real
   affinity request cannot be honoured; returning success is the same lie as the modelled create and
   is gated by the same flag, with its own line. Default is the diagnostic below, not a silent no-op. */
static int thread_setaffinity(uint64_t thread, int affinity)
{
    /* A real guest thread handle is an 8-aligned pointer; a fabricated one is odd. Applying the
       mask to the host pthread is the only honest implementation: the guest asked for scheduling
       state, and the host has it. A failure is reported, not hidden. */
    fprintf(stderr, "pbboot: scePthreadSetaffinity raw: thread=%#llx affinity=%#x\n",
            (unsigned long long)thread, (unsigned)affinity);
    {
        guest_thread *t = thread ? (guest_thread *)(uintptr_t)thread : main_thread;
        if (thread_handle_ok(t) && (t->has_host || t == main_thread)) {
            cpu_set_t set;
            CPU_ZERO(&set);
            const long ncpu = sysconf(_SC_NPROCESSORS_ONLN);
            int cpu = 0;
            while (cpu < 64 && !(affinity & (1 << cpu))) cpu++;
            if (ncpu > 0) CPU_SET((size_t)(cpu % ncpu), &set);
            const pthread_t host = t->has_host ? t->host : pthread_self();
            const int r = pthread_setaffinity_np(host, sizeof set, &set);
            fprintf(stderr, "pbboot: scePthreadSetaffinity: %s %p affinity %#x -> host cpu %d "
                            "(%s)\n", t->has_host ? "REAL thread" : "main thread", (void *)t,
                    (unsigned)affinity, ncpu > 0 ? cpu % (int)ncpu : -1,
                    r ? "host refused" : "set");
            return r ? SCE_KERNEL_ERROR(r) : 0;
        }
    }
    if (!rt_thread_modelled_enabled())
        rt_fatal("scePthreadSetaffinity",
                 "no per-thread scheduler state exists; set BB_THREAD_MODELLED=1 to model the call");
    fprintf(stderr, "pbboot: scePthreadSetaffinity: MODELLED thread 0x%llx affinity 0x%x -- no "
                    "scheduler state exists; BB_THREAD_MODELLED=1\n",
            (unsigned long long)thread, (unsigned)affinity);
    return 0;
}
RT_SYSLIB_UNRESOLVED("libkernel", scePthreadSetaffinity, thread_setaffinity);
RT_SYSLIB("libkernel", sched_yield, kernel_sched_yield);
RT_SYSLIB_UNRESOLVED("libkernel", scePthreadYield, thread_yield);
RT_SYSLIB("libkernel", scePthreadAttrInit, attr_init);
RT_SYSLIB("libkernel", scePthreadAttrDestroy, attr_destroy);
RT_SYSLIB("libkernel", scePthreadAttrGet, attr_get);
RT_SYSLIB("libkernel", scePthreadAttrGetaffinity, attr_get_affinity);
RT_SYSLIB("libkernel", scePthreadAttrSetdetachstate, sce_attr_set_detach_state);
RT_SYSLIB("libkernel", scePthreadAttrSetstacksize, sce_attr_set_stack_size);
RT_SYSLIB("libkernel", scePthreadAttrSetschedpolicy, sce_attr_set_sched_policy);

/* libScePosix: errno values. pthread_attr_init and pthread_attr_destroy are not registered yet, so
   eboot's own POSIX path stops at those first. */
RT_SYSLIB("libScePosix", pthread_attr_setdetachstate, attr_set_detach_state);
