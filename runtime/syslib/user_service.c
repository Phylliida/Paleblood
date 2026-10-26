/* SPDX-License-Identifier: GPL-2.0-or-later */
/* User service. The guest reaches this after the modelled thread and the wide-string work;
   sceUserServiceInitialize is accepted as a modelled no-op because this runtime has no user
   database. The distinction that keeps it honest: the call establishes no state, so every query
   that would need a user id is left to refuse by name when it is reached. Initialization is not
   a grant of users. */
#include "runtime/syslib.h"

#include <stdio.h>

static int user_service_initialize(const void *params)
{
    static unsigned reported;
    if (!reported++)
        fprintf(stderr, "pbboot: libSceUserService sceUserServiceInitialize: MODELLED success, "
                        "no user-service state was created; user queries refuse by name "
                        "(params=%p)\n", params);
    return 0;
}

RT_SYSLIB_MODELLED("libSceUserService", sceUserServiceInitialize, user_service_initialize);
