/* The selector decision in rt_boot_call, exercised through the real asm rather than modelled.
   A live %gs whose guest_block is zero must refuse; it must not fall through to main's published word.
   The test forks because the refusal calls rt_fatal, which aborts on the host %fs. */
#include "runtime/boot_call.h"
#include "runtime/tls.h"

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

int main(void)
{
    rt_tls_init();
    if (!rt_tls_have_wrfsbase()) {
        fprintf(stderr, "boot_call: SKIP: host has no user-mode wrfsbase\n");
        return 77;
    }

    /* A state with a valid self-pointer and a zero guest block. tls_state() checks the self-pointer;
       rt_boot_call checks the block. The published word is made nonzero so the old fall-through
       would call marker instead of refusing. */
    static unsigned char state[0x48] __attribute__((aligned(8)));
    static unsigned char guest_block[0x100] __attribute__((aligned(16)));
    static unsigned char guest_stack[0x1000] __attribute__((aligned(16)));
    memset(state, 0, sizeof state);
    *(void **)state = state;
    *(uint64_t *)(state + RT_TLS_GS_GUEST_BLOCK_OFF) = 0;
    *(uint64_t *)(state + RT_TLS_GS_HOST_FSBASE_OFF) = read_fsbase();

    int fds[2];
    if (pipe(fds) != 0) return 1;
    const pid_t pid = fork();
    if (pid < 0) return 1;
    if (pid == 0) {
        close(fds[0]);
        if (dup2(fds[1], 2) < 0) _exit(2);
        close(fds[1]);
        write_gsbase(state);
        rt_tls_guest_base_v = (uint64_t)(uintptr_t)guest_block;
        rt_boot_call(marker, NULL, guest_stack + sizeof guest_stack, NULL, NULL);
        _exit(marker_ran ? 1 : 2); /* old fall-through runs marker; fixed asm never reaches here */
    }
    close(fds[1]);
    char message[1024];
    const ssize_t n = read(fds[0], message, sizeof message - 1);
    close(fds[0]);
    int status = 0;
    if (waitpid(pid, &status, 0) != pid) return 1;
    /* A wrong path may print nothing at all (the fall-through runs marker and exits 1). Report the
       status even when the pipe is empty; an exit code is the observation, the message is a bonus. */
    message[n > 0 ? n : 0] = '\0';
    if (!WIFSIGNALED(status) || WTERMSIG(status) != SIGABRT) {
        fprintf(stderr, "boot_call: live selector with no block was not refused: status=0x%x marker=%d message=%s\n",
                status, (int)marker_ran, message);
        return 1;
    }
    if (!strstr(message, "live %gs names a thread with no guest TLS block") ||
        !strstr(message, "refusing to enter guest code with a null TCB")) {
        fprintf(stderr, "boot_call: refusal did not name the live-selector case: %s\n", message);
        return 1;
    }
    return 0;
}
