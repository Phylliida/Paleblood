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

   Measured, not assumed: the 15 bytes of the movsx_deref row were found in eboot.elf at file offset
   0x1573030 and nowhere else; its catalogue address minus 0x400000 plus 0x4000 is 0x1573030. The exact
   row identity lives in docs/addressing.md, not here: runtime/ may not carry a tracked address, even in
   a comment (tools/check_agnostic.py). The entry point reads 0xa0 in the
   ELF header and the docs quote it as 0x004000a0. A fix for a cross-space comparison (032) originally
   compared a runtime address against kPs4ImageBase and rejected a true guest address; that is why this header
   exists.

   WORKED EXAMPLES, both wrong numbers this campaign actually published or nearly published:

   1. `0x53E5B38` is vaddr + filesz: the image-space end of the RW segment. It was carried as a guest/
      catalogue address and retracted as one base short; the catalogue value is 0x57e5b38. It is also the
      INIT_ARRAY address in `readelf -dW`, but that coincidence is not evidence about the boundary. Three
      frames, three values: image 0x53e5b38, file 0x53e9b38, guest 0x57e5b38.
   2. A disassembler prints a RIP-relative target in VADDR space. `add 0x2da9110(%rip),%rax # 0x53e4328`
      is entry code reaching eboot's TLS init slot: at file 0x53e8328 the eight bytes are 70 f9 ff ff ff ff
      ff ff = -0x690, landing the following store at fs-0x690 inside eboot's 0x750-byte TLS block. Read the
      same digits in CATALOGUE space (file 0x4fe8328) and you get -240564068892484384. Same digits, two
      spaces: the label is the whole difference, which is why rg_* conversions exist and why a printed
      coordinate now carries both. */

#define kGuestExecBase 0x800000000ull /* eboot's image start at execution time */
#define kPs4ImageBase  0x400000u      /* PS4/catalogue space bias */
#define kImageFileBias 0x4000u        /* file offset = vaddr + this */

static inline uint64_t rt_runtime_to_vaddr(uint64_t a) { return a - kGuestExecBase; }
static inline uint64_t rt_vaddr_to_catalogue(uint64_t v) { return v + (uint64_t)kPs4ImageBase; }
static inline uint64_t rt_catalogue_to_file(uint64_t c) { return c - (uint64_t)kPs4ImageBase + kImageFileBias; }
static inline uint64_t rt_vaddr_to_runtime(uint64_t v) { return kGuestExecBase + v; }

#endif
