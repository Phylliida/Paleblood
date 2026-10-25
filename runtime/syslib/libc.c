/* libc group. Only imports the runtime answers itself belong here; everything else stays
   unresolved and reports loudly by NID.

   `_init_env` (NID bzQExy189ZI) is the first import eboot calls -- at eboot+0xb9, about 25 bytes
   into the entry function -- and it initialises the C library's environment block. The guest
   supplies its own `environ` through the loader, so there is nothing for the host to do: this is
   a no-op by nature, not a stub returning zero, and the distinction matters because a permissive
   zero would hide an import that actually needed behaviour. */
#include "runtime/inflight.h"
#include "runtime/guest.h"
#include "runtime/loader.h"
#include "runtime/process.h"
#include "runtime/syslib.h"
#include <limits.h>
#include <sys/mman.h>
#include <unistd.h>
#include "runtime/tls.h"

#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <unistd.h>

static void libc_init_env(void) {}

RT_SYSLIB("libc", _init_env, libc_init_env);

/* `atexit` (NID 8G2LB+A3rzg, libc import 33) and `__cxa_atexit` (NID tsvEmnenz48, libc import 41)
   both REGISTER a handler to run at normal termination. They share one table, because two tables
   would be two answers to "what is registered". The runtime leaves through the guest's own exit
   import and does not re-enter guest code afterwards, so the handlers do not run -- and that gap is
   printed as a COUNT at exit, not left as a sentence: a registration that is accepted and silently
   forgotten is the "success while doing nothing" class. What is honest here is the record and the
   refusal: the table is real, a full table returns -1 by name, and the exit report says how many
   were registered and that none ran. */
/* 64 was a policy nobody measured, and the guest wanted more: the 64-cap boot refused an unknown number of
   registrations. Raised to 512 so the guest's DEMAND is measured rather than truncated, and every refusal is
   counted instead of merely printed -- a refusal that is not in the exit total is a refusal nobody can audit. */
#define ATEXIT_CAPACITY 512u
static struct {
    void (*fn)(void *);
    void *arg;
    void *dso;
} atexit_handlers[ATEXIT_CAPACITY];
static unsigned atexit_registered;
static unsigned atexit_refused;

unsigned rt_libc_atexit_registered(void) { return atexit_registered; }
unsigned rt_libc_atexit_refused(void) { return atexit_refused; }
unsigned rt_libc_atexit_capacity(void) { return ATEXIT_CAPACITY; }

static int atexit_record(void (*fn)(void *), void *arg, void *dso)
{
    if (!fn) return -1;
    if (atexit_registered >= ATEXIT_CAPACITY) {
        atexit_refused++;
        fprintf(stderr, "libc atexit: table full (%u registered, %u refused), registration refused by name\n",
                atexit_registered, atexit_refused);
        return -1;
    }
    atexit_handlers[atexit_registered].fn = fn;
    atexit_handlers[atexit_registered].arg = arg;
    atexit_handlers[atexit_registered].dso = dso;
    atexit_registered++;
    return 0;
}

static int libc_atexit(void (*fn)(void))
{
    /* ISO C atexit: no argument, no dso. Same table, so the exit count is one number. */
    int rc = atexit_record((void (*)(void *))(uintptr_t)fn, NULL, NULL);
    /* Only on success: the refusal line above already names the refusal, and printing "registered" beside a
       refused registration is a refusal that reads as a completion. */
    if (rc == 0 && getenv("BB_ATEXIT_TRACE"))
        fprintf(stderr, "libc atexit: handler registered (%u total), not run -- the runtime does not "
                        "re-enter guest code after exit (modelled)\n", atexit_registered);
    return rc;
}

static int libc_cxa_atexit(void (*fn)(void *), void *arg, void *dso)
{
    int rc = atexit_record(fn, arg, dso);
    if (rc == 0 && getenv("BB_ATEXIT_TRACE"))
        fprintf(stderr, "libc __cxa_atexit: handler registered (%u total, dso %p), not run -- the runtime "
                        "does not re-enter guest code after exit (modelled)\n", atexit_registered, dso);
    return rc;
}

