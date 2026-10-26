/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libkernel scePthreadExit: end the calling host thread, after leaving guest %fs.

   The boot reached scePthreadExit at eboot+0x207f9a0 (catalogue 0x247f9a0) from a real worker whose
   handle the runtime created. The body must do two things in this order: leave the guest TLS block (the
   host's %fs must be restored before any host libc call, including pthread_exit), then end the thread.
   rt_tls_thread_end() is the existing pair to rt_tls_thread_begin() in thread_trampoline; it frees the
   per-thread block and restores the host base. pthread_exit then unwinds on host %fs, never guest %fs.
   The retval is not dereferenced or interpreted: it is handed to the host thread as the join value. */
#include "runtime/syslib.h"
#include "runtime/tls.h"

#include <pthread.h>
#include <stdint.h>

static void pthread_exit_impl(void *retval)
{
    rt_tls_thread_end();
    pthread_exit(retval);
}

RT_SYSLIB("libkernel", scePthreadExit, pthread_exit_impl);
