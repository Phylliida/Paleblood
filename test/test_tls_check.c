/* The failing-first baseline for the %gs magic check at the boundary.

   A nonzero %gs is not evidence that the state is this runtime's (glibc's TCB is nonzero and has a dtv
   at +8, exactly the field the stub reads as guest_block). The per-thread boundary stub currently reads
   %gs:0x28 (host_fsbase) before it reads anything else. With %gs == 0 that read faults at the linear
   address 0x28, not at 0 and not at 8 -- and which offset the fault names is the placement argument
   stated as a measurement.

   Child A is the control: a raw `mov %gs:0x28,%r11` with %gs == 0. It stays green after the checker and
   proves the harness (not the product) produced the address.
   Child B is the zero-selector case: the gated stub must not fault at all; it must exit 134 naming
   SELECTOR_ZERO with observed 0, and the body must not run.
   Child D is the foreign-state case: a nonzero %gs whose magic is wrong must exit 134 naming
   FOREIGN_STATE with the observed word. A test that only walks the zero arm cannot see the jne's
   displacement, which is why D exists.

   si_addr is captured by a SA_SIGINFO handler and copied out with one write(2) of two uint64_t; the
   handler then _exit()s. No stdio and no %gs in the handler. si_code is printed, not asserted: with a
   zero base SEGV_MAPERR is expected, but SI_KERNEL is the kernel's classification, not a fact this test
   controls. */
#include "runtime/boundary_stub.h"
#include "runtime/tls.h"

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

#if !defined(__x86_64__)
#error "the %gs boundary baseline is x86-64 only"
#endif

static volatile int target_called;
static unsigned char *g_stub;
static unsigned char *g_page;
static unsigned char foreign_tcb[0x48] __attribute__((aligned(8)));
static int g_refuse_pipe = -1;

struct refusal {
    uint64_t reason;
    uint64_t observed;
};

/* The checker's failure body in this fixture. It is reached only when the emitted bytes work; the
   product's rt_tls_check_fail prints a sentence, but a test needs the reason and observed word the
   parent can assert, so it writes both down the refusal pipe and still exits 134. */
__attribute__((noreturn, no_stack_protector)) static void test_check_fail(int reason, uint64_t observed)
{
    char msg[96];
    int n = snprintf(msg, sizeof msg, "test_tls_check: checker refused reason=%d observed=0x%llx\n",
                     reason, (unsigned long long)observed);
    if (n > 0) {
        ssize_t ignored = write(2, msg, (size_t)n);
        (void)ignored;
    }
    if (g_refuse_pipe >= 0) {
        struct refusal r = {(uint64_t)reason, observed};
        ssize_t ignored = write(g_refuse_pipe, &r, sizeof r);
        (void)ignored;
    }
    _exit(134);
}

struct sigrec {
    uint64_t addr;
    uint64_t code;
};

struct child_result {
    int signal_seen;
    uint64_t fault_addr;
    uint64_t fault_code;
    int exited;
    int code;
    int wait_signaled;
    int wait_signal;
    int refused;
    uint64_t reason;
    uint64_t observed;
};

static int g_sigpipe = -1;

static void on_sig(int sig, siginfo_t *si, void *ctx)
{
    (void)sig;
    (void)ctx;
    struct sigrec r = {(uint64_t)(uintptr_t)si->si_addr, (uint64_t)si->si_code};
    /* One write, at most two uint64_t. The pipe is non-blocking and the parent reads before waitpid. */
    ssize_t n = write(g_sigpipe, &r, sizeof r);
    (void)n;
    _exit(0);
}

/* No libc, no TLS: the body must be runnable on the fake %fs the stub installs. */
__attribute__((naked, used)) static void target(void)
{
    __asm__ volatile("movl $1, target_called(%rip)\n\t"
                     "ret\n\t");
}

/* Child A's subject: the first %gs read the stub performs, with no product in between. */
__attribute__((naked, used)) static void raw_read_host_fsbase(void)
{
    __asm__ volatile("movq %gs:0x28, %r11\n\t"
                     "ret\n\t");
}

