/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libkernel scePthreadGetprio (NID 1tKyG7RlMJo, bind 78).

   The boot asked for the priority of thread id 7 after the modelled create returned a tagged handle;
   the out pointer is on the guest stack, which is a registered mapping. This runtime has no scheduler,
   so there is no priority to report: the model writes the neutral value 0, prints the thread id and the
   pointer it wrote, and returns 0. It does not claim the thread exists; it says the only priority this
   runtime can truthfully report is the neutral one. */
#include "runtime/guest_mem.h"
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

static unsigned reported;

static int thread_getprio_modelled(int64_t thread, int *prio)
{
    if (!rt_guest_write_ok((uintptr_t)prio, sizeof *prio, "scePthreadGetprio"))
        return -1;
    *(int *)prio = 0;
    if (!reported++)
        fprintf(stderr, "pbboot: libkernel scePthreadGetprio: MODELLED priority 0 for thread 0x%llx; "
                        "wrote 4 bytes at %p (guest stack); no scheduler state exists\n",
                (unsigned long long)thread, (const void *)prio);
    return 0;
}

RT_SYSLIB_MODELLED("libkernel", scePthreadGetprio, thread_getprio_modelled);

/* scePthreadSetprio (NID W0Hpm2X0uPE, bind 77): same absence of scheduler state, so the set is accepted
   and printed rather than silently dropped. A caller that reads the priority back gets the neutral 0 the
   getter reports, which is the one pair of statements this runtime can keep. */
static unsigned setprio_reported;

static int thread_setprio_modelled(int64_t thread, int prio)
{
    if (!setprio_reported++)
        fprintf(stderr, "pbboot: libkernel scePthreadSetprio: MODELLED accept priority %d for thread "
                        "0x%llx; no scheduler state exists, the getter reports 0\n", prio,
                (unsigned long long)thread);
    return 0;
}

RT_SYSLIB_MODELLED("libkernel", scePthreadSetprio, thread_setprio_modelled);
