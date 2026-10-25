/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include "runtime/host_hooks.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#include "runtime/boundary_stub.h"
#include "runtime/tls.h"

enum { GUEST_CODE_SIZE = 32, MINIMUM_HOOK_SIZE = 14 };

static int replacement(int left, int right)
{
    return left * 3 + right;
}

/* The boundary crossing, measured from inside the C body it calls: the body records the %fs base it
   was entered with, so the test can tell "the stub swapped" from "the stub exists". */
static uint64_t live_host_fs;
static uint64_t live_guest_fs;
static uint64_t body_saw_fs;
static int boundary_body(int left, int right)
{
    unsigned long base;
    __asm__ volatile("rdfsbase %0" : "=r"(base));
    body_saw_fs = base;
    return left * 3 + right;
}

/* Strong definitions: host_hooks.c references these weakly, because the differential harness links no
   TLS. Here they are the point of the test. */
static uint64_t fake_guest_fs;
static uint64_t fake_host_fs;
uint64_t rt_tls_guest_base(void) { return fake_guest_fs; }
/* This fixture installs a real %gs TCB, so the emitter may read it. */
int rt_tls_thread_ready(void) { return 1; }
uint64_t rt_tls_host_base(void) { return fake_host_fs; }

static uint64_t read_fs(void)
{
    unsigned long base;
    __asm__ volatile("rdfsbase %0" : "=r"(base));
    return (uint64_t)base;
}

static void write_fs(uint64_t base)
{
    __asm__ volatile("wrfsbase %0" : : "r"(base) : "memory");
}

static uint64_t read_gs(void)
{
    unsigned long base;
    __asm__ volatile("rdgsbase %0" : "=r"(base));
    return (uint64_t)base;
}

static void write_gs(uint64_t base)
{
    __asm__ volatile("wrgsbase %0" : : "r"(base) : "memory");
}

/* The only fields the emitted selector reads, at the displacements tls.c asserts against offsetof. */
struct fake_tcb {
    uintptr_t self;          /* 0x00 */
    uint64_t guest_block;    /* 0x08 */
    uint64_t pad[3];         /* 0x10 .. 0x20 */
    uint64_t host_fsbase;    /* 0x28 */
};
_Static_assert(sizeof(struct fake_tcb) == 0x30, "fake TCB keeps the product's field offsets");

/* Does this host actually have FSGSBASE? Ask the instruction, not CPUID: this machine reports
   CPUID.07H:EBX[16] == 0 and still executes rdfsbase, so a capability bit is a claim and the round
   trip is the measurement. SIGILL means "no", not "the test is broken". */
static sigjmp_buf ill_env;
static void on_ill(int signal_number)
{
    (void)signal_number;
    siglongjmp(ill_env, 1);
}

static int try_wrfsbase(void)
{
    struct sigaction sa, old;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_ill;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_NODEFER;
    sigaction(SIGILL, &sa, &old);

    const uint64_t saved = read_fs();
    int ok = 0;
    if (!sigsetjmp(ill_env, 1)) {
        const uint64_t probe = saved + 0x4000;
        write_fs(probe);
        ok = (read_fs() == probe);
        write_fs(saved);
    }
    sigaction(SIGILL, &old, NULL);
    return ok;
}

static int check(int condition, const char *message)
{
    if (condition)
        return 0;
    fprintf(stderr, "test_host_hooks: %s\n", message);
    return 1;
}

