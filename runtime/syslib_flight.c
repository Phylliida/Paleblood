#include <stdint.h>
#include "runtime/inflight.h"

volatile uint32_t rt_syslib_in_flight = 0xffffffffu;

/* A library-only link (test_syslib, libbbgame without pbboot) has no import trampoline, so it has no captured
   guest PC. Zero is the honest answer there: the refusal prints "call site not captured" rather than a host
   address wearing a guest label. pbboot's strong definition wins in every link that HAS the trampoline. */
__attribute__((weak)) uint64_t rt_guest_call_pc(void) { return 0; }
