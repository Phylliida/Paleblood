/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libSceAjm, refused as a library because no AJM state exists.

   The boot reached sceAjmInitialize at eboot+0xd18a6a (catalogue 0x1118a6a). There is no audio job
   manager, no instance table and no codec state in this runtime, so every return that claims success
   would be a handle the guest passes to the next import. A negative return is the guest's own failure
   arm; each name prints once, so the log says which calls the guest made instead of one blanket line.
   Signatures take no arguments: under the SysV ABI the caller's registers are ignored and an int64_t
   return is the failure value for every integer- and pointer-returning call in this list. */
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

#define AJM_REFUSED(sym)                                                                                 \
    static unsigned sym##_reported;                                                                      \
    static int64_t sym##_refused(void)                                                                   \
    {                                                                                                    \
        if (!sym##_reported++)                                                                           \
            fprintf(stderr, "pbboot: libSceAjm " #sym ": MODELLED failure (-1), no AJM state\n");        \
        return -1;                                                                                       \
    }                                                                                                    \
    RT_SYSLIB_MODELLED("libSceAjm", sym, sym##_refused)

AJM_REFUSED(sceAjmInitialize);
AJM_REFUSED(sceAjmFinalize);
AJM_REFUSED(sceAjmModuleRegister);
AJM_REFUSED(sceAjmModuleUnregister);
AJM_REFUSED(sceAjmInstanceCreate);
AJM_REFUSED(sceAjmInstanceDestroy);
AJM_REFUSED(sceAjmBatchWait);
AJM_REFUSED(sceAjmBatchCancel);
AJM_REFUSED(sceAjmBatchJobControlBufferRa);
AJM_REFUSED(sceAjmBatchJobRunBufferRa);
