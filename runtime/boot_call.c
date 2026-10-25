/* SPDX-License-Identifier: GPL-2.0-or-later */
/* rt_boot_call lives apart from boot.c for one reason: its selector decision is a branch on asm that
   must be exercised by a test, and boot.c has a main() that a test cannot link. */
#include "runtime/boot_call.h"
#include "runtime/process.h"
#include "runtime/tls.h"

#include <stdio.h>
#include <stdlib.h>

/* Reached from the asm below with the host stack and the host %fs still installed. It must not return:
   writing a zero %fs and calling the guest is legal, silent, and gives the guest a null TCB. */
__attribute__((noreturn, used)) void rt_boot_call_bad_stack(uintptr_t stack_top);
void rt_boot_call_bad_stack(uintptr_t stack_top)
{
    /* The guest stack is switched in before the call; a misaligned rsp faults on the first movaps
       inside the guest (si_addr is 0, not the stack), and a zero stack faults on the first push.
       This path is before wrfsbase, so the host TCB is still installed and libc is safe. */
    char msg[192];
    snprintf(msg, sizeof msg,
             "rt_boot_call: stack_top=0x%llx is not a usable 16-byte-aligned guest stack; refusing to "
             "enter guest code",
             (unsigned long long)stack_top);
    rt_fatal("boot", msg);
}

__attribute__((noreturn, used)) void rt_boot_call_no_guest_tls(int reason);
void rt_boot_call_no_guest_tls(int reason)
{
    if (reason)
        rt_fatal("boot", "rt_boot_call: a live %gs names a thread with no guest TLS block; refusing to "
                         "enter guest code with a null TCB (the published word belongs to main, not to "
                         "the executing thread)");
    rt_fatal("boot", "rt_boot_call: no guest TLS block (%gs selector and published base are both zero); "
                     "refusing to enter guest code with a null TCB");
}
__asm__(".text\n"
        ".globl rt_boot_call\n"
        "rt_boot_call:\n"
        "  push %rbp\n  push %rbx\n  push %r12\n  push %r13\n  push %r14\n  push %r15\n"
        "  mov %rsp, %r12\n"
        "  mov %rdi, %rax\n"
        "  mov %rsi, %rdi\n"
        "  mov %rcx, %rsi\n"
        /* Selector: the current thread's state through %gs, never main's published word. A zero %gs is
           the pre-init or post-end case; fall back to the published word only so that a zero there is
           named by rt_boot_call_no_guest_tls instead of becoming a legal null %fs.

           A live %gs with no guest block is NOT that case: it is a thread whose state exists and whose
           block does not. Falling through to main's published word here was todo/047's defect surviving
           in the arm added to prevent it, so this branch refuses and names which zero it saw. */
        "  rdgsbase %r11\n"
        "  test %r11, %r11\n"
        "  jz 1f\n"
        "  mov %gs:0x8, %r11\n"
        "  test %r11, %r11\n"
        "  jnz 2f\n"
        "  mov $1, %edi\n"                                  /* live selector, no block */
        "  jmp 9f\n"
        "1:\n"
        "  xor %edi, %edi\n"                                /* no selector and no published block */
        "  mov rt_tls_guest_base_v(%rip), %r11\n"
        "  test %r11, %r11\n"
        "  jz 9f\n"
        "2:\n"
        "  test %rdx, %rdx\n"
        "  jz 6f\n"
        "  test $15, %dl\n"
        "  jnz 6f\n"                                       /* SysV: callee entry rsp is 8 mod 16 */
        "  mov %rdx, %rsp\n"                                /* switch to the guest stack after the check */
        "  mov %r8, %rdx\n"
        "  wrfsbase %r11\n"
        "  call *%rax\n"
        "  rdgsbase %r11\n"
        "  test %r11, %r11\n"
        "  jz 3f\n"
        "  mov %gs:0x28, %r11\n"
        "  test %r11, %r11\n"
        "  jz 5f\n"                                        /* live state, zero host base */
        "  jmp 4f\n"
        "3:\n"
        "  mov rt_tls_host_base_v(%rip), %r11\n"           /* back to the host's TCB on return */
        "  test %r11, %r11\n"
        "  jz 5f\n"
        "4:\n"
        "  wrfsbase %r11\n"
        "  mov %r12, %rsp\n"
        "  pop %r15\n  pop %r14\n  pop %r13\n  pop %r12\n  pop %rbx\n  pop %rbp\n"
        "  ret\n"
        "9:\n"
        "  sub $8, %rsp\n"                                  /* host rsp is 8 mod 16 after six pushes */
        "  call rt_boot_call_no_guest_tls\n"
        "  ud2\n"
        "5:\n"
        "  and $-16, %rsp\n"                                /* raw refusal; no return, alignment still matters */
        "  call rt_tls_host_base_refuse\n"
        "  ud2\n"
        "6:\n"
        "  mov %rdx, %rdi\n"
        "  and $-16, %rsp\n"
        "  call rt_boot_call_bad_stack\n"
        "  ud2\n");
