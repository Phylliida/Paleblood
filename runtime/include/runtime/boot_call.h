/* Enter guest code on the guest stack, swapping %fs from the calling thread's host TCB to its guest
   block. Defined in boot_call.c so a test can exercise the selector decision without linking boot.c. */
#include <stdint.h>
uint64_t rt_boot_call(void *fn, void *a, void *stack_top, void *b, void *c);
