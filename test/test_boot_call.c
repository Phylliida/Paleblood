/* The two decisions rt_boot_call makes about a thread's registers, exercised through the real asm
   rather than modelled:
     - a live %gs whose guest_block is zero must refuse, not fall through to main's published word;
     - a live %gs whose host_fsbase is zero must refuse, not install a null %fs and fault in libc.
   The second is silent and legal: wrfsbase 0 succeeds, and the next malloc dereferences %fs:0.
   Fork because both refusals leave the process (134 raw, or abort through rt_fatal). */
#include "runtime/boot_call.h"
#include "runtime/tls.h"

#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static volatile sig_atomic_t marker_ran;

static void marker(void) { marker_ran = 1; }

/* A guest that exercises WRGSBASE, which guest code is not entitled to use. The call must refuse on
   return rather than substitute main's host base for the thread's lost one. */
static void marker_clear_gs(void)
{
    marker_ran = 1;
    unsigned long zero = 0;
    __asm__ volatile("wrgsbase %0" ::"r"(zero) : "memory");
}

/* A guest that installs a nonzero %gs pointing at something that is not our state. The entry gate
   already ran on the real state; this is the return path's version of the same question. */
static unsigned char foreign_state[0x48] __attribute__((aligned(8)));
static void marker_foreign_gs(void)
{
    marker_ran = 1;
    __asm__ volatile("wrgsbase %0" ::"r"((unsigned long)(uintptr_t)foreign_state) : "memory");
}

static uint64_t read_fsbase(void)
{
    uint64_t v = 0;
    __asm__ volatile("rdfsbase %0" : "=r"(v));
    return v;
}

static void write_gsbase(void *p)
{
    __asm__ volatile("wrgsbase %0" ::"r"((unsigned long)p));
}

/* Everything a state needs for rt_boot_call: a self-pointer, a guest block, a host base. */
static void make_state(unsigned char *state, void *guest_block, uint64_t host_fsbase)
{
    memset(state, 0, 0x48);
    *(void **)state = state;
    *(uint64_t *)(state + RT_TLS_GS_GUEST_BLOCK_OFF) = (uint64_t)(uintptr_t)guest_block;
    *(uint64_t *)(state + RT_TLS_GS_HOST_FSBASE_OFF) = host_fsbase;
    *(uint64_t *)(state + RT_TLS_GS_MAGIC_OFF) = RT_TLS_MAGIC;
}

typedef struct {
    int status;
    int marker;   /* marker_ran in the parent is always 0; keep it out of the assertion */
    char message[1024];
} child_result;

static child_result run_boot_child(unsigned char *state, int malloc_after, int stack_mode,
                                   int zero_selector, uint64_t published_guest, int clear_gs)
{
    child_result r;
    memset(&r, 0, sizeof r);
    int fds[2];
    if (pipe(fds) != 0) return r;
    const pid_t pid = fork();
    if (pid < 0) return r;
    if (pid == 0) {
        close(fds[0]);
        if (dup2(fds[1], 2) < 0) _exit(2);
        close(fds[1]);
        static unsigned char guest_stack[0x1000] __attribute__((aligned(16)));
        unsigned char *stack_top = guest_stack + sizeof guest_stack;
        if (stack_mode == 1) stack_top -= 8;   /* 8 mod 16: callee entry would be 0 mod 16 */
        if (stack_mode == 2) stack_top = NULL;
        if (zero_selector) write_gsbase(NULL);
        else write_gsbase(state);
        rt_tls_guest_base_v = published_guest;
        rt_boot_call(clear_gs == 1 ? marker_clear_gs : clear_gs == 2 ? marker_foreign_gs : marker,
                     NULL, stack_top, NULL, NULL);
        if (malloc_after) {
            /* The point of the valid control: prove %fs is the host's, not just that the call returned.
               malloc alone did not catch a null %fs in this test; errno does, because the macro reads
               glibc's TCB through %fs. */
            errno = 42;
            if (errno != 42) _exit(3);
            void *p = malloc(64);
            if (!p) _exit(3);
            free(p);
        }
        _exit(0);
    }
    close(fds[1]);
    const ssize_t n = read(fds[0], r.message, sizeof r.message - 1);
    close(fds[0]);
    if (waitpid(pid, &r.status, 0) != pid) return r;
    r.message[n > 0 ? n : 0] = '\0';
    return r;
}

