"""The case root is an interface, not a string: a caller must fail at the boundary.

The old `case_dir()` returned a directory, so every caller spelled its own layout beside it --
`<addr8>/case.json`, `0x<addr8>/a.json`, and one undeclared third form. The reader now asks the
root for a case by address; the writer asks for a declared layout. The tests below construct the
second spelling and assert it cannot be joined, and construct two layouts for one address and
assert the root refuses the ambiguity instead of taking the first match.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from case_dir import CaseRoot, case_dir  # noqa: E402
from catalogue import read_rows  # noqa: E402


class CaseRootTest(unittest.TestCase):
    def test_root_cannot_be_joined(self):
        root = case_dir('chain_deref')
        with self.assertRaises(TypeError):
            os.path.join(root, '00000000', 'case.json')
        with self.assertRaises(TypeError):
            os.fspath(root)

    def test_chain_case_is_found_by_address(self):
        row = next(iter(read_rows(os.path.join(ROOT, 'symbols', 'chain_family.csv'))))
        path = case_dir('chain_deref').find(row['address'])
        self.assertIsNotNone(path, 'the chain family has a case for its first row')
        self.assertTrue(path.endswith(os.path.join('chain', '%08x' % row['address'], 'case.json')))

    def test_table_case_is_found_by_address(self):
        prefix = 'leaf_movsx_deref_'
        row = next(r for r in read_rows(os.path.join(ROOT, 'symbols', 'functions.csv'))
                   if r['name'].startswith(prefix))
        path = case_dir('movsx_deref').find(row['address'])
        self.assertIsNotNone(path, 'the table family has a case for its body address')
        self.assertTrue(path.endswith(os.path.join('leaf', '0x%08x' % row['address'], 'a.json')))
        self.assertIsNone(case_dir('movsx_deref').find(row['address'] + 1))

    def test_unknown_family_refuses(self):
        with self.assertRaises(SystemExit) as cm:
            case_dir('no_such_family')
        self.assertIn('no declared case layout', str(cm.exception))

    def test_every_emitter_template_is_registered(self):
        import emit_leaf_family
        for family in emit_leaf_family.TEMPLATES:
            with self.subTest(family=family):
                self.assertIsInstance(case_dir(family), CaseRoot)

    def test_two_declared_layouts_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, '00000001'))
            os.makedirs(os.path.join(td, '0x00000001'))
            open(os.path.join(td, '00000001', 'case.json'), 'w').close()
            open(os.path.join(td, '0x00000001', 'a.json'), 'w').close()
            with self.assertRaises(SystemExit) as cm:
                CaseRoot(td).find(1)
            self.assertIn('declared layouts', str(cm.exception))

    def test_no_layout_is_none_not_first_match(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(CaseRoot(td).find(1))

    def test_path_components_refuse_escape(self):
        root = CaseRoot('/tmp')
        with self.assertRaises(ValueError):
            root.key_dir('../escape')
        with self.assertRaises(ValueError):
            root.bare('/absolute')

    def test_unknown_layout_refuses(self):
        with self.assertRaises(ValueError):
            case_dir('chain_deref').row_dir(1, 'third')
        with self.assertRaises(ValueError):
            case_dir('chain_deref').row_file(1, 'third')


if __name__ == '__main__':
    unittest.main()
