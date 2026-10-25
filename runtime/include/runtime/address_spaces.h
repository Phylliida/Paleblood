#ifndef RT_ADDRESS_SPACES_H
#define RT_ADDRESS_SPACES_H
#include <stdint.h>

/* FOUR coordinates are in play, and two of them have been called "base". Each constant names its space, so a
   comparison across spaces now needs a longer sentence than the correct one.

     vaddr        image-relative offset. `where()` prints it as `eboot+0x...`. Not a file offset.
     catalogue    PS4 space = vaddr + kPs4ImageBase. THIS is what symbols/functions.csv and
                  symbols/ghidra_functions.csv are written in, and what docs quote as 0x004000a0.
     runtime      an actual pointer at execution = kGuestExecBase + vaddr. What the guest hands us.
     file offset  vaddr + kImageFileBias = catalogue - 0x3FC000.

   Measured, not assumed: the 15 bytes of catalogue row 0x0196f030 were found in eboot.elf at file offset
   0x1573030 and nowhere else; 0x0196f030 - 0x400000 + 0x4000 = 0x1573030. The entry point reads 0xa0 in the
   ELF header and the docs quote it as 0x004000a0. A fix for a cross-space comparison (032) originally
   compared a runtime address against kPs4ImageBase and rejected a true guest address; that is why this header
   exists. */

#define kGuestExecBase 0x800000000ull /* eboot's image start at execution time */
#define kPs4ImageBase  0x400000u      /* PS4/catalogue space bias */
#define kImageFileBias 0x4000u        /* file offset = vaddr + this */

static inline uint64_t rt_runtime_to_vaddr(uint64_t a) { return a - kGuestExecBase; }
static inline uint64_t rt_vaddr_to_catalogue(uint64_t v) { return v + (uint64_t)kPs4ImageBase; }
static inline uint64_t rt_catalogue_to_file(uint64_t c) { return c - (uint64_t)kPs4ImageBase + kImageFileBias; }
static inline uint64_t rt_vaddr_to_runtime(uint64_t v) { return kGuestExecBase + v; }

#endif
