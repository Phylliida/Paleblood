/* SPDX-License-Identifier: GPL-2.0-or-later */
/* The loader proved before pbboot has a caller: three causes, three sentences, one function. */
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include "runtime/plugin_load.h"

static int failed;

static void check(int ok, const char *what)
{
    if (!ok) {
        printf("test_plugin_load: %s\n", what);
        failed = 1;
    }
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        printf("test_plugin_load: usage: %s <no-entry-lib> <good-lib>\n", argv[0]);
        return 2;
    }

    /* RWX, because the installer checks both bits and a refused page is the finding, not the fixture. */
    unsigned char *image = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (image == MAP_FAILED) {
        printf("test_plugin_load: mmap failed\n");
        return 2;
    }
    memset(image, 0x90, 0x1000);
    image[0] = 0x89; image[1] = 0xf8; image[2] = 0x01; image[3] = 0xf0; image[4] = 0xc3;

    unsigned installed = 99;

    /* 1. No such file: dlopen fails, and the message names the path. */
    check(rt_boot_load_plugin(image, 0x1000, "/nonexistent/paleblood-plugin.so", &installed) != 0,
          "a missing library must refuse");
    check(installed == 0, "a refusal must not report an installation count");

    /* 2. Loads, exports nothing: dlsym is a different cause from dlopen and must be a different sentence. */
    check(rt_boot_load_plugin(image, 0x1000, argv[1], &installed) != 0,
          "a library without bbgame_init must refuse");

    /* 3. The real thing: one hook installed through a real installer. */
    check(rt_boot_load_plugin(image, 0x1000, argv[2], &installed) == 0, "a good plugin must load");
    check(installed == 1, "the good plugin installs exactly one hook");

    /* 4. A NULL path is refused, not passed to dlopen. */
    check(rt_boot_load_plugin(image, 0x1000, NULL, &installed) != 0, "a null path must refuse");

    munmap(image, 0x1000);
    return failed;
}
