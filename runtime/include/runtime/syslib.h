/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RUNTIME_SYSLIB_H
#define RUNTIME_SYSLIB_H

/* The PS4 system functions and unresolved diagnostics our runtime registers, by library and symbol
   name. The loader binds an import to an entry here when the import's NID is the entry's
   (runtime/nid.h); every other import is bound to a trampoline that stops the boot and reports it
   by name.

   Functional implementations live in runtime/syslib/<group>.c and use RT_SYSLIB. A diagnostic for
   unresolved behavior may use RT_SYSLIB_UNRESOLVED; it is registered so the call can fail loudly,
   but is not counted as implemented by tools/runtime_issues.py. Clean room: written from public
   documentation and observed behaviour, never from another emulator's code. */

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    RT_SYSLIB_CAPABILITY_UNRESOLVED = 0,
    RT_SYSLIB_CAPABILITY_IMPLEMENTED = 1,
} rt_syslib_capability;

/* What a registered entry IS, declared at the registration site rather than described in a log:
     real     -- provides the behaviour the guest asked for
     modelled -- provides a stand-in for behaviour this runtime cannot perform (fixed epoch, no module
                 file read); the guest proceeds through fabricated state and must be able to see it
     noop     -- correct only because the guest is single-threaded (blocking primitives that cannot block)
     refused  -- a named fail-loud diagnostic; never counted as implemented
   Only the declaration survives the next contributor, so the split is printed on the boot line. */
typedef enum {
    RT_SYSLIB_KIND_REAL = 0,
    RT_SYSLIB_KIND_MODELLED = 1,
    RT_SYSLIB_KIND_NOOP = 2,
    RT_SYSLIB_KIND_REFUSED = 3,
} rt_syslib_kind;

typedef struct {
    const char *library;   /* "libkernel", "libc", "libScePad", ... */
    const char *symbol;    /* "sceKernelGetProcessTime", "malloc", ... */
    void *fn;              /* called with the System V AMD64 convention, as the PS4 does */
    rt_syslib_capability capability;
    rt_syslib_kind kind;
} rt_syslib_entry;

/* All entries, from every group (gathered by the linker; see RT_SYSLIB and RT_SYSLIB_UNRESOLVED). */
const rt_syslib_entry *rt_syslib_begin(void);
const rt_syslib_entry *rt_syslib_end(void);

/* Two registrations of one (library, symbol) mean the FIRST in section order wins and the second never
   runs -- a policy nobody chose. Returns the number of duplicate keys and prints every pair with both
   section indices and both function pointers. Callers must refuse on a nonzero return. */
unsigned rt_syslib_check_unique(const rt_syslib_entry *begin, const rt_syslib_entry *end);

#define RT_SYSLIB_CAT2(a, b) a##b
#define RT_SYSLIB_CAT(a, b) RT_SYSLIB_CAT2(a, b)
#define RT_SYSLIB_REGISTER(entry, library, symbol, fn, capability, kind)                                 \
    __attribute__((used, section("rt_syslib"), aligned(sizeof(void *)))) static const rt_syslib_entry     \
        entry = {library, #symbol, (void *)(fn), capability, kind}
/* RT_SYSLIB("libkernel", sceKernelUsleep, my_usleep); at file scope. Use only when the runtime
   provides the imported behavior. tools/runtime_issues.py counts these as implemented. */
#define RT_SYSLIB(library, symbol, fn) \
    RT_SYSLIB_REGISTER(RT_SYSLIB_CAT(rt_syslib_entry_, __LINE__), library, symbol, fn, \
                       RT_SYSLIB_CAPABILITY_IMPLEMENTED, RT_SYSLIB_KIND_REAL)
/* The same registration with a declared kind; use these instead of describing the difference in a comment. */
#define RT_SYSLIB_MODELLED(library, symbol, fn)                                                          \
    RT_SYSLIB_REGISTER(RT_SYSLIB_CAT(rt_syslib_entry_, __LINE__), library, symbol, fn,                    \
                       RT_SYSLIB_CAPABILITY_IMPLEMENTED, RT_SYSLIB_KIND_MODELLED)
#define RT_SYSLIB_NOOP(library, symbol, fn)                                                              \
    RT_SYSLIB_REGISTER(RT_SYSLIB_CAT(rt_syslib_entry_, __LINE__), library, symbol, fn,                    \
                       RT_SYSLIB_CAPABILITY_IMPLEMENTED, RT_SYSLIB_KIND_NOOP)
/* A registered fail-loud diagnostic for a behavior that remains unresolved. The loader can bind
   this entry and report the specific call when reached, but runtime issue coverage must leave it
   unchecked. */
#define RT_SYSLIB_UNRESOLVED(library, symbol, fn) \
    RT_SYSLIB_REGISTER(RT_SYSLIB_CAT(rt_syslib_unresolved_entry_, __LINE__), library, symbol, fn, \
                       RT_SYSLIB_CAPABILITY_UNRESOLVED, RT_SYSLIB_KIND_REFUSED)

/* atexit handlers the guest registered and this runtime does not run (see libc.c): the guest leaves
   through its own exit import and the runtime does not re-enter guest code afterwards. Exposed so the
   exit report can print the gap as a COUNT rather than leave it inside a registration line. */
unsigned rt_libc_atexit_registered(void);
unsigned rt_libc_atexit_capacity(void);

/* Section bounds provided by the linker. Weak: a build with no entries still links. */
extern const rt_syslib_entry __start_rt_syslib[] __attribute__((weak));
extern const rt_syslib_entry __stop_rt_syslib[] __attribute__((weak));
#ifdef __cplusplus
}
#endif

#endif
