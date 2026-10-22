/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Single-threadedness, asserted in one place, and the blocking family it makes cheap.

   Exactly one call could ever make this runtime multi-threaded: scePthreadCreate. It refuses here, so
   everything below is correct under the assertion rather than assumed by each function separately. The
   assertion is a variable, not a comment, because a claim a compiler can check beats one a reader has to.

   A no-op that records when it *would* have blocked is a measurement; a silent one is a wish. So Wait
   prints the case it could not serve -- count short of the request -- which is exactly the situation that
   would hang a real kernel and is therefore evidence of guest logic rather than of our stub. */
#include "runtime/guest_mem.h"
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define HANDLE_MAGIC 0x53454d41u /* "SEMA" */
#define HANDLE_ROWS 32

enum { k_err_inval = (int)0x80020016u, k_err_nomem = (int)0x8002000cu };

/* THE ASSERTION. Only scePthreadCreate could clear it, and it refuses instead -- so the family below is
   correct *under* it rather than each function assuming it privately. Every entry point checks. */
static int guest_threads = 1;

static void require_single_threaded(const char *call)
{
    if (!guest_threads) rt_fatal(call, "the guest is no longer single-threaded and this model is");
}

static struct {
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
    if (max_count <= 0 || init_count < 0 || init_count > max_count) return k_err_inval;
    for (int i = 0; i < HANDLE_ROWS; i++) {
        if (rows[i].used) continue;
        rows[i].used = 1;
        rows[i].count = (int)init_count;
        rows[i].max = (int)max_count;
        *(uint64_t *)(uintptr_t)out = ((uint64_t)HANDLE_MAGIC << 32) | (uint64_t)(i + 1);
        return 0;
    }
    return k_err_nomem;
}

/* ABI class note, measured: semaphore, mutex, event flag and cond take the ID BY VALUE;
   Map/Allocate/gettimeofday take pointers. We learned this the expensive way -- rdi held
   0x53454d4100000012 ("SEMA" | 19) and the old body dereferenced it as a pointer to storage.
   Arity is knowable from the import record; a first argument's kind is not, so it is written here. */
static int sema_wait(int64_t sema_id, int64_t need, int64_t timeout)
{
    require_single_threaded("Sema wait");
    (void)timeout;
    uint64_t h = (uint64_t)sema_id;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Wait");
    if (rows[i].count < (int)need) {
        /* Correct here, a hang on a real kernel: this is the guest asking to block. */
        fprintf(stderr, "pbboot: sema: Wait on %016llx asked %lld, count %d -- would have blocked, "
                        "served as success because the guest is single-threaded\n",
                (unsigned long long)h, (long long)need, rows[i].count);
        rows[i].count = 0;
        return 0;
    }
    rows[i].count -= (int)need;
    return 0;
}

static int sema_signal(int64_t sema_id, int64_t count)
{
    require_single_threaded("Sema signal");
    uint64_t h = (uint64_t)sema_id;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Signal");
    rows[i].count += (int)count;
    if (rows[i].count > rows[i].max) {
        fprintf(stderr, "pbboot: sema: Signal over max on %016llx (%d > %d), clamped\n",
                (unsigned long long)h, rows[i].count, rows[i].max);
        rows[i].count = rows[i].max;
    }
    return 0;
}

static int sema_poll(int64_t sema_id, int64_t need)
{
    require_single_threaded("Sema poll");
    uint64_t h = (uint64_t)sema_id;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Poll");
    if (rows[i].count < (int)need) return (int)0x8002000eu; /* would block: a poll's honest answer */
    rows[i].count -= (int)need;
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
    rows[i].used = 0;
    return 0;
}

/* The one call that could falsify the assertion above. It refuses, loudly and by name, instead of
   spawning a host thread that runs guest code without a modelled TLS block or a locked arena. */