RT_SYSLIB_MODELLED("libc", atexit, libc_atexit);
RT_SYSLIB_MODELLED("libc", __cxa_atexit, libc_cxa_atexit);

/* `std::ios_base::Init::Init` (NID sqWytnhYdEg, libc import 259) and `std::_Winit::_Winit` (import 260).

   Measured before writing this: of this target's 34 mangled libc imports, SIX are the standard stream
   OBJECTS -- cin, cerr, wcerr, wcin, cout, wcout (libc ordinals 26-31) -- and NOT ONE stream operation
   is imported: no operator<<, no __ostream_insert, no basic_ios method. So this constructor's entire
   observable effect is the existence of those six objects. It does not touch the object it is handed
   (an ios_base::Init has no state under the Itanium ABI); it raises a process-wide counter and makes
   the streams exist.

   The streams are data imports with no provider, and boot.c binds each unbound data import to its own
   page of private zeroed `data` (4096 B per import), so a guest that READS one gets zeroes and a guest
   that CALLS through one faults at 0 with the call site naming itself. This entry therefore does no
   work, and says so with a reason rather than returning a permissive zero. The reason is falsifiable:
   build with BB_DATA_GUARD=1 and those pages are PROT_NONE, so any dereference faults at the object's
   own address -- which is the witness that decides whether "noop by unobservability" is true for this
   guest. Working the constructor's declared effect means constructing the six objects, and that ABI
   (basic_ostream/basic_ios layout and vtables) is not in this tree. */
static unsigned ios_init_calls;
static void libc_ios_init(void *self)
{
    ios_init_calls++;
    if (ios_init_calls == 1)
        fprintf(stderr, "libc ios_base::Init: called at %p -- a GAP, not a model: the six standard stream "
                        "objects (cin/cout/cerr/... ) are unbound data imports, so no stream operand exists. "
                        "If the guest uses one, BB_DATA_GUARD (default on) faults at that import's own "
                        "guarded page and NAMES it; with the guard off it would fault at -0x18 through a null "
                        "vptr, which is NOT attributable to the import. Options priced in "
                        "docs/decisions-owed.md; do not promote this to MODELLED without the object graph.\n",
                self);
}
/* Two registrations, one gap. The guest's use is STATIC and proven: eboot reads the GOT slot for `cin`
   (0x53e45f8) at eboot+0x1fa5437, loads [cin], then [vptr-0x18], then calls a virtual through the embedded
   streambuf at cin+0x50; all six slots are referenced at 0x20e2681..0x20e26be. Those addresses are
   module-local to data/bb/elf/libc.elf and must not be transplanted to the retrobios sprx -- different
   build. A shared dummy buffer would alias unrelated objects and a zero page would fault at -0x18; the
   guarded page is the only option that makes the first use attributable, so it stays the default. */
RT_SYSLIB_NOOP("libc", _ZNSt8ios_base4InitC1Ev, libc_ios_init);
RT_SYSLIB_NOOP("libc", _ZNSt6_WinitC1Ev, libc_ios_init);

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
/* The space decision, extracted so a READER and a WRITER cannot disagree about what "a guest pointer"
   is: strlen normalises exactly as memset and the guard triple do, and there is one implementation. */
static uint64_t guest_address_of(uint64_t raw, const char *symbol)
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
    /* Behind a trace flag, not unconditional: a library body must print nothing, and this printed on
     * every call -- 34 lines per boot from memcmp alone, in a log whose parser has no reason to expect
     * them. The evidence it used to give ("all (image space)") is one env var away. */
    if (getenv("RT_TRACE_ADDR"))
        fprintf(stderr, "%s: 0x%llx (%s space)\n", symbol, (unsigned long long)raw, space);
    return g;
}

