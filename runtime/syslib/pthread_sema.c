/* SPDX-License-Identifier: GPL-2.0-or-later */
/* The blocking semaphore family, with real threads in front of it.

   This file used to assert single-threadedness because scePthreadCreate refused.  Real threads now
   exist, so each row owns a pthread mutex and condvar, and Wait actually sleeps; the ticket in a
   row is the guest's count, not a host mutex held across a syscall.  A refusal is a return code;
   a wait that cannot be served is a block, and the one-shot BLOCKING line names the handle, the
   thread and the count at the decision.  It deliberately does not print guest_pc: rt_guest_call_pc()
   is one global pair and, under two real threads, named the wrong import for the parked wait.

   BB_SEMA_TIMER is a probe, not coverage: a declared host supplier that issues one token per pool
   semaphore in create order.  It exists because the boot parks on a sequence of pool completions
   that no code in the process produces; with it the guest runs hundreds of thousands of imports
   and reaches later walls.  Nothing in the product is registered for it, and a normal boot never
   starts the thread. */
#include "runtime/address_spaces.h"
#include "runtime/guest_mem.h"
#include "runtime/inflight.h"
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define HANDLE_MAGIC 0x53454d41u /* "SEMA" */
#define HANDLE_ROWS 256

enum { k_err_inval = (int)0x80020016u, k_err_nomem = (int)0x8002000cu,
       k_err_fault = (int)0x8002000eu };

/* The ladder's first rung, measured rather than remembered: the refusal sets this before it stops, and the
   sites report reads it through a weak symbol. In an artifact that does not link this file the symbol is
   absent and the report says so, which is the same fact one level up. */
static volatile int thread_wall_reached;

int rt_thread_wall_reached(void) { return thread_wall_reached; }

static struct {
    pthread_mutex_t lock;
    pthread_cond_t cond;
    int count, max, used;
} rows[HANDLE_ROWS];

static int row_of(uint64_t h)
{
    /* The table is allocated on first Create. A Wait before any Create finds it absent, and that is a
       refusal, not a fault: this function dereferenced `rows` unconditionally and took signal 11 at
       address 0x0 (pbboot+0xaadb = sema_wait+0xb) the first time the guest waited on a handle whose
       storage was zero -- the __sFILE absence family arriving inside our own handle table.
       NOTE on zero: zero is NOT the sentinel for "no handle". A handle is (magic << 32) | (index + 1),
       so index 0 is legal and validity is carried by the magic word alone. Create always writes the
       magic, so `h == 0` means storage was never written, not that the table's first row is special. */
    if ((uint32_t)(h >> 32) != HANDLE_MAGIC) return -1;
    uint32_t idx = (uint32_t)h;
    if (idx == 0 || idx > HANDLE_ROWS || !rows[idx - 1].used) return -1;
    return (int)(idx - 1);
}

static int refuse(uint64_t h, const char *call)
{
    /* Split the two bugs this refusal can mean: never created, or created somewhere other than the
       storage this call reads. A live row holding exactly this value means the handle is valid and the
       caller is looking at a different address; no such row means it was never handed out. */
    int live = 0;
    for (int i = 0; i < HANDLE_ROWS; i++) live += rows[i].used ? 1 : 0;
    fprintf(stderr, "pbboot: sema: %s refused, %016llx is not a live handle (%d of %d rows in use -- 0 rows "
                    "means no Create ran before this Wait, i.e. never handed out rather than created "
                    "elsewhere)\n", call, (unsigned long long)h, live, HANDLE_ROWS);
    return k_err_inval;
}

static int sema_create(int64_t out, int64_t name, int64_t attr, int64_t init_count, int64_t max_count,
                       int64_t opt)
{
    (void)name; (void)attr; (void)opt;
    if (out == 0) return k_err_inval;
    if (max_count <= 0 || init_count < 0 || init_count > max_count) {
        fprintf(stderr, "pbboot: sema: Create refused: name=%#llx init=%lld max=%lld\n",
                (unsigned long long)name, (long long)init_count, (long long)max_count);
        return k_err_inval;
    }
    for (int i = 0; i < HANDLE_ROWS; i++) {
        if (rows[i].used) continue;
        pthread_mutex_init(&rows[i].lock, NULL);
        pthread_cond_init(&rows[i].cond, NULL);
        rows[i].used = 1;
        rows[i].count = (int)init_count;
        rows[i].max = (int)max_count;
        *(uint64_t *)(uintptr_t)out = ((uint64_t)HANDLE_MAGIC << 32) | (uint64_t)(i + 1);
        if (getenv("BB_SEMA_TRACE")) {
            long tid; __asm__ volatile("syscall" : "=a"(tid) : "a"(186L) : "rcx", "r11", "memory");
            fprintf(stderr, "pbboot: sema: Create %016llx init=%lld max=%lld tid=%ld\n",
                    (unsigned long long)*(uint64_t *)(uintptr_t)out, (long long)init_count,
                    (long long)max_count, tid);
        }
        return 0;
    }
    fprintf(stderr, "pbboot: sema: Create table full (%d rows), refusing name=%#llx\n", HANDLE_ROWS,
            (unsigned long long)name);
    return k_err_nomem;
}

