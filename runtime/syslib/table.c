/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime/syslib.h"

/* The linker gathers every RT_SYSLIB entry into the section "rt_syslib" and defines these bounds.
   An empty table still links: the weak bounds then stay null. */

const rt_syslib_entry *rt_syslib_begin(void) { return __start_rt_syslib; }
const rt_syslib_entry *rt_syslib_end(void) { return __stop_rt_syslib; }

#include <stdio.h>
#include <string.h>

unsigned rt_syslib_check_unique(const rt_syslib_entry *begin, const rt_syslib_entry *end)
{
    unsigned dup = 0;
    if (!begin || !end) return 0;
    for (const rt_syslib_entry *a = begin; a < end; a++) {
        if (!a->library || !a->symbol) continue;
        for (const rt_syslib_entry *b = a + 1; b < end; b++) {
            if (!b->library || !b->symbol) continue;
            if (strcmp(a->library, b->library) || strcmp(a->symbol, b->symbol)) continue;
            fprintf(stderr, "syslib: duplicate (library, symbol) = (%s, %s): entry %zu [%p] keeps the key, "
                            "entry %zu [%p] never runs\n",
                    a->library, a->symbol, (size_t)(a - begin), a->fn, (size_t)(b - begin), b->fn);
            dup++;
        }
    }
    return dup;
}
