#include "runtime/boundary_stub.h"

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

size_t rt_boundary_stub_size(uint64_t in_flight_addr)
{
    /* 10 movabs target + 10 movabs host + 5 wrfsbase + 1 push + 3 mov rbx,rsp + 4 and rsp + 3 call
       + 3 mov rsp,rbx + 1 pop + 10 movabs guest + 5 wrfsbase + 1 ret = 56, plus 22 for the import
       path's bookkeeping word. */
    return 56u + (in_flight_addr ? 22u : 0u);
}

size_t rt_write_boundary_stub(unsigned char *dst, size_t capacity, uint64_t target, uint64_t host_fs, uint64_t guest_fs,
                              uint64_t in_flight_addr)
{
    /* Refuse before the first store: a bound checked after the write is a report about an overrun. */
    const size_t needed = rt_boundary_stub_size(in_flight_addr);
    if (!dst || capacity < needed) return 0;

    unsigned char *p = dst;

    /* r10 and r11 are caller-saved and carry no arguments in the System V convention, so the guest
       cannot hold anything live in them across its call: no saves, no restores, no hazard. */
    *p++ = 0x49, *p++ = 0xba, memcpy(p, &target, 8), p += 8;           /* movabs r10, target */
    *p++ = 0x49, *p++ = 0xbb, memcpy(p, &host_fs, 8), p += 8;          /* movabs r11, host %fs base */
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
    *p++ = 0x49, *p++ = 0xbb, memcpy(p, &guest_fs, 8), p += 8;         /* movabs r11, guest %fs base */
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

size_t rt_snapshot_stub_size(int capturing)
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
    return capturing ? 88u : 5u; /* 88 = capture form + entry counter; 5 = e9 rel32 */
}

size_t rt_write_snapshot_stub(unsigned char *dst, size_t capacity, uint64_t self_addr, uint64_t stub_addr,
                              uint64_t host_fs, uint64_t guest_fs, uint64_t entered_addr, int capturing)
{
    const size_t needed = rt_snapshot_stub_size(capturing);
    /* Refuse before the first store, and refuse an unsatisfiable size: capacity < SIZE_MAX is every
       capacity, so B cannot be installed by accident before it is written. */
    if (!dst || !self_addr || !stub_addr || capacity < needed) return 0;
    if (capturing && !entered_addr) return 0;   /* the counter is part of the form, not an option */

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
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &host_fs, 8), p += 8;      /* movabs r11, host %fs */
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
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &guest_fs, 8), p += 8;     /* movabs r11, guest %fs */
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
