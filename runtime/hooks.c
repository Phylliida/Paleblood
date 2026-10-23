/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime/hooks.h"
#include "runtime/capture.h"

#include <stdio.h>

static const rt_hook_entry *g_table;
static size_t g_count;

int rt_hooks_install(const rt_hook_entry *table, size_t count)
{
    for (size_t i = 1; i < count; i++) {
        if (table[i].address <= table[i - 1].address)
            return -1;
    }
    g_table = table;
    g_count = count;
    return 0;
}

static const rt_hook_entry *find_entry(uint32_t address)
{
    size_t lo = 0, hi = g_count;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (g_table[mid].address == address)
            return &g_table[mid];
        if (g_table[mid].address < address)
            lo = mid + 1;
        else
            hi = mid;
    }
    return 0;
}

rt_hook_fn rt_hook_lookup(uint32_t address)
{
    const rt_hook_entry *e = find_entry(address);
    return e ? e->fn : 0;
}

/* One ring of `nargs` arguments is all a capture can honestly describe: six is what the System V
   convention passes in registers, and an argument beyond the sixth lives on a stack this side
   never saw. Refusing the extra argument is the only way to keep the recorded case replayable. */
int rt_hook_invoke(uint32_t address, const uint64_t *args, size_t nargs, uint64_t *out)
{
    const rt_hook_entry *e = find_entry(address);
    if (!e || !e->fn) return -1;
    if (nargs > 6) return -1;

    uint64_t a[6] = {0, 0, 0, 0, 0, 0};
    for (size_t i = 0; i < nargs; i++) a[i] = args ? args[i] : 0;

    const char *name = (e->name && *e->name) ? e->name : 0;
    const int case_number = name ? rt_capture_begin(name) : -1;

    /* The body is a C function with whatever signature its family gives it; the boundary calls it
       through the same six-register convention, so this cast adds no assumption the trampoline
       does not already make. */
    typedef uint64_t (*rt_hook_six)(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
    const uint64_t ret = ((rt_hook_six)(uintptr_t)e->fn)(a[0], a[1], a[2], a[3], a[4], a[5]);
    if (out) *out = ret;

    if (case_number >= 0) {
        static const char *const REG[6] = {"rdi", "rsi", "rdx", "rcx", "r8", "r9"};
        char json[1024];
        int n = snprintf(json, sizeof json,
                         "{\"schema\": 1, \"address\": \"0x%08x\", \"function\": \"%s\", "
                         "\"capture\": {\"kind\": \"hook callback\", \"run_id\": \"%s\"}, "
                         "\"cases\": [{\"id\": \"hook_%d\", \"registers\": {",
                         address, name, rt_capture_run_id() ? rt_capture_run_id() : "", case_number);
        for (size_t i = 0; n > 0 && (size_t)n < sizeof json && i < nargs; i++)
            n += snprintf(json + n, sizeof json - (size_t)n, "%s\"%s\": %llu", i ? ", " : "", REG[i],
                          (unsigned long long)a[i]);
        if (n > 0 && (size_t)n < sizeof json)
            n += snprintf(json + n, sizeof json - (size_t)n,
                          "}, \"ret\": {\"rax\": %llu}}]}", (unsigned long long)ret);
        /* A truncated case is refused rather than written: a capture that lost a digit replays as a
           mismatch against a body that was right, and the reader would go hunting the body. */
        if (n > 0 && (size_t)n < sizeof json) rt_capture_write(name, case_number, json);
    }
    return 0;
}

size_t rt_hook_count(void)
{
    return g_count;
}
