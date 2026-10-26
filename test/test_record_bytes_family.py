"""The byte-family writer must not truncate the table it is sorting or flipping."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import record_bytes_family as R  # noqa: E402


class Writes(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'functions.csv')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir)

    def _write(self, text):
        with open(self.path, 'w', newline='') as f:
            f.write(text)

    def test_a_failing_sort_leaves_the_table_byte_identical(self):
        before = 'address,size\n0x00000020,2\n0x00000010,1\n'
        self._write(before)
        with mock.patch.object(R.atomicio, 'atomic_write', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                R._sort_address_keyed_file(self.path)
        with open(self.path) as f:
            self.assertEqual(f.read(), before)

    def test_a_sorted_table_is_not_rewritten(self):
        self._write('address,size\n0x00000010,1\n0x00000020,2\n')
        with mock.patch.object(R.atomicio, 'atomic_write') as w:
            self.assertFalse(R._sort_address_keyed_file(self.path))
            w.assert_not_called()

    def test_an_unsorted_table_is_sorted_atomically(self):
        self._write('address,size\n0x00000020,2\n0x00000010,1\n')
        self.assertTrue(R._sort_address_keyed_file(self.path))
        with open(self.path) as f:
            self.assertEqual(f.read(), 'address,size\n0x00000010,1\n0x00000020,2\n')


if __name__ == '__main__':
    unittest.main()