/* ABI class note, measured: semaphore, mutex, event flag and cond take the ID BY VALUE;
   Map/Allocate/gettimeofday take pointers. We learned this the expensive way -- rdi held
   0x53454d4100000012 ("SEMA" | 19) and the old body dereferenced it as a pointer to storage.
   Arity is knowable from the import record; a first argument's kind is not, so it is written here. */
static int sema_signal(int64_t sema_id, int64_t count);
static void sema_timer_start(void);

static int sema_wait(int64_t sema_id, int64_t need, int64_t timeout)
{
    sema_timer_start();
    uint64_t h = (uint64_t)sema_id;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Wait");
    if (need <= 0) return k_err_inval;
    pthread_mutex_lock(&rows[i].lock);
    {
        static int waits_seen;
        if (getenv("BB_SEMA_TRACE") && waits_seen++ < 64) {
            long tid; __asm__ volatile("syscall" : "=a"(tid) : "a"(186L) : "rcx", "r11", "memory");
            fprintf(stderr, "pbboot: sema: Wait %016llx tid=%ld need=%lld count=%d\n",
                    (unsigned long long)h, tid, (long long)need, rows[i].count);
        }
    }
    while (rows[i].count < (int)need) {
        /* Timeout 0 is not "poll" in this ABI: the adaptive mutex passes 0 on its blocking slow path
           and treats ANY error as a logical panic. 0 and -1 both mean wait without a deadline; only a
           positive value is a usecond deadline. Treating 0 as now+0 returned ETIMEDOUT before the
           signaller could run, and the guest panicked at CSPlainAdaptiveMutexImp_sce.cpp:169. */
        if (timeout <= 0) {
            static int announced[HANDLE_ROWS];
            if (!announced[i]) {
                announced[i] = 1;
                { long tid; __asm__ volatile("syscall" : "=a"(tid) : "a"(186L) : "rcx", "r11", "memory");
                  /* No guest_pc here: rt_guest_call_pc() reads one global, and a sema wait on the main
                     thread printed wmemcmp's return address because the worker had run an import since.
                     Under real threads that number names the last caller, not this thread's. It stays
                     out of the line until the in-flight record is per-thread. */
                  fprintf(stderr, "pbboot: sema: Wait %016llx BLOCKING tid=%ld (need %lld count %d)\n",
                          (unsigned long long)h, tid, (long long)need, rows[i].count); }
            }
            pthread_cond_wait(&rows[i].cond, &rows[i].lock);
        } else {
            struct timespec ts;
            clock_gettime(CLOCK_REALTIME, &ts);
            uint64_t ns = (uint64_t)ts.tv_nsec + (uint64_t)(timeout % 1000000) * 1000ull;
            ts.tv_sec += (time_t)(timeout / 1000000) + (time_t)(ns / 1000000000ull);
            ts.tv_nsec = (long)(ns % 1000000000ull);
            int rc = pthread_cond_timedwait(&rows[i].cond, &rows[i].lock, &ts);
            if (rc == ETIMEDOUT) {
                pthread_mutex_unlock(&rows[i].lock);
                fprintf(stderr, "pbboot: sema: Wait on %016llx timed out (need %lld, count %d, timeout %lld us)\n",
                        (unsigned long long)h, (long long)need, rows[i].count, (long long)timeout);
                return (int)0x8002003cu; /* ETIMEDOUT is BSD 60, so 0x80020000 | 60 -- the code
                                             the guest's own switch knows; 0x8002001c was ENOSPC, a
                                             numeral guessed from position, and the guest printed
                                             "Unknown Error" because its table had no such row */
            }
        }
    }
    rows[i].count -= (int)need;
    pthread_mutex_unlock(&rows[i].lock);
    return 0;
}

