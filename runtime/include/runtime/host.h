/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RUNTIME_HOST_H
#define RUNTIME_HOST_H

/* The loader interface of the runtime scaffold (third_party/bbport, src/bbgame.h), version 1.
   Mirrored here so this repository builds without the scaffold; the version is checked. */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RT_HOST_API_VERSION 1u

/* install_hook's return codes. 0 means installed. RT_INSTALL_NO_ROOM means the instrument could not
   be PLACED -- the shared stub page, a boundary stub, or the capture table's slots are full -- which
   is a coverage gap the caller prints and walks past: the body then runs as shipped, which is a
   smaller truth than refusing every hook in the table. The caller must not name one exhausted
   resource when install_hook can refuse for three. Every other nonzero value means the site could not
   be instrumented HONESTLY (readback disagrees, the wrapper would not emit), which is a lie about the
   subject and must stop the install. */
#define RT_INSTALL_NO_ROOM (-2)

typedef struct {
    uint32_t version;
    unsigned char *image;      /* host address of guest offset 0 (ELF p_vaddr 0) */
    uint64_t image_size;
    int (*install_hook)(uint64_t offset, uint64_t size, const void *target);
} rt_host;

/* Called by the loader before any game code runs: checks the version, records the image,
   installs every hook of the generated table. Returns 0 or nonzero to stop the loader. */
int bbgame_init(const rt_host *host);

#ifdef __cplusplus
}
#endif

#endif
