/* SPDX-License-Identifier: GPL-2.0-or-later */
/* A library that loads fine and exports nothing: the dlsym failure must be its own sentence. */
int not_the_entry_point(void) { return 0; }
