"""The shape test: a failure after the open must leave the artifact as it was.

Reordering one call site fixed one call site. These tests fix the property.
"""
import os
import tempfile
import unittest
from unittest import mock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import atomicio


class AtomicWrite(unittest.TestCase):
    def test_writes_the_content_and_leaves_no_temporary(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.txt')
            atomicio.atomic_write(p, 'hello\n')
            self.assertEqual(open(p).read(), 'hello\n')
            self.assertEqual(sorted(os.listdir(d)), ['x.txt'])

    def test_a_failure_at_the_rename_leaves_the_old_bytes(self):
        """The refutation: patch the last step to raise, and the artifact must still be the old one."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.txt')
            open(p, 'w').write('old\n')
            with mock.patch.object(atomicio.os, 'replace', side_effect=OSError('disk says no')):
                with self.assertRaises(OSError):
                    atomicio.atomic_write(p, 'new\n')
            self.assertEqual(open(p).read(), 'old\n')
            self.assertEqual(sorted(os.listdir(d)), ['x.txt'], 'a .tmp file survived a failed write')

    def test_a_failure_while_writing_leaves_the_old_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.txt')
            open(p, 'w').write('old\n')
            with mock.patch.object(atomicio.os, 'fsync', side_effect=OSError('no fsync for you')):
                with self.assertRaises(OSError):
                    atomicio.atomic_write(p, 'new\n')
            self.assertEqual(open(p).read(), 'old\n')
            self.assertEqual(sorted(os.listdir(d)), ['x.txt'])

    def test_bytes_and_str_agree(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, 'a'), os.path.join(d, 'b')
            atomicio.atomic_write(a, 'x\n')
            atomicio.atomic_write(b, b'x\n')
            self.assertEqual(open(a, 'rb').read(), open(b, 'rb').read())


if __name__ == '__main__':
    unittest.main()
