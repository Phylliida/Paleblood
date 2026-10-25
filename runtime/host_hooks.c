/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime/host_hooks.h"
#include "runtime/host.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/mman.h>

#include "runtime/boundary_stub.h"
#include "runtime/site_guard.h"   /* the bias constant, in a header nothing pins */

/* The entry counter's backing store: one cacheline-honest slot per installed site, plus the site address so a
   count can name which of several sites arrived. Printed from every exit we can reach -- clean (atexit) and the
   designed abort (SIGABRT) -- because a counter printed only on the clean path is silent in exactly the run it
   was built for. `sig_atomic_t` widened to uint64_t: a counter is incremented by emitted code, read by a handler. */
#define RT_SITES_MAX 64
static volatile uint64_t g_site_entered[RT_SITES_MAX];
static uint64_t g_site_address[RT_SITES_MAX];
static unsigned g_site_count;
static unsigned installed_count;   /* reported by the signal-safe line; defined here so the reporter can see it */

/* Write-only, bounded, no stdio: this function is called from a SIGABRT handler, and it used to call
   snprintf. Its final call passed the buffer's FULL size at an advanced pointer, glibc's fortify aborted
   inside the handler, the handler called the reporter again, and the process printed `abort:` until it was
   killed. A claim of async-signal-safety beside `snprintf` was the defect, and the recursion was its proof. */
static char *sites_app(char *p, char *end, const char *s)
{
    while (*s && p < end) *p++ = *s++;
    return p;
}

static char *sites_dec(char *p, char *end, uint64_t v)
{
    char t[24];
    int n = 0;
    do { t[n++] = (char)('0' + (v % 10)); v /= 10; } while (v);
    while (n > 0 && p < end) *p++ = t[--n];
    return p;
}

static char *sites_hex16(char *p, char *end, uint64_t v)
{
    static const char digits[] = "0123456789abcdef";
    for (int i = 15; i >= 0; i--) { if (p < end) *p++ = digits[(v >> (i * 4)) & 0xf]; }
    return p;
}

static void rt_sites_report(void)
{
    uint64_t n = 0, total = 0;
    for (unsigned i = 0; i < g_site_count && i < RT_SITES_MAX; i++) {
        if (g_site_entered[i]) n++;
        total += g_site_entered[i];
    }
    char line[4096];
    char *p = line, *end = line + sizeof line;
    p = sites_app(p, end, "sites entered ");
    p = sites_dec(p, end, n);
    p = sites_app(p, end, " of ");
    p = sites_dec(p, end, g_site_count);
    p = sites_app(p, end, " tracked (");
    p = sites_dec(p, end, total);
    p = sites_app(p, end, " hits), hooks installed ");
    p = sites_dec(p, end, installed_count);
    for (unsigned i = 0; i < g_site_count && i < RT_SITES_MAX; i++) {
        p = sites_app(p, end, " 0x");
        p = sites_hex16(p, end, g_site_address[i]);
        p = sites_app(p, end, "=");
        p = sites_dec(p, end, g_site_entered[i]);
    }
    p = sites_app(p, end, "\n");
    const char *q = line;
    size_t left = (size_t)(p - line);
    while (left) {
        ssize_t w = write(2, q, left);
        if (w <= 0) break;
        q += w;
        left -= (size_t)w;
    }
}

static void rt_sites_on_abort(int sig)
{
    /* Async-signal-safe now BY CONSTRUCTION: write(2) only, no malloc, no stdio, no snprintf. The old comment
       licensed the hazard it named; this one is checkable by reading the body. */
    (void)sig;
    ssize_t wrote = write(2, "abort: ", 7);
    (void)wrote;
    rt_sites_report();
    signal(SIGABRT, SIG_DFL);
    raise(SIGABRT);
}

#if !defined(__x86_64__)
#error "The version-1 host hook callback requires an x86-64 host"
#endif

enum { ABSOLUTE_JUMP_SIZE = 14 };

