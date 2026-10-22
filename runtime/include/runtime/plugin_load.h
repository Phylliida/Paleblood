/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RUNTIME_PLUGIN_LOAD_H
#define RUNTIME_PLUGIN_LOAD_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Load the game plugin and hand it a REAL installer.

   dlopen, dlsym("bbgame_init"), call it, report the count. One function so that the endpoint is proved in a test
   binary before pbboot has a caller: the first pbboot run must not also be the first execution of the loader path.
   Returns 0 on success, non-zero on every refusal, and prints one sentence per cause -- four causes, four sentences,
   because the person reading the log gets one line and must be able to tell them apart. */
int rt_boot_load_plugin(void *image, uint64_t image_size, const char *path, unsigned *hooks_installed);

#ifdef __cplusplus
}
#endif

#endif
