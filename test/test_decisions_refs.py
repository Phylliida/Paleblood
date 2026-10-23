"""Section ids in docs/decisions.md are load-bearing, so both arms are proved by planting.

The two defects: a duplicate id (a yes under one of five `1j` headings is indistinguishable from no) and a
citation to an id with no heading (an invented symbol in a doc). Each is planted in a temp root and must
refuse; the real tree must pass.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import decisions  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DecisionsRefs(unittest.TestCase):
    def test_the_real_tree_passes(self):
        rc, detail = decisions.audit_decisions(REPO)
        self.assertEqual(rc, 0, detail)

    def _root(self, md, cited=''):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, 'docs'))
        os.makedirs(os.path.join(root, 'tools'))
        with open(os.path.join(root, 'docs', 'decisions.md'), 'w') as f:
            f.write(md)
        if cited:
            with open(os.path.join(root, 'tools', 'x.py'), 'w') as f:
                f.write(cited)
        return root

    def test_a_new_duplicate_id_refuses(self):
        root = self._root('### 1z. one\n### 1z. two\n')
        rc, detail = decisions.audit_decisions(root)
        self.assertEqual(rc, 1)
        self.assertIn('### 1z appears 2x', detail)

    def test_a_citation_with_no_heading_refuses(self):
        root = self._root('### 1a. only\n', cited='# see decisions 1k\n')
        rc, detail = decisions.audit_decisions(root)
        self.assertEqual(rc, 1)
        self.assertIn('cites decisions 1k', detail)

    def test_a_frozen_entry_that_vanished_refuses(self):
        root = self._root('### 1a. only\n')
        saved = dict(decisions.KNOWN_DUPLICATES)
        decisions.KNOWN_DUPLICATES['1j'] = 5
        try:
            rc, detail = decisions.audit_decisions(root)
        finally:
            decisions.KNOWN_DUPLICATES.clear()
            decisions.KNOWN_DUPLICATES.update(saved)
        self.assertEqual(rc, 1)
        self.assertIn('still lists 1j', detail)


if __name__ == '__main__':
    unittest.main()