static unsigned char *guest_image;
static uint64_t guest_image_size;

/* Once the boot has installed a guest block, the guest's %fs is live, and a bare jump would run the
   replacement on the guest's TCB, where glibc's errno and stack protector are not -- the shape that
   cost seven slices in the import trampoline, one level down. So when TLS is live the 14 bytes point
   at a stub that swaps %fs and aligns the stack; the crossing itself is emitted by
   runtime/boundary_stub.c, the same code the import trampolines use, because a second hand-written
   prologue is how the /3-for-/2 bug survived for days. Weak, because the differential harness links
   no TLS, has no guest block, and passes an installer that installs nothing. */
extern uint64_t rt_tls_guest_base(void) __attribute__((weak));
extern uint64_t rt_tls_host_base(void) __attribute__((weak));

static int guest_tls_is_live(void)
{
    return rt_tls_guest_base && rt_tls_host_base && rt_tls_guest_base() != 0;
}

/* One page of executable memory holds every hook's stub. Bounded and reported, never a silent
   overrun: a hook that cannot get a stub must fail loudly, because a jump to nowhere is a green run
   that executes nothing. */
/* The stub page is one resource shared by every wrapper. It is a test-overridable constant because
   RT_SITES_MAX = 64 capture wrappers cannot fit in the shipped 4096-byte page (64 * 86 = 5504), so
   the capture-table-full branch is otherwise unreachable in the shipped configuration; the fixture
   enlarges the page to exercise the real 64 -> 65 boundary rather than lowering the table cap. */
#ifndef RT_STUB_PAGE
#define RT_STUB_PAGE 4096
#endif
enum { STUB_PAGE = RT_STUB_PAGE };
static unsigned char *stub_area;
static size_t stub_used;

static unsigned char *stub_alloc(size_t n)
{
    if (!stub_area) {
        void *p = mmap(NULL, STUB_PAGE, PROT_READ | PROT_WRITE | PROT_EXEC,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p == MAP_FAILED) return NULL;
        stub_area = p;
    }
    if (n > STUB_PAGE - stub_used) return NULL;
    unsigned char *p = stub_area + stub_used;
    stub_used += n;
    return p;
}

/* A hook written into a page the process cannot execute reads back perfectly and never fires: the
   readback proves the bytes, not the mapping. Ask /proc/self/maps about the page the patch lands in,
   and fail closed if the answer cannot be read. This is the "N installed counts writes" defect one
   level up, and it is cheap here for the same reason it is expensive later. */
/* Symmetric with the executable check: same /proc/self/maps walk, looking for 'w'. A read-only page reads back
   perfectly and faults inside memcpy, which is a SIGSEGV attributed to the body if the body is what runs next. */
static int region_is_writable(void *addr, unsigned long n)
{
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 0;
    char line[512];
    unsigned long target = (unsigned long)addr;
    while (fgets(line, sizeof line, maps)) {
        unsigned long lo = 0, hi = 0;
        char perms[8] = {0};
        if (sscanf(line, "%lx-%lx %7s", &lo, &hi, perms) != 3) continue;
        if (target >= lo && target + n <= hi) {
            fclose(maps);
            return perms[1] == 'w';
        }
    }
    fclose(maps);
    return 0;
}

static int region_is_executable(const void *address, size_t length)
{
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 0;
    const uintptr_t start = (uintptr_t)address;
    const uintptr_t end = start + length;
    char line[512];
    int executable = 0;
    while (fgets(line, sizeof line, maps)) {
        unsigned long low = 0, high = 0;
        char perms[5] = {0};
        if (sscanf(line, "%lx-%lx %4s", &low, &high, perms) != 3) continue;
        if ((uintptr_t)low <= start && end <= (uintptr_t)high) {
            executable = (perms[2] == 'x');
            break;
        }
    }
    fclose(maps);
    return executable;
}

