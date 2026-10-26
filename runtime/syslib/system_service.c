/* SPDX-License-Identifier: GPL-2.0-or-later */
/* System service parameter queries. The first one the guest asks is LANG (id 1), and the guest uses
   the written value to index its own language table: returning a value without writing the output
   would leave its local at 0xffffffff and silently select the fallback branch. This is a model with a
   named default, not a guessed implementation: the value is printed, and BB_SYSTEM_LANG overrides it
   in the documented 0..0x14 range. Any other parameter refuses by name and is left for its own slice. */
#include "runtime/syslib.h"

#include <stdio.h>
#include <stdlib.h>

enum { k_err_inval = (int)0x80020016u };

static int system_service_param_get_int(int id, int *value)
{
    if (!value)
        return k_err_inval;
    if (id != 1) {
        static unsigned reported[32];
        if (id >= 0 && id < 32 && !reported[id]++)
            fprintf(stderr, "pbboot: libSceSystemService sceSystemServiceParamGetInt: param %d is not "
                            "modelled; refusing with 0x%08x\n", id, (unsigned)k_err_inval);
        return k_err_inval;
    }

    /* The guest passed a pointer into its own stack, which is the host stack. The image-range guard
       (rt_guest_write_ok) is the wrong check for that address space and would refuse a pointer the
       guest can already write itself; the accessors that write guest-image memory use it. */
    const char *env = getenv("BB_SYSTEM_LANG");
    int lang = 1; /* English (United States), the documented value of SCE_SYSTEM_SERVICE_PARAM_LANG */
    if (env && *env) {
        char *end = NULL;
        long v = strtol(env, &end, 10);
        if (!end || *end || v < 0 || v > 0x14) {
            fprintf(stderr, "pbboot: BB_SYSTEM_LANG=%s is not an integer in 0..0x14; refusing the query\n", env);
            return k_err_inval;
        }
        lang = (int)v;
    }
    *value = lang;
    static unsigned reported;
    if (!reported++)
        fprintf(stderr, "pbboot: libSceSystemService sceSystemServiceParamGetInt: MODELLED param 1 (LANG) = %d "
                        "%s, written to %p\n", lang, env && *env ? "from BB_SYSTEM_LANG" : "(English, default)", (void *)value);
    return 0;
}

RT_SYSLIB_MODELLED("libSceSystemService", sceSystemServiceParamGetInt, system_service_param_get_int);
