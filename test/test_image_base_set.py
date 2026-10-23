"""The setter, proved on a library that actually carries a based body.

A fixture exporting `pbl_image_base` and leaving it zero proves `nm`. It proves the setter only
when the library also contains a body that dereferences the base -- so this fixture has both, and
load_replacement must (a) report image_base_set True and (b) leave the symbol holding IMAGE.
The remaining half -- that the based body returns the image's dword rather than faulting -- needs
IMAGE mapped, which only Machine does; it is owed, and this test does not claim to cover it.
"""
import ctypes
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import harness  # noqa: E402

SOURCE = r'''
#include <stdint.h>
extern "C" { uint64_t pbl_image_base = 0;
             int bbgame_init(void *) { return 0; } }
extern "C" uint32_t bb_leaf_based_probe(void)
{ return *reinterpret_cast<uint32_t *>(pbl_image_base + 0x24); }
'''


class ImageBaseSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='based-')
        cls.src = os.path.join(cls.dir.name, 'based.cpp')
        cls.lib = os.path.join(cls.dir.name, 'libbased.so')
        open(cls.src, 'w').write(SOURCE)
        r = subprocess.run(['c++', '-shared', '-fPIC', '-O1', '-o', cls.lib, cls.src],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise unittest.SkipTest(f'cannot build the based fixture: {r.stderr[-400:]}')

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_the_setter_reaches_a_library_that_dereferences_the_base(self):
        _, base_set = harness.load_replacement(self.lib, 'bb_leaf_based_probe', 0x1000)
        self.assertTrue(base_set, 'a library carrying a based body must report its base as set')
        lib = ctypes.CDLL(self.lib)
        value = ctypes.c_uint64.in_dll(lib, 'pbl_image_base').value
        self.assertEqual(value, harness.IMAGE,
                         'the base must hold IMAGE after load_replacement, not its 0 default')

    def test_the_flag_is_per_library_not_per_process(self):
        harness.load_replacement(self.lib, 'bb_leaf_based_probe', 0x1000)
        plain = os.path.join(self.dir.name, 'libplain.so')
        r = subprocess.run(['c++', '-shared', '-fPIC', '-x', 'c++', '-o', plain, '-'],
                           input='extern "C" int bbgame_init(void*){return 0;}'
                                 'extern "C" unsigned bb_x(void){return 1;}',
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest('cannot build the plain fixture')
        addr, base_set = harness.load_replacement(plain, 'bb_x', 0x1000)
        self.assertTrue(addr)
        self.assertFalse(base_set, 'a library with no base must not inherit the previous True')


if __name__ == '__main__':
    unittest.main()