static int thread_create_refused(int64_t out, int64_t attr, int64_t entry, int64_t arg, int64_t name)
{
    (void)out; (void)attr; (void)name;
    /* The wall, named and stopped at rather than served past. Returning an error here is what the guest
       did NOT handle: it panicked, and the panic path dereferences the unpopulated __sFILE, so the run
       ended in a stdio-looking fault two layers away from the cause. Stopping here means nothing after this
       point is fabricated state -- a synchronisation model that cannot be honoured must not be handed a
       success, and the guest's own failure path is not an honest alternative when the failure is ours. */
    static char wall[512];
    snprintf(wall, sizeof wall,
             "the guest asked for a thread (entry %p, arg %p) and this runtime cannot give it one: guest "
             "TLS is unmodelled (PT_TLS filesz 0x220, memsz 0x4a0), the arena is one unlocked bump "
             "pointer, and every host call assumes one guest thread in flight",
             (void *)(uintptr_t)entry, (void *)(uintptr_t)arg);
    rt_fatal("scePthreadCreate", wall);
}

RT_SYSLIB_NOOP("libkernel", sceKernelCreateSema, sema_create);
RT_SYSLIB_NOOP("libkernel", sceKernelWaitSema, sema_wait);
RT_SYSLIB_NOOP("libkernel", sceKernelSignalSema, sema_signal);
RT_SYSLIB_NOOP("libkernel", sceKernelPollSema, sema_poll);
RT_SYSLIB_NOOP("libkernel", sceKernelDeleteSema, sema_delete);
RT_SYSLIB_UNRESOLVED("libkernel", scePthreadCreate, thread_create_refused);

/* pthread_cond_init(cond, attr): the FIRST ARGUMENT IS A POINTER to caller-provided storage, unlike the
   semaphore family whose id is by value. That difference is the ABI class the two runs paid for: arity is
   knowable from the import record, a first argument's kind is not. Modelled: the object is zeroed through
   the write check and no host condvar is created, because a condvar here would only ever be signalled by a
   worker thread, and scePthreadCreate refuses to make one. */
static int cond_init(int64_t cond, int64_t attr)
{
    (void)attr;
    if (cond == 0) return (int)0x80020016u;
    if (!rt_guest_write_ok((uintptr_t)cond, 8, "PthreadCondInit")) return (int)0x8002000eu;
    *(uint64_t *)(uintptr_t)cond = 0;
    fprintf(stderr, "pbboot: posix: CondInit(%llx) -> 0 (modelled: zeroed storage, no host condvar)\n",
            (unsigned long long)cond);
    return 0;
}

RT_SYSLIB_MODELLED("libScePosix", pthread_cond_init, cond_init);

/* scePthreadAttrSetstacksize(attr, size): the first argument is a POINTER to a guest attr object, the
   second a scalar. Modelled, and modelled as a no-op that says so: this runtime refuses to create threads
   (see thread_create_refused), so a stack size is a value nobody will ever read. Recording it in the attr
   object would be writing state that no code path can observe -- the definition of a decorative write. */
static int attr_set_stacksize(int64_t attr, int64_t size)
{
    if (attr == 0) return (int)0x80020016u;
    fprintf(stderr, "pbboot: posix: AttrSetstacksize(%llx, %lld) -> 0 (modelled: no-op, threads are refused)\n",
            (unsigned long long)attr, (long long)size);
    return 0;
}

RT_SYSLIB_MODELLED("libkernel", scePthreadAttrSetstacksize, attr_set_stacksize);

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

PB_ATTR_NOOP("libkernel", scePthreadAttrInit);
PB_ATTR_NOOP("libkernel", scePthreadAttrDestroy);
PB_ATTR_NOOP("libkernel", scePthreadAttrSetdetachstate);
PB_ATTR_NOOP("libkernel", scePthreadAttrSetinheritsched);
PB_ATTR_NOOP("libkernel", scePthreadAttrSetschedparam);
PB_ATTR_NOOP("libkernel", scePthreadAttrSetschedpolicy);
PB_ATTR_NOOP("libkernel", scePthreadAttrSetaffinity);
PB_ATTR_NOOP("libkernel", scePthreadAttrGet);
PB_ATTR_NOOP("libkernel", scePthreadAttrGetaffinity);
PB_ATTR_NOOP("libScePosix", pthread_attr_init);
PB_ATTR_NOOP("libScePosix", pthread_attr_destroy);
PB_ATTR_NOOP("libScePosix", pthread_attr_setdetachstate);
PB_ATTR_NOOP("libScePosix", pthread_attr_setstacksize);
PB_ATTR_NOOP("libScePosix", pthread_attr_setschedparam);
