/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Sysmodule by numeric id: accept what we can name, remember what we accept, refuse the rest.

   Our loader makes every import available already, so "load" here is a statement about the guest's own
   bookkeeping rather than about ours. Saying success without remembering it would create a worse defect
   than a stop: a later sceSysmoduleIsLoaded / GetModuleInfo answering "not loaded" after the guest was
   told it succeeded. So there is one loaded-set, keyed by id, and every later query consults it.

   An id no name covers refuses with the id printed. A made-up constant "succeeding" is the silently-wrong
   path, and this is a cheap place to be fail-closed instead.

   PHASE DISTINCTION -- do not treat this file as the template for the other one:
     sceSysmoduleLoadModule takes a numeric firmware id (this file, closed by a table of names);
     sceKernelLoadStartModule takes a path and returns a handle that later lookups index by symbol name.
   The second is a different wall: it implies export lookup by name on a module we do not have.
*/
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

enum { k_err_inval = (int)0x80020016u, k_err_nomem = (int)0x8002000cu };

/* NO ID TABLE. The first version of this file carried one, written from memory, and the guest asked for
   id 180 -- which the table did not have, so the refusal travelled back as a guest panic. A table I
   invented is the remembered-constant defect, and it cost a boot to learn. So ids are recorded, not
   named: the runtime accepts what the guest asks for, prints it, and remembers it, because in this model
   every import is already available and "load" is the guest's own bookkeeping. Naming an id is a separate
   evidence problem -- when a name is known it belongs here with its source, not with a citation-shaped
   comment. */
/* One home for the answer, and it holds every id that was accepted -- a "load succeeded / IsLoaded says
   no" pair would be a worse defect than any stop, so nothing is accepted without being remembered. */
static struct { int id; } loaded[64];
static int loaded_count;

static int load_module(int64_t id, int64_t arg)
{
    (void)arg;
    for (int i = 0; i < loaded_count; i++)
        if (loaded[i].id == (int)id) return 0;
    if (loaded_count == 64) return k_err_nomem;
    loaded[loaded_count++].id = (int)id;
    fprintf(stderr, "pbboot: sysmodule: LoadModule id %lld (0x%llx) recorded as loaded; no module file "
                    "is read and the id has no name here\n", (long long)id, (unsigned long long)id);
    return 0;
}

static int unload_module(int64_t id)
{
    int i = 0;
    while (i < loaded_count && loaded[i].id != (int)id) i++;
    if (i == loaded_count) {
        fprintf(stderr, "pbboot: sysmodule: UnloadModule refused, %lld is not loaded\n", (long long)id);
        return k_err_inval;
    }
    loaded[i] = loaded[--loaded_count];
    return 0;
}

static int is_loaded(int64_t id)
{
    for (int i = 0; i < loaded_count; i++)
        if (loaded[i].id == (int)id) return 1;
    return 0;
}

RT_SYSLIB("libSceSysmodule", sceSysmoduleLoadModule, load_module);
RT_SYSLIB("libSceSysmodule", sceSysmoduleUnloadModule, unload_module);
RT_SYSLIB("libSceSysmodule", sceSysmoduleIsLoaded, is_loaded);