int main(void)
{
    const long page_size = sysconf(_SC_PAGESIZE);
    unsigned char *image = mmap(NULL, (size_t)page_size, PROT_READ | PROT_WRITE | PROT_EXEC,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (image == MAP_FAILED) {
        perror("test_host_hooks: mmap");
        return 1;
    }

    /* A synthetic SysV AMD64 function: return the sum of its two integer arguments. */
    static const unsigned char guest_code[] = {0x89, 0xf8, 0x01, 0xf0, 0xc3};
    memset(image, 0x90, GUEST_CODE_SIZE);
    memcpy(image, guest_code, sizeof guest_code);
    int (*guest_function)(int, int) = (int (*)(int, int))(void *)image;

    rt_host host = {RT_HOST_API_VERSION, image, GUEST_CODE_SIZE, NULL};
    int failed = 0;
    failed |= check(guest_function(5, 8) == 13, "synthetic guest function must execute before patching");
    failed |= check(rt_host_hooks_initialize(&host) == 0, "valid v1 host must initialize");
    failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)replacement) == 0,
                    "valid image-relative hook must install");
    failed |= check(guest_function(5, 8) == 23, "patched guest entry must call replacement with ABI arguments");

    unsigned char before[MINIMUM_HOOK_SIZE];
    memcpy(before, image, sizeof before);
    failed |= check(host.install_hook(1, GUEST_CODE_SIZE, (const void *)replacement) != 0,
                    "a hook outside the function entry must fail");
    failed |= check(memcmp(before, image, sizeof before) == 0, "rejected hook must not change guest bytes");
    failed |= check(host.install_hook(0, MINIMUM_HOOK_SIZE - 1, (const void *)replacement) != 0,
                    "a short function must fail without a partial jump");
    failed |= check(host.install_hook(0, GUEST_CODE_SIZE, NULL) != 0, "null replacement must fail");

    host.version++;
    failed |= check(rt_host_hooks_initialize(&host) != 0, "unsupported v1 interface version must fail");
    host.version = RT_HOST_API_VERSION;
    host.image = NULL;
    failed |= check(rt_host_hooks_initialize(&host) != 0, "missing guest image must fail");

    /* A patch into a page the process cannot execute reads back and never fires: refused, and the
       image is untouched. The synthetic image above is mmap'd PROT_EXEC, so this is the negative
       control for that check, not a second test of the same path. */
    {
        unsigned char plain[64];
        memset(plain, 0x90, sizeof plain);
        rt_host plain_host = {RT_HOST_API_VERSION, plain, sizeof plain, NULL};
        failed |= check(rt_host_hooks_initialize(&plain_host) == 0, "a plain image must still initialize");
        failed |= check(plain_host.install_hook(0, sizeof plain, (const void *)replacement) != 0,
                        "a hook into a non-executable page must be refused");
        failed |= check(plain[0] == 0x90, "a refused non-executable hook must not change the bytes");
        /* rt_host_hooks_initialize stores the image in module state, so the control above must put it
           back or every later case patches the stack array. Found by the segfault it caused, which is
           the only reason it is written down here. */
        host.version = RT_HOST_API_VERSION;
        host.image = image;
        host.image_size = GUEST_CODE_SIZE;
        failed |= check(rt_host_hooks_initialize(&host) == 0, "the real image must be restored after the control");
    }

    /* The emitted crossing is pinned to bytes the test derives itself, so an emitter edit that changes
       the instruction stream fails here instead of at the first boot on a machine with a live %fs. */
    {
        unsigned char want[128];
        unsigned char *w = want;
        const uint64_t target = 0x1122334455667788ULL, host = 0x99aabbccddeeff00ULL;
        const uint64_t guest = 0x0f1e2d3c4b5a6978ULL;
        *w++ = 0x49, *w++ = 0xba, memcpy(w, &target, 8), w += 8;   /* movabs r10, target */
        *w++ = 0x49, *w++ = 0xbb, memcpy(w, &host, 8), w += 8;     /* movabs r11, host */
        *w++ = 0xf3, *w++ = 0x49, *w++ = 0x0f, *w++ = 0xae, *w++ = 0xd3; /* wrfsbase r11 */
        *w++ = 0x53; *w++ = 0x48, *w++ = 0x89, *w++ = 0xe3;        /* push rbx; mov rbx, rsp */
        *w++ = 0x48, *w++ = 0x83, *w++ = 0xe4, *w++ = 0xf0;        /* and rsp, -16 */
        *w++ = 0x41, *w++ = 0xff, *w++ = 0xd2;                     /* call r10 */
        *w++ = 0x48, *w++ = 0x89, *w++ = 0xdc; *w++ = 0x5b;        /* mov rsp, rbx; pop rbx */
        *w++ = 0x49, *w++ = 0xbb, memcpy(w, &guest, 8), w += 8;    /* movabs r11, guest */
        *w++ = 0xf3, *w++ = 0x49, *w++ = 0x0f, *w++ = 0xae, *w++ = 0xd3; /* wrfsbase r11 */
        *w++ = 0xc3;                                               /* ret */
        unsigned char got[128];
        size_t n = rt_write_boundary_stub(got, sizeof got, target, host, guest, 0, 0);
        failed |= check(n == rt_boundary_stub_size(0, 0), "the emitted length must match the size helper");
        /* A capacity one byte short must be refused before the first store, and the buffer untouched. */
        unsigned char tiny[128];
        memset(tiny, 0xcc, sizeof tiny);
        const size_t full = rt_boundary_stub_size(0, 0);
        failed |= check(rt_write_boundary_stub(tiny, full - 1, target, host, guest, 0, 0) == 0,
                        "an under-sized capacity must be refused");
        failed |= check(tiny[0] == 0xcc, "a refused emission must not write a single byte");
        failed |= check(rt_write_boundary_stub(tiny, full, target, host, guest, 0, 0) == full,
                        "an exactly-sized capacity must be accepted");
        failed |= check(rt_boundary_stub_size(1, 0) == full + 22,
                        "the import path's bookkeeping word must be counted in the size");
        failed |= check(rt_boundary_stub_size(0, 1) == full - 2,
                        "the per-thread selector is two bytes shorter than the baked one");
        failed |= check(rt_boundary_stub_size(1, 1) == full + 20,
                        "the import path's bookkeeping word is selector-independent");
        failed |= check(n == (size_t)(w - want), "boundary stub length must match the derived bytes");
        failed |= check(memcmp(got, want, n) == 0, "boundary stub bytes must match the derived bytes");
        /* Counted, not indexed: hand-computed offsets into an instruction stream were wrong twice in
           this very test, which is the defect the test exists to catch. */
        int wrfsbase = 0, wrgsbase = 0;
        for (size_t k = 0; k + 5 <= n; k++) {
            static const unsigned char wf[5] = {0xf3, 0x49, 0x0f, 0xae, 0xd3};
            static const unsigned char wg[5] = {0xf3, 0x49, 0x0f, 0xae, 0xdb};
            if (memcmp(got + k, wf, 5) == 0) wrfsbase++;
            if (memcmp(got + k, wg, 5) == 0) wrgsbase++;
        }
        failed |= check(wrfsbase == 2, "the crossing must write %fs exactly twice, both wrfsbase");
        failed |= check(wrgsbase == 0, "%fs must never be written with wrgsbase (/3 = 0xdb)");
    }

    /* The product's selector shape: two %gs loads and no baked base. The fixture has a TCB, which is
       the only way to represent the subject; a baked-bases fixture cannot notice this leaving the
       product. */
    {
        unsigned char got[128];
        unsigned char *g = got;
        const uint64_t target = 0x1122334455667788ULL;
        const size_t n = rt_write_boundary_stub(got, sizeof got, target, 0x99aabbccddeeff00ULL,
                                                0x0f1e2d3c4b5a6978ULL, 0, 1);
        failed |= check(n == 54u, "the per-thread boundary stub is 54 bytes");
        failed |= check(n == rt_boundary_stub_size(0, 1), "the per-thread size helper must agree");
        failed |= check(g[0] == 0x49 && g[1] == 0xba, "the per-thread stub still starts with movabs r10");
        static const unsigned char host_gs[] = {0x65, 0x4c, 0x8b, 0x1c, 0x25,
                                                RT_TLS_GS_HOST_FSBASE_OFF & 0xffu, 0, 0, 0};
        static const unsigned char guest_gs[] = {0x65, 0x4c, 0x8b, 0x1c, 0x25,
                                                 RT_TLS_GS_GUEST_BLOCK_OFF & 0xffu, 0, 0, 0};
        failed |= check(memcmp(g + 10, host_gs, sizeof host_gs) == 0,
                        "the host base must be read from %gs, not baked");
        failed |= check(g[19] == 0xf3 && g[23] == 0xd3, "the first wrfsbase follows the %gs load");
        failed |= check(memcmp(g + 39, guest_gs, sizeof guest_gs) == 0,
                        "the guest base must be read from %gs, not baked");
        failed |= check(g[48] == 0xf3 && g[52] == 0xd3, "the second wrfsbase follows the %gs load");
        int movabs_r11 = 0;
        for (size_t k = 0; k + 2 <= n; k++)
            if (g[k] == 0x49 && g[k + 1] == 0xbb) movabs_r11++;
        failed |= check(movabs_r11 == 0, "the per-thread selector must not bake an r11 immediate");
    }

    /* Capture mode: the table is the contract. The .so identity is mandatory (a default would manufacture
       agreement with a stale table), the verdict must be `none`, and every refusal is checked against the
       site's bytes -- a refusal that already patched is not a refusal. */
    {
        const char *path = "capture_ok_test.csv";
        /* The site is restored to its original bytes BEFORE anything is compared, because an earlier case patched
           it and the double-patch guard would then refuse for its own reason. `pristine` comes from the code
           constant, never from the site's current contents; `before` is then a snapshot of that restored site, so
           every "byte-identical" check below compares against bytes that were actually there. */
        unsigned char pristine[14], before[14];
        memset(pristine, 0x90, sizeof pristine);
        memcpy(pristine, guest_code, sizeof guest_code);
        memcpy(image, pristine, sizeof pristine);
        memcpy(before, image, sizeof before);

        setenv("BB_CAPTURE", "1", 1);
        setenv("BB_CAPTURE_OK", path, 1);

        /* The catalog join: capture mode refuses an unlisted site, so the test supplies the 14 bytes it derived
           itself. The hex is built from `pristine` -- a literal here would be a second copy of the facts. */
        char site_hex[2 * 14 + 1];
        for (int k = 0; k < 14; k++) snprintf(site_hex + 2 * k, 3, "%02x", pristine[k]);
        FILE *sf = fopen("site_ok_test.csv", "w");
        fprintf(sf, "address,prologue\n0x%08x,%s\n", 0x400000, site_hex);
        fclose(sf);
        setenv("BB_SITE_OK", "site_ok_test.csv", 1);

        FILE *f = fopen(path, "w");
        fprintf(f, "address,xmm_used,scanned_sha256,so_sha256\n0x400000,none,00,aa\n");
        fclose(f);

        unsetenv("BB_CAPTURE_TABLE_ID");
        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) != 0,
                        "capture mode must refuse when BB_CAPTURE_TABLE_ID is unset");
        failed |= check(memcmp(image, before, sizeof before) == 0,
                        "a missing-id refusal must leave the site byte-identical");

        setenv("BB_CAPTURE_TABLE_ID", "bb", 1);
        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) != 0,
                        "capture mode must refuse a table derived from a different library");
        failed |= check(memcmp(image, before, sizeof before) == 0,
                        "a stale-table refusal must leave the site byte-identical");

        setenv("BB_CAPTURE_TABLE_ID", "aa", 1);
        memcpy(image, before, sizeof before);   /* pristine site: the guard refuses a patched one for its own reason */
        f = fopen(path, "w");
        fprintf(f, "address,xmm_used,scanned_sha256,so_sha256\n0x400000,xmm0,00,aa\n");
        fclose(f);
        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) != 0,
                        "capture mode must refuse a non-none verdict");
        failed |= check(memcmp(image, before, sizeof before) == 0,
                        "a refused capture install must leave the site byte-identical");

        memcpy(image, before, sizeof before);
        f = fopen(path, "w");
        fprintf(f, "address,xmm_used,scanned_sha256,so_sha256\n0x1,none,00,aa\n");
        fclose(f);
        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) != 0,
                        "capture mode must refuse an address with no row");
        failed |= check(memcmp(image, before, sizeof before) == 0,
                        "a missing-row refusal must leave the site byte-identical");

        memcpy(image, pristine, sizeof pristine);
        sf = fopen("site_ok_test.csv", "w");
        fprintf(sf, "address,prologue\n0x%08x,%s\n", 0x400000,
                "9090909090909090909090909090");   /* not this site: the image is not the catalog */
        fclose(sf);
        f = fopen(path, "w");
        fprintf(f, "address,xmm_used,scanned_sha256,so_sha256\n0x400000,none,00,aa\n");
        fclose(f);
        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) != 0,
                        "capture mode must refuse a site that does not match its catalogued prologue");
        failed |= check(memcmp(image, pristine, sizeof pristine) == 0,
                        "a prologue mismatch must leave the site byte-identical");

        sf = fopen("site_ok_test.csv", "w");
        fprintf(sf, "address,prologue\n0x%08x,%s\n", 0x400000, site_hex);
        fclose(sf);
        /* This case used to assert a SUCCESSFUL capture install, and it passed -- which was the capacity hole
           wearing a green test: with every guard satisfied the installer emitted the ORDINARY stub, because
           `capturing` was hardcoded 0 at the call site. Now the form is derived and unsatisfiable until the
           capture stub exists, so the honest assertion is the refusal plus byte identity. THE PASS CASE COMES
           BACK WITH THE CAPTURE STUB, and it is named here so it cannot be quietly forgotten. */
        /* THE PASS CASE CAME BACK WITH THE CAPTURE STUB, exactly as the comment promised it would, and the
           assertion is the same one that was here before the hole was found -- now it is true for the right
           reason, because rt_snapshot_stub_size(1, 1) is 73 and the form exists. */
        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) == 0,
                        "capture mode must allow a pass row with a matching library and a matching prologue");
        remove(path);
        remove("site_ok_test.csv");
        unsetenv("BB_SITE_OK");   /* the allowed case leaves the site patched; later cases restore it themselves */
        unsetenv("BB_CAPTURE");
        unsetenv("BB_CAPTURE_OK");
        unsetenv("BB_CAPTURE_TABLE_ID");
        memset(image, 0x90, 14);
    }

    /* Live guest %fs: the 14 bytes must point at a stub, not at the replacement, and executing the
       patched site must enter the body on the host base and give the guest its base back. */
    if (try_wrfsbase()) {
        unsigned char *pages = image;
        memset(pages, 0x90, GUEST_CODE_SIZE);
        memcpy(pages, guest_code, sizeof guest_code);
        fake_host_fs = read_fs();
        fake_guest_fs = fake_host_fs + 0x4000;
        live_host_fs = fake_host_fs;
        live_guest_fs = fake_guest_fs;
        body_saw_fs = 0;

        /* The product reads the executing thread's state through %gs. Without a TCB the per-thread
           stub would fault on its own first instruction, and a fixture that cannot have one cannot
           notice that the selector left the product. */
        struct fake_tcb tcb;
        memset(&tcb, 0, sizeof tcb);
        tcb.self = (uintptr_t)&tcb;
        tcb.guest_block = fake_guest_fs;
        tcb.host_fsbase = fake_host_fs;
        const uint64_t saved_gs = read_gs();
        write_gs((uint64_t)(uintptr_t)&tcb);

        failed |= check(host.install_hook(0, GUEST_CODE_SIZE, (const void *)boundary_body) == 0,
                        "with a live guest %fs the hook must install a boundary stub");
        uintptr_t dest = 0;
        memcpy(&dest, image + 6, sizeof dest);
        failed |= check(dest != (uintptr_t)(void *)boundary_body,
                        "live-TLS patch must point at the stub, not straight at the body");
        /* Commit A inserted a wrapper between the site and the stub, so the patch lands on a 5-byte
           `e9 rel32` whose target is the stub. Follow it instead of assuming the old layout: an
           assertion written against one shape outlives its subject and then reports the shape as a
           defect. Both addresses print, because "did the guest enter the wrapper" and "did it reach
           the stub" are opposite findings. */
        unsigned char *site_target = (unsigned char *)dest;
        failed |= check(site_target[0] == 0xe9, "the site's destination must be a near-jump wrapper");
        if (site_target[0] == 0xe9) {
            int32_t rel = 0;
            memcpy(&rel, site_target + 1, 4);
            uintptr_t stub = (uintptr_t)(site_target + 5 + rel);
            fprintf(stderr, "test: wrapper at %p -> stub at %p (distance %d)\n",
                    (void *)site_target, (void *)stub, (int)rel);
            failed |= check(stub != (uintptr_t)site_target, "the wrapper must jump somewhere else");
            dest = stub; /* the stub is the subject of the byte assertions below */
        }
        failed |= check(((unsigned char *)dest)[0] == 0x49 && ((unsigned char *)dest)[1] == 0xba,
                        "stub must start with movabs r10, target");
        {
            static const unsigned char host_gs[] = {0x65, 0x4c, 0x8b, 0x1c, 0x25,
                                                    RT_TLS_GS_HOST_FSBASE_OFF & 0xffu, 0, 0, 0};
            static const unsigned char wf[5] = {0xf3, 0x49, 0x0f, 0xae, 0xd3};
            failed |= check(memcmp((unsigned char *)dest + 10, host_gs, sizeof host_gs) == 0,
                            "the live stub must read the thread's host base through %gs");
            failed |= check(memcmp((unsigned char *)dest + 19, wf, 5) == 0,
                            "the stub must swap %fs before it calls the body");
        }

        uint64_t saved = read_fs();
        write_fs(fake_guest_fs);
        int result = guest_function(5, 8);
        uint64_t after = read_fs();
        write_fs(saved);
        failed |= check(result == 23, "the body must receive ABI arguments through the stub");
        failed |= check(body_saw_fs == live_host_fs, "the body must run on the host %fs base");
        failed |= check(after == live_guest_fs, "the guest's %fs base must be restored before return");
        write_gs(saved_gs);
    } else {
        fprintf(stderr, "test_host_hooks: SIGILL from wrfsbase on this host, live-TLS case skipped\n");
    }

    if (munmap(image, (size_t)page_size) != 0) {
        perror("test_host_hooks: munmap");
        failed = 1;
    }
    return failed;
}
