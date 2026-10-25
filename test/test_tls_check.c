/* The failing-first baseline for the %gs magic check at the boundary.

   A nonzero %gs is not evidence that the state is this runtime's (glibc's TCB is nonzero and has a dtv
   at +8, exactly the field the stub reads as guest_block). The per-thread boundary stub currently reads
   %gs:0x28 (host_fsbase) before it reads anything else. With %gs == 0 that read faults at the linear
   address 0x28, not at 0 and not at 8 -- and which offset the fault names is the placement argument
   stated as a measurement.

   Child A is the control: a raw `mov %gs:0x28,%r11` with %gs == 0. It stays green after the checker and
   proves the harness (not the product) produced the address.
   Child B is the pre-checker characterization: the current ungated stub must fault at 0x28.
   Child C is the failing-first assertion: a gated stub must not fault at all; it must exit 134 naming a
   zero selector. Today C observes B's signal at 0x28 and fails, which is the red.

   si_addr is captured by a SA_SIGINFO handler and copied out with one write(2) of two uint64_t; the
   handler then _exit()s. No stdio and no %gs in the handler. si_code is printed, not asserted: with a
   zero base SEGV_MAPERR is expected, but SI_KERNEL is the kernel's classification, not a fact this test
   controls. */
#include "runtime/boundary_stub.h"

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

static struct child_result run_child(void (*fn)(void))
{
    struct child_result r;
    memset(&r, 0, sizeof r);
    int fds[2];
    if (pipe(fds) != 0) {
        perror("test_tls_check: pipe");
        r.code = 5;
        return r;
    }
    (void)fcntl(fds[1], F_SETFL, O_NONBLOCK);
    const pid_t pid = fork();
    if (pid < 0) {
        perror("test_tls_check: fork");
        close(fds[0]);
        close(fds[1]);
        r.code = 5;
        return r;
    }
    if (pid == 0) {
        close(fds[0]);
        g_sigpipe = fds[1];
        child_common();
        if (set_gs_zero() != 0) _exit(4);
        fn();
        _exit(target_called ? 3 : 0);
    }
    close(fds[1]);
    struct sigrec rec;
    memset(&rec, 0, sizeof rec);
    ssize_t n;
    do {
        n = read(fds[0], &rec, sizeof rec);
    } while (n < 0 && errno == EINTR);
    close(fds[0]);
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
    g_stub = mmap(NULL, (size_t)page, PROT_READ | PROT_WRITE | PROT_EXEC,
                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (g_stub == MAP_FAILED) {
        perror("test_tls_check: mmap");
        return 0;
    }
    const size_t n = rt_write_boundary_stub(g_stub, (size_t)page, (uint64_t)(uintptr_t)target, 0, 0, 0, 1);
    if (n == 0) {
        fprintf(stderr, "test_tls_check: boundary emitter refused (page %ld)\n", page);
        return 0;
    }
    __builtin___clear_cache((char *)g_stub, (char *)g_stub + n);
    fprintf(stderr, "test_tls_check: ungated per-thread stub %zu bytes at %p -> target %p\n", n, (void *)g_stub,
            (void *)target);
    return 1;
}

int main(void)
{
    int failed = 0;

    /* A: the control. This is the raw read the stub performs, with no product code between the register
       set and the fault. It is green before and after the checker, so it proves the harness did not
       change when C did. */
    {
        const struct child_result a = run_child(raw_read_host_fsbase);
        fprintf(stderr, "test_tls_check: control raw %%gs:0x28 si_addr=0x%llx si_code=%llu%s\n",
                (unsigned long long)a.fault_addr, (unsigned long long)a.fault_code,
                a.signal_seen ? "" : " (NO SIGNAL)");
        failed |= check(a.signal_seen, "control: a raw %gs:0x28 read with gs=0 must fault");
        failed |= check(a.fault_addr == 0x28, "control: the raw read must fault at 0x28");
    }

    if (!make_stub()) return 1;

    /* B: pre-checker characterization. The ungated stub must touch host_fsbase first. If this reports
       0x8, the guest_block read came first and the placement argument is wrong. */
    {
        const struct child_result b = run_child(call_stub);
        fprintf(stderr, "test_tls_check: ungated stub si_addr=0x%llx si_code=%llu "
                        "exited=%d code=%d wait_signal=%d\n",
                (unsigned long long)b.fault_addr, (unsigned long long)b.fault_code, b.exited, b.code,
                b.wait_signal);
        failed |= check(b.signal_seen, "ungated stub: a zero %gs must fault, not return");
        failed |= check(b.fault_addr == 0x28, "ungated stub: the first %gs read must be host_fsbase at 0x28");
        failed |= check(!b.exited || b.code != 3, "ungated stub: the body must not run when the read faults");
    }

    /* C: failing-first. After the checker, no %gs read happens: the process exits 134 naming the zero
       selector, and the signal handler is never entered. Today this observes B's signal at 0x28. */
    {
        const struct child_result c = run_child(call_stub);
        if (c.signal_seen)
            fprintf(stderr, "test_tls_check: gated stub observed the ungated fault: si_addr=0x%llx "
                            "si_code=%llu (expected exit 134, no signal)\n",
                    (unsigned long long)c.fault_addr, (unsigned long long)c.fault_code);
        else
            fprintf(stderr, "test_tls_check: gated stub exited=%d code=%d wait_signal=%d\n",
                    c.exited, c.code, c.wait_signal);
        failed |= check(!c.signal_seen, "gated stub: a zero selector must be refused, not fault at %gs:0x28");
        failed |= check(c.exited && c.code == 134, "gated stub: a zero selector must exit 134");
        /* A body that ran and returned exits 3; the child encodes that, so no parent-side copy of
           target_called can be mistaken for evidence. */
    }

    if (munmap(g_stub, (size_t)sysconf(_SC_PAGESIZE)) != 0) perror("test_tls_check: munmap");
    return failed;
}
