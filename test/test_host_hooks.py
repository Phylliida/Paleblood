"""runtime/host_hooks.c: the patch, its bounds, its readback, and the stub it refuses to skip.

The installer has never had a client: tools/harness.py:739 passes `lambda o, s, t: 0`, so no
`edge-verified` row was ever produced through a patched site. These cases exercise the callback
directly on a stand-in image, which is the only way to see the bytes before a boot installs one.

  * a site of 32 bytes gets the 14-byte `jmp qword ptr [rip]` plus the absolute target, and the
    bytes after the patch are untouched;
  * a site shorter than 14 bytes is refused and the image is unchanged (the smallest row in
    game/hooks.csv is 16 bytes, so this refuses a table mistake, not a real site);
  * a site that would run past the end of the image is refused;
  * with a live guest %fs -- the boot, as opposed to the harness -- the 14 bytes point at a boundary
    stub emitted by runtime/boundary_stub.c (the same emitter the import trampolines use), not at the
    replacement, because a bare jump would run the body on the guest's TCB.
"""

import os
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CC = os.environ.get('CC', 'cc')

DRIVER = r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <signal.h>
#include "runtime/host_hooks.h"

enum { IMAGE_SIZE = 0x100 };

int main(void)
{
    /* Executable, because the installer now proves the page it patches is executable: a hook into a
       plain array reads back and never fires, and refusing it is the point of the check below. */
    unsigned char *image = mmap(NULL, IMAGE_SIZE, PROT_READ | PROT_WRITE | PROT_EXEC,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (image == MAP_FAILED) { puts("mmap failed"); return 1; }
    rt_host host = {0};
    memset(image, 0x90, IMAGE_SIZE);
    host.version = RT_HOST_API_VERSION;
    host.image = image;
    host.image_size = IMAGE_SIZE;
    if (rt_host_hooks_initialize(&host) != 0) { puts("init refused"); return 2; }

    const unsigned char before = image[0x10 + 14];

    /* 1. a 32-byte site: patched, target readable at +6, tail untouched */
    if (host.install_hook(0x10, 0x20, (const void *)0x1234567890abcdefULL) != 0) { puts("1 refused"); return 3; }
    const unsigned char want[6] = {0xff, 0x25, 0, 0, 0, 0};
    if (memcmp(image + 0x10, want, 6) != 0) { puts("1 wrong opcode"); return 4; }
    uint64_t dest = 0;
    memcpy(&dest, image + 0x16, 8);
    /* Without a live guest %fs there is nothing to swap, so the jump names the target; with one it
       names a boundary stub. Both are correct, and the difference is printed rather than assumed. */
    if (dest == 0x1234567890abcdefULL)
        printf("dest 0x%llx tail %02x\n", (unsigned long long)dest, image[0x10 + 14]);
    else
        printf("stub 0x%llx tail %02x\n", (unsigned long long)dest, image[0x10 + 14]);
    if (before != image[0x10 + 14]) { puts("1 wrong bytes"); return 5; }

    /* The abort reporter is a separate exit path; raise here to exercise it with one installed site. */
    if (getenv("RAISE_ABORT")) raise(SIGABRT);

    /* 2. a 6-byte site (pool B's shape): refused, image unchanged */
    unsigned char keep[IMAGE_SIZE];
    memcpy(keep, image, sizeof keep);
    if (host.install_hook(0x40, 6, (const void *)0x1000ULL) == 0) { puts("2 accepted a 6-byte site"); return 6; }
    if (memcmp(keep, image, sizeof keep) != 0) { puts("2 changed the image"); return 7; }

    /* 2b. a page the process cannot execute: refused, image untouched. The negative control for the
       executable-mapping check, in the other direction from case 1. */
    {
        rt_host plain = {0};
        plain.version = RT_HOST_API_VERSION;
        plain.image = (unsigned char *)keep;   /* stack memory: readable, not executable */
        plain.image_size = sizeof keep;
        if (rt_host_hooks_initialize(&plain) != 0) { puts("2b init refused"); return 9; }
        if (plain.install_hook(0, sizeof keep, (const void *)0x1000ULL) == 0) { puts("2b accepted a non-executable page"); return 10; }
        if (keep[0] != 0x90) { puts("2b changed a refused image"); return 11; }
        /* the module keeps the image it was handed: put the real one back */
        host.version = RT_HOST_API_VERSION;
        host.image = image;
        host.image_size = IMAGE_SIZE;
        if (rt_host_hooks_initialize(&host) != 0) { puts("2b restore refused"); return 12; }
    }

    /* 3. a site past the end of the image: refused */
    if (host.install_hook(0xf8, 0x20, (const void *)0x1000ULL) == 0) { puts("3 accepted an overlong site"); return 8; }

    puts("ok");
    return 0;
}
'''


CAP_DRIVER = r'''
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "runtime/host_hooks.h"

enum { IMAGE_SIZE = 0x1000, CAPTURE_SITES = 65 };

static int replacement(int left, int right) { return left * 3 + right; }

int main(void)
{
    char dir[] = "/tmp/pb_capture_cap.XXXXXX";
    if (!mkdtemp(dir)) { puts("mkdtemp failed"); return 1; }
    char cap_path[256], site_path[256];
    snprintf(cap_path, sizeof cap_path, "%s/capture_ok.csv", dir);
    snprintf(site_path, sizeof site_path, "%s/site_ok.csv", dir);
    char hex[29];
    for (int k = 0; k < 14; k++) { hex[2 * k] = '9'; hex[2 * k + 1] = '0'; }
    hex[28] = '\0';
    FILE *site = fopen(site_path, "w");
    FILE *cap = fopen(cap_path, "w");
    if (!site || !cap) { puts("table write failed"); return 1; }
    for (int i = 0; i < CAPTURE_SITES; i++) {
        const unsigned addr = 0x400000u + 0x20u + (unsigned)i * 0x10u;
        fprintf(site, "0x%08x,%s\n", addr, hex);
        fprintf(cap, "0x%08x,none,deadbeef,cafe\n", addr);
    }
    fclose(site);
    fclose(cap);
    setenv("BB_CAPTURE", "1", 1);
    setenv("BB_CAPTURE_OK", cap_path, 1);
    setenv("BB_SITE_OK", site_path, 1);
    setenv("BB_CAPTURE_TABLE_ID", "cafe", 1);

    unsigned char *image = mmap(NULL, IMAGE_SIZE, PROT_READ | PROT_WRITE | PROT_EXEC,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (image == MAP_FAILED) { puts("mmap failed"); return 1; }
    memset(image, 0x90, IMAGE_SIZE);
    rt_host host = {0};
    host.version = RT_HOST_API_VERSION;
    host.image = image;
    host.image_size = IMAGE_SIZE;
    if (rt_host_hooks_initialize(&host) != 0) { puts("init refused"); return 2; }

    int refusals = 0, last = 0;
    for (int i = 0; i < CAPTURE_SITES; i++) {
        last = host.install_hook(0x20 + (uint64_t)i * 0x10, 0x20, (const void *)replacement);
        printf("%d %d\n", i, last);
        if (last == RT_INSTALL_NO_ROOM) refusals++;
    }
    /* The 65th is the first past RT_SITES_MAX: exactly one named placement refusal, and its site
       byte is untouched. Without the fix this is 0 refusals and the 65th aliases slot 63. */
    if (refusals != 1 || last != RT_INSTALL_NO_ROOM) { printf("refusals %d last %d\n", refusals, last); return 3; }
    if (image[0x20 + 64 * 0x10] != 0x90) { puts("65th site was patched"); return 4; }
    puts("ok");
    return 0;
}
'''

LIVE_TLS = r'''
/* Stands in for runtime/tls.c once the boot has a guest block: the weak probes resolve and say the
   guest %fs is live, which is the condition under which the jump must go through a boundary stub. */
#include <stdint.h>
uint64_t rt_tls_guest_base(void) { return 0x7f0000001000ULL; }
uint64_t rt_tls_host_base(void) { return 0x7f0000000000ULL; }
'''


class HostHooks(unittest.TestCase):
    def build(self, extra_source=None, env=None):
        d = tempfile.mkdtemp()
        src = os.path.join(d, 'driver.c')
        with open(src, 'w') as f:
            f.write(DRIVER)
        cmd = [CC, '-O1', '-Wall', '-Wextra', f'-I{os.path.join(ROOT, "runtime", "include")}',
               src, os.path.join(ROOT, 'runtime', 'host_hooks.c'),
               os.path.join(ROOT, 'runtime', 'boundary_stub.c'), '-o', os.path.join(d, 'driver')]
        if extra_source:
            extra = os.path.join(d, 'tls.c')
            with open(extra, 'w') as f:
                f.write(extra_source)
            cmd.insert(-2, extra)
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        run = subprocess.run([os.path.join(d, 'driver')], capture_output=True, text=True,
                             env={**os.environ, **(env or {})}, timeout=20)
        return run

    def test_abort_reporter_prints_once_and_terminates(self):
        """The SIGABRT reporter used snprintf; fortify aborted inside the handler and the handler recursed.
        One `abort:` line and a SIGABRT exit are the property, not a message containing it."""
        run = self.build(env={'RAISE_ABORT': '1'})
        self.assertEqual(run.returncode, -signal.SIGABRT, run.stdout + run.stderr)
        self.assertEqual(run.stderr.count('abort: '), 1, run.stderr[:2000])
        # Without capture there is no entered-counter row, and "0 of 0" is only honest with its population:
        # one hook installed, zero tracked. A bare "0 of 0" is the zero-without-a-selector defect.
        self.assertIn('sites entered 0 of 0 tracked', run.stderr)
        self.assertIn('hooks installed 1', run.stderr)

    def test_patch_refusals_and_readback(self):
        run = self.build()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('ok', run.stdout)
        self.assertIn('dest 0x1234567890abcdef tail 90', run.stdout)

    def test_a_live_guest_tls_installs_a_boundary_stub(self):
        run = self.build(LIVE_TLS)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('ok', run.stdout)
        # the patch no longer names the replacement; it names a stub that leads to it
        self.assertNotIn('dest 0x1234567890abcdef', run.stdout)
        self.assertIn('stub ', run.stdout)


    def test_capture_table_full_refuses_the_65th(self):
        """The stub page cannot hold 64 capture wrappers, so the real cap is unreachable in the shipped
        page. Compile with a larger page and drive 65 installs: the 65th must be a named placement
        refusal, not a wrapper aliasing slot 63. The compile-time page size is the seam; the table cap
        stays at its production value."""
        d = tempfile.mkdtemp()
        src = os.path.join(d, 'capture_cap.c')
        with open(src, 'w') as f:
            f.write(CAP_DRIVER)
        exe = os.path.join(d, 'capture_cap')
        cmd = [CC, '-O1', '-Wall', '-Wextra', '-DRT_STUB_PAGE=16384',
               f'-I{os.path.join(ROOT, "runtime", "include")}', src,
               os.path.join(ROOT, 'runtime', 'host_hooks.c'),
               os.path.join(ROOT, 'runtime', 'boundary_stub.c'), '-o', exe]
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        run = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('ok', run.stdout)
        self.assertIn('64 -2', run.stdout)
        self.assertIn('capture table is full (64 of 64 slots)', run.stderr)


if __name__ == '__main__':
    unittest.main()
