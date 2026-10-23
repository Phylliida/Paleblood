"""The entry point is the last top-level statement -- shown refusing, then pinned on the real tree.

A function defined below `if __name__ == '__main__':` is unbound when the module runs as a script,
because main() executes at the guard. I inserted one definition above another, the anchor was unique,
the text was correct, and the file parsed -- 44 tests died with `name 'fixture_seeds' is not defined`.
Anchors protect the write and ast.parse protects the file; neither protects the program.
"""
import os
import sys
import tempfile
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
sys.path.insert(0, TOOLS)

import check_import_order as C

GOOD = """def f():
    return 1


if __name__ == '__main__':
    f()
"""
BAD = """if __name__ == '__main__':
    f()


def f():
    return 1
"""
NO_GUARD = """def f():
    return 1
"""
CLEVER = """import sys

if __name__ == '__main__':
    sys.exit(0)

x = 1
"""


def scan_of(*sources):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'tools'))
    for i, src in enumerate(sources):
        with open(os.path.join(d, 'tools', f'm{i}.py'), 'w') as f:
            f.write(src)
    return C.scan(d)


class TheGuardMustBeLast(unittest.TestCase):
    def test_a_definition_after_the_guard_is_refused(self):
        problems = scan_of(BAD)
        guard = [p for p in problems if '__main__ guard' in p]
        self.assertEqual(len(guard), 1)
        self.assertIn('m0.py:5', guard[0])      # the trailing statement's line, not the guard's
        # the guard's own line, DERIVED from the fixture rather than typed: my first version wrote
        # 'at :2' because I assumed a blank line led the string, and BAD's guard is on line 1.
        self.assertIn(f"at :{BAD.splitlines().index("if __name__ == '__main__':") + 1}", guard[0])

    def test_guard_last_is_accepted(self):
        self.assertEqual([p for p in scan_of(GOOD) if '__main__ guard' in p], [])

    def test_a_module_with_no_guard_is_not_the_question(self):
        self.assertEqual([p for p in scan_of(NO_GUARD) if '__main__ guard' in p], [])

    def test_the_key_is_per_file_so_one_property_cannot_grandfather_the_other(self):
        # scan() produces problem strings, never keys -- my first version asserted a key against it. The
        # rule lives in key_of(), so that is what the roster law is tested against.
        (guard,) = [p for p in scan_of(CLEVER) if '__main__ guard' in p]
        self.assertEqual(C.key_of(guard), 'guard:m0.py')
        self.assertEqual(C.key_of('REFUSED x.py:12: imports sibling \'y\' with no sys.path.insert -- needs'),
                         'x.py:12')


class TheRealTreeIsClean(unittest.TestCase):
    def test_every_tool_passes_both_properties(self):
        root = os.path.join(os.path.dirname(TOOLS))
        self.assertEqual(C.scan(root), [])

    def test_the_harness_itself_is_pinned(self):
        src = open(os.path.join(TOOLS, 'harness.py')).read()
        self.assertTrue(src.rstrip().endswith('sys.exit(main())'))


if __name__ == '__main__':
    unittest.main()