static int sema_signal(int64_t sema_id, int64_t count)
{
    uint64_t h = (uint64_t)sema_id;
    static int seen;
    if (seen < 12) { seen++; fprintf(stderr, "pbboot: sema: Signal entry %016llx count %lld\n",
                                      (unsigned long long)h, (long long)count); }
    int i = row_of(h);
    if (i < 0) return refuse(h, "Signal");
    if (count <= 0) return k_err_inval;
    pthread_mutex_lock(&rows[i].lock);
    rows[i].count += (int)count;
    if (rows[i].count > rows[i].max) {
        fprintf(stderr, "pbboot: sema: Signal over max on %016llx (%d > %d), clamped\n",
                (unsigned long long)h, rows[i].count, rows[i].max);
        rows[i].count = rows[i].max;
    }
    pthread_cond_broadcast(&rows[i].cond);
    pthread_mutex_unlock(&rows[i].lock);
    return 0;
}


/* MODELLED SUPPLIER (BB_SEMA_TIMER).  The boot parks on a sequence of pool semaphores
   (0x3, 0x8, ...) whose tokens no code in the process produces; the hand-token experiment
   showed the guest accepts one token as one completion and advances to the next pool member.
   This thread stands in for whatever outside event was supposed to deliver those completions:
   it issues one token per pool semaphore, in create order, at a declared period, and prints
   each one.  It is a model of a supplier, not of an import; nothing binds to it. */
static void *sema_timer_main(void *arg)
{
    long period_ms = (long)(intptr_t)arg;
    for (int i = 0; i < 17; i++) {
        struct timespec ts;
        ts.tv_sec = period_ms / 1000;
        ts.tv_nsec = (period_ms % 1000) * 1000000L;
        nanosleep(&ts, NULL);
        uint64_t h = 0x53454d4100000000ull | (uint64_t)(i + 1);
        fprintf(stderr, "pbboot: sema: TIMER (MODELLED) %ld ms -> Signal %016llx\n",
                period_ms, (unsigned long long)h);
        (void)sema_signal((int64_t)h, 1);
    }
    return NULL;
}

static void sema_timer_start(void)
{
    static long period_ms;
    static int started;
    const char *e = getenv("BB_SEMA_TIMER");
    if (!e || !*e || started) return;
    period_ms = strtol(e, NULL, 10);
    if (period_ms <= 0 || period_ms > 1000) period_ms = 2;
    pthread_t t;
    started = 1;
    fprintf(stderr, "pbboot: sema: TIMER (MODELLED) registered: one token per pool sema, period %ld ms\n", period_ms);
    pthread_create(&t, NULL, sema_timer_main, (void *)(intptr_t)period_ms);
    pthread_detach(t);
}

static int sema_poll(int64_t sema_id, int64_t need)
{
    uint64_t h = (uint64_t)sema_id;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Poll");
    pthread_mutex_lock(&rows[i].lock);
    if (rows[i].count < (int)need) {
        pthread_mutex_unlock(&rows[i].lock);
        /* A poll that cannot take the count is busy, not faulting: EFAULT (0x8002000e) was a lie
           about the guest's own storage and the adaptive mutex read it as a logical error. EBUSY is
           BSD 16, so 0x80020010. */
        return (int)0x80020010u;
    }
    rows[i].count -= (int)need;
    pthread_mutex_unlock(&rows[i].lock);
    return 0;
}

static int sema_delete(int64_t sema_id)
{
    uint64_t h = (uint64_t)sema_id;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Delete");
    /* The id is by value, so there is no guest word to clear: destroying must make the id itself dead,
       and it does, because row_of() checks `used` before anything else. Clearing through a pointer here
       is what the old body did and it was the same defect as dereferencing the id in Wait. */
    pthread_mutex_destroy(&rows[i].lock);
    pthread_cond_destroy(&rows[i].cond);
    rows[i].used = 0;
    return 0;
}

/* The one call that could falsify the assertion above. It refuses, loudly and by name, instead of
   spawning a host thread that runs guest code without a modelled TLS block or a locked arena. */
