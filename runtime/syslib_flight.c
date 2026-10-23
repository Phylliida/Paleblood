#include <stdint.h>
#include "runtime/inflight.h"

volatile uint32_t rt_syslib_in_flight = 0xffffffffu;