static int set_gs_zero(void)
{
    /* ARCH_SET_GS, not wrgsbase: this test is about the read, not about FSGSBASE availability. */
    return (int)syscall(158, 0x1001UL, 0UL);
}

static int set_gs_foreign(void)
{
    memset(foreign_tcb, 0, sizeof foreign_tcb);
    *(uint64_t *)(void *)(foreign_tcb + 0x28) = 0x1000;      /* a plausible host_fsbase */
    *(uint64_t *)(void *)(foreign_tcb + 0x40) = RT_TLS_MAGIC ^ 1;
    return (int)syscall(158, 0x1001UL, (uint64_t)(uintptr_t)foreign_tcb);
}

static void child_common(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_sig;
    sa.sa_flags = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGSEGV, &sa, NULL) != 0 || sigaction(SIGBUS, &sa, NULL) != 0) _exit(4);
}

static void call_stub(void)
{
    ((void (*)(void))(uintptr_t)g_stub)();
    if (target_called) _exit(3);
}

static struct child_result run_child(void (*fn)(void), int foreign)
{
    struct child_result r;
    memset(&r, 0, sizeof r);
    int fds[2], rfds[2];
    if (pipe(fds) != 0 || pipe(rfds) != 0) {
        perror("test_tls_check: pipe");
        r.code = 5;
        return r;
    }
    (void)fcntl(fds[1], F_SETFL, O_NONBLOCK);
    (void)fcntl(rfds[1], F_SETFL, O_NONBLOCK);
    const pid_t pid = fork();
    if (pid < 0) {
        perror("test_tls_check: fork");
        close(fds[0]);
        close(fds[1]);
        close(rfds[0]);
        close(rfds[1]);
        r.code = 5;
        return r;
    }
    if (pid == 0) {
        close(fds[0]);
        close(rfds[0]);
        g_sigpipe = fds[1];
        g_refuse_pipe = rfds[1];
        child_common();
        const int gs = foreign ? set_gs_foreign() : set_gs_zero();
        if (gs != 0) _exit(4);
        fn();
        _exit(target_called ? 3 : 0);
    }
    close(fds[1]);
    close(rfds[1]);
    struct sigrec rec;
    memset(&rec, 0, sizeof rec);
    ssize_t n;
    do {
        n = read(fds[0], &rec, sizeof rec);
    } while (n < 0 && errno == EINTR);
    close(fds[0]);
    struct refusal ref;
    memset(&ref, 0, sizeof ref);
    ssize_t rn;
    do {
        rn = read(rfds[0], &ref, sizeof ref);
    } while (rn < 0 && errno == EINTR);
    close(rfds[0]);
    int status = 0;
    if (waitpid(pid, &status, 0) != pid) {
        r.code = 5;
        return r;
    }
    r.signal_seen = (n == (ssize_t)sizeof rec);
    if (r.signal_seen) {
        r.fault_addr = rec.addr;
        r.fault_code = rec.code;
    }
    r.refused = (rn == (ssize_t)sizeof ref);
    if (r.refused) {
        r.reason = ref.reason;
        r.observed = ref.observed;
    }
    r.exited = WIFEXITED(status);
    r.code = r.exited ? WEXITSTATUS(status) : -1;
    r.wait_signaled = WIFSIGNALED(status);
    r.wait_signal = r.wait_signaled ? WTERMSIG(status) : 0;
    return r;
}

static int check(int cond, const char *what)
{
    if (!cond) fprintf(stderr, "test_tls_check: FAIL: %s\n", what);
    return cond ? 0 : 1;
}

