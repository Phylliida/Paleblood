/* Two host threads must get two guest TCBs. This is the first half of todo/047: the runtime's TLS state
   was one static block, so a second thread trampled the first's fs:[0] and its fs-0x690 slot. The test
   runs the real runtime/tls.c, not a model, and each thread reads its own %fs back through the register
   the guest will use. A thread that only checks a C pointer proves the bytes were written, not which
   base they belong to -- the 0xdb-class mistake this file exists to catch.
 *
 * Skip 77 when the host cannot wrfsbase; that is a host capability absence, not a green. */
#include "runtime/tls.h"

#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>

enum { THREADS = 4 };

static pthread_barrier_t barrier;
static uint64_t guest_bases[THREADS];
static uint64_t host_bases[THREADS];
static uint64_t main_guest;
static atomic_int failures;

static uint64_t read_fsbase(void)
{
    uint64_t v = 0;
    __asm__ volatile("rdfsbase %0" : "=r"(v));
    return v;
}

static void fail(int i, const char *what, uint64_t got, uint64_t want)
{
    fprintf(stderr, "tls_threads[%d]: %s: got 0x%llx want 0x%llx\n", i, what,
            (unsigned long long)got, (unsigned long long)want);
    atomic_fetch_add(&failures, 1);
}

static void *worker(void *arg)
{
    const int i = (int)(intptr_t)arg;
    rt_tls_thread_begin();
    rt_tls_layout(NULL, 0, 0x750u); /* eboot's memsz: fs-0x690 is inside the block */

    const uint64_t host = rt_tls_host_base();
    const uint64_t guest = rt_tls_guest_base();
    if (read_fsbase() != host) fail(i, "host fs before guest", read_fsbase(), host);
    if (guest == main_guest) {
        fail(i, "guest base distinct from main", guest, main_guest);
        pthread_barrier_wait(&barrier);
        rt_tls_thread_end();
        return NULL;
    }

    rt_tls_enter_guest();
    if (read_fsbase() != guest) fail(i, "guest fs", read_fsbase(), guest);

    uint64_t self = 0;
    __asm__ volatile("movq %%fs:0, %0" : "=r"(self));

    rt_tls_view view;
    rt_tls_view_read(&view);       /* capture while %fs is the guest block, without any libc call */

    volatile unsigned char *slot = (volatile unsigned char *)(uintptr_t)(guest - 0x690u);
    *slot = (unsigned char)(0xa0 + i);

    rt_tls_enter_host();           /* from here on printf and fail() are safe */
    if (read_fsbase() != host) fail(i, "host fs restored", read_fsbase(), host);
    if (self != guest) fail(i, "fs:[0] self-pointer", self, guest);

    rt_tls_trace_view("worker-after-guest", &view);
    if (view.gs != view.state) fail(i, "gs == tls_state", view.gs, view.state);
    if (view.state_self != view.state) fail(i, "state.self == state", view.state_self, view.state);
    if (view.fsbase != guest) fail(i, "fsbase == guest", view.fsbase, guest);
    if (view.fs0 != guest) fail(i, "fs[0] == guest", view.fs0, guest);
    if (view.installer != guest) fail(i, "installer == guest", view.installer, guest);
    if (view.enter_guest != guest) fail(i, "enter_guest == guest", view.enter_guest, guest);
    /* A child must not overwrite the main thread's published globals. This asserts the record, not the
       selector: rt_boot_call still reads rt_tls_guest_base_v, which is todo/047. The trace prints both
       values side by side so that defect is visible rather than silently absorbed. */
    if (view.published != main_guest) fail(i, "published is main's global", view.published, main_guest);

    guest_bases[i] = guest;
    host_bases[i] = host;
    /* Keep every block alive until all four have written their slot; otherwise the distinctness check
       could pass merely because the threads ran one after another. */
    pthread_barrier_wait(&barrier);
    rt_tls_thread_end();
    return NULL;
}

/* The first worker supplies 0x750 explicitly. That override is necessary for the slot test, but it
   vendors the value the product's default gets wrong: rt_tls_thread_begin() must inherit the main
   thread's 0x750, not install a 0x4a0 block that cannot hold eboot's fs-0x690 slot. This worker omits
   the override so the default itself is measured. */
static void *default_worker(void *arg)
{
    (void)arg;
    rt_tls_thread_begin();
    rt_tls_view view;
    rt_tls_view_read(&view);
    rt_tls_trace_view("default-after-begin", &view);
    if (view.memsz != 0x750u) fail(THREADS, "default child memsz", view.memsz, 0x750u);
    rt_tls_thread_end();
    return NULL;
}

int main(void)
{
    rt_tls_init();
    rt_tls_layout(NULL, 0, 0x750u); /* model eboot on the main thread: children inherit this */
    main_guest = rt_tls_guest_base();
    if (!rt_tls_have_wrfsbase()) {
        fprintf(stderr, "tls_threads: SKIP: host has no user-mode wrfsbase\n");
        return 77;
    }

    pthread_t threads[THREADS];
    if (pthread_barrier_init(&barrier, NULL, THREADS) != 0) {
        fprintf(stderr, "tls_threads: barrier init failed\n");
        return 1;
    }
    for (int i = 0; i < THREADS; i++) {
        if (pthread_create(&threads[i], NULL, worker, (void *)(intptr_t)i) != 0) {
            fprintf(stderr, "tls_threads: pthread_create %d failed\n", i);
            return 1;
        }
    }
    for (int i = 0; i < THREADS; i++) pthread_join(threads[i], NULL);
    pthread_barrier_destroy(&barrier);

    const uint64_t main_guest_after = rt_tls_guest_base();
    for (int i = 0; i < THREADS; i++) {
        if (guest_bases[i] == 0) fail(i, "guest base recorded", guest_bases[i], 1);
        if (guest_bases[i] == main_guest_after) fail(i, "guest base distinct from main", guest_bases[i], main_guest_after);
        for (int j = 0; j < i; j++)
            if (guest_bases[i] == guest_bases[j])
                fail(i, "guest base distinct from peer", guest_bases[i], guest_bases[j]);
    }

    pthread_t default_thread;
    if (pthread_create(&default_thread, NULL, default_worker, NULL) != 0) {
        fprintf(stderr, "tls_threads: pthread_create default failed\n");
        return 1;
    }
    pthread_join(default_thread, NULL);

    if (atomic_load(&failures) != 0) {
        fprintf(stderr, "tls_threads: FAIL (%d)\n", atomic_load(&failures));
        return 1;
    }
    printf("tls_threads: OK: %d host threads, %d distinct guest TCBs, host FS restored\n", THREADS, THREADS);
    return 0;
}
