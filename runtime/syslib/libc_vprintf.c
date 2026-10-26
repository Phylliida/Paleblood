/* SPDX-License-Identifier: GPL-2.0-or-later */
/* libSceLibcInternal vprintf: hand the guest's format and va_list to the host's vprintf.

   The boot reached vprintf at eboot+0x20dfb02 (catalogue 0x24dfb02). The guest's ABI for va_list on
   x86-64 SysV is the same array-of-struct pointer the host compiler passes, so the body forwards the
   pointer it was given; it does not copy or rebuild the list. This is a forwarding body, not a model:
   the value printed is the guest's own, and the format string is the guest's own. Output goes to the
   host stdout, which is where the runtime's other guest-visible messages go; the guest's stdio stream
   objects are unbound data imports and are not involved. */
#include "runtime/syslib.h"

#include <stdarg.h>
#include <stdio.h>

static int libc_vprintf(const char *fmt, va_list ap)
{
    return vprintf(fmt, ap);
}

/* The wall prints the library as `libc` (the name in eboot's import record), while
   symbols/import_names.csv lists the provider as libSceLibcInternal. The registry keys on the
   guest's library string, which is what every other libc body here uses; register both spellings so
   the lookup cannot depend on which of the two tables is authoritative. */
RT_SYSLIB("libc", vprintf, libc_vprintf);
RT_SYSLIB("libSceLibcInternal", vprintf, libc_vprintf);
