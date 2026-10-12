// SPDX-License-Identifier: GPL-2.0-or-later
// Kernel: a bounds-checked read out of a small constant table in .rodata.
//
// kernel_index_code (0x004664e0) maps a small index to a code word. The table is seven 32-bit
// entries in the executable's read-only data at 0x02fc5480, and the function is a leaf: it makes
// no calls and writes nothing.
//
//   index <= 6          the entry at that index
//   index > 6           0x2bc
//
// The bound is unsigned. The original compares `cmp edi,0x6; ja`, so a negative index -- whose
// bit pattern is above 6 when read unsigned -- takes the default rather than indexing backwards
// into the table, and the index is sign-extended only after it has passed the test.
//
// Two values appear twice in the table, so some cases are weaker than they look: 0x100 at indices
// 0 and 1, and 0x2ff at 5 and 6. Index 6 in particular cannot reveal an off-by-one in the bound,
// because the entry at 6 and the default are both 0x2ff; index 7 is the case that does, and
// 0x2bc is likewise both the default and the entry at index 3.
//
// The load is `mov eax,dword ptr [rcx+rax*4]`, a 32-bit zero-extending read, so the full 64-bit
// return is the code with a zero high half. The table is addressed as a PS4 address and translated
// once through rt::ptr; the table itself is never written.
#include <cstdint>

#include "runtime/guest.h"

namespace {

// The table's seven entries, read from the shipped image: 0x100, 0x100, 0x28a, 0x2bc, 0x2ee, 0x2ff,
// 0x2ff.
constexpr uint32_t table_address = 0x02fc5480;
constexpr uint32_t table_entries = 7;
constexpr uint32_t out_of_range = 0x2bc;

}  // namespace

extern "C" uint64_t bb_kernel_index_code(uint32_t index)
{
    if (index >= table_entries) {
        return out_of_range;
    }
    return rt::ptr<const uint32_t>(table_address)[index];
}
