/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libkernel __error: the per-thread errno cell.

   The boot reached __error at eboot+0x20745aa (catalogue 0x24745aa). FreeBSD's __error() returns a
   pointer to the calling thread's errno; the guest dereferences it directly, so the body must hand back
   writable storage that is DIFFERENT for each host thread. A single global would let two guest threads
   overwrite one cell, which is the "a global is one slot" defect this runtime has already paid for once.
   __thread gives one cell per host thread, which is exactly the guest's contract; the pointer is a host
   address and the guest's own loads/stores do not pass through the runtime's guest-range checks, so it
   must stay mapped for the life of the thread (it does: static TLS). */
#include "runtime/syslib.h"

#include <stdint.h>

static __thread int guest_errno;

static int64_t libkernel_error(void)
{
    return (int64_t)(uintptr_t)&guest_errno;
}

RT_SYSLIB("libkernel", __error, libkernel_error);
