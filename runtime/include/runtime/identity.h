/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RT_IDENTITY_H
#define RT_IDENTITY_H
#include <stddef.h>
/* Prints "pbboot sha256 <12 hex>" for the running executable, so a run states what it measured. */
void rt_announce_identity(void);

/* The running executable's sha256 prefix, computed once; safe to call from a report path. */
const char *rt_identity_sha(void);

/* 12-hex sha256 prefix of an arbitrary file into out[13]; 0 on success, -1 if it cannot be read.
   Used so the plugin's identity comes from the binary that loads it, not from the wrapper that launched it:
   a run has to be attributable when someone invokes pbboot directly, not only through tools/boot.sh. */
int rt_identity_file_sha(const char *path, char out[13]);
/* Hash the bytes a caller already holds, so a loader can attest exactly what it parses. One open with
   hash-then-load is one open and two reads; only one read is one subject. */
int rt_identity_bytes_sha(const void *data, size_t len, char out[13]);
#endif
