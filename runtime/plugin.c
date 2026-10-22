/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "runtime/guest.h"
#include "runtime/host.h"
#include "runtime/hooks.h"
#include "runtime/probe.h"

unsigned char *rt_image;

extern const rt_hook_entry game_hooks[];
extern const unsigned game_hook_count;

/* Hook selection is ONE filter with two directions, never two filters:
 *
 *   BB_HOOK_ONLY  comma-separated addresses or names; when set, nothing else is installed
 *   BB_HOOK_SKIP  comma-separated addresses or names subtracted from whatever ONLY selected
 *
 * Setting both is refused rather than resolved: two ways to express one filter disagree the first
 * time someone sets both, and the disagreement would look like a hook that did not fire. The first
 * capture installs exactly one hook, so that the bodies firing earlier cannot divert the guest before
 * the address under investigation is reached -- one hook, one variable, trivial attribution. */
static int listed(const char *env, const rt_hook_entry *h)
{
    char addr[16];
    if (!env || !*env)
        return 0;
    snprintf(addr, sizeof addr, "0x%08x", h->address);
    for (const char *p = env; *p;) {
        size_t n = strcspn(p, ",");
        if ((n == strlen(addr) && !strncmp(p, addr, n)) || (n == strlen(h->name) && !strncmp(p, h->name, n)))
            return 1;
        p += n + (p[n] == ',');
    }
    return 0;
}

static int selected_by_environment(const rt_hook_entry *h, const char **by)
{
    const char *only = getenv("BB_HOOK_ONLY");
    const char *skip = getenv("BB_HOOK_SKIP");
    const int want = (only && *only) ? listed(only, h) : 1;
    if (!want)
        return 0;
    if (listed(skip, h)) {
        *by = "BB_HOOK_SKIP";
        return 0;
    }
    return 1;
}

int bbgame_init(const rt_host *host)
{
    if (!host || host->version != RT_HOST_API_VERSION) {
        fprintf(stderr, "bbgame: loader interface version %u, expected %u\n",
                host ? host->version : 0u, RT_HOST_API_VERSION);
        return 1;
    }
    const char *only = getenv("BB_HOOK_ONLY");
    const char *skip = getenv("BB_HOOK_SKIP");
    if (only && *only && skip && *skip) {
        fprintf(stderr, "bbgame: BB_HOOK_ONLY and BB_HOOK_SKIP are one filter in two directions; "
                "unset one rather than guessing which wins\n");
        return 1;
    }
    rt_image = host->image;
    if (rt_hooks_install(game_hooks, game_hook_count))
        return 1;
    unsigned installed = 0, selected = 0;
    for (unsigned i = 0; i < game_hook_count; i++) {
        const rt_hook_entry *h = &game_hooks[i];
        const char *by = NULL;
        if (!selected_by_environment(h, &by)) {
            if (by) fprintf(stderr, "bbgame: %s (0x%08x) skipped (%s)\n", h->name, h->address, by);
            continue;
        }
        selected++;
        installed++;
        if (h->address < RT_EBOOT_BASE ||
            host->install_hook(h->address - RT_EBOOT_BASE, h->size, (const void *)h->fn)) {
            fprintf(stderr, "bbgame: cannot hook %s at 0x%08x (%u bytes)\n", h->name, h->address, h->size);
            return 1;
        }
    }
    fprintf(stderr, "bbgame: installed %u of %u selected (%s)\n", installed, selected,
            (only && *only) ? "BB_HOOK_ONLY" : "all hooks");
    return rt_probes_install(host->image, host->image_size);
}
