/* SPDX-License-Identifier: GPL-2.0-or-later */
/* App content: succeed where the real machine succeeds, be empty where the real machine is empty.

   sceAppContentInitialize is how this title reaches its own application, and on a real PS4 it succeeds --
   the content exists. Returning "not found" would be a fabricated failure, and a fabricated failure is
   not more honest than a fabricated success: both are models, and the right one is the one the real
   system produces. So it succeeds, prints its arguments, and says so in the log.

   Where reality IS empty, the answer is truthful: a base-game disc has no add-on content, so the
   add-on queries report zero rather than inventing entries. That exercises the guest's real path instead
   of its panic path. */
#include "runtime/guest_mem.h"
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

/* Modelled: the real machine succeeds for this title. Recorded here so the success is never mistaken for
   a measurement about content existing in this tree. */
static int app_content_initialize(int64_t args)
{
    fprintf(stderr, "pbboot: appcontent: Initialize(args=%p) -> success (modelled: the title's own "
                    "content exists on a real machine, and this runtime has none to check)\n",
            (void *)(uintptr_t)args);
    return 0;
}

/* Truthful emptiness: no add-ons. `count` is an out-parameter, so it goes through the write check. */
static int app_content_num_addcont(int64_t count)
{
    if (count == 0) return (int)0x80020016u;
    if (!rt_guest_write_ok((uintptr_t)count, 4, "AppContentNumAddcont")) return (int)0x8002000eu;
    *(uint32_t *)(uintptr_t)count = 0;
    fprintf(stderr, "pbboot: appcontent: NumAddcont -> 0 (truthful: a base-game disc has no add-ons)\n");
    return 0;
}

static int app_content_addcont_list(int64_t list, int64_t list_num, int64_t count)
{
    (void)list; (void)list_num;
    if (count == 0) return (int)0x80020016u;
    if (!rt_guest_write_ok((uintptr_t)count, 4, "AppContentAddcontList")) return (int)0x8002000eu;
    *(uint32_t *)(uintptr_t)count = 0;
    return 0;
}

RT_SYSLIB("libSceAppContent", sceAppContentInitialize, app_content_initialize);
RT_SYSLIB("libSceAppContent", sceAppContentGetNumAddcont, app_content_num_addcont);
RT_SYSLIB("libSceAppContent", sceAppContentGetAddcontInfoList, app_content_addcont_list);
