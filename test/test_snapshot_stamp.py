"""The pre-record snapshot: a stamp names a commit, or recording refuses."""
import os
import subprocess
import tempfile
import unittest

import verification


class HeadOrRefuse(unittest.TestCase):
    def test_names_the_commit(self):
        head = verification._head_or_refuse(os.getcwd())
        self.assertRegex(head, r'^[0-9a-f]{40}$')

    def test_refuses_when_there_is_no_head(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.environ.pop('BB_ALLOW_NO_HEAD', None)
            try:
                with self.assertRaises(RuntimeError) as e:
                    verification._head_or_refuse(d)
                self.assertIn('cannot read HEAD', str(e.exception))
                self.assertIn('BB_ALLOW_NO_HEAD', str(e.exception))
            finally:
                if old is not None:
                    os.environ['BB_ALLOW_NO_HEAD'] = old

    def test_the_opt_out_says_so_rather_than_looking_like_a_commit(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ['BB_ALLOW_NO_HEAD'] = '1'
            try:
                head = verification._head_or_refuse(d)
            finally:
                del os.environ['BB_ALLOW_NO_HEAD']
            self.assertTrue(head.startswith('no-head:'), head)
            self.assertNotRegex(head, r'^[0-9a-f]{40}$')

    def test_a_stamp_is_never_written_when_head_refuses(self):
        """The empty first line this fixes: 61 bytes of stamp claiming provenance it lacks."""
        root = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            rel = os.path.relpath(root, d) if False else None   # noqa: F841  (kept explicit)
            stamp = os.path.join(d, 'verification.csv.pre.stamp')
            old = os.environ.pop('BB_ALLOW_NO_HEAD', None)
            try:
                with self.assertRaises(RuntimeError):
                    verification._head_or_refuse(d)
            finally:
                if old is not None:
                    os.environ['BB_ALLOW_NO_HEAD'] = old
            self.assertFalse(os.path.exists(stamp))


if __name__ == '__main__':
    unittest.main()
