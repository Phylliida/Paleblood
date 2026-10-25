/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include "runtime/plugin_load.h"

#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

#include "runtime/host.h"
#include "runtime/host_hooks.h"

/* Declared here rather than in host_hooks.h on purpose: that header is included by pinned replacements, and the pin
   set is a constraint on where code may live (see check_pins.py). Counters are a diagnostic, not an ABI. */
extern unsigned rt_host_hooks_installed_count(void);
extern void rt_host_hooks_sites_snapshot(unsigned *checked, unsigned *already_patched, unsigned *mismatched, unsigned *unlisted);

int rt_boot_load_plugin(void *image, uint64_t image_size, const char *path, unsigned *hooks_installed)
{
    if (hooks_installed) *hooks_installed = 0;
    if (!image || !image_size || !path || !*path) {
        fprintf(stderr, "plugin: refusing to load: image=%p size=%llu path=%s\n", image,
                (unsigned long long)image_size, path ? path : "(null)");
        return -1;
    }

    rt_host host;
    memset(&host, 0, sizeof host);
    /* The runtime refuses a host whose version it does not recognise: an unset version is a zero the check is
       designed to catch, not a default. */
    host.version = RT_HOST_API_VERSION;
    host.image = image;
    host.image_size = image_size;
    if (rt_host_hooks_initialize(&host) != 0) {
        fprintf(stderr, "plugin: refusing to load %s: the installer could not be configured\n", path);
        return -1;
    }
    if (!host.install_hook) {
        /* install_hook is the default we just published; NULL here means rt_host_hooks_initialize did not take. */
        fprintf(stderr, "plugin: installer=NULL after initialize: the plugin would count hooks and install none\n");
        return -1;
    }

    void *lib = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!lib) {
        const char *why = dlerror();
        fprintf(stderr, "plugin: dlopen failed: %s: %s\n", path, why ? why : "(no dlerror)");
        return -1;
    }

    int (*init)(const rt_host *) = (int (*)(const rt_host *))dlsym(lib, "bbgame_init");
    if (!init) {
        fprintf(stderr, "plugin: %s does not export bbgame_init\n", path);
        return -1;
    }

    const int rc = init(&host);
    const unsigned installed = rt_host_hooks_installed_count();
    unsigned checked = 0, already_patched = 0, mismatched = 0, unlisted = 0;
    rt_host_hooks_sites_snapshot(&checked, &already_patched, &mismatched, &unlisted);
    fprintf(stderr, "install: sites_checked=%u already_patched=%u mismatched=%u unlisted=%u refused=%u "
                    "hooks_installed=%u\n",
            checked, already_patched, mismatched, unlisted,
            already_patched + mismatched + unlisted, installed);
    if (hooks_installed) *hooks_installed = installed;
    fprintf(stderr, "capture: installer=default hooks_installed=%u\n", installed);
    if (rc != 0) {
        fprintf(stderr, "plugin: bbgame_init refused (%d) after installing %u hook(s)\n", rc, installed);
        return -1;
    }
    if (installed == 0) {
        fprintf(stderr, "plugin: bbgame_init returned 0 and installed 0 hooks: nothing is patched\n");
        return -1;
    }
    return 0;
}