static int thread_create_refused(int64_t out, int64_t attr, int64_t entry, int64_t arg, int64_t name)
{
    thread_wall_reached = 1;
    /* Print the five raw arguments before interpreting any of them. The two prototypes in this tree
       disagree at positions 2 and 5 (name second/attr fifth in sce_pthread_create_a, attr second/name
       fifth here), and the dead body casts every argument to (void), so it cannot witness the order at
       all. No dereference here: a name that is not a string must not fault the witness that would say so. */
    fprintf(stderr, "pbboot: scePthreadCreate raw: out=%#llx attr=%#llx entry=%#llx arg=%#llx name=%#llx\n",
            (unsigned long long)(uint64_t)out, (unsigned long long)(uint64_t)attr,
            (unsigned long long)(uint64_t)entry, (unsigned long long)(uint64_t)arg,
            (unsigned long long)(uint64_t)name);
    (void)name;
    /* Read the attribute once, before either branch: the refusal wants it for its sentence, and the
       modelled branch wants the same stack size. A setter whose value nothing reads is decorative;
       this is the only path that reads one today. */
    void *const *av = attr ? (void *const *)(uintptr_t)attr : NULL;
    uint64_t size = 0;
    int policy = 0;
    const int has_size = rt_thread_attr_stack_size(av, &size);
    const int has_policy = rt_thread_attr_sched_policy(av, &policy);
    fprintf(stderr, "pbboot: scePthreadCreate: attr stack %s0x%llx, policy %s%d\n",
            has_size < 0 ? "absent " : has_size ? "asked " : "not asked ",
            has_size > 0 ? (unsigned long long)size : 0ull,
            has_policy < 0 ? "absent " : has_policy ? "asked " : "not asked ",
            has_policy > 0 ? policy : 0);

    /* Real threads: a host pthread per guest thread, with its own guest TLS block and %fs. The
       hypothesis is that the pool's continuation was waiting for workers that never existed; the
       falsifier is that the boot still stops at CondWait (or faults earlier) with this on. */
    if (getenv("BB_THREAD_REAL"))
        return rt_thread_create_real(out, entry, arg, size, has_size > 0);

    /* EXPERIMENT A-success. The guest's own failure path panicked; this branch gives it the success it
       asked for and creates no host thread. The handle is a tagged integer, never a plausible pointer:
       a real guest_thread* is 8-byte aligned, so bit 0 is a marker the log and any later refusal can
       name. The registration stays UNRESOLVED because the shipped default is still the refusal below;
       a declaration true only when a flag is set would be the comment-with-a-macro defect. */
    if (rt_thread_modelled_enabled()) {
        if (out == 0) return k_err_inval;
        if (!rt_guest_write_ok((uintptr_t)out, 8, "scePthreadCreate")) return k_err_fault;
        static uint64_t modelled_serial;
        const uint64_t handle = ((++modelled_serial) << 1) | 1;
        *(uint64_t *)(uintptr_t)out = handle;
        fprintf(stderr, "pbboot: scePthreadCreate: MODELLED handle 0x%llx (tagged, no host thread), "
                        "entry %p arg %p, stack %s0x%llx; BB_THREAD_MODELLED=1 -- the guest proceeds "
                        "through fabricated state and must be able to see it\n",
                (unsigned long long)handle, (void *)(uintptr_t)entry, (void *)(uintptr_t)arg,
                has_size > 0 ? "" : "not asked ", has_size > 0 ? (unsigned long long)size : 0ull);
        return 0;
    }

    /* The wall, named and stopped at rather than served past. Returning an error here is what the guest
       did NOT handle: it panicked, and the panic path dereferences the unpopulated __sFILE, so the run
       ended in a stdio-looking fault two layers away from the cause. Stopping here means nothing after this
       point is fabricated state -- a synchronisation model that cannot be honoured must not be handed a
       success, and the guest's own failure path is not an honest alternative when the failure is ours. */
    static char wall[768];
    /* Each module owns its PT_TLS block; they are not supposed to agree, and calling that a contradiction
       was a misdiagnosis (measured with readelf -lW on this tree, not quoted from an older text):
         eboot.elf  filesz 0x0    memsz 0x750   -- zero-init, no TLS image
         libc.elf   filesz 0x220  memsz 0x4a0   -- an init image that would have to be copied per thread
       What is actually missing is machinery, not agreement. */
    (void)rt_thread_attr_detach_state(av, "scePthreadCreate");
    const uint64_t call = rt_guest_call_pc();
    if (call)
        snprintf(wall, sizeof wall,
                 "the guest asked for a thread (entry %p, arg %p, called from eboot+0x%llx = catalogue 0x%llx) "
                 "and this runtime cannot give it one: there is no per-thread TCB/TLS allocation (eboot TLS "
                 "0x0/0x750 zero-init; libc.elf TLS 0x220/0x4a0 needs its image copied per thread), no guest/host "
                 "%%fs switch on the child side, the arena is one unlocked bump pointer, and every host call "
                 "assumes one guest thread in flight",
                 (void *)(uintptr_t)entry, (void *)(uintptr_t)arg, (unsigned long long)rt_runtime_to_vaddr(call),
                 (unsigned long long)rt_vaddr_to_catalogue(rt_runtime_to_vaddr(call)));
    else
        snprintf(wall, sizeof wall,
                 "the guest asked for a thread (entry %p, arg %p, call site not captured for this object) and "
                 "this runtime cannot give it one: no per-thread TCB/TLS allocation (eboot 0x0/0x750 zero-init; "
                 "libc.elf 0x220/0x4a0), no guest/host %%fs switch on the child side, one unlocked bump arena, "
                 "and every host call assumes one guest thread in flight",
                 (void *)(uintptr_t)entry, (void *)(uintptr_t)arg);
    rt_fatal("scePthreadCreate", wall);
}

