#ifndef RT_INFLIGHT_H
#define RT_INFLIGHT_H
#include <stdint.h>

/* The import currently crossing into the runtime, or 0xffffffff for "none". It lives in its own
   translation unit because two targets need it and their externs had disagreed about its SIGNEDNESS
   since the counter was introduced: boot.c defined `volatile uint32_t`, libc.c declared
   `volatile int32_t`. The linker cannot see signedness, the code that reads it can, and boot.c already
   casts to int32_t to read the negative sentinel. Declared once here so no third spelling can appear. */
extern volatile uint32_t rt_syslib_in_flight;

#endif
