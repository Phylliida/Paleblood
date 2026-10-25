/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "runtime/guest.h"
#include "runtime/hooks.h"
#include "runtime/host.h"

typedef struct {
    uint64_t offset;
    uint64_t size;
    const void *target;
} installed_hook;

static installed_hook installed[4];
static unsigned installed_count;
static unsigned installed_ok;      /* calls that returned 0; `installed_count` counts attempts */
static int install_error;
static int install_error_at = -1;  /* -1: every call fails; else only that call index does */
static unsigned probe_count;
static unsigned char *probe_image;
static uint64_t probe_size;
static int probe_error;

static void replacement_one(void) {}
static void replacement_two(void) {}

const rt_hook_entry game_hooks[] = {
    {0x00401000u, 8u, "replacement_one", replacement_one},
    {0x00402000u, 12u, "replacement_two", replacement_two},
};
const unsigned game_hook_count = sizeof game_hooks / sizeof game_hooks[0];

int rt_probes_install(unsigned char *image, uint64_t image_size)
{
    probe_count++;
    probe_image = image;
    probe_size = image_size;
    return probe_error;
}

static int fake_install_hook(uint64_t offset, uint64_t size, const void *target)
{
    if (installed_count >= sizeof installed / sizeof installed[0])
        return -1;
    const unsigned call = installed_count;
    installed[installed_count++] = (installed_hook){offset, size, target};
    /* The fixture has to be able to say "this ONE site failed", or a test about the site after a
       refusal can only be written by failing every site -- which is the case that already aborts. */
    const int rc = (install_error_at < 0 || (unsigned)install_error_at == call) ? install_error : 0;
    if (rc == 0) installed_ok++;
    return rc;
}

static int check(int condition, const char *what)
{
    if (condition)
        return 0;
    fprintf(stderr, "test_plugin: %s\n", what);
    return 1;
}

static void reset_observations(void)
{
    installed_count = 0;
    installed_ok = 0;
    install_error = 0;
    install_error_at = -1;
    probe_count = 0;
    probe_image = NULL;
    probe_size = 0;
    probe_error = 0;
}

int main(void)
{
    unsigned char image[64] = {0};
    rt_host host = {RT_HOST_API_VERSION, image, sizeof image, fake_install_hook};
    int failed = 0;

    reset_observations();
    failed |= check(bbgame_init(NULL) != 0, "null host must be rejected");
    failed |= check(installed_count == 0 && probe_count == 0,
                    "null host must not install hooks or probes");

    reset_observations();
    host.version++;
    failed |= check(bbgame_init(&host) != 0, "unsupported host version must be rejected");
    failed |= check(installed_count == 0 && probe_count == 0,
                    "unsupported host must not install hooks or probes");
    host.version = RT_HOST_API_VERSION;

    reset_observations();
    failed |= check(bbgame_init(&host) == 0, "compatible host must initialize");
    failed |= check(installed_count == 2, "compatible host must receive both hooks");
    failed |= check(installed[0].offset == 0x1000 && installed[0].size == 8 &&
                    installed[0].target == (const void *)replacement_one,
                    "first hook must use image-relative offset, size, and replacement");
    failed |= check(installed[1].offset == 0x2000 && installed[1].size == 12 &&
                    installed[1].target == (const void *)replacement_two,
                    "second hook must use image-relative offset, size, and replacement");
    failed |= check(rt_image == image, "guest image must be retained for replacements");
    failed |= check(probe_count == 1 && probe_image == image && probe_size == sizeof image,
                    "probe installation must receive the host image and size after hooks");
    failed |= check(rt_hook_count() == 2 && rt_hook_lookup(0x00401000u) == replacement_one &&
                    rt_hook_lookup(0x00402000u) == replacement_two,
                    "registered replacements must remain available by guest address");

    reset_observations();
    failed |= check(setenv("BB_HOOK_SKIP", "replacement_two", 1) == 0,
                    "hook-name skip setting must be configurable");
    failed |= check(bbgame_init(&host) == 0, "host must initialize with one hook skipped by name");
    failed |= check(installed_count == 1 && installed[0].offset == 0x1000 && probe_count == 1,
                    "name skip must omit only the selected hook and continue initialization");

    reset_observations();
    failed |= check(setenv("BB_HOOK_SKIP", "0x00401000", 1) == 0,
                    "hook-address skip setting must be configurable");
    failed |= check(bbgame_init(&host) == 0, "host must initialize with one hook skipped by address");
    failed |= check(installed_count == 1 && installed[0].offset == 0x2000 && probe_count == 1,
                    "address skip must omit only the selected hook and continue initialization");
    failed |= check(unsetenv("BB_HOOK_SKIP") == 0, "hook skip setting must be removed after the test");

    /* The first capture installs exactly one hook, selected by address: nothing else can fire earlier
       and divert the guest, so a divergence has one candidate instead of 1,737. */
    reset_observations();
    failed |= check(setenv("BB_HOOK_ONLY", "0x00402000", 1) == 0,
                    "single-hook selection must be configurable");
    failed |= check(bbgame_init(&host) == 0, "host must initialize with BB_HOOK_ONLY");
    failed |= check(installed_count == 1 && installed[0].offset == 0x2000 && probe_count == 1,
                    "BB_HOOK_ONLY must install one of the selected hooks and nothing else");

    /* One filter, two directions: setting both is refused, not resolved. Two expressions of one filter
       disagree the first time both are set, and the disagreement looks like a hook that did not fire. */
    reset_observations();
    failed |= check(setenv("BB_HOOK_SKIP", "replacement_one", 1) == 0,
                    "the second direction must be settable alongside");
    failed |= check(bbgame_init(&host) != 0, "both directions set at once must be refused");
    failed |= check(installed_count == 0 && probe_count == 0, "a refused selection must install nothing");
    failed |= check(unsetenv("BB_HOOK_SKIP") == 0 && unsetenv("BB_HOOK_ONLY") == 0,
                    "both selection settings must be removed after the test");

    reset_observations();
    install_error = 1;
    failed |= check(bbgame_init(&host) != 0, "hook installation failure must abort initialization");
    failed |= check(installed_count == 1 && probe_count == 0,
                    "hook failure must stop before later hooks and probes");

    /* The capacity refusal is the one failure that means "not PLACED", and it must not refuse the
       boot: fail ONLY the first site, for that reason, and the second site must still install. Before
       the split, one site on a full stub page aborted the install, the plugin refused, and no
       evidence run could start -- 40 installed of 41 selected was reported as the plugin's refusal. */
    reset_observations();
    install_error = RT_INSTALL_NO_ROOM;
    install_error_at = 0;
    failed |= check(bbgame_init(&host) == 0,
                    "a site that cannot be placed must not refuse the whole install");
    failed |= check(installed_count == 2 && installed_ok == 1,
                    "the site after a capacity refusal must still be installed");

    reset_observations();
    probe_error = 1;
    failed |= check(bbgame_init(&host) != 0, "probe installation failure must be returned");
    failed |= check(installed_count == 2 && probe_count == 1,
                    "probe failure must occur after hooks are installed");

    return failed ? 1 : 0;
}