RT_SYSLIB_NOOP("libkernel", sceKernelCreateSema, sema_create);
RT_SYSLIB_NOOP("libkernel", sceKernelWaitSema, sema_wait);
RT_SYSLIB_NOOP("libkernel", sceKernelSignalSema, sema_signal);
RT_SYSLIB_NOOP("libkernel", sceKernelPollSema, sema_poll);
RT_SYSLIB_NOOP("libkernel", sceKernelDeleteSema, sema_delete);
RT_SYSLIB_UNRESOLVED("libkernel", scePthreadCreate, thread_create_refused);

/* The cond family moved to kernel_mutex.c, where the mutex object it must lock also lives: a
   condvar in this file could only wait on a host mutex it cannot name. The old body zeroed guest
   storage and created no host condvar -- true while scePthreadCreate refused every thread, false
   the moment a real thread exists. */

/* The pthread attribute family, landed as one declaration instead of eight turns.

   Every one of these sets a field of a guest attr object that no code path will ever read, because this
   runtime refuses to create threads (scePthreadCreate is a named refusal, not a stub). The values they
   carry -- stack size, scheduling policy, detach state, scope, affinity -- are only observable to a thread
   that exists. Writing them into guest memory would be a decorative write: state that validates as
   correct and that nothing can observe.

   Declared MODELLED and printed on every call, so the log says how far the boot is walking on these
   before the guest reaches the create call that cannot succeed. First argument is a pointer for every
   member of the family; the rest are scalars. */
#define PB_ATTR_NOOP(lib, sym)                                                                        \
    static int attr_noop_##sym(int64_t a, int64_t b, int64_t c)                                       \
    {                                                                                                 \
        (void)c;                                                                                      \
        fprintf(stderr, "pbboot: posix: " #sym "(%llx, %lld) -> 0 (modelled: attr no-op, threads "     \
                        "are refused)\n", (unsigned long long)a, (long long)b);                       \
        return 0;                                                                                     \
    }                                                                                                 \
    RT_SYSLIB_MODELLED(lib, sym, attr_noop_##sym)

/* removed: PB_ATTR_NOOP("libkernel", scePthreadAttrInit); -- kernel_thread.c registers the real body for this key and wins on
   section order, so this row has never run. The startup duplicate check now refuses such rows. */
/* removed: PB_ATTR_NOOP("libkernel", scePthreadAttrDestroy); -- kernel_thread.c registers the real body for this key and wins on
   section order, so this row has never run. The startup duplicate check now refuses such rows. */
/* removed: PB_ATTR_NOOP("libkernel", scePthreadAttrSetdetachstate); -- kernel_thread.c registers the real body for this key and wins on
   section order, so this row has never run. The startup duplicate check now refuses such rows. */
PB_ATTR_NOOP("libkernel", scePthreadAttrSetinheritsched);
PB_ATTR_NOOP("libkernel", scePthreadAttrSetschedparam);
/* removed: PB_ATTR_NOOP("libkernel", scePthreadAttrSetschedpolicy); -- kernel_thread.c registers the real body
   (stores has_policy/policy; the create path reads and prints it) and wins on section order. */
PB_ATTR_NOOP("libkernel", scePthreadAttrSetaffinity);
/* removed: PB_ATTR_NOOP("libkernel", scePthreadAttrGet); -- kernel_thread.c registers the real body for this key and wins on
   section order, so this row has never run. The startup duplicate check now refuses such rows. */
/* removed: PB_ATTR_NOOP("libkernel", scePthreadAttrGetaffinity); -- kernel_thread.c registers the real body for this key and wins on
   section order, so this row has never run. The startup duplicate check now refuses such rows. */
PB_ATTR_NOOP("libScePosix", pthread_attr_init);
PB_ATTR_NOOP("libScePosix", pthread_attr_destroy);
/* removed: PB_ATTR_NOOP("libScePosix", pthread_attr_setdetachstate); -- kernel_thread.c registers the real body for this key and wins on
   section order, so this row has never run. The startup duplicate check now refuses such rows. */
PB_ATTR_NOOP("libScePosix", pthread_attr_setstacksize);
PB_ATTR_NOOP("libScePosix", pthread_attr_setschedparam);
