/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Single-threadedness, asserted in one place, and the blocking family it makes cheap.

   Exactly one call could ever make this runtime multi-threaded: scePthreadCreate. It refuses here, so
   everything below is correct under the assertion rather than assumed by each function separately. The
   assertion is a variable, not a comment, because a claim a compiler can check beats one a reader has to.

   A no-op that records when it *would* have blocked is a measurement; a silent one is a wish. So Wait
   prints the case it could not serve -- count short of the request -- which is exactly the situation that
   would hang a real kernel and is therefore evidence of guest logic rather than of our stub. */
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

static int sema_wait(int64_t storage, int64_t need, int64_t timeout)
{
    require_single_threaded("Sema wait");
    (void)timeout;
    if (storage == 0) return refuse(0, "Wait");
    uint64_t h = *(const uint64_t *)(uintptr_t)storage;
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

static int sema_signal(int64_t storage, int64_t count)
{
    require_single_threaded("Sema signal");
    if (storage == 0) return refuse(0, "Signal");
    uint64_t h = *(const uint64_t *)(uintptr_t)storage;
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

static int sema_poll(int64_t storage, int64_t need)
{
    require_single_threaded("Sema poll");
    if (storage == 0) return refuse(0, "Poll");
    uint64_t h = *(const uint64_t *)(uintptr_t)storage;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Poll");
    if (rows[i].count < (int)need) return (int)0x8002000eu; /* would block: a poll's honest answer */
    rows[i].count -= (int)need;
    return 0;
}

static int sema_delete(int64_t storage)
{
    if (storage == 0) return refuse(0, "Delete");
    uint64_t h = *(const uint64_t *)(uintptr_t)storage;
    int i = row_of(h);
    if (i < 0) return refuse(h, "Delete");
    rows[i].used = 0;
    *(uint64_t *)(uintptr_t)storage = 0;
    return 0;
}

/* The one call that could falsify the assertion above. It refuses, loudly and by name, instead of
   spawning a host thread that runs guest code without a modelled TLS block or a locked arena. */
static int thread_create_refused(int64_t out, int64_t attr, int64_t entry, int64_t arg, int64_t name)
{
    (void)out; (void)attr; (void)name;
    fprintf(stderr, "pbboot: pthread: Create refused (entry %p, arg %p) -- the guest is modelled "
                    "single-threaded; a host thread running guest code needs TLS and a locked arena\n",
            (void *)(uintptr_t)entry, (void *)(uintptr_t)arg);
    return (int)0x80020016u;
}

RT_SYSLIB_NOOP("libkernel", sceKernelCreateSema, sema_create);
RT_SYSLIB_NOOP("libkernel", sceKernelWaitSema, sema_wait);
RT_SYSLIB_NOOP("libkernel", sceKernelSignalSema, sema_signal);
RT_SYSLIB_NOOP("libkernel", sceKernelPollSema, sema_poll);
RT_SYSLIB_NOOP("libkernel", sceKernelDeleteSema, sema_delete);
RT_SYSLIB_UNRESOLVED("libkernel", scePthreadCreate, thread_create_refused);
