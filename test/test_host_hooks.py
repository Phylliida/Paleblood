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
#include "runtime/host_hooks.h"

int main(void)
{
    unsigned char image[0x100];
    rt_host host = {0};
    memset(image, 0x90, sizeof image);
    host.version = RT_HOST_API_VERSION;
    host.image = image;
    host.image_size = sizeof image;
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

    /* 2. a 6-byte site (pool B's shape): refused, image unchanged */
    unsigned char keep[0x100];
    memcpy(keep, image, sizeof keep);
    if (host.install_hook(0x40, 6, (const void *)0x1000ULL) == 0) { puts("2 accepted a 6-byte site"); return 6; }
    if (memcmp(keep, image, sizeof keep) != 0) { puts("2 changed the image"); return 7; }

    /* 3. a site past the end of the image: refused */
    if (host.install_hook(0xf8, 0x20, (const void *)0x1000ULL) == 0) { puts("3 accepted an overlong site"); return 8; }

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
    def build(self, extra_source=None):
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
        run = subprocess.run([os.path.join(d, 'driver')], capture_output=True, text=True)
        return run

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


if __name__ == '__main__':
    unittest.main()
