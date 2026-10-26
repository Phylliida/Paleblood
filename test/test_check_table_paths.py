"""The presence gate must see a composed path, not just a filename."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_table_paths as C  # noqa: E402

OLD = """\
TABLES = ('functions.csv', 'install_mode.csv')
def main():
    for table in TABLES:
        path = os.path.join(ROOT, 'symbols', table)
        rows = list(csv.DictReader(open(path)))
"""


class TablePaths(unittest.TestCase):
    def test_the_old_tables_loop_is_a_finding(self):
        got = C.scan_text(OLD)
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][0], 5)
        self.assertIn('open', got[0])

    def test_a_message_is_not_a_reader(self):
        self.assertEqual(C.scan_text("print('install_mode.csv has one reader')\n"), [])

    def test_a_direct_path_is_a_reader(self):
        got = C.scan_text("open(os.path.join(ROOT, 'symbols', 'install_mode.csv'))\n")
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][2], 'open')

    def test_a_write_text_is_a_writer(self):
        got = C.scan_text("(Path(root) / 'symbols' / 'install_mode.csv').write_text('')\n")
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][2], 'write_text')

    def test_the_tree_has_no_second_reader(self):
        bad = []
        for path in sorted((ROOT / 'tools').glob('*.py')):
            if path.name == 'install_mode.py':
                continue
            bad.extend((path.name, line, func, call) for line, func, call in C.scan_file(path))
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
