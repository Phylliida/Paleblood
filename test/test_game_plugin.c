/* SPDX-License-Identifier: GPL-2.0-or-later */
/* A stand-in game plugin built as a shared library: exports bbgame_init and installs exactly one hook. */
#include "runtime/host.h"

int bbgame_init(const rt_host *host)
{
    if (!host || !host->install_hook) return 1;
    /* Offset 0 of the image, the full patch width. The target only has to be a non-null code pointer. */
    return host->install_hook(0, 16, (const void *)bbgame_init) == 0 ? 0 : 1;
}