/* The capture wrapper saves six GPRs and not xmm0-7, so it must not be installed at a body that uses them.
   The scan lives in tools/capture_precheck.py (one Capstone binding, never two); the FILE is the contract and
   the installer refuses absent -- the shape symbols/install_mode.csv already uses. Each row carries the sha256
   of the bytes scanned, so an edited body stops matching; the C side cannot recompute that hash, and the test
   that regenerates the table is the instrument that does. */
/* One definition of capture mode. It used to be two: capture_allowed treated BB_CAPTURE=0 (or an
   empty value) as off, while `capturing` below treated any non-NULL value as on. A boot with
   BB_CAPTURE=0 therefore skipped the table checks and emitted the capturing wrapper, so "off"
   installed capture instrumentation that no table had authorized. */
static int capture_mode(void)
{
    const char *cap = getenv("BB_CAPTURE");
    return cap && *cap && *cap != '0';
}

static int capture_allowed(uint64_t offset)
{
    if (!capture_mode()) return 1;    /* not a capture install: A's proven wrapper, no table needed */

    const char *path = getenv("BB_CAPTURE_OK");
    if (!path || !*path) path = "symbols/capture_ok.csv";
    FILE *table = fopen(path, "r");
    if (!table) {
        fprintf(stderr, "capture: no table at %s: refusing to install at 0x%llx; nothing is recorded\n",
                path, (unsigned long long)offset);
        return 0;
    }
    /* The run wrapper passes the digest of the library the table was derived from. C cannot hash a body (its
       extent is unknown) and should not hash the .so either -- it compares a string, and the comparison catches
       the whole table going stale after a rebuild, which is the failure mode that actually happens. Mandatory in
       capture mode: a default here would manufacture agreement with a table nobody regenerated. */
    const char *want = getenv("BB_CAPTURE_TABLE_ID");
    if (!want || !*want) {
        fprintf(stderr, "capture: BB_CAPTURE_TABLE_ID is unset: refusing; it is mandatory in capture mode and a "
                        "default would manufacture agreement with a stale table\n");
        fclose(table);
        return 0;
    }
    char line[512];
    int seen = 0;
    while (fgets(line, sizeof line, table)) {
        unsigned long long addr = 0;
        char verdict[64] = {0};
        char body_sha[80] = {0};
        char so_sha[80] = {0};
        if (sscanf(line, "0x%llx,%63[^,],%79[^,],%79[^,\n]", &addr, verdict, body_sha, so_sha) != 4) continue;
        if (strcmp(so_sha, want) != 0) {
            fprintf(stderr, "capture: table was derived from libbbgame.so %s but the run says %s: refusing; "
                            "regenerate with `capture_precheck.py --table`\n", so_sha, want);
            fclose(table);
            return 0;
        }
        if (addr != rt_guest_address(offset)) continue;   // guest-keyed table, offset-keyed caller
        seen = 1;
        if (strcmp(verdict, "none") != 0) {
            fprintf(stderr, "capture: refusing to install at 0x%llx: %s\n", (unsigned long long)offset,
                    verdict);
            fclose(table);
            return 0;
        }
    }
    fclose(table);
    if (!seen) {
        fprintf(stderr, "capture: no row for guest 0x%llx in %s: refusing; nothing is recorded\n",
                (unsigned long long)rt_guest_address(offset), path);
        return 0;
    }
    return 1;
}

/* Four distinct findings, four counters. A total called "refused" merges them, and the two that matter most --
   the site was already patched (two hooks on one site) and the site does not match the catalog (the image is not
   the catalog) -- are opposite diagnoses with the same symptom. They are read as one snapshot by
   plugin_load.c after bbgame_init returns; the startup line below necessarily prints the zero-initialised values
   before any install, and must not be read as the final count. */
static unsigned sites_checked, sites_already_patched, sites_mismatched, sites_unlisted;

unsigned rt_host_hooks_installed_count(void) { return installed_count; }

