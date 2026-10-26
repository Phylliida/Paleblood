/* SPDX-License-Identifier: GPL-2.0-or-later */
/* NP (PlayStation Network) manager. Content restriction is a setter: accepting it creates no NP state,
   and every query that would need an NP identity is left to refuse by name. The accepted call is
   printed because a guest that believes a restriction was applied is a different guest from one that
   was told the runtime has no NP service. */
#include "runtime/syslib.h"

#include <stdio.h>

static int np_set_content_restriction(const void *restriction, unsigned reserved, unsigned flags)
{
    (void)reserved;
    (void)flags;
    static unsigned reported;
    if (!reported++)
        fprintf(stderr, "pbboot: libSceNpManager sceNpSetContentRestriction: MODELLED accepted "
                        "(restriction=%p); no NP state or identity exists, queries refuse by name\n", restriction);
    return 0;
}

RT_SYSLIB_MODELLED("libSceNpManager", sceNpSetContentRestriction, np_set_content_restriction);
