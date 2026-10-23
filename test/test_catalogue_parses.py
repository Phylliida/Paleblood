"""The catalogue gate, tested where a gate can be tested: on inputs it must refuse and must not.

The first version of this gate was a regex and refused tools/join_import_pc.py for its own docstring,
which quotes the defect it had just stopped making. So the detector is now AST-based, and these tests
feed it syntax directly -- a planted violation in a string, never a file in the tree.
"""
import ast
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import check_catalogue as C  # noqa: E402


class DetectorFires(unittest.TestCase):
    def test_explicit_size_radix_is_counted(self):
        self.assertEqual(C._count(ast.parse('int(r["size"], 16)')), (1, 0))

    def test_the_getter_spelling_is_counted(self):
        self.assertEqual(C._count(ast.parse('int(r.get("size"), 16)')), (1, 0))

    def test_a_hex_address_radix_is_not_a_violation(self):
        """Addresses ARE hex. A gate that forbids this one forbids reading the file."""
        self.assertEqual(C._count(ast.parse('int(r["address"], 16)')), (0, 0))

    def test_a_docstring_quoting_the_defect_is_not_a_violation(self):
        src = 'def f():\n    """was int(r["size"], 16), a decimal column read as hex"""\n'
        self.assertEqual(C._count(ast.parse(src)), (0, 0))

    def test_a_raw_dictreader_is_counted(self):
        self.assertEqual(C._count(ast.parse('list(csv.DictReader(open(p)))')), (0, 1))

    def test_the_real_tree_passes(self):
        r = subprocess.run([sys.executable, "-P", str(REPO / "tools" / "check_catalogue.py")],
                           capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
