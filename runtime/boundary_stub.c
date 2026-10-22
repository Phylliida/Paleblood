#include "runtime/boundary_stub.h"

#include <string.h>

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
