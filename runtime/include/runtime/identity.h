/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RT_IDENTITY_H
#define RT_IDENTITY_H
/* Prints "pbboot sha256 <12 hex>" for the running executable, so a run states what it measured. */
void rt_announce_identity(void);

/* The running executable's sha256 prefix, computed once; safe to call from a report path. */
const char *rt_identity_sha(void);
#endif