static int make_stub(void)
{
    const long page = sysconf(_SC_PAGESIZE);
    if (page <= 0) return 0;
    g_page = mmap(NULL, (size_t)page, PROT_READ | PROT_WRITE | PROT_EXEC,
                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (g_page == MAP_FAILED) {
        perror("test_tls_check: mmap");
        return 0;
    }
    /* One checker per region, then the stub 128 bytes in: the call target is within rel32 and the two
       byte strings cannot overlap. The checker is emitted first, so the stub's first instruction can
       never call bytes that were not written. */
    const uint64_t check = (uint64_t)(uintptr_t)g_page;
    const size_t cn = rt_write_tls_check(g_page, (size_t)page, (uint64_t)(uintptr_t)test_check_fail);
    if (cn == 0) {
        fprintf(stderr, "test_tls_check: checker emitter refused (page %ld)\n", page);
        return 0;
    }
    g_stub = g_page + 128;
    const size_t n = rt_write_boundary_stub(g_stub, (size_t)page - 128, (uint64_t)(uintptr_t)target, 0, 0, 0, 1,
                                            check);
    if (n == 0) {
        fprintf(stderr, "test_tls_check: boundary emitter refused (page %ld)\n", page);
        return 0;
    }
    __builtin___clear_cache((char *)g_page, (char *)g_page + (size_t)page);
    fprintf(stderr, "test_tls_check: checker %zu bytes at %p; gated per-thread stub %zu bytes at %p -> target %p\n",
            cn, (void *)g_page, n, (void *)g_stub, (void *)target);
    return 1;
}

int main(void)
{
    int failed = 0;

    /* A: the control. This is the raw read the stub performs, with no product code between the register
       set and the fault. It is green before and after the checker, so it proves the harness did not
       change when C did. */
    {
        const struct child_result a = run_child(raw_read_host_fsbase, 0);
        fprintf(stderr, "test_tls_check: control raw %%gs:0x28 si_addr=0x%llx si_code=%llu%s\n",
                (unsigned long long)a.fault_addr, (unsigned long long)a.fault_code,
                a.signal_seen ? "" : " (NO SIGNAL)");
        failed |= check(a.signal_seen, "control: a raw %gs:0x28 read with gs=0 must fault");
        failed |= check(a.fault_addr == 0x28, "control: the raw read must fault at 0x28");
    }

    if (!make_stub()) return 1;

    /* B: the gated stub. Before 9bb02e4 this same call faulted at 0x28, which is the placement
       measurement that made the checker the first instruction. Now the checker must refuse before any
       selector-dependent read: no signal, exit 134, body not run. */
    {
        const struct child_result b = run_child(call_stub, 0);
        if (b.signal_seen)
            fprintf(stderr, "test_tls_check: gated stub faulted: si_addr=0x%llx si_code=%llu "
                            "(expected exit 134, no signal)\n",
                    (unsigned long long)b.fault_addr, (unsigned long long)b.fault_code);
        else
            fprintf(stderr, "test_tls_check: gated stub exited=%d code=%d wait_signal=%d\n",
                    b.exited, b.code, b.wait_signal);
        failed |= check(!b.signal_seen, "gated stub: a zero selector must be refused, not fault at %gs:0x28");
        failed |= check(b.exited && b.code == 134, "gated stub: a zero selector must exit 134");
        failed |= check(!b.exited || b.code != 3, "gated stub: the body must not run when the selector is zero");
        failed |= check(b.refused && b.reason == 0x11 && b.observed == 0,
                        "gated stub: the refusal must name SELECTOR_ZERO and observed 0");
    }

    /* D: a nonzero %gs that is not this runtime's state. The checker must read the magic, find the
       wrong word, and refuse -- with the observed magic in the sentence. This is the arm the
       zero-selector test cannot reach, and the one a plausible foreign TCB would otherwise walk past. */
    {
        const struct child_result d = run_child(call_stub, 1);
        fprintf(stderr, "test_tls_check: foreign state refused=%d reason=0x%llx observed=0x%llx exited=%d code=%d\n",
                d.refused, (unsigned long long)d.reason, (unsigned long long)d.observed, d.exited, d.code);
        failed |= check(!d.signal_seen, "foreign state: a wrong magic must be refused, not fault");
        failed |= check(d.exited && d.code == 134, "foreign state: must exit 134");
        failed |= check(d.refused && d.reason == 0x12 && d.observed == (RT_TLS_MAGIC ^ 1),
                        "foreign state: the refusal must name FOREIGN_STATE and print the observed magic");
        failed |= check(!d.exited || d.code != 3, "foreign state: the body must not run");
    }

    if (munmap(g_page, (size_t)sysconf(_SC_PAGESIZE)) != 0) perror("test_tls_check: munmap");
    return failed;
}
