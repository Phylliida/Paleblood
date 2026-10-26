/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Time: reproducible, from one origin, and written through a range check.

   Host wall clock would make two boots differ in guest-visible state and quietly invalidate any replay
   or differential of the boot, so the epoch is a fixed constant and the only thing that moves is elapsed
   monotonic time measured from one origin captured at startup. Every clock -- gettimeofday now,
   clock_gettime and process time when they arrive -- reads that origin, so the guest can never see time
   go backwards between two calls, which two independent host reads would allow at 1 us resolution.

   The guest timeval is declared here rather than borrowed from the host headers, and asserted: "happens
   to match x86-64 glibc" is exactly the assumption that produced the __sFILE defect. Writes go through
   rt_guest_write_ok(), because the first system call that writes guest memory is the wrong place to
   discover that the range was never validated. */
#include "runtime/guest_mem.h"
#include "runtime/syslib.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

/* 2023-11-14T22:13:20Z: fixed, so a boot is reproducible. */
#define rt_epoch_seconds 1700000000

typedef struct {
    int64_t tv_sec;
    int64_t tv_usec;
} guest_timeval;

_Static_assert(sizeof(guest_timeval) == 16, "guest timeval is 16 bytes");
_Static_assert(offsetof(guest_timeval, tv_usec) == 8, "guest timeval has usec at 8");

enum { k_err_fault = (int)0x8002000eu };

/* THE ORIGIN. One clock reading at first use; everything else is an offset from it. */
static uint64_t origin_ns;

static uint64_t elapsed_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    uint64_t now = (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
    if (origin_ns == 0) origin_ns = now ? now : 1;
    return now - origin_ns;
}

static int gettimeofday_impl(int64_t tv, int64_t tz)
{
    if (tv != 0) {
        if (!rt_guest_write_ok((uintptr_t)tv, sizeof(guest_timeval), "gettimeofday")) return k_err_fault;
        uint64_t ns = elapsed_ns();
        guest_timeval v;
        v.tv_sec = rt_epoch_seconds + (int64_t)(ns / 1000000000ull);
        v.tv_usec = (int64_t)((ns % 1000000000ull) / 1000ull);
        *(guest_timeval *)(uintptr_t)tv = v; /* field by field, in the guest's own layout */
    }
    if (tz != 0) {
        if (!rt_guest_write_ok((uintptr_t)tz, 8, "gettimeofday")) return k_err_fault;
        *(int32_t *)(uintptr_t)tz = 32;
        *(int32_t *)((uintptr_t)tz + 4) = 0;
    }
    return 0;
}

RT_SYSLIB_MODELLED("libkernel", gettimeofday, gettimeofday_impl);
RT_SYSLIB_MODELLED("libScePosix", gettimeofday, gettimeofday_impl);

/* The guest timespec, declared rather than borrowed: the same rule as the timeval above. The measured
   caller (game/frame_timing/monotonic_clock.cpp) asks for id 4, which is the id its own code names
   CLOCK_MONOTONIC. Ids are not guessed past the two the guest's own sources name: 0 realtime, 4 monotonic. */
typedef struct {
    int64_t tv_sec;
    int64_t tv_nsec;
} guest_timespec;

_Static_assert(sizeof(guest_timespec) == 16, "guest timespec is 16 bytes");
_Static_assert(offsetof(guest_timespec, tv_nsec) == 8, "guest timespec has nsec at 8");

enum { k_clock_realtime = 0, k_clock_monotonic = 4 };

static int clock_gettime_impl(int64_t clock_id, int64_t ts)
{
    if (ts == 0) return k_err_fault;
    if (!rt_guest_write_ok((uintptr_t)ts, sizeof(guest_timespec), "clock_gettime")) return k_err_fault;
    const uint64_t ns = elapsed_ns();
    guest_timespec v;
    if (clock_id == k_clock_realtime) {
        v.tv_sec = rt_epoch_seconds + (int64_t)(ns / 1000000000ull);
        v.tv_nsec = (int64_t)(ns % 1000000000ull);
    } else if (clock_id == k_clock_monotonic) {
        v.tv_sec = (int64_t)(ns / 1000000000ull);
        v.tv_nsec = (int64_t)(ns % 1000000000ull);
    } else {
        /* A clock id we cannot honour is named, not rounded to monotonic: the caller can see the
           refusal and the log names the id, instead of receiving a plausible time from a clock it
           did not ask for. */
        fprintf(stderr, "pbboot: clock_gettime: refusing unknown clock id %lld (ts=%#llx)\n",
                (long long)clock_id, (unsigned long long)(uint64_t)ts);
        return (int)0x80020016u;
    }
    *(guest_timespec *)(uintptr_t)ts = v;
    return 0;
}

RT_SYSLIB_MODELLED("libkernel", sceKernelClockGettime, clock_gettime_impl);
RT_SYSLIB_MODELLED("libkernel", clock_gettime, clock_gettime_impl);
