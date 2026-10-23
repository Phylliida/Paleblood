/* libc group. Only imports the runtime answers itself belong here; everything else stays
   unresolved and reports loudly by NID.

   `_init_env` (NID bzQExy189ZI) is the first import eboot calls -- at eboot+0xb9, about 25 bytes
   into the entry function -- and it initialises the C library's environment block. The guest
   supplies its own `environ` through the loader, so there is nothing for the host to do: this is
   a no-op by nature, not a stub returning zero, and the distinction matters because a permissive
   zero would hide an import that actually needed behaviour. */
#include "runtime/guest.h"
#include "runtime/loader.h"
#include "runtime/process.h"
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

/* The Itanium C++ ABI's one-time static initialisation guard: `__cxa_guard_acquire` (libc import 40,
   NID 3GPpjQdAMTw), `release` and `abort`. The guard is an 8-byte word in guest memory whose low byte
   means "initialised". acquire answers 1 when the initialiser must run and 0 when it already has;
   release sets that byte; abort leaves it clear because the initialiser did not finish. All three are
   registered, and release is the load-bearing one: acquire alone runs every initialiser on every call,
   and an acquire that always answered 0 runs none of them -- both continue the boot and neither is
   visible in a log that only shows the boot proceeding.

   This is the first body in the chain that reads guest memory. The space is not assumed: guest code
   runs at the image mapping, so a `lea rip`-computed guard arrives in image space while a value from a
   computed field may arrive in guest space. Both are normalised to the guest address for the segment
   test, the raw value is printed, and anything outside a writable load segment stops the boot by name
   rather than being written. A guard read through a host address would be zero for ever: acquire would
   answer 1 every time and the initialiser would run every time, which looks exactly like a correct
   first run. */
static volatile unsigned char *guard_byte(uint64_t *guard, const char *symbol)
{
    const uint64_t raw = (uint64_t)(uintptr_t)guard;
    const uint64_t image = rt_map_image();
    uint64_t g;
    const char *space;
    if (image && raw >= image) {                 /* image space: what the CPU actually addresses */
        g = RT_EBOOT_BASE + (raw - image);
        space = "image";
    } else {                                     /* guest space: what a PS4 pointer holds */
        g = raw;
        space = "guest";
    }
    fprintf(stderr, "%s: guard 0x%llx (%s space)", symbol, (unsigned long long)raw, space);
    if (!image || !rt_guest_writable(g, 8)) {
        fprintf(stderr, "\n");
        rt_fatal(symbol, "the guard word is not inside a writable load segment");
    }
    return (volatile unsigned char *)(uintptr_t)(image + (g - RT_EBOOT_BASE));
}

static int cxa_guard_acquire(uint64_t *guard)
{
    volatile unsigned char *byte = guard_byte(guard, "__cxa_guard_acquire");
    const int run = *byte == 0;
    fprintf(stderr, ", byte %d -- %s\n", *byte, run ? "initialiser must run" : "already initialised");
    return run;
}

static void cxa_guard_release(uint64_t *guard)
{
    volatile unsigned char *byte = guard_byte(guard, "__cxa_guard_release");
    fprintf(stderr, ", byte %d -- setting it\n", *byte);
    *byte = 1;
}

static void cxa_guard_abort(uint64_t *guard)
{
    volatile unsigned char *byte = guard_byte(guard, "__cxa_guard_abort");
    fprintf(stderr, ", byte %d -- leaving it clear\n", *byte);
    *byte = 0;
}

RT_SYSLIB("libc", __cxa_guard_acquire, cxa_guard_acquire);
RT_SYSLIB("libc", __cxa_guard_release, cxa_guard_release);
RT_SYSLIB("libc", __cxa_guard_abort, cxa_guard_abort);
