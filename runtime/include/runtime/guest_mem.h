/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RT_GUEST_MEM_H
#define RT_GUEST_MEM_H
#include <stddef.h>
#include <stdint.h>
/* Returns 1 if [addr, addr+len) lies inside the guest image and a system call may write it; otherwise
   prints the refusal with both the address and the bounds, and returns 0. */
int rt_guest_write_ok(uintptr_t addr, size_t len, const char *call);
#endif
