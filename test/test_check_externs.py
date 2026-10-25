"""Every gate tested on inputs it must ACCEPT as well as inputs it must refuse.

A detector tested only on its refusals will happily refuse the input it must accept, and the first
symptom is somebody adding an exemption. So half of these cases assert silence.
"""
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import check_externs as E  # noqa: E402


class Classifier(unittest.TestCase):
    def test_a_data_extern_is_data(self):
        self.assertEqual(E.classify("extern int32_t rt_x;\n"), [("data", "rt_x")])

    def test_a_function_extern_is_a_function(self):
        self.assertEqual(E.classify("extern unsigned f(void);\n"), [("function", "f")])

    def test_a_weak_array_symbol_is_data(self):
        self.assertEqual(E.classify("extern const T __start_s[] __attribute__((weak));\n"),
                         [("data", "__start_s")])

    def test_a_function_extern_split_across_lines_is_still_a_function(self):
        """A line-oriented scanner refuses a correct prototype that a formatter wrapped. The declaration is the unit."""
        self.assertEqual(E.classify("extern void\nf(unsigned *a,\n         unsigned *b);\n"),
                         [("function", "f")])

    def test_a_data_extern_split_across_lines_is_still_data(self):
        self.assertEqual(E.classify("extern int32_t\nrt_x;\n"), [("data", "rt_x")])

    def test_a_static_inline_definition_is_not_an_extern(self):
        self.assertEqual(E.classify("static inline int f(void) { return 0; }\n"), [])

    def test_a_comment_quoting_an_extern_is_not_a_declaration(self):
        """The catalogue gate's first version fired on a docstring. Same trap, same guard."""
        self.assertEqual(E.classify('/* was extern int32_t rt_x; here */\n'), [])
        self.assertEqual(E.classify('// extern int32_t rt_x;\n'), [])

    def test_the_real_tree_passes(self):
        r = subprocess.run([sys.executable, "-P", str(REPO / "tools" / "check_externs.py")],
                           capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("data 0", r.stdout)


if __name__ == "__main__":
    unittest.main()
