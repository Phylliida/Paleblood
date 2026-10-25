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
}

typedef struct {
    int status;
    int marker;   /* marker_ran in the parent is always 0; keep it out of the assertion */
    char message[1024];
} child_result;

static child_result run_boot_child(unsigned char *state, void *guest_block, int malloc_after)
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
        write_gsbase(state);
        rt_tls_guest_base_v = (uint64_t)(uintptr_t)guest_block;
        rt_boot_call(marker, NULL, guest_stack + sizeof guest_stack, NULL, NULL);
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
    child_result r = run_boot_child(state, guest_block, 0);
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

    /* 2. Live %gs, valid guest block, zero host base: the guest runs, then the restore must refuse
          before wrfsbase 0. Raw write+exit_group(134), and the message must name the host base. */
    make_state(state, guest_block, 0);
    r = run_boot_child(state, guest_block, 1);
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

    /* 3. Positive control: same shape, valid host base, and malloc/free after return. This is what
          distinguishes "refuses the zero" from "refuses everything". */
    make_state(state, guest_block, host_fs);
    r = run_boot_child(state, guest_block, 1);
    if (!WIFEXITED(r.status) || WEXITSTATUS(r.status) != 0) {
        fprintf(stderr, "boot_call: valid host base did not survive the round trip: status=0x%x message=%s\n",
                r.status, r.message);
        return 1;
    }
    return 0;
}
