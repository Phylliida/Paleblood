#include "runtime/boundary_stub.h"
#include "runtime/tls.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* The site identity costs no bytes and no alignment: this takes the six uint64_t arguments rdi..r9 already hold,
   so the emitter needs no argument setup, and it learns WHICH site it is from the return address, which lies
   inside a per-site wrapper. A seventh `site` argument would have needed `sub rsp,16; mov [rsp],site` to keep
   the alignment the push-rbx/and-rsp idiom establishes; that form is not in the bytes. */
void rt_capture_snapshot_c(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5);
static uint64_t g_capture_entry_sp __attribute__((used));

/* Save the stack pointer at the wrapper's `call`, before the C prologue moves it, then jump to the
   reporting body. Measuring rsp inside a normal C function measured the compiler's push rbp, not the
   wrapper's call site: it printed MISALIGNED on a correctly aligned call and could never witness the
   defect it was written for. A naked entry point with a jmp preserves both the return address and the
   six argument registers. */
__attribute__((naked)) void rt_capture_snapshot(
    uint64_t a0 __attribute__((unused)), uint64_t a1 __attribute__((unused)),
    uint64_t a2 __attribute__((unused)), uint64_t a3 __attribute__((unused)),
    uint64_t a4 __attribute__((unused)), uint64_t a5 __attribute__((unused)))
{
    __asm__ volatile("movq %rsp, g_capture_entry_sp(%rip)\n\t"
                     "jmp rt_capture_snapshot_c\n\t");
}

void rt_capture_snapshot_c(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5)
{
    const uintptr_t sp = (uintptr_t)g_capture_entry_sp;
    const uintptr_t ret = (uintptr_t)__builtin_return_address(0);
    /* The assertion the /3-class defect would have failed in one line: the callee must see rsp == 8 (mod 16). */
    const unsigned align = (unsigned)(sp & 15u);
    fprintf(stderr, "capture: site wrapper(%#llx) rsp%%16=%u (expect 8) %s | rdi=%#llx rsi=%#llx rdx=%#llx "
                    "rcx=%#llx r8=%#llx r9=%#llx\n",
            (unsigned long long)ret, align, align == 8u ? "aligned" : "MISALIGNED", (unsigned long long)a0,
            (unsigned long long)a1, (unsigned long long)a2, (unsigned long long)a3, (unsigned long long)a4,
            (unsigned long long)a5);
}

/* mov r11, qword ptr gs:[off] -- 65 4c 8b 1c 25 <disp32>. The displacement is asserted against
   offsetof(struct rt_tls_thread, ...) in tls.c, so this is a constant the build checks rather than a
   number copied into an emitter. */
static unsigned char *stub_mov_r11_gs(unsigned char *p, uint32_t off)
{
    *p++ = 0x65;
    *p++ = 0x4c;
    *p++ = 0x8b;
    *p++ = 0x1c;
    *p++ = 0x25;
    memcpy(p, &off, 4), p += 4;
    return p;
}

size_t rt_tls_check_size(void)
{
    /* rdgsbase 5 + test 3 + jz 2 + mov gs:0x40,r11 9 + movabs magic 10 + cmp 3 + jne 2 + xor eax,eax 2
       + ret 1 = 37; zero arm mov edi,0x11 5 + xor esi,esi 2 + jmp 2 = 9; foreign arm mov gs:0x40,rsi 9
       + mov edi,0x12 5 = 14; fail arm movabs fail 10 + call *r11 3 + ud2 2 = 15. Total 75. */
    return 75u;
}

