// SPDX-License-Identifier: GPL-2.0-or-later
// The ONE definition of the two facts every generated based body needs: the guest load base as a
// named constant (the style gate refuses a bare 0x400000, and it was right to), and the image base
// the differential runner supplies.
//
// Why a header + a defining translation unit rather than a definition in the header:
//   * a weak definition in a header leans on linker coalescing, which is a rule I would be trusting
//     rather than checking;
//   * an inline variable gets vague linkage, whose dynamic export varies by compiler and flags;
//   * two definitions in one link collide, and a `static` per translation unit gives the runner a
//     symbol it cannot set.
// One definition, one export, and load_base.cpp becomes a file that must stay in the build -- which
// is what the nm -D assertion on the artifact checks.
//
// The mechanism this serves was dormant for two commits: pbl_image_base and kGuestLoadBase existed
// only inside game/leaf/rip_load_family.cpp, and withdrawing that family (f511666) removed both, so
// every comparison reported image_base_set = False and no test noticed, because the test compiled its
// own library. A fixture that vendors the property cannot notice the property leaving the product.
// Two runners read this tree and they are not equally strong: `unittest discover -s test`
// imports the whole module, while running a test file directly stops at its entry point -- so a
// class appended after `if __name__ == '__main__'` is invisible to the direct run and collected
// by the suite. A direct run is the weaker check wearing the stronger one's name.

#ifndef BB_LEAF_LOAD_BASE_H
#define BB_LEAF_LOAD_BASE_H

#include <cstdint>

// 0x400000 is the value; this name is the meaning. The gate's readability check refuses the bare
// literal in game/, and it refused it 161 times on the last family.
inline constexpr std::uintptr_t kGuestLoadBase = 0x400000;

// Set ONCE by the differential runner (tools/harness.py:load_replacement) to IMAGE, the address at
// which the harness maps the guest image. Default 0 is the in-game value: unmapped means a based
// body faults loudly instead of silently reading the instrument's own mapping.
extern "C" std::uintptr_t pbl_image_base;

#endif  // BB_LEAF_LOAD_BASE_H
