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
#include "runtime/tls.h"

#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <unistd.h>

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
/* Turns a pointer the guest handed us into a host pointer this runtime may write, or stops the boot
   by name. One implementation, because the guard triple and memset must agree about what "a guest
   pointer" is: the space is measured (image space when the value lands inside the mapping, guest space
   when it is below it), and the test is a RANGE on both sides -- image <= v < image + extent -- since a
   threshold accepts infinity and a value past the end of the mapping is not in the mapping. */
static unsigned char *guest_write_ptr(uint64_t raw, size_t length, const char *symbol)
{
    const uint64_t image = rt_map_image();
    const uint64_t extent = rt_map_extent();
    uint64_t g;
    const char *space;
    if (image && raw >= image) {
        if (extent && raw - image >= extent) {
            fprintf(stderr, "%s: 0x%llx is past the mapping (image 0x%llx + 0x%llx)\n", symbol,
                    (unsigned long long)raw, (unsigned long long)image, (unsigned long long)extent);
            rt_fatal(symbol, "the pointer is above the mapping");
        }
        g = RT_EBOOT_BASE + (raw - image);       /* image space: what the CPU actually addresses */
        space = "image";
    } else {
        g = raw;                                 /* guest space: what a PS4 pointer holds */
        space = "guest";
    }
    fprintf(stderr, "%s: 0x%llx (%s space)", symbol, (unsigned long long)raw, space);
    if (!image || !rt_guest_writable(g, length)) {
        fprintf(stderr, "\n");
        rt_fatal(symbol, "the range is not inside a writable load segment");
    }
    return (unsigned char *)(uintptr_t)(image + (g - RT_EBOOT_BASE));
}

static volatile unsigned char *guard_byte(uint64_t *guard, const char *symbol)
{
    return (volatile unsigned char *)guest_write_ptr((uint64_t)(uintptr_t)guard, 8, symbol);
}

static int cxa_guard_acquire(uint64_t *guard)
{
    /* WHOSE %fs IS THIS? The crossing stub is handed the right bases and switches before the call, so a body
       that opens on the GUEST TCB means the body was not entered through that stub -- and a body that opens on
       host and closes on guest means something inside switched back. One read at each end answers which. */
    extern volatile int32_t rt_syslib_in_flight;
    if (getenv("BB_GUARD_TRACE")) {
        unsigned long long fs = 0, fs2 = 0;
        syscall(158, 0x1003UL, &fs);
        fprintf(stderr, "guard acquire: entry fs %#llx (guest %#llx host %#llx) in_flight %d\n",
                fs, (unsigned long long)rt_tls_guest_base(), (unsigned long long)rt_tls_host_base(),
                (int32_t)rt_syslib_in_flight);
        syscall(158, 0x1003UL, &fs2);
        fprintf(stderr, "guard acquire: fs stable across the print %s\n", fs == fs2 ? "yes" : "NO");
    }
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

/* `memset` (libSceLibcInternal 11 / libc bind 61, NID 8zTFvBIAIN8 -- one NID in two module tables).
   It returns its destination, so the body returns `dst`: a void body breaks every caller that chains
   memset into an expression, and the value is free here. The range is proved writable BEFORE the first
   byte -- a gate that fires after a partial write has already written -- and the whole range must sit
   in one writable segment, so a store that would cross out of .data is refused rather than half done. */
static void *libc_memset(void *dst, int c, size_t n)
{
    unsigned char *p = guest_write_ptr((uint64_t)(uintptr_t)dst, n, "memset");
    fprintf(stderr, ", %zu bytes of 0x%02x -- writing\n", n, (unsigned)(c & 0xff));
    for (size_t i = 0; i < n; i++) p[i] = (unsigned char)c;
    return dst;
}

RT_SYSLIB("libc", memset, libc_memset);

/* The guard triple's fixture, run by the boot on request (--selftest-guard) against a real guard word
   inside the mapped image. It asserts the BYTE, not the return values: acquire->1, release, acquire->0
   is equally satisfied by a body that remembers which guards it has seen on the host and never writes
   the word -- that body passes a return-value fixture and fails the moment a guest reads its own guard
   byte or a second module shares the guard. The byte is the fact; the return codes are bookkeeping. */
int rt_libc_guard_selftest(void *guard)
{
    uint64_t *g = (uint64_t *)guard;
    unsigned char *byte = guest_write_ptr((uint64_t)(uintptr_t)g, 8, "guard selftest");
    *byte = 0;
    const int first = cxa_guard_acquire(g);
    const int after_acquire = *byte;
    cxa_guard_release(g);
    const int after_release = *byte;
    const int second = cxa_guard_acquire(g);
    const int after_second = *byte;
    const int ok = first == 1 && after_acquire == 0 && after_release == 1 && second == 0 && after_second == 1;
    fprintf(stderr,
            "\nguard selftest: acquire=%d byte-after-acquire=%d release->byte=%d second-acquire=%d byte=%d -- %s\n",
            first, after_acquire, after_release, second, after_second, ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