/* One function, four outputs: the caller cannot print one counter and silently omit its neighbours. */
void rt_host_hooks_sites_snapshot(unsigned *checked, unsigned *already_patched,
                                  unsigned *mismatched, unsigned *unlisted)
{
    if (checked) *checked = sites_checked;
    if (already_patched) *already_patched = sites_already_patched;
    if (mismatched) *mismatched = sites_mismatched;
    if (unlisted) *unlisted = sites_unlisted;
}

static int install_hook(uint64_t offset, uint64_t size, const void *target)
{
    if (!guest_image || !target || size < ABSOLUTE_JUMP_SIZE || offset > guest_image_size ||
        size > guest_image_size - offset)
        return -1;

    if (!capture_allowed(offset)) return -1;

    /* The guard's width is the patch's width: 14 bytes, the same constant the write and the readback use. Ten
       unverified bytes at the tail of the first instruction is exactly what a 16 KiB-shifted patch still passes.
       Fail closed in capture mode; the table is a contract, so absence is a refusal and not a default. */
    {
        if (capture_mode()) {
            const char *path = getenv("BB_SITE_OK");
            if (!path || !*path) path = "symbols/site_ok.csv";
            FILE *tbl = fopen(path, "r");
            char line[256];
            int found = 0, match = 0;
            if (!tbl) {
                fprintf(stderr, "hook: no site table at %s: refusing; capture mode will not patch an unlisted site\n",
                        path);
                sites_unlisted++;
                return -1;
            }
            while (!found && fgets(line, sizeof line, tbl)) {
                unsigned long long addr = 0;
                char hex[64] = {0};
                if (sscanf(line, "0x%llx,%63s", &addr, hex) != 2) continue;
                if (addr != rt_guest_address(offset) || strlen(hex) != 28) continue;
                found = 1;
                match = 1;
                for (int k = 0; k < ABSOLUTE_JUMP_SIZE; k++) {
                    unsigned v = 0;
                    if (sscanf(hex + 2 * k, "%2x", &v) != 1 || guest_image[offset + k] != (unsigned char)v) {
                        match = 0;
                        break;
                    }
                }
            }
            fclose(tbl);
            if (!found) {
                sites_unlisted++;
                fprintf(stderr, "hook: 0x%llx has no site_ok row: refusing rather than patching an unlisted site\n",
                        (unsigned long long)rt_guest_address(offset));
                return -1;
            }
            if (!match) {
                sites_mismatched++;
                fprintf(stderr, "hook: 0x%llx does not match its site_ok prologue over %d bytes: the image is not "
                                "the catalog; refusing\n",
                        (unsigned long long)(offset + RT_SITE_EBOOT_BASE), ABSOLUTE_JUMP_SIZE);
                return -1;
            }
        }
    }

    /* One memcmp per site, and it is the check that matters: a site whose bytes are not what the caller expected
       is a patch into a different function. It reads back perfectly, passes the exec check, and fires at a site
       nobody selected -- the 16 KiB bias class. A site that is already a jump is refused too: patching over a
       patch hides the first one. */
    sites_checked++;
    /* One variable, one derivation. `capturing` changes the emitted length, so it must reach the size function
       and the emitter together. It was hardcoded 0 at every call site below, so the size function and the emitter
       agreed about a form neither had been asked about, and a capture install emitted the ordinary stub. */
    unsigned char site_before[ABSOLUTE_JUMP_SIZE];
    memcpy(site_before, guest_image + offset, sizeof site_before);
    const int capturing = capture_mode();
    /* The slot is reserved here, before any allocation, and committed only after the jump reads back.
       The capacity check and the pointer derivation are one decision: previously the write was guarded
       by `g_site_count < RT_SITES_MAX` while entered_addr was derived afterwards from
       `g_site_count - 1`, so every capturing site past the cap incremented slot 63 and the report
       named 64 sites while 65 wrappers ran. A slot that is reserved but not committed is invisible
       to rt_sites_report (it iterates g_site_count), so a refused emit cannot leave a phantom row. */
    unsigned capture_slot = 0;
    uint64_t entered_addr = 0;
    if (capturing) {
        if (g_site_count >= RT_SITES_MAX) {
            fprintf(stderr, "hook: refusing to install at 0x%llx: capture table is full (%u of %u slots); "
                            "the site is not recorded and the body runs as shipped\n",
                    (unsigned long long)rt_guest_address(offset), g_site_count, (unsigned)RT_SITES_MAX);
            return RT_INSTALL_NO_ROOM;
        }
        capture_slot = g_site_count;
        g_site_address[capture_slot] = rt_guest_address(offset);   /* guest-keyed, like every table */
        g_site_entered[capture_slot] = 0;
        entered_addr = (uint64_t)(uintptr_t)&g_site_entered[capture_slot];
    }
    const size_t wrapper_capacity = rt_snapshot_stub_size(capturing, 1);
    if (wrapper_capacity == SIZE_MAX) {
        fprintf(stderr, "hook: refusing to install at 0x%llx: the capture form is unsatisfiable "
                        "(rt_snapshot_stub_size(%d, 1) == SIZE_MAX); nothing is written\n",
                (unsigned long long)offset, capturing);
        sites_unlisted++;   /* the form, not the catalog: counted, so a zero cannot silently hide it */
        /* The assertion is an instrument, not a claim: hooks_installed=0 counts successful installs and is not a
           memory comparison. This is the comparison. */
        fprintf(stderr, "hook: site byte-identical: %s\n",
                memcmp(site_before, guest_image + offset, sizeof site_before) == 0 ? "yes" : "no");
        return -1;
    }
    if (guest_image[offset] == 0xe9 || guest_image[offset] == 0xcc || guest_image[offset] == 0xff) {
        sites_already_patched++;
        fprintf(stderr, "hook: refusing 0x%llx: site begins 0x%02x, which is already a patch or a trap\n",
                (unsigned long long)offset, (unsigned)guest_image[offset]);
        return -1;
    }

    /* Writable first: a read-only page reads back correctly and faults inside memcpy, and the SIGSEGV would be
       attributed to whatever runs next. Named refusal instead of a crash with an innocent suspect. */
    if (!region_is_writable(guest_image + offset, ABSOLUTE_JUMP_SIZE)) {
        fprintf(stderr, "hook: refusing 0x%llx: the page is not writable, so the patch would fault in memcpy\n",
                (unsigned long long)offset);
        return -1;
    }
    if (!region_is_executable(guest_image + offset, ABSOLUTE_JUMP_SIZE)) {
        fprintf(stderr, "hook: refusing to patch 0x%llx: the 14 bytes at 0x%llx are not in an "
                "executable mapping, so the patch would read back and never fire\n",
                (unsigned long long)offset, (unsigned long long)(uintptr_t)(guest_image + offset));
        return -1;
    }

    /* With a live guest %fs the jump goes to a boundary stub: swap to the host base, park the guest's
       rsp in rbx, align, call, restore both. Without TLS (the harness) there is nothing to swap and
       the jump goes straight to the target, which is what every existing caller sees. */
    uintptr_t destination = (uintptr_t)target;
    if (guest_tls_is_live()) {
        unsigned char *stub = stub_alloc(RT_BOUNDARY_STUB_MAX);
        if (!stub) {
            fprintf(stderr, "hook: no room for a boundary stub at 0x%llx (page holds %u of %u bytes)\n",
                    (unsigned long long)offset, (unsigned)STUB_PAGE, (unsigned)stub_used);
            return RT_INSTALL_NO_ROOM;
        }
        size_t n = rt_write_boundary_stub(stub, RT_BOUNDARY_STUB_MAX, (uint64_t)(uintptr_t)target,
                                          rt_tls_host_base(), rt_tls_guest_base(), 0, 1);
        if (n == 0 || n > RT_BOUNDARY_STUB_MAX) {
            fprintf(stderr, "hook: boundary stub refused to emit into %d bytes at offset 0x%llx\n",
                    RT_BOUNDARY_STUB_MAX, (unsigned long long)offset);
            return -1;
        }
        __builtin___clear_cache((char *)stub, (char *)stub + n);
        destination = (uintptr_t)stub;

        /* Commit A's wrapper: a 5-byte `e9 rel32` from its own slot to the stub, emitted and proved
           BEFORE the site is patched -- a site patched to a wrapper that failed to allocate points at
           junk the moment the guest arrives, and with 1,737 candidate sites that is a crash with no
           owner. Emit-before-patch is the gate-before-client rule applied to bytes. */
        unsigned char *wrapper = stub_alloc(wrapper_capacity);
        if (!wrapper) {
            fprintf(stderr, "hook: no room for a snapshot wrapper at 0x%llx\n", (unsigned long long)offset);
            return RT_INSTALL_NO_ROOM;
        }
        /* The site's executability is checked above; the wrapper is a different page, and a wrapper in a
           read-only page reads back perfectly and faults on entry -- the same defect one level earlier,
           and it would look like a body fault because the wrapper's last instruction is a jump. */
        if (!region_is_executable(wrapper, wrapper_capacity)) {
            fprintf(stderr, "hook: refusing to enter a wrapper at 0x%llx: page is not executable\n",
                    (unsigned long long)(uintptr_t)wrapper);
            return -1;
        }
        size_t w = rt_write_snapshot_stub(wrapper, wrapper_capacity, (uint64_t)(uintptr_t)wrapper,
                                          (uint64_t)destination, rt_tls_host_base(), rt_tls_guest_base(),
                                          entered_addr, capturing, 1);
        if (w == 0) {
            fprintf(stderr, "hook: snapshot wrapper refused to emit at 0x%llx -> 0x%llx (distance %lld)\n",
                    (unsigned long long)(uintptr_t)wrapper, (unsigned long long)destination,
                    (long long)((intptr_t)destination - (intptr_t)(uintptr_t)wrapper));
            return -1;
        }
        __builtin___clear_cache((char *)wrapper, (char *)wrapper + w);
        /* Readback from the page, not the emitter's return: "emitted N bytes" is a claim, the page is
           the evidence. The assertion's inputs are printed beside its verdict. */
        /* The readback follows the FORM: a 5-byte wrapper opens with `e9`, and the 73-byte capture form opens
           with `push rdi` and carries its `e9 rel32` in the last five bytes. An assertion written against one
           shape outlived its subject here once already; this one decodes the jump where the form puts it. */
        const unsigned char want_first = capturing ? 0x49 : 0xe9;   /* capture form opens with `movabs r11, &entered` */
        const unsigned char *jump_at = capturing ? wrapper + w - 5 : wrapper;
        if (memcmp(wrapper, &want_first, 1) != 0 || memcmp(jump_at, "\xe9", 1) != 0) {
            fprintf(stderr, "hook: wrapper readback at 0x%llx is not the %s form (first byte 0x%02x)\n",
                    (unsigned long long)(uintptr_t)wrapper, capturing ? "capture" : "jump", (unsigned)wrapper[0]);
            return -1;
        }
        if (getenv("BB_HOOK_VERBOSE"))
            fprintf(stderr, "hook: wrapper emitted %zu bytes at 0x%llx, jmp -> stub 0x%llx "
                    "(distance %lld bytes), readback ok\n",
                    w, (unsigned long long)(uintptr_t)wrapper, (unsigned long long)destination,
                    (long long)((intptr_t)destination - (intptr_t)(uintptr_t)wrapper));
        destination = (uintptr_t)wrapper;
        if (getenv("BB_HOOK_VERBOSE")) {
            /* A new allocator with no readback is where the next objects[1] lives: print the bytes
               that are actually in the page, not the length the emitter reported. */
            fprintf(stderr, "hook: 0x%llx -> %zu-byte boundary stub at 0x%llx -> body 0x%llx\n",
                    (unsigned long long)offset, n, (unsigned long long)destination,
                    (unsigned long long)(uintptr_t)target);
            fprintf(stderr, "hook: stub bytes");
            for (size_t k = 0; k < n && k < 16; k++) fprintf(stderr, " %02x", stub[k]);
            fprintf(stderr, "%s\n", n > 16 ? " ..." : "");
        }
    }

    /* `jmp qword ptr [rip]` followed by the 64-bit destination preserves every argument register,
       including AL for variadic calls. The loader installs hooks before entering guest code. */
    unsigned char jump[ABSOLUTE_JUMP_SIZE] = {0xff, 0x25, 0, 0, 0, 0};
    memcpy(jump + 6, &destination, sizeof destination);
    memcpy(guest_image + offset, jump, sizeof jump);
    __builtin___clear_cache((char *)guest_image + offset, (char *)guest_image + offset + sizeof jump);

    /* "N installed" counts writes. Prove the bytes the guest will execute are the bytes written, or
       a write that landed somewhere else reads as a working hook. */
    if (memcmp(guest_image + offset, jump, sizeof jump) == 0) installed_count++;
    if (memcmp(guest_image + offset, jump, sizeof jump) != 0) {
        fprintf(stderr, "hook: readback at 0x%llx does not match the jump written\n",
                (unsigned long long)offset);
        return -1;
    }
    if (getenv("BB_HOOK_VERBOSE"))
        fprintf(stderr, "hook: 0x%llx size %llu bytes patched with a %u-byte absolute jump to "
                "host 0x%llx (distance %lld bytes), readback ok\n",
                (unsigned long long)offset, (unsigned long long)size, (unsigned)ABSOLUTE_JUMP_SIZE,
                (unsigned long long)destination,
                (long long)((intptr_t)destination -
                            (intptr_t)(uintptr_t)(guest_image + offset)));
    /* Commit the reserved slot only after the patch and its readback succeeded. A failed install leaves
       g_site_count untouched, so the slot is reused rather than reported as a site that never entered. */
    if (capturing) g_site_count = capture_slot + 1;
    return 0;
}

