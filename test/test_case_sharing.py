import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import case_sharing  # noqa: E402


class Sharing(unittest.TestCase):
    def _tree(self, n_dirs, n_distinct):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        for i in range(n_dirs):
            d = os.path.join(root, f'{i:08x}')
            os.makedirs(d)
            with open(os.path.join(d, 'case.json'), 'w') as f:
                f.write('{"slot": %d}' % (i % n_distinct))
        return root

    def test_designed_sharing_passes(self):
        rc, detail = case_sharing.audit_sharing(self._tree(78, 62))
        self.assertEqual(rc, 0, detail)
        self.assertIn('ok (78 directories / 62 distinct', detail)

    def test_no_sharing_is_reported_not_refused(self):
        rc, detail = case_sharing.audit_sharing(self._tree(78, 78))
        self.assertEqual(rc, 0)
        self.assertIn('sharing did NOT happen', detail)

    def test_a_collision_refuses(self):
        rc, detail = case_sharing.audit_sharing(self._tree(78, 61))
        self.assertEqual(rc, 1)
        self.assertIn('wrong-body hazard', detail)

    def test_a_directory_without_a_case_refuses(self):
        root = self._tree(78, 62)
        os.remove(os.path.join(root, sorted(os.listdir(root))[0], 'case.json'))
        rc, detail = case_sharing.audit_sharing(root)
        self.assertEqual(rc, 1)
        self.assertIn('a directory is not a case', detail)


if __name__ == '__main__':
    unittest.main()
