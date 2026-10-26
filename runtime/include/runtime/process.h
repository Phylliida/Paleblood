/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RUNTIME_PROCESS_H
#define RUNTIME_PROCESS_H

/* The running guest process, as the system libraries see it. Set by whoever loads the
   executable (runtime/boot.c) before the guest runs. */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    void *image;         /* where the executable is mapped */
    uint64_t image_size;
    void *proc_param;    /* its process parameter block (PT_SCE_PROCPARAM), or NULL */
    void **heap_api;     /* the C library's heap functions, as it registered them, or NULL */
} rt_process_info;

extern rt_process_info rt_process;

/* Registers the calling host thread as the guest's main thread, running on the given stack. */
void rt_thread_register_main(void *stack, uint64_t stack_size);

/* The detach state (0 joinable, 1 detached) recorded on a guest thread attribute variable, for the
   system call that creates a thread from it; caller names that call. A state the guest did not set
   is one the system supplies (a fresh attribute's default, or the state scePthreadAttrGet copied
   from a running thread), and it is not known, so asking for it stops the process (rt_fatal). So
   does a null or empty variable, for which thread creation would use the system's defaults. */
int rt_thread_attr_detach_state(void *const *attr, const char *caller);

/* The stack size and scheduling policy recorded on a guest thread attribute variable: 1 = the guest asked
   (value written through `size`/`policy`), 0 = it did not, -1 = no attribute variable. The distinction is
   the point: a default substituted for an unasked value is indistinguishable from a request this runtime
   ignored. */
int rt_thread_attr_stack_size(void *const *attr, uint64_t *size);
/* Creates a real host thread that runs the guest entry with its own guest TLS block and %fs.
   Returns 0 on success; writes the guest_thread pointer to `out` through the guest write check.
   Declared here because the syslib create path is in pthread_sema.c and the object type lives in
   kernel_thread.c. */
int rt_thread_create_real(int64_t out, int64_t entry, int64_t arg, uint64_t stack_size, int has_stack);
int rt_thread_join_real(int64_t handle);
int rt_thread_detach_real(int64_t handle);
int rt_thread_attr_sched_policy(void *const *attr, int *policy);

/* Whether the thread-model experiment is on (BB_THREAD_MODELLED unset/0/empty = off). One reader
   for one switch: the modelled create and every modelled call that exists only to let it proceed
   consult this, so the log and the branch cannot disagree about the flag. */
int rt_thread_modelled_enabled(void);

/* Stops the process with a message naming the system function: behaviour the runtime does not
   know is never guessed. */
_Noreturn void rt_fatal(const char *function, const char *message);

#ifdef __cplusplus
}
#endif

#endif