int main(void)
{
    rt_tls_init();
    if (!rt_tls_have_wrfsbase()) {
        fprintf(stderr, "boot_call: SKIP: host has no user-mode wrfsbase\n");
        return 77;
    }

    static unsigned char guest_block[0x100] __attribute__((aligned(16)));
    static unsigned char state[0x48] __attribute__((aligned(8)));
    const uint64_t host_fs = read_fsbase();

    /* 1. Live %gs, zero guest block, nonzero published word: old code ran marker and returned. */
    make_state(state, NULL, host_fs);
    child_result r = run_boot_child(state, 0, 0, 0, (uint64_t)(uintptr_t)guest_block, 0);
    if (!WIFSIGNALED(r.status) || WTERMSIG(r.status) != SIGABRT) {
        fprintf(stderr, "boot_call: live selector with no block was not refused: status=0x%x marker=%d message=%s\n",
                r.status, (int)marker_ran, r.message);
        return 1;
    }
    if (!strstr(r.message, "live %gs names a thread with no guest TLS block") ||
        !strstr(r.message, "refusing to enter guest code with a null TCB")) {
        fprintf(stderr, "boot_call: refusal did not name the live-selector case: %s\n", r.message);
        return 1;
    }

    /* 1b. A live %gs that is not this runtime's state. glibc's TCB is also nonzero and also points
           at itself, so the self-pointer cannot decide this; only the magic can. The message must
           print the offending word, not the expected constant. */
    make_state(state, guest_block, host_fs);
    *(uint64_t *)(state + RT_TLS_GS_MAGIC_OFF) = RT_TLS_MAGIC ^ 1;
    r = run_boot_child(state, 0, 0, 0, (uint64_t)(uintptr_t)guest_block, 0);
    if (!WIFSIGNALED(r.status) || WTERMSIG(r.status) != SIGABRT) {
        fprintf(stderr, "boot_call: a foreign %%gs was not refused: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }
    char want_magic[64];
    snprintf(want_magic, sizeof want_magic, "magic=0x%llx",
             (unsigned long long)(RT_TLS_MAGIC ^ 1));
    if (!strstr(r.message, "does not name this runtime's TLS state") ||
        !strstr(r.message, want_magic)) {
        fprintf(stderr, "boot_call: foreign-%%gs refusal did not print the offending word (%s): %s\n",
                want_magic, r.message);
        return 1;
    }

    /* 2. Zero %gs selector with a published block: the published word is main's, and a thread with
          no state must not run on it. This is the fallback arm todo/047 left behind; it refuses. */
    make_state(state, guest_block, host_fs);
    r = run_boot_child(state, 0, 0, 1, (uint64_t)(uintptr_t)guest_block, 0);
    if (!WIFSIGNALED(r.status) || WTERMSIG(r.status) != SIGABRT) {
        fprintf(stderr, "boot_call: zero selector with a published block was not refused: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }
    if (!strstr(r.message, "no per-thread guest TLS state") ||
        !strstr(r.message, "refusing to run on main's block")) {
        fprintf(stderr, "boot_call: zero-selector refusal did not name main's block: %s\n", r.message);
        return 1;
    }

    /* 3. Zero %gs selector and nothing published: the pre-init case. It must refuse by name, not
          become a legal null TCB. */
    r = run_boot_child(state, 0, 0, 1, 0, 0);
    if (!WIFSIGNALED(r.status) || WTERMSIG(r.status) != SIGABRT) {
        fprintf(stderr, "boot_call: zero selector with no published block was not refused: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }
    if (!strstr(r.message, "no guest TLS block") || !strstr(r.message, "both zero")) {
        fprintf(stderr, "boot_call: zero-zero refusal did not name both zeros: %s\n", r.message);
        return 1;
    }

    /* 4. The guest clears %gs with WRGSBASE. The return path must refuse: this thread's host base is
          unknown, and main's is another thread's TCB. Raw write+exit_group(134), no libc. */
    make_state(state, guest_block, host_fs);
    r = run_boot_child(state, 0, 0, 0, (uint64_t)(uintptr_t)guest_block, 1);
    if (!WIFEXITED(r.status) || WEXITSTATUS(r.status) != 134) {
        fprintf(stderr, "boot_call: a guest-cleared selector was not refused: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }
    if (!strstr(r.message, "guest returned with %gs selector zero") ||
        !strstr(r.message, "refusing to install main's host base")) {
        fprintf(stderr, "boot_call: cleared-selector refusal did not name the selector: %s\n", r.message);
        return 1;
    }

    /* 4b. The guest installs a nonzero but foreign %gs. The return path must check the magic before
            reading host_fsbase from it; otherwise a forged state with a plausible host base would be
            installed and this call would return as if nothing had happened. */
    make_state(state, guest_block, host_fs);
    memset(foreign_state, 0, sizeof foreign_state);
    *(uint64_t *)(foreign_state + RT_TLS_GS_MAGIC_OFF) = RT_TLS_MAGIC ^ 2;
    *(uint64_t *)(foreign_state + RT_TLS_GS_HOST_FSBASE_OFF) = host_fs;
    r = run_boot_child(state, 0, 0, 0, (uint64_t)(uintptr_t)guest_block, 2);
    if (!WIFEXITED(r.status) || WEXITSTATUS(r.status) != 134) {
        fprintf(stderr, "boot_call: a foreign %%gs after return was not refused: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }
    if (!strstr(r.message, "foreign TLS state") ||
        !strstr(r.message, "refusing to install its host base")) {
        fprintf(stderr, "boot_call: foreign-state refusal did not name the state: %s\n", r.message);
        return 1;
    }

    /* 5. Live %gs, valid guest block, zero host base: the guest runs, then the restore must refuse
          before wrfsbase 0. Raw write+exit_group(134), and the message must name the host base. */
    make_state(state, guest_block, 0);
    r = run_boot_child(state, 1, 0, 0, (uint64_t)(uintptr_t)guest_block, 0);
    if (!WIFEXITED(r.status) || WEXITSTATUS(r.status) != 134) {
        fprintf(stderr, "boot_call: zero host base was not refused: status=0x%x marker=%d message=%s\n",
                r.status, (int)marker_ran, r.message);
        return 1;
    }
    if (!strstr(r.message, "host %fs base is zero after guest return") ||
        !strstr(r.message, "refusing to install a null TCB")) {
        fprintf(stderr, "boot_call: zero-host refusal did not name the base: %s\n", r.message);
        return 1;
    }

    /* 6. Positive control: same shape, valid host base, and malloc/free after return. This is what
          distinguishes "refuses the zero" from "refuses everything". */
    make_state(state, guest_block, host_fs);
    r = run_boot_child(state, 1, 0, 0, (uint64_t)(uintptr_t)guest_block, 0);
    if (!WIFEXITED(r.status) || WEXITSTATUS(r.status) != 0) {
        fprintf(stderr, "boot_call: valid host base did not survive the round trip: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }

    /* 7. A valid state, but a stack that violates the SysV contract. The old code switched rsp anyway:
          an 8-mod-16 top faults on the guest's first movaps, and a null top faults on its first push,
          both inside a function nobody suspects. The refusal must come before wrfsbase. */
    for (int mode = 1; mode <= 2; mode++) {
        r = run_boot_child(state, 0, mode, 0, (uint64_t)(uintptr_t)guest_block, 0);
        if (!WIFSIGNALED(r.status) || WTERMSIG(r.status) != SIGABRT) {
            fprintf(stderr, "boot_call: stack_top mode %d was not refused: status=0x%x message=%s\n",
                    mode, r.status, r.message);
            return 1;
        }
        if (!strstr(r.message, "stack_top=0x") || !strstr(r.message, "16-byte-aligned guest stack")) {
            fprintf(stderr, "boot_call: stack refusal did not name the stack: %s\n", r.message);
            return 1;
        }
    }
    return 0;
}
