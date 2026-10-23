// SPDX-License-Identifier: GPL-2.0-or-later
#include "load_base.h"

// The single definition. Default 0 is the in-game semantics: Map is identity or refusal, so a body
// that dereferences this base with the value unset faults rather than reading a harness-only mapping.
extern "C" std::uintptr_t pbl_image_base = 0;
