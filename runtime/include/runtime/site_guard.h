/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RUNTIME_SITE_GUARD_H
#define RUNTIME_SITE_GUARD_H

/* Three biases live in this repository and none is interchangeable:
     guest - 0x3fc000          -> FILE offset (p_offset = 0x4000)
     guest - 0x400000          -> IMAGE offset, which is what install_hook takes
     the host mapping at 0x800000000 -> a third thing entirely
   A patch off by 0x4000 lands 16 KiB into a different function: it reads back, passes the exec check, and fires
   at a site nobody selected. One function computes the bias so no caller re-derives it.

   This lives in its own header on purpose. `guest.h` is a defining file for pinned functions, so editing it
   stales every pin that includes it -- the shared-file pin is a deliberate tree-wide decision and not something
   a helper is allowed to spend. */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RT_SITE_EBOOT_BASE 0x400000u

static inline uint64_t rt_image_offset(uint64_t guest_address)
{
    return guest_address - (uint64_t)RT_SITE_EBOOT_BASE;
}

/* The right function has the right prologue; a shifted patch generally does not. Refuse rather than patch. */
static inline int rt_site_matches(const unsigned char *image, uint64_t image_size, uint64_t guest_address,
                                  const unsigned char *expected, uint64_t n)
{
    const uint64_t offset = rt_image_offset(guest_address);
    if (!image || !expected || n == 0) return 0;                  /* nothing to compare is not agreement */
    if (offset > image_size || n > image_size - offset) return 0;  /* outside the image is not a match */
    for (uint64_t k = 0; k < n; k++)
        if (image[offset + k] != expected[k]) return 0;
    return 1;
}

#ifdef __cplusplus
}
#endif

#endif
