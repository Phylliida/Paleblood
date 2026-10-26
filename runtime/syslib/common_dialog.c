/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Common dialog service. Same shape as user-service initialization: the call is accepted as a modelled
   no-op because this runtime has no dialog backend, and it creates no state. Any call that would need a
   dialog to exist is left to refuse by name; initialization is not a grant. */
#include "runtime/syslib.h"

#include <stdio.h>

static int common_dialog_initialize(void)
{
    static unsigned reported;
    if (!reported++)
        fprintf(stderr, "pbboot: libSceCommonDialog sceCommonDialogInitialize: MODELLED success, "
                        "no dialog backend or state exists; dialog calls refuse by name\n");
    return 0;
}

RT_SYSLIB_MODELLED("libSceCommonDialog", sceCommonDialogInitialize, common_dialog_initialize);
