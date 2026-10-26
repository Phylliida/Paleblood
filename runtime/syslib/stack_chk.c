/* SPDX-License-Identifier: GPL-2.0-or-later */
/* __stack_chk_fail: the guest's canary check calls this import when it has already decided that
   its own stack frame is corrupt.  The ABI answer is not "return"; it is "do not continue".  An
   unbound import here returns 0 through the unimplemented trampoline and the guest falls through
   into whatever function happens to follow the call site -- which is how a canary failure was
   first seen as a SIGSEGV at [rdi+0xdc10] with rdi == NULL, one function later.

   This body does not diagnose the canary.  It names the event, writes the guest's return address
   (the caller's PC is on the stack; the trampoline does not change rsp), and exits 134, the same
   code as abort().  A canary mismatch is never recoverable in the guest, so returning is a lie and
   a model of a stack check that cannot fail is worse than no model. */
#include "runtime/syslib.h"

#include <stdint.h>
#include <unistd.h>

static __attribute__((noreturn)) int stack_chk_fail(void)
{
    static const char msg[] =
        "pbboot: libkernel:__stack_chk_fail: the guest detected a corrupt stack canary; "
        "exiting 134 (a canary failure is not recoverable)\n";
    ssize_t n = write(2, msg, sizeof msg - 1);
    (void)n;
    _exit(134);
}

RT_SYSLIB("libkernel", __stack_chk_fail, stack_chk_fail);
