/* SPDX-License-Identifier: GPL-2.0-or-later */
/* The C PRNG, modelled deterministically.

   The guest seeds from clock_gettime, which this runtime has already made deterministic, so a fixed
   algorithm here keeps two boots equal. The sequence is the POSIX example LCG (1103515245/12345), NOT
   glibc's rand(): the guest's libc is FreeBSD's, and no measured caller compares a value against a
   constant. If a caller is measured comparing one, this body is wrong and the comparison names it.

   srand takes one unsigned int. The unimplemented wall printed a sema handle in rdi because the stub
   clobbers the argument registers before the host reporter reads them; the return address was the
   reliable part, which is why this body names the caller it was written for. */
#include "runtime/syslib.h"

#include <stdint.h>

static uint32_t rand_state = 1;

static void srand_impl(uint32_t seed)
{
    rand_state = seed;
}

static int rand_impl(void)
{
    rand_state = rand_state * 1103515245u + 12345u;
    return (int)((rand_state >> 16) & 0x7fffu);
}

RT_SYSLIB_MODELLED("libc", srand, srand_impl);
RT_SYSLIB_MODELLED("libc", rand, rand_impl);