size_t rt_write_tls_check(unsigned char *dst, size_t capacity, uint64_t fail_addr)
{
    const size_t needed = rt_tls_check_size();
    if (!dst || !fail_addr || capacity < needed) return 0;
    const uint64_t magic = RT_TLS_MAGIC;
    const uint32_t zero_reason = RT_TLS_REFUSE_SELECTOR_ZERO;
    const uint32_t foreign_reason = RT_TLS_REFUSE_FOREIGN_STATE;
    unsigned char *p = dst;

    *p++ = 0xf3, *p++ = 0x49, *p++ = 0x0f, *p++ = 0xae, *p++ = 0xcb; /* rdgsbase r11 */
    *p++ = 0x4d, *p++ = 0x85, *p++ = 0xdb;                            /* test r11,r11 */
    *p++ = 0x74, *p++ = 0x1b;                                         /* jz zero (+27 from next) */
    p = stub_mov_r11_gs(p, RT_TLS_GS_MAGIC_OFF);                      /* mov r11, gs:[0x40] */
    *p++ = 0x49, *p++ = 0xba, memcpy(p, &magic, 8), p += 8;           /* movabs r10, MAGIC */
    *p++ = 0x4d, *p++ = 0x39, *p++ = 0xd3;                            /* cmp r10,r11 */
    *p++ = 0x75, *p++ = 0x0c;                                         /* jne foreign (+12) */
    *p++ = 0x31, *p++ = 0xc0;                                         /* xor eax,eax */
    *p++ = 0xc3;                                                      /* ret */
    /* zero: exit 134, reason 0x11, observed 0. */
    *p++ = 0xbf, memcpy(p, &zero_reason, 4), p += 4;                  /* mov edi, 0x11 */
    *p++ = 0x31, *p++ = 0xf6;                                         /* xor esi,esi */
    *p++ = 0xeb, *p++ = 0x0e;                                         /* jmp fail (+14) */
    /* foreign: observed magic in rsi, reason 0x12. */
    *p++ = 0x65, *p++ = 0x48, *p++ = 0x8b, *p++ = 0x34, *p++ = 0x25;
    {
        const uint32_t off = RT_TLS_GS_MAGIC_OFF;
        memcpy(p, &off, 4), p += 4;                                   /* mov rsi, gs:[0x40] */
    }
    *p++ = 0xbf, memcpy(p, &foreign_reason, 4), p += 4;               /* mov edi, 0x12 */
    /* fail: no return. The helper is absolute, so this is a 64-bit address, not a rel32. */
    *p++ = 0x49, *p++ = 0xbb, memcpy(p, &fail_addr, 8), p += 8;       /* movabs r11, fail */
    *p++ = 0x41, *p++ = 0xff, *p++ = 0xd3;                            /* call *r11 */
    *p++ = 0x0f, *p++ = 0x0b;                                         /* ud2 */
    return (size_t)(p - dst);
}

size_t rt_boundary_stub_size(uint64_t in_flight_addr, int per_thread, uint64_t check_addr)
{
    /* per-thread: checker call 5 + 10 movabs target + 9 gs load + 5 wrfsbase + 1 push + 3 mov rbx,rsp
       + 4 and rsp + 3 call + 3 mov rsp,rbx + 1 pop + 9 gs load + 5 wrfsbase + 1 ret = 59.
       baked: 10 + 10 + 5 + 1 + 3 + 4 + 3 + 3 + 1 + 10 + 5 + 1 = 56. Both plus 22 for the import
       path's bookkeeping word. A per-thread form with no checker is unemittable, and says so as 0. */
    if (per_thread && !check_addr) return 0;
    return (per_thread ? 59u : 56u) + (in_flight_addr ? 22u : 0u);
}

size_t rt_write_boundary_stub(unsigned char *dst, size_t capacity, uint64_t target, uint64_t host_fs, uint64_t guest_fs,
                              uint64_t in_flight_addr, int per_thread, uint64_t check_addr)
{
    /* Refuse before the first store: a bound checked after the write is a report about an overrun. */
    const size_t needed = rt_boundary_stub_size(in_flight_addr, per_thread, check_addr);
    if (!dst || needed == 0 || capacity < needed) return 0;
    if (per_thread) {
        const int64_t delta = (int64_t)check_addr - (int64_t)((uintptr_t)dst + 5);
        if (delta > INT32_MAX || delta < INT32_MIN) return 0;
    }

    unsigned char *p = dst;

    /* The gate is the FIRST instruction. The checker clobbers r10/r11, and the stub's target lives in
       r10: putting this call after `movabs r10,target` would destroy the target it was called to make
       safe. It also precedes the first %gs read by construction, which is the property child B measured
       at 0x28 before this call existed. */
    if (per_thread) {
        const int64_t delta = (int64_t)check_addr - (int64_t)((uintptr_t)p + 5);
        const int32_t rel = (int32_t)delta;
        *p++ = 0xe8;                                                   /* call check_addr */
        memcpy(p, &rel, 4), p += 4;
    }
    /* r10 and r11 are caller-saved and carry no arguments in the System V convention, so the guest
       cannot hold anything live in them across its call: no saves, no restores, no hazard. */
    *p++ = 0x49, *p++ = 0xba, memcpy(p, &target, 8), p += 8;           /* movabs r10, target */
    if (per_thread) {
        /* A child never sees main's base: read the current thread's state, which is the only subject. */
        p = stub_mov_r11_gs(p, RT_TLS_GS_HOST_FSBASE_OFF);
    } else {
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &host_fs, 8), p += 8;      /* movabs r11, host %fs base */
    }
    /* F3 is mandatory and the ModRM /2 field names the register: 0xd3 is wrfsbase r11, 0xdb is
       wrgsbase r11. The 0xdb form is legal, silent, and writes the wrong register. */
    *p++ = 0xf3, *p++ = 0x49, *p++ = 0x0f, *p++ = 0xae, *p++ = 0xd3;   /* wrfsbase r11 */
    /* The guest's stack alignment at its call site is the guest's business; a C body needs the ABI's,
       and glibc spills xmm with movaps, which faults on a misaligned rsp and reports address 0. rbx
       carries the guest's rsp because it is callee-saved: a global would be wrong the moment a body
       re-enters another import. */
    *p++ = 0x53;                                                       /* push rbx */
    *p++ = 0x48, *p++ = 0x89, *p++ = 0xe3;                             /* mov rbx, rsp */
    *p++ = 0x48, *p++ = 0x83, *p++ = 0xe4, *p++ = 0xf0;                /* and rsp, -16 */
    *p++ = 0x41, *p++ = 0xff, *p++ = 0xd2;                             /* call r10 */
    *p++ = 0x48, *p++ = 0x89, *p++ = 0xdc;                             /* mov rsp, rbx */
    *p++ = 0x5b;                                                       /* pop rbx */
    if (per_thread) {
        p = stub_mov_r11_gs(p, RT_TLS_GS_GUEST_BLOCK_OFF);
    } else {
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &guest_fs, 8), p += 8;     /* movabs r11, guest %fs base */
    }
    *p++ = 0xf3, *p++ = 0x49, *p++ = 0x0f, *p++ = 0xae, *p++ = 0xd3;   /* wrfsbase r11 */
    if (in_flight_addr) {
        /* Bookkeeping, not boundary: the import path records which import is running and clears it
           here. Emitted after the ABI segment is complete, so it cannot move a register the crossing
           depends on. */
        const uint32_t none = 0xffffffffu;
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &in_flight_addr, 8), p += 8;   /* movabs r11, &in_flight */
        *p++ = 0x41, *p++ = 0xc7, *p++ = 0x03, memcpy(p, &none, 4), p += 4; /* mov dword [r11], -1 */
    }
    *p++ = 0xc3;                                                       /* ret */
    return (size_t)(p - dst);
}

