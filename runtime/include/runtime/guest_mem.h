/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RT_GUEST_MEM_H
#define RT_GUEST_MEM_H
#include <stddef.h>
#include <stdint.h>
/* Returns 1 if [addr, addr+len) lies inside the guest image and a system call may write it; otherwise
   prints the refusal with both the address and the bounds, and returns 0. */
int rt_guest_write_ok(uintptr_t addr, size_t len, const char *call);
int rt_guest_ptr_ok(uintptr_t addr, size_t len, const char *call);
/* Register a mapping the runtime handed the guest outside the ELF image (flexible memory). The bounds
   checks below accept writes inside a registered mapping; a pointer there is a guest pointer even though
   it is not an image offset. Returns 1 on success, 0 when the table is full. */
int rt_guest_register_mapping(uintptr_t base, size_t len);
/* Bytes from addr to the end of the guest region containing it (the image or a registered mapping), or
   0 when addr is in neither. A caller that walks a guest string needs the span, not just a yes/no. */
size_t rt_guest_span(uintptr_t addr);
#endif
