/* libc group. Only imports the runtime answers itself belong here; everything else stays
   unresolved and reports loudly by NID.

   `_init_env` (NID bzQExy189ZI) is the first import eboot calls -- at eboot+0xb9, about 25 bytes
   into the entry function -- and it initialises the C library's environment block. The guest
   supplies its own `environ` through the loader, so there is nothing for the host to do: this is
   a no-op by nature, not a stub returning zero, and the distinction matters because a permissive
   zero would hide an import that actually needed behaviour. */
#include "runtime/syslib.h"

#include <stdio.h>

static void libc_init_env(void) {}

RT_SYSLIB("libc", _init_env, libc_init_env);

/* `atexit` (NID 8G2LB+A3rzg, libc import 33) registers a function to run at normal process
   termination and returns 0 on success (ISO C atexit). The runtime never terminates the process
   through the C library's exit path -- the guest leaves through its own exit import -- so a handler
   registered here is never invoked. Declared MODELLED for exactly that reason: a REAL entry would
   have to run the handler at exit. The guest is told the registration succeeded, which is what a
   real system would tell it, and it proceeds. Import 33 is where the boot stopped before this
   existed, two calls into the entry function. */
static int libc_atexit(void (*fn)(void))
{
    (void)fn;
    fprintf(stderr, "libc atexit: handler registered, will not run -- the runtime does not exit "
                    "through libc (modelled)\n");
    return 0;
}

RT_SYSLIB_MODELLED("libc", atexit, libc_atexit);