size_t rt_snapshot_stub_size(int capturing, int per_thread, uint64_t check_addr)
{
    /* Commit A emits only the empty form. The capture form (+ six pushes, movabs host, wrfsbase,
       movabs snapshot, call, six pops) is Commit B; until its bytes exist, its size is UNSATISFIABLE
       rather than a number, because a capacity refusal proved against a guessed size stops covering
       the form it is not checking -- and here it would be the form that is not emitted at all. */
    /* Commit B's capture form, byte by byte, because the size is a claim about those bytes:
         6 pushes (rdi,rsi,rdx,rcx,r8,r9)      8
         movabs r11, host %fs                 10
         wrfsbase r11                          5
         push rbx / mov rbx,rsp / and rsp,-16  8
         movabs rax, snapshot                 10   <- the SITE IDENTITY COSTS NO BYTES:
         call rax                              2      the snapshot takes exactly the six uint64_t
         mov rsp,rbx / pop rbx                 4      arguments rdi..r9 already hold at entry and learns
         movabs r11, guest %fs / wrfsbase     15      which site it is from __builtin_return_address(0),
         6 pops                                8      a return address inside a per-site wrapper.
         e9 rel32 to the boundary stub          5
        A seventh argument would need `sub rsp,16; mov [rsp],site` to keep the 16-byte alignment the
        push-rbx/and-rsp idiom exists to establish -- an 8-byte push before `call` looks right in review
        and puts the callee 8 bytes off. THAT FORM IS NOT IN THESE BYTES. */
    /* 75 + 13 for the entry counter (`movabs r11,&entered; incq [r11]`), which must run BEFORE the first push:
       a counter inside the snapshot cannot tell "never entered" from "entered and died in the prologue", and the
       /3- and rsp-class defects live in exactly those bytes. */
    if (capturing && per_thread && !check_addr) return 0;
    /* 91 = 86 per-thread + 5 for the checker call; 88 baked; 5 = e9 rel32. */
    return capturing ? (per_thread ? 91u : 88u) : 5u;
}

