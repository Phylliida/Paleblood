/* SPDX-License-Identifier: GPL-2.0-or-later */
/* System call group: kernel, threads and memory. Threads and thread attributes (libkernel,
   libScePosix).

   Facts used: a thread or attribute variable holds a pointer to an object the library allocates
   (FreeBSD libthr, which the PS4's thread library is); the SCE names return 0 or 0x80020000 plus a
   FreeBSD error number, and their POSIX names (libScePosix) return that error number itself. An
   attribute records only what has been set or copied into it; reading a value the runtime does not
   know (one the system would supply) is not implemented, so the boot stops there by name instead of
   guessing. */
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { BSD_ENOMEM = 12, BSD_EINVAL = 22 };
#define SCE_KERNEL_ERROR(e) ((int)(0x80020000u + (unsigned)(e)))

/* PTHREAD_CREATE_JOINABLE and PTHREAD_CREATE_DETACHED in FreeBSD's <pthread.h>. The OpenOrbis
   homebrew SDK header (include/orbis/_types/pthread.h) defines ORBIS_PTHREAD_CREATE_JOINABLE and
   ORBIS_PTHREAD_CREATE_DETACHED with the same values; it follows FreeBSD's text, so it corroborates
   them rather than measuring them. */
enum { DETACH_JOINABLE = 0, DETACH_DETACHED = 1 };

typedef struct {
    void *stack;
    uint64_t stack_size;
} guest_thread;

typedef struct {
    int has_stack;
    void *stack;
    uint64_t stack_size;
    int has_detach_state;
    int detach_state;
    int has_affinity;
    uint64_t affinity;
} guest_attr;

/* The CPU affinity mask the system supplies when an attribute carries none: the PS4 leaves six of
   its eight cores available (Digital Foundry, "Inside the PlayStation 4", July 2013), so bits 0-5
   are set. What that source does not fix is *which* six; this assumes the OS keeps the top two.
   The game bit-counts the mask to size its worker threads, so a wrong constant changes thread
   topology without failing any call -- which is why the assumption is here, once, in a place a
   reader cannot mistake for a measurement, instead of being invented at a call site. */
enum { PS4_DEFAULT_AFFINITY = 0x3F };

static int sce(int bsd) { return bsd ? SCE_KERNEL_ERROR(bsd) : 0; }

static guest_thread main_thread;
static _Thread_local guest_thread *current;

void rt_thread_register_main(void *stack, uint64_t stack_size)
{
    main_thread.stack = stack;
    main_thread.stack_size = stack_size;
    current = &main_thread;
}

static guest_thread *thread_self(void)
{
    if (!current) rt_fatal("scePthreadSelf", "no guest thread registered on this host thread");
    return current;
}

/* Two thread variables name the same thread when they hold the same object pointer. Non-zero when
   equal, zero otherwise, with no error return (FreeBSD pthread_equal(3)). */
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

RT_SYSLIB("libkernel", scePthreadSelf, thread_self);
/* NOT registered: `libkernel`/scePthreadCreate is bound by pthread_sema.c's refusal. Until this slice both
   rows existed and THIS one won on section order (index 36 against 88), so every boot ran EXPERIMENT A
   while the tree's later, deliberate policy never executed once. EXPERIMENT A is not pre-registered
   anywhere -- measured: the only occurrences of the name in the tree are the comment above and the print
   below. It produced the guest's Dantelion2 panic (the error path dereferences the unpopulated __sFILE),
   which is why the refusal exists at all. Reproduce it by restoring this line. */
RT_SYSLIB("libkernel", scePthreadEqual, thread_equal);
RT_SYSLIB("libkernel", sched_yield, kernel_sched_yield);
RT_SYSLIB_UNRESOLVED("libkernel", scePthreadYield, thread_yield);
RT_SYSLIB("libkernel", scePthreadAttrInit, attr_init);
RT_SYSLIB("libkernel", scePthreadAttrDestroy, attr_destroy);
RT_SYSLIB("libkernel", scePthreadAttrGet, attr_get);
RT_SYSLIB("libkernel", scePthreadAttrGetaffinity, attr_get_affinity);
RT_SYSLIB("libkernel", scePthreadAttrSetdetachstate, sce_attr_set_detach_state);

/* libScePosix: errno values. pthread_attr_init and pthread_attr_destroy are not registered yet, so
   eboot's own POSIX path stops at those first. */
RT_SYSLIB("libScePosix", pthread_attr_setdetachstate, attr_set_detach_state);
