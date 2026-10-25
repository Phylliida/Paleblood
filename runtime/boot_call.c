/* SPDX-License-Identifier: GPL-2.0-or-later */
/* rt_boot_call lives apart from boot.c for one reason: its selector decision is a branch on asm that
   must be exercised by a test, and boot.c has a main() that a test cannot link. */
#include "runtime/boot_call.h"
#include "runtime/process.h"
#include "runtime/tls.h"

#include <stdio.h>
#include <stdlib.h>

/* A whole-function asm block has no operands, so it cannot use %c0; stringifying the same
   macro the struct static-asserts compare against makes a wrong displacement unproducible all
   the same. The constants are deliberately unsuffixed: gas does not accept a C `u` suffix. */
#define RT_STR_(x) #x
#define RT_STR(x) RT_STR_(x)

/* Entry refusal reasons. They are a different axis from tls.h's RT_TLS_REFUSE_*: here 1 means a live
   selector with no block, there 0x11 means a zero selector after return. Name them, and give them
   values that cannot be mistaken for one another in a disassembly. */
#define RT_BC_NO_TLS_NONE 0
#define RT_BC_NO_TLS_LIVE 1
#define RT_BC_NO_TLS_PUBLISHED 2

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
    if (reason == RT_BC_NO_TLS_PUBLISHED)
        rt_fatal("boot", "rt_boot_call: no per-thread guest TLS state (%gs selector is zero) but a "
                         "published block exists; refusing to run on main's block from a thread that "
                         "has no state");
    if (reason == RT_BC_NO_TLS_LIVE)
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
        /* Selector: the current thread's state through %gs, never main's published word. A zero %gs
           is a thread with no state. It is NOT a reason to substitute the published word: that word is
           main's, and a child thread running on it is todo/047's defect. Refuse, and name which zero
           was seen: reason 0 = nothing published either, reason 2 = a published block exists but
           belongs to another thread. */
        "  rdgsbase %r11\n"
        "  test %r11, %r11\n"
        "  jnz .Lrtbc_live\n"
        "  mov rt_tls_guest_base_v(%rip), %r11\n"
        "  test %r11, %r11\n"
        "  jnz .Lrtbc_no_selector_published\n"
        "  mov $" RT_STR(RT_BC_NO_TLS_NONE) ", %edi\n"    /* no selector and no published block */
        "  jmp .Lrtbc_no_tls\n"
        ".Lrtbc_no_selector_published:\n"
        "  mov $" RT_STR(RT_BC_NO_TLS_PUBLISHED) ", %edi\n" /* selector zero, main's block published */
        "  jmp .Lrtbc_no_tls\n"
        ".Lrtbc_live:\n"
        "  mov %gs:" RT_STR(RT_TLS_GS_GUEST_BLOCK_OFF) ", %r11\n"
        "  test %r11, %r11\n"
        "  jnz .Lrtbc_have_block\n"
        "  mov $" RT_STR(RT_BC_NO_TLS_LIVE) ", %edi\n"    /* live selector, no block */
        "  jmp .Lrtbc_no_tls\n"
        ".Lrtbc_have_block:\n"
        "  test %rdx, %rdx\n"
        "  jz .Lrtbc_bad_stack\n"
        "  test $15, %dl\n"
        "  jnz .Lrtbc_bad_stack\n"                        /* SysV: callee entry rsp is 8 mod 16 */
        "  mov %rdx, %rsp\n"                              /* switch to the guest stack after the check */
        "  mov %r8, %rdx\n"
        "  wrfsbase %r11\n"
        "  call *%rax\n"
        /* The guest may clear %gs (a WRGSBASE the guest is not entitled to use). If it does, this
           thread's host base is unknown; installing main's published host base would give glibc
           another thread's TCB. Refuse instead. */
        "  rdgsbase %r11\n"
        "  test %r11, %r11\n"
        "  jz .Lrtbc_no_selector_after\n"
        "  mov %gs:" RT_STR(RT_TLS_GS_HOST_FSBASE_OFF) ", %r11\n"
        "  test %r11, %r11\n"
        "  jz .Lrtbc_zero_host\n"
        "  jmp .Lrtbc_restore\n"
        ".Lrtbc_no_selector_after:\n"
        "  mov $" RT_STR(RT_TLS_REFUSE_SELECTOR_ZERO) ", %edi\n" /* raw refusal: selector zero */
        "  jmp .Lrtbc_host_refuse\n"
        ".Lrtbc_zero_host:\n"
        "  mov $" RT_STR(RT_TLS_REFUSE_HOST_ZERO) ", %edi\n"     /* raw refusal: host base zero */
        ".Lrtbc_host_refuse:\n"
        "  and $-16, %rsp\n"                              /* raw refusal; no return, alignment still matters */
        "  call rt_tls_host_base_refuse\n"
        "  ud2\n"
        ".Lrtbc_restore:\n"
        "  wrfsbase %r11\n"
        "  mov %r12, %rsp\n"
        "  pop %r15\n  pop %r14\n  pop %r13\n  pop %r12\n  pop %rbx\n  pop %rbp\n"
        "  ret\n"
        ".Lrtbc_no_tls:\n"
        "  sub $8, %rsp\n"                                /* host rsp is 8 mod 16 after six pushes */
        "  call rt_boot_call_no_guest_tls\n"
        "  ud2\n"
        ".Lrtbc_bad_stack:\n"
        "  mov %rdx, %rdi\n"
        "  and $-16, %rsp\n"
        "  call rt_boot_call_bad_stack\n"
        "  ud2\n");