size_t rt_write_snapshot_stub(unsigned char *dst, size_t capacity, uint64_t self_addr, uint64_t stub_addr,
                              uint64_t host_fs, uint64_t guest_fs, uint64_t entered_addr, int capturing,
                              int per_thread, uint64_t check_addr)
{
    const size_t needed = rt_snapshot_stub_size(capturing, per_thread, check_addr);
    /* Refuse before the first store, and refuse an unsatisfiable size: capacity < SIZE_MAX is every
       capacity, so B cannot be installed by accident before it is written. */
    if (!dst || !self_addr || !stub_addr || needed == 0 || capacity < needed) return 0;
    if (capturing && !entered_addr) return 0;   /* the counter is part of the form, not an option */
    if (capturing && per_thread) {
        const int64_t delta = (int64_t)check_addr - (int64_t)((uintptr_t)dst + 21 + 5);
        if (delta > INT32_MAX || delta < INT32_MIN) return 0;
    }

    /* A near jump needs the target inside signed 32 bits of the byte after the opcode. Two pages from
       one mmap'd region are far inside that, but a far target silently needs the 14-byte absolute form
       (+9 bytes nobody budgeted), so the distance is asserted at emit time rather than assumed. */
    const int64_t delta = (int64_t)stub_addr - (int64_t)(self_addr + needed);
    if (delta > INT32_MAX || delta < INT32_MIN) return 0;
    const int32_t rel = (int32_t)delta;

    unsigned char *p = dst;
    if (capturing) {
        /* Entry counter FIRST -- before the pushes, before wrfsbase. If the prologue is wrong, this is the only
           instrument that already ran, and it is read from the abort and fault paths as well as the clean one. */
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &entered_addr, 8), p += 8;   /* movabs r11, &entered */
        *p++ = 0x49, *p++ = 0xff, *p++ = 0x03;                          /* incq [r11] */
        /* The six argument registers are pushed in the order the snapshot takes them, and the snapshot
           reads them back as its parameters -- no argument setup, no seventh argument, no alignment
           change beyond the idiom already in the boundary stub. */
        *p++ = 0x57;                                                   /* push rdi */
        *p++ = 0x56;                                                   /* push rsi */
        *p++ = 0x52;                                                   /* push rdx */
        *p++ = 0x51;                                                   /* push rcx */
        *p++ = 0x41, *p++ = 0x50;                                      /* push r8 */
        *p++ = 0x41, *p++ = 0x51;                                      /* push r9 */
        if (per_thread) {
            const int64_t check_delta = (int64_t)check_addr - (int64_t)((uintptr_t)p + 5);
            const int32_t check_rel = (int32_t)check_delta;
            *p++ = 0xe8;                                               /* call check_addr */
            memcpy(p, &check_rel, 4), p += 4;
        }
        if (per_thread) {
            p = stub_mov_r11_gs(p, RT_TLS_GS_HOST_FSBASE_OFF);
        } else {
            *p++ = 0x49, *p++ = 0xbb, memcpy(p, &host_fs, 8), p += 8;  /* movabs r11, host %fs */
        }
        *p++ = 0xf3, *p++ = 0x49, *p++ = 0x0f, *p++ = 0xae, *p++ = 0xd3; /* wrfsbase r11: F3 and /2 are
                                                                          mandatory; 0xdb is /3 (wrgsbase),
                                                                          legal, silent, wrong register */
        *p++ = 0x53;                                                   /* push rbx */
        *p++ = 0x48, *p++ = 0x89, *p++ = 0xe3;                         /* mov rbx, rsp */
        *p++ = 0x48, *p++ = 0x83, *p++ = 0xe4, *p++ = 0xf0;            /* and rsp, -16 */
        const uint64_t snap = (uint64_t)(uintptr_t)&rt_capture_snapshot;
        *p++ = 0x48, *p++ = 0xb8, memcpy(p, &snap, 8), p += 8;         /* movabs rax, snapshot */
        *p++ = 0xff, *p++ = 0xd0;                                      /* call rax */
        *p++ = 0x48, *p++ = 0x89, *p++ = 0xdc;                         /* mov rsp, rbx */
        *p++ = 0x5b;                                                   /* pop rbx */
        if (per_thread) {
            p = stub_mov_r11_gs(p, RT_TLS_GS_GUEST_BLOCK_OFF);
        } else {
            *p++ = 0x49, *p++ = 0xbb, memcpy(p, &guest_fs, 8), p += 8; /* movabs r11, guest %fs */
        }
        *p++ = 0xf3, *p++ = 0x49, *p++ = 0x0f, *p++ = 0xae, *p++ = 0xd3; /* wrfsbase r11 */
        /* The pushes above are rdi, rsi, rdx, rcx, r8, r9; the pops must therefore be the reverse.
           Popping in push order restores r9 into rdi (and so on), which looks symmetrical in review and
           hands the replacement body a complete rotation of its six arguments. The capture-execution
           test calls with six distinct byte lanes; with push-order pops it returned 0x112233445566
           instead of 0x665544332211. */
        *p++ = 0x41, *p++ = 0x59;                                      /* pop r9 */
        *p++ = 0x41, *p++ = 0x58;                                      /* pop r8 */
        *p++ = 0x59;                                                   /* pop rcx */
        *p++ = 0x5a;                                                   /* pop rdx */
        *p++ = 0x5e;                                                   /* pop rsi */
        *p++ = 0x5f;                                                   /* pop rdi */
        *p++ = 0xe9;                                                   /* jmp rel32 to the boundary stub */
        memcpy(p, &rel, 4), p += 4;
        return (size_t)(p - dst);
    }
    *p++ = 0xe9;                              /* jmp rel32 */
    memcpy(p, &rel, 4), p += 4;
    return (size_t)(p - dst);                 /* 5 */
}
