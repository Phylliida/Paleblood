/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Guest storage holds an opaque handle; the host object lives on our side of the fence.

   A host pthread_rwlock_t must never be written into guest memory: its size differs between libcs
   (glibc's is 56 bytes), the guest allocated its own sce_pthread_rwlock_t of a size we do not own, and
   the guest may zero-check or copy that storage. That is the __sFILE defect one structure over -- a
   host layout standing in for a guest object -- so the guest gets 8 bytes it may treat as opaque, and
   every operation resolves through this table. A stale handle refuses loudly instead of locking freed
   memory.

   This is a family, not a function: mutex, once and cond will land on the same table. */
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define HANDLE_MAGIC 0x50545748u /* "PTWH" */
#define HANDLE_ROWS 32

/* The model's own error values, as the arena's are: no console citation, so not dressed as one. */
enum { k_err_inval = (int)0x80020016u, k_err_nomem = (int)0x8002000cu };

static struct {
    pthread_rwlock_t host;
    int used;
} rows[HANDLE_ROWS];
static pthread_mutex_t table_lock = PTHREAD_MUTEX_INITIALIZER;

static int row_resolve(uint64_t handle)
{
    if ((uint32_t)(handle >> 32) != HANDLE_MAGIC) return -1;
    uint32_t idx = (uint32_t)handle;
    if (idx == 0 || idx > HANDLE_ROWS) return -1;
    if (!rows[idx - 1].used) return -1;
    return (int)(idx - 1);
}

static int row_refuse(uint64_t handle, const char *call)
{
    fprintf(stderr, "pbboot: rwlock: %s refused, %016llx is not a live handle\n", call,
            (unsigned long long)handle);
    return k_err_inval;
}

static int rwlock_init(int64_t storage, int64_t attr)
{
    (void)attr; /* attribute objects are not modelled; the caller's policy is not read */
    if (storage == 0) return k_err_inval;
    pthread_mutex_lock(&table_lock);
    for (int i = 0; i < HANDLE_ROWS; i++) {
        if (rows[i].used) continue;
        if (pthread_rwlock_init(&rows[i].host, NULL) != 0) {
            pthread_mutex_unlock(&table_lock);
            return k_err_nomem;
        }
        rows[i].used = 1;
        *(uint64_t *)(uintptr_t)storage = ((uint64_t)HANDLE_MAGIC << 32) | (uint64_t)(i + 1);
        pthread_mutex_unlock(&table_lock);
        return 0;
    }
    pthread_mutex_unlock(&table_lock);
    return k_err_nomem;
}

static int rwlock_op(int64_t storage, const char *call, int (*op)(pthread_rwlock_t *))
{
    if (storage == 0) return row_refuse(0, call);
    uint64_t h = *(const uint64_t *)(uintptr_t)storage;
    int i = row_resolve(h);
    if (i < 0) return row_refuse(h, call);
    return op(&rows[i].host) == 0 ? 0 : k_err_inval;
}

static int op_rdlock(pthread_rwlock_t *l) { return pthread_rwlock_rdlock(l); }
static int op_wrlock(pthread_rwlock_t *l) { return pthread_rwlock_wrlock(l); }
static int op_unlock(pthread_rwlock_t *l) { return pthread_rwlock_unlock(l); }
static int op_tryrd(pthread_rwlock_t *l) { return pthread_rwlock_tryrdlock(l); }
static int op_trywr(pthread_rwlock_t *l) { return pthread_rwlock_trywrlock(l); }

static int rwlock_destroy(int64_t storage)
{
    if (storage == 0) return row_refuse(0, "Destroy");
    uint64_t h = *(const uint64_t *)(uintptr_t)storage;
    int i = row_resolve(h);
    if (i < 0) return row_refuse(h, "Destroy");
    pthread_rwlock_destroy(&rows[i].host);
    pthread_mutex_lock(&table_lock);
    rows[i].used = 0;
    pthread_mutex_unlock(&table_lock);
    *(uint64_t *)(uintptr_t)storage = 0;
    return 0;
}

static int rwlock_rdlock(int64_t s) { return rwlock_op(s, "Rdlock", op_rdlock); }
static int rwlock_wrlock(int64_t s) { return rwlock_op(s, "Wrlock", op_wrlock); }
static int rwlock_unlock(int64_t s) { return rwlock_op(s, "Unlock", op_unlock); }
static int rwlock_tryrdlock(int64_t s) { return rwlock_op(s, "Tryrdlock", op_tryrd); }
static int rwlock_trywrlock(int64_t s) { return rwlock_op(s, "Trywrlock", op_trywr); }

RT_SYSLIB("libkernel", scePthreadRwlockInit, rwlock_init);
RT_SYSLIB("libkernel", scePthreadRwlockDestroy, rwlock_destroy);
RT_SYSLIB("libkernel", scePthreadRwlockRdlock, rwlock_rdlock);
RT_SYSLIB("libkernel", scePthreadRwlockWrlock, rwlock_wrlock);
RT_SYSLIB("libkernel", scePthreadRwlockUnlock, rwlock_unlock);
RT_SYSLIB("libkernel", scePthreadRwlockTryrdlock, rwlock_tryrdlock);
RT_SYSLIB("libkernel", scePthreadRwlockTrywrlock, rwlock_trywrlock);