static unsigned char *guest_write_ptr(uint64_t raw, size_t length, const char *symbol)
{
    const uint64_t image = rt_map_image();
    const uint64_t g = guest_address_of(raw, symbol);
    if (!image || !rt_guest_writable(g, length))
        rt_fatal(symbol, "the range is not inside a writable load segment");
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
    fprintf(stderr, "__cxa_guard_acquire: byte %d -- %s\n", *byte,
            run ? "initialiser must run" : "already initialised");
    return run;
}

static void cxa_guard_release(uint64_t *guard)
{
    volatile unsigned char *byte = guard_byte(guard, "__cxa_guard_release");
    fprintf(stderr, "__cxa_guard_release: byte %d -- setting it\n", *byte);
    *byte = 1;
}

static void cxa_guard_abort(uint64_t *guard)
{
    volatile unsigned char *byte = guard_byte(guard, "__cxa_guard_abort");
    fprintf(stderr, "__cxa_guard_abort: byte %d -- leaving it clear\n", *byte);
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
static __attribute__((unused)) void *libc_memset_unused(void *dst, int c, size_t n)
{
    unsigned char *p = guest_write_ptr((uint64_t)(uintptr_t)dst, n, "memset");
    fprintf(stderr, ", %zu bytes of 0x%02x -- writing\n", n, (unsigned)(c & 0xff));
    for (size_t i = 0; i < n; i++) p[i] = (unsigned char)c;
    return dst;
}

/* NOT registered under `libc`: kernel.c's plain body holds that key because this one refuses a pointer it
   cannot resolve to the image ("the pointer is above the mapping") and the guest's first memset is exactly
   such a pointer. Kept as a function, compiled and unused, because its range-proof is the design the guest
   model eventually wants -- see card 055. Two TUs each defined a static `libc_memset`; the duplicate was a
   NAME collision, never one implementation registered twice. */

/* `strlen` (libc bind 53, NID j4ViWNHEgww -- the wall the boot named after the byte at offset 53 of
   slot 40 was fixed). Two ways to get this wrong, both silent: scan until something faults and report
   the fault as a length, or trust a NUL that is outside the mapping. So the readable SPAN comes from
   the segment table first, the scan is bounded by it, and a string with no NUL inside it stops the
   boot by name instead of returning a number the caller will believe. The return is a size_t from the
   same conversion memset's destination uses. */
static unsigned wcslen_reported;
static size_t libc_wcslen(const unsigned short *s);

static size_t libc_strlen(const char *s)
{
    const uint64_t image = rt_map_image();
    const uint64_t g = guest_address_of((uint64_t)(uintptr_t)s, "strlen");
    const size_t span = image ? rt_guest_readable_span(g) : 0;
    if (!span) rt_fatal("strlen", "the pointer is not inside a readable load segment");
    const unsigned char *p = (const unsigned char *)(uintptr_t)(image + (g - RT_EBOOT_BASE));
    const unsigned char *nul = memchr(p, 0, span);
    if (!nul) {
        fprintf(stderr, "strlen: 0x%llx: no NUL in %zu readable bytes\n", (unsigned long long)g, span);
        rt_fatal("strlen", "the string runs off the end of its mapping -- refusing to report a length");
    }
    fprintf(stderr, "strlen: %zu bytes\n", (size_t)(nul - p));
    return (size_t)(nul - p);
}

RT_SYSLIB("libc", strlen, libc_strlen);
/* wcslen. Nothing in this tree states this target's `wchar_t` width, so the first version ASSUMED 4 bytes
   and printed its evidence -- and the evidence refuted the assumption inside one run: the first code unit
   read 0x00650074, which is the bytes 74 00 65 00, i.e. UTF-16LE "te", not 4-byte "t" (0x00000074).
   So wchar_t is 2 bytes here. The first version returned 34,747 -- not half of anything, but a walk that
   ran ~139 KB past a 28-unit string and terminated by luck in adjacent mapped memory (UTF-16's single NUL
   is only half of a 4-byte unit). Silently: the number was plausible, the guest used it, and nothing faulted. The assumption is now
   measured; the print stays, because it is the check that caught it. */
#define RT_WCSLEN_MAX (1u << 20)

static size_t libc_wcslen(const unsigned short *s)
{
    size_t n = 0;
    while (n < RT_WCSLEN_MAX && s[n]) n++;
    if (n == RT_WCSLEN_MAX) {
        fprintf(stderr, "pbboot: libc wcslen: no NUL within %u code units\n", RT_WCSLEN_MAX);
        rt_fatal("libc", "wcslen: the bounded walk found no terminator; a length from a walk that did not "
                         "terminate would be a number nobody measured");
    }
    if (!wcslen_reported++)
        fprintf(stderr, "pbboot: libc wcslen: %zu code units, first unit 0x%04x (width 2 MEASURED: this "
                        "line read 0x00650074 when the walk assumed 4)\n", n, n ? s[0] : 0u);
    return n;
}

RT_SYSLIB("libc", wcslen, libc_wcslen);
/* wmemcpy, the wall wcslen left behind (libc 239, NID fL3O02ypZFE). n counts UNITS, not bytes, and the unit
   is the same 2 bytes wcslen measured -- so the whole body is a byte copy with the multiply made explicit
   and the overflow refused rather than wrapped. First call prints n once: if the guest ever passes a byte
   count where a unit count is expected, that print is where it shows. */
static size_t wmemcpy_reported;

static void *libc_wmemcpy(void *d, const void *s, size_t n)
{
    if (n > SIZE_MAX / 2)
        rt_fatal("libc", "wmemcpy: unit count overflows a byte count; refusing to copy a wrapped size");
    if (!wmemcpy_reported++)
        fprintf(stderr, "pbboot: libc wmemcpy: n=%zu units (%zu bytes at width 2)\n", n, n * 2);
    return memcpy(d, s, n * 2);
}

RT_SYSLIB("libc", wmemcpy, libc_wmemcpy);
/* wmemset, libc ordinal 242 (NID Al8MZJh-4hM) -- the wall wmemset became when the guest got past
   _Getpctype. It inherits the unit wcslen MEASURED (2 bytes), never the host's sizeof(wchar_t): at width 4
   this body would fill half the units the guest asked for, leave the other half untouched, and return a
   pointer that looks right -- the same silent-wrong-number shape as the original wcslen defect, one
   function over. n counts UNITS; the multiply is explicit and an overflow is refused rather than wrapped.
   The first call prints n, the byte count and the fill value, so a guest passing a byte count where a unit
   count is expected shows up in the log rather than in a later fault. */
static unsigned wmemset_reported;

static unsigned short *libc_wmemset(unsigned short *s, unsigned short c, size_t n)
{
    if (n > SIZE_MAX / 2)
        rt_fatal("libc", "wmemset: unit count overflows a byte count; refusing to fill a wrapped size");
    if (!wmemset_reported++)
        fprintf(stderr, "pbboot: libc wmemset: n=%zu units (%zu bytes at width 2), c=0x%04x\n", n, n * 2, c);
    for (size_t i = 0; i < n; i++)
        s[i] = c;
    return s;
}

RT_SYSLIB("libc", wmemset, libc_wmemset);
/* wmemchr, libc ordinal 246 (NID fnUEjBCNRVU) -- fourth in the wide-character family, same 2-byte unit,
   same reason the width is inherited rather than re-derived. Returns a pointer to the first matching unit
   or NULL; the guest's count is units, and a byte count passed where a unit count is expected would show in
   the first-call print as an impossibly large n rather than as a later fault. */
static unsigned wmemchr_reported;

static unsigned short *libc_wmemchr(const unsigned short *s, unsigned short c, size_t n)
{
    if (n > SIZE_MAX / 2)
        rt_fatal("libc", "wmemchr: unit count overflows a byte count; refusing to scan a wrapped size");
    if (!wmemchr_reported++)
        fprintf(stderr, "pbboot: libc wmemchr: n=%zu units (%zu bytes at width 2), c=0x%04x\n", n, n * 2, c);
    for (size_t i = 0; i < n; i++)
        if (s[i] == c) return (unsigned short *)(s + i);
    return NULL;
}

RT_SYSLIB("libc", wmemchr, libc_wmemchr);
/* wcstol, libc 504 (d3dMyWORw8A): the first wide import the guest reaches that is not a wmem* copy or scan.
   Unit: 2 bytes, MEASURED (wcslen), never sizeof(wchar_t); the host's wcstol expects 4 and is not called.

   Measured call site, before this body existed: eboot+0x20ebb0f, `mov $0xa,%edx` / `lea -0x70(%rbp),%rsi` /
   rdi = a stack wchar_t buffer -- base 10, non-NULL endptr, corroborated at runtime (rdx 0xa) and by the
   raw bytes (file offset = vaddr + 0x4000, since this image has no section table for objdump to read).

   Modelled: the ISO C success path, and the defined no-conversion result (0, *endptr = nptr).
   NOT modelled: guest errno. There is no errno model in this runtime, so an overflow REFUSES by name rather
   than returning a clamped value that would never fault and never agree. */
static long libc_wcstol(const unsigned short *s, unsigned short **endptr, int base)
{
    static int announced;
    const unsigned short *p = s;
    const unsigned short *digits;
    int neg = 0, any = 0;
    unsigned long long acc = 0, limit;

    if (!s) rt_fatal("wcstol", "the string pointer is NULL");
    if (base != 0 && (base < 2 || base > 36)) {
        char why[128];
        snprintf(why, sizeof why, "base %d is outside 0 and 2..36; the original sets EINVAL and this runtime "
                                  "has no guest errno to set", base);
        rt_fatal("wcstol", why);
    }
    for (;; p++) {
        const unsigned short c = *p;
        if (c == 0x20 || (c >= 0x09 && c <= 0x0d)) continue;
        break;
    }
    if (*p == 0x2b || *p == 0x2d) { neg = (*p == 0x2d); p++; }
    if ((base == 0 || base == 16) && p[0] == 0x30 && (p[1] == 0x78 || p[1] == 0x58)) {
        base = 16;
        p += 2;
    } else if (base == 0) {
        base = (p[0] == 0x30) ? 8 : 10;
    }
    digits = p;
    limit = neg ? (unsigned long long)LONG_MAX + 1ull : (unsigned long long)LONG_MAX;
    for (;; p++) {
        const unsigned short c = *p;
        int d;
        if (c >= 0x30 && c <= 0x39) d = c - 0x30;
        else if (c >= 0x61 && c <= 0x7a) d = c - 0x61 + 10;
        else if (c >= 0x41 && c <= 0x5a) d = c - 0x41 + 10;
        else break;
        if (d >= base) break;
        if (acc > (limit - (unsigned)d) / (unsigned)base)
            rt_fatal("wcstol", "value overflows long; the original sets ERANGE and this runtime has no guest "
                               "errno, so no clamped value is returned");
        acc = acc * (unsigned)base + (unsigned)d;
        any = 1;
    }
    if (endptr) *endptr = (unsigned short *)(any ? p : s);
    if (!any) {
        if (!announced)
            fprintf(stderr, "pbboot: libc wcstol: no digits converted at %p -- ISO C defines the result "
                            "(0, endptr = nptr), so it is returned; errno is NOT modelled here\n", (const void *)s);
        announced = 1;
        return 0;
    }
    {
        const long v = (neg && acc == (unsigned long long)LONG_MAX + 1ull) ? LONG_MIN
                                                                          : (neg ? -(long)acc : (long)acc);
        if (!announced) {
            fprintf(stderr, "pbboot: libc wcstol: %llu unit(s) parsed, base %d, value %ld (unit 2 bytes, "
                            "measured)\n", (unsigned long long)(p - digits), base, v);
            announced = 1;
        }
        return v;
    }
}
RT_SYSLIB("libc", wcstol, libc_wcstol);

/* _FSin, libc ordinal 38 -- the first wall whose right answer is not fixed by a standard but by an
   IMPLEMENTATION's rounding. Two things are NOT established here and are not pretended to be:
     - that `_FSin` takes and returns a float (the `_F` prefix is a hypothesis, not a citation in this tree);
     - what accuracy the original has. If `_FSin` is a fast-math variant, the host's sinf is MORE accurate,
       which is the one direction a model may differ safely for a value that feeds further arithmetic --
       but the difference is stated, not hidden, and no call is bit-compared against it.
   The instrument is the print: an argument outside float range would refute the width, so the first call
   publishes its input and output and the assumption is falsifiable from the log. */
static unsigned fsin_reported;

static float libc_FSin(float x)
{
    float y = sinf(x);
    if (!fsin_reported++)
        fprintf(stderr, "pbboot: libc _FSin: x=%g -> %g (modelled: host sinf; float width ASSUMED from the "
                        "_F prefix, and a magnitude a float cannot hold would refute that here)\n",
                (double)x, (double)y);
    return y;
}

RT_SYSLIB("libc", _FSin, libc_FSin);
/* wmemcmp, libc ordinal 245 -- same measured unit as wcslen and wmemcpy (2 bytes), so the body is a
   unit-wise compare with the guest's own count. Bounded like the walks: a refusal is better than
   comparing however much memory happens to be mapped. */
static unsigned wmemcmp_reported;

static int libc_wmemcmp(const unsigned short *a, const unsigned short *b, size_t n)
{
    if (n > RT_WCSLEN_MAX)
        rt_fatal("libc", "wmemcmp: unit count beyond any buffer this runtime models; refusing rather than "
                         "walking an unbounded span");
    size_t i = 0;
    while (i < n && a[i] == b[i]) i++;
    int r = i == n ? 0 : (a[i] < b[i] ? -1 : 1);
    if (!wmemcmp_reported++)
        fprintf(stderr, "pbboot: libc wmemcmp: n=%zu units, first difference at %zu%s\n", n, i,
                i == n ? " (equal)" : "");
    return r;
}

RT_SYSLIB("libc", wmemcmp, libc_wmemcmp);
/* wcschr, libc ordinal 243: the first occurrence of a unit, or NULL. The walk is bounded for the same
   reason wcslen's is -- if the terminator is not where a 2-byte walk expects it, the honest answer is a
   refusal, not a pointer into whatever happens to be mapped. */
static unsigned wcschr_reported;

static unsigned short *libc_wcschr(const unsigned short *s, unsigned short c)
{
    size_t n = 0;
    while (n < RT_WCSLEN_MAX && s[n] && s[n] != c) n++;
    if (n == RT_WCSLEN_MAX)
        rt_fatal("libc", "wcschr: no terminator within the bounded walk");
    unsigned short *r = s[n] == c ? (unsigned short *)(s + n) : NULL;
    if (!wcschr_reported++)
        fprintf(stderr, "pbboot: libc wcschr: c=0x%04x %s at unit %zu\n", c, r ? "found" : "absent", n);
    return r;
}

RT_SYSLIB("libc", wcschr, libc_wcschr);
/* wcsncmp, libc ordinal 269 -- the wide-path dispatcher's compare. Same measured 2-byte unit; the walk
   stops at a difference OR at a NUL in both, which is what the standard fixes, and prints once so the
   width stays falsifiable from the log rather than from my confidence in it. */
static unsigned wcsncmp_reported;

static int libc_wcsncmp(const unsigned short *a, const unsigned short *b, size_t n)
{
    if (n > RT_WCSLEN_MAX)
        rt_fatal("libc", "wcsncmp: unit count beyond any buffer this runtime models");
    size_t i = 0;
    while (i < n && a[i] == b[i] && a[i]) i++;
    int r = (i == n || a[i] == b[i]) ? 0 : (a[i] < b[i] ? -1 : 1);
    if (!wcsncmp_reported++)
        fprintf(stderr, "pbboot: libc wcsncmp: n=%zu, stopped at unit %zu, first units 0x%04x/0x%04x -> %d\n",
                n, i, i < n ? a[i] : 0u, i < n ? b[i] : 0u, r);
    return r;
}

RT_SYSLIB("libc", wcsncmp, libc_wcsncmp);
/* _Getpctype, libc 65: the locale's character-classification table. Now MEASURED, not assumed.
   Provenance: data/bb/elf/libc.elf `_Getpctype` at 0xe880 is `48 8d 05 eb 37 07 00 c3`
   (`lea rax,[rip+0x737eb]; ret`), returning the immutable RX-image table at **0x82072**;
   256 x uint16 = 512 bytes, sha256 of those raw bytes
   ~~~~7a679e4cdb13e9f5626792152188f568bc35e895d6151397446bd03a91b94b8e (verified here, not quoted).
   Module-local: do NOT transplant to the retrobios libSceLibcInternal.sprx.

   The encoding was settled from the guest's own call sites (eboot stub 0x2fbe6c8 for this slot, 73 `e8`
   call sites; windows read at 0x457cc8, 0x835e1a, 0xe033a4, 0xe03674, 0xe10804, 0xe10a60, 0xe11087):
     (a) the call takes NO argument -- the pointer is the return value, index supplied after the call;
     (b) the return is used with NO second dereference -- `[rax + idx*2]` directly, so this is a table
         pointer, not a pointer to a table pointer;
     (c) stride is TWO bytes -- `movzx eax, word ptr [rax + rbx*2]`, `movzx ecx, word ptr [rax + rbx*2]`;
     and every test is a 16-bit mask: `test ax,0x144`, `test ax,0x232`, `test ax,0x23e`, `test ax,0x212`,
     `test byte ptr [...], 0x80`, `test byte ptr [...], 1`.
   Bits this table actually sets: 0x0001,0x0002,0x0004,0x0008,0x0010,0x0020,0x0040,0x0080,0x0400.
   The call sites also test 0x0100 and 0x0200, which this table never sets -- consistent (a test that is
   always false is not a contradiction), and it is why the stride had to be measured before any mask was
   named: an immediate read at the wrong width is a correct mask describing the wrong byte.

   The body returns a private writable copy, and refuses if its own literal array does not hash to the
   measured bytes: a source edit that changes one entry must not fail *plausibly*. */
#define PCTYPE_ENTRIES 256u
static const unsigned short pctype_source[PCTYPE_ENTRIES] = {
    0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080,
    0x0080, 0x04c0, 0x00c0, 0x00c0, 0x00c0, 0x00c0, 0x0080, 0x0080,
    0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080,
    0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080, 0x0080,
    0x0004, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008,
    0x0008, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008,
    0x0021, 0x0021, 0x0021, 0x0021, 0x0021, 0x0021, 0x0021, 0x0021,
    0x0021, 0x0021, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008,
    0x0008, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0002,
    0x0002, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002,
    0x0002, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002,
    0x0002, 0x0002, 0x0002, 0x0008, 0x0008, 0x0008, 0x0008, 0x0008,
    0x0008, 0x0011, 0x0011, 0x0011, 0x0011, 0x0011, 0x0011, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0008, 0x0008, 0x0008, 0x0008, 0x0080,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
};
/* The original table lives in the image's RX segment, so a guest WRITE to it faults. A writable copy would
   accept the write silently and answer a question the original never asks — a model that behaves differently
   in exactly the operation the original forbids. The copy is therefore placed on its own page and made
   PROT_READ before any guest can see it; if that protection cannot be applied the body REFUSES rather than
   handing back a writable table, because a fidelity claim that silently does not hold is worse than a stop. */
static unsigned short *pctype_page;
static int pctype_ready;
static unsigned short *libc_Getpctype(void)
{
    if (!pctype_ready) {
        unsigned long long h = 0xcbf29ce484222325ull;
        for (unsigned i = 0; i < PCTYPE_ENTRIES; i++) {
            unsigned lo = pctype_source[i] & 0xffu, hi = (pctype_source[i] >> 8) & 0xffu;
            h = (h ^ lo) * 0x100000001b3ull;
            h = (h ^ hi) * 0x100000001b3ull;
        }
        if (h != 0xd0bafaafcf18b805ull)
            rt_fatal("_Getpctype", "the embedded ctype table does not match the measured bytes "
                              "(FNV-1a mismatch); the table is evidence and a source edit may not alter it");
        long pg = sysconf(_SC_PAGESIZE);
        if (pg <= 0 || (size_t)pg < sizeof pctype_source)
            rt_fatal("_Getpctype", "page size unusable for the table page");
        pctype_page = mmap(NULL, (size_t)pg, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (pctype_page == MAP_FAILED)
            rt_fatal("_Getpctype", "the table page could not be mapped");
        memcpy(pctype_page, pctype_source, sizeof pctype_source);
        if (mprotect(pctype_page, (size_t)pg, PROT_READ) != 0)
            rt_fatal("_Getpctype", "the table page could not be made read-only; refusing to hand back a "
                                   "writable table the original keeps in RX");
        pctype_ready = 1;
        /* The page's address is printed because a fault at it is reported as a HOST address (it is not in
           guest space); without this line that fault cannot be attributed to the model table. Printed once,
           at init, which is also the only moment the mapping is new. */
        fprintf(stderr, "pbboot: libc _Getpctype: 256 entries at width 2, page %p read-only (the original is "
                        "RX; a guest write faults here too; this address is host space, match it here)\n",
                (void *)pctype_page);
    }
    return pctype_page;
}
RT_SYSLIB("libc", _Getpctype, libc_Getpctype);










/* `memcmp` (libc bind 56, NID DfivPArhucg, import_names.csv:138) -- the import the boot named once strlen
   was served. Same rule as strlen twice over: BOTH ranges are proved readable for the full n BEFORE the
   comparison touches either, because a memcmp that reads past a mapping reports an ordering for bytes that
   were never there, and a positive result would be believed. The comparison itself is the host library's,
   on host memory already proved readable -- re-implementing it would be a second definition of ordering. */
static int libc_memcmp(const void *a, const void *b, size_t n)
{
    const uint64_t image = rt_map_image();
    const uint64_t ga = guest_address_of((uint64_t)(uintptr_t)a, "memcmp");
    const uint64_t gb = guest_address_of((uint64_t)(uintptr_t)b, "memcmp");
    const size_t sa = image ? rt_guest_readable_span(ga) : 0;
    const size_t sb = image ? rt_guest_readable_span(gb) : 0;
    if (!sa || n > sa) rt_fatal("memcmp", "the first range is not readable for the requested length");
    if (!sb || n > sb) rt_fatal("memcmp", "the second range is not readable for the requested length");
    const unsigned char *pa = (const unsigned char *)(uintptr_t)(image + (ga - RT_EBOOT_BASE));
    const unsigned char *pb = (const unsigned char *)(uintptr_t)(image + (gb - RT_EBOOT_BASE));
    const int r = memcmp(pa, pb, n);
    fprintf(stderr, "memcmp: %zu bytes -> %d\n", n, r);
    return r;
}

RT_SYSLIB("libc", memcmp, libc_memcmp);

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