int rt_host_hooks_initialize(rt_host *host)
{
    static int report_registered;
    if (!report_registered) {
        report_registered = 1;
        atexit(rt_sites_report);
        struct sigaction sa_abort;
        memset(&sa_abort, 0, sizeof sa_abort);
        sa_abort.sa_handler = rt_sites_on_abort;
        sigaction(SIGABRT, &sa_abort, NULL);
    }
    if (!host || host->version != RT_HOST_API_VERSION || !host->image ||
        host->image_size < ABSOLUTE_JUMP_SIZE)
        return -1;

    guest_image = host->image;
    guest_image_size = host->image_size;
    host->install_hook = install_hook;

    /* One line, always, before any hook can install. Without it "nothing was printed" is indistinguishable
       between off, refused, no row, and not on the path -- three different findings and one silence. The four
       counters here are pre-install zeros by construction; the post-install snapshot is plugin_load.c's line. */
    {
        const char *path = getenv("BB_CAPTURE_OK");
        const int on = capture_mode();
        if (!path || !*path) path = "symbols/capture_ok.csv";
        int present = 0;
        if (on) {
            FILE *probe = fopen(path, "r");
            if (probe) { present = 1; fclose(probe); }
        }
        fprintf(stderr, "capture: mode=%s table=%s hooks_installed=%u sites_checked=%u already_patched=%u "
                        "mismatched=%u unlisted=%u\n",
                on ? "on" : "off", on ? (present ? path : "absent") : "-", installed_count, sites_checked,
                sites_already_patched, sites_mismatched, sites_unlisted);
    }
    return 0;
}
