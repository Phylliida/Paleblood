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
        # 'n/a', not False: this library exports no base at all, which is a different fact from
        # 'the base existed and could not be set' -- that one is a BadInput above, never a value.
        # The property under test is unchanged: the answer belonged to the second library and did
        # not inherit the first's True.
        self.assertEqual(base_set, 'n/a', 'a library with no base must not inherit the previous True')



class ExportedByTheArtifact(unittest.TestCase):
    """The mechanism must exist in the SHIPPED library, not only in a fixture that vendors it.

    pbl_image_base and kGuestLoadBase lived only inside game/leaf/rip_load_family.cpp; withdrawing
    that family removed both and no test noticed, because test_image_base_set's fixtures compile
    their own .so. This asserts the export on build-release/game/libbbgame.so, and asserts the
    assertion can fail by checking a library that has no base at all.
    """

    LIB = os.path.join(ROOT, 'build-release', 'game', 'libbbgame.so')

    def exported(self, path):
        r = subprocess.run(['nm', '-D', '--defined-only', path], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        return any('pbl_image_base' in line for line in r.stdout.splitlines())

    def test_the_shipped_library_exports_the_base(self):
        if not os.path.exists(self.LIB):
            self.fail(f'{self.LIB} is missing: the export cannot be asserted against an unbuilt '
                      'artifact, and a skip here would read as a green')
        self.assertTrue(self.exported(self.LIB),
                        'libbbgame.so does not export pbl_image_base: load_base.cpp left the build')

    def test_the_assertion_can_fail(self):
        with tempfile.TemporaryDirectory(prefix='nobase-') as d:
            src = os.path.join(d, 'plain.cpp')
            lib = os.path.join(d, 'libplain.so')
            with open(src, 'w') as fh:
                fh.write('extern "C" int bbgame_init(void*){return 0;}')
            r = subprocess.run(['c++', '-shared', '-fPIC', '-o', lib, src], capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest('cannot build the control library')
            self.assertFalse(self.exported(lib), 'a library with no base must not pass this check')

    def test_the_three_values_are_distinguishable_and_only_two_of_them_are_values(self):
        """'n/a', True, and a refusal -- because False for both meanings records a failure as a fact.

        (a) a library exporting no base: nothing to set, nothing claimed -> 'n/a'.
        (b) a library exporting the base: set and read back -> True.
        (c) a library exporting the NAME as something that is not a writable u64: the set cannot be
            established, so this is a raise. A False here would say "no base was needed", which is
            the opposite of what happened, in the one field that exists to make that unsayable.
        Existence is decided by dlsym, not by in_dll's ValueError, since one exception covered both.
        """
        import harness
        with tempfile.TemporaryDirectory(prefix='tristate-') as d:
            cases = {
                'plain': ('extern "C" int bbgame_init(void*){return 0;}', 'n/a'),
                'based': ('#include <cstdint>\nextern "C" std::uintptr_t pbl_image_base = 0;\n'
                          'extern "C" int bbgame_init(void*){return 0;}', True),
                # A FUNCTION wearing the name: dlsym finds it, in_dll returns a u64 bound to its
                # code, and writing it segfaulted the interpreter before the writability guard
                # existed. The refusal must come from the mapping, not from the write.
                'wrongtype': ('extern "C" void pbl_image_base(void){}\n'
                              'extern "C" int bbgame_init(void*){return 0;}', 'raise'),
                # A const in .rodata, same class by a different road.
                'roconst': ('#include <cstdint>\nextern "C" { extern const std::uintptr_t '
                            'pbl_image_base; const std::uintptr_t pbl_image_base = 0; }\n'
                            'extern "C" int bbgame_init(void*){return 0;}', 'raise'),
            }
            for name, (body, want) in cases.items():
                src = os.path.join(d, name + '.cpp')
                lib = os.path.join(d, 'lib' + name + '.so')
                with open(src, 'w') as fh:
                    fh.write(body)
                r = subprocess.run(['c++', '-shared', '-fPIC', '-o', lib, src],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    self.skipTest('cannot build the fixture library: ' + r.stderr[-300:])
                if want == 'raise':
                    with self.assertRaises(harness.BadInput, msg=f'{name}: a failed set is a refusal'):
                        harness.load_replacement(lib, 'bbgame_init', 0)
                else:
                    _addr, got = harness.load_replacement(lib, 'bbgame_init', 0)
                    self.assertEqual(got, want, f'{name}: recorded {got!r}, expected {want!r}')


if __name__ == '__main__':
    unittest.main()
