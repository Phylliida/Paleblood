/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libkernel's file system, refused as a library because no guest file system exists.

   The boot reached sceKernelStat at eboot+0x207451e (catalogue 0x247451e). This runtime maps no guest
   files, so every success would be a fabricated descriptor or a stat buffer the guest dereferences.
   A negative return is the guest's own failure arm; each name prints once. The path pointer is printed,
   not dereferenced: the caller's memory is not this body's to read, and a bad pointer here must name the
   import rather than fault inside the model. */
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

#define FS_REFUSED(sym)                                                                                  \
    static unsigned sym##_reported;                                                                      \
    static int64_t sym##_refused(void)                                                                   \
    {                                                                                                    \
        if (!sym##_reported++)                                                                           \
            fprintf(stderr, "pbboot: libkernel " #sym ": MODELLED failure (-1), no guest file system\\n");\
        return -1;                                                                                       \
    }                                                                                                    \
    RT_SYSLIB_MODELLED("libkernel", sym, sym##_refused)

FS_REFUSED(sceKernelStat);
FS_REFUSED(sceKernelFstat);
FS_REFUSED(sceKernelOpen);
FS_REFUSED(sceKernelClose);
FS_REFUSED(sceKernelRead);
FS_REFUSED(sceKernelLseek);
FS_REFUSED(sceKernelGetdirentries);
