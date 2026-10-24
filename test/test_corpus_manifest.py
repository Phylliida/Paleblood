"""The manifest that makes a recorded corpus count re-derivable: three arms on a fixture, then the real thing.

The fixture arms matter more than the corpus arm. A `--check` that has only ever printed zero is a comparison
never shown to refuse, and the three ways a corpus moves -- added, removed, changed -- each need their own name,
because a diff that collapses them is the two-way-verdict-over-a-three-way-fact this campaign keeps meeting.
"""
import hashlib
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import corpus_manifest as C  # noqa: E402


class TheThreeWaysAcorpusMoves(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix='cman'))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.corpus = self.dir / 'cases'
        (self.corpus / 'a').mkdir(parents=True)
        (self.corpus / 'b').mkdir(parents=True)
        (self.corpus / 'a' / 'one.json').write_text('{"memory":[1]}')
        (self.corpus / 'b' / 'two.json').write_text('{"pointer":"x"}')
        (self.corpus / 'b' / 'noise.json').write_text('{"other":0}')
        self.man = self.dir / 'm.gz'
        C.write_manifest(C.live_rows(self.corpus), self.man)

    def check(self, root=None):
        return C.check(root or self.corpus, self.man)

    def test_the_control_is_identical(self):
        rc, lines = self.check()
        self.assertEqual(rc, 0, '\n'.join(lines))

    def test_added_removed_and_changed_are_each_named(self):
        (self.corpus / 'a' / 'three.json').write_text('{"memory":[2]}')
        (self.corpus / 'b' / 'two.json').unlink()
        (self.corpus / 'a' / 'one.json').write_text('{"memory":[1],"pointer":"y"}')
        rc, lines = self.check()
        self.assertEqual(rc, 1, '\n'.join(lines))
        body = '\n'.join(lines)
        for want in ('+ a/three.json (added)', '- b/two.json (removed)',
                     '~ a/one.json (content changed)'):
            self.assertIn(want, body)

    def test_a_file_matching_no_predicate_is_not_a_member(self):
        (self.corpus / 'b' / 'noise2.json').write_text('{"other":1}')
        rc, lines = self.check()
        self.assertEqual(rc, 0, '\n'.join(lines))  # a non-member changing is not the population moving

    def test_the_count_comes_from_the_manifest_with_the_corpus_absent(self):
        self.assertEqual(C.counts(C.read_manifest(self.man)), {'memory': 1, 'pointer': 1})
        rc, lines = self.check(self.dir / 'does-not-exist')
        self.assertEqual(rc, 1, '\n'.join(lines))
        self.assertEqual(len([l for l in lines if l.startswith('- ')]), 2, '\n'.join(lines))

    def test_the_manifest_is_byte_reproducible(self):
        a = C.write_manifest(C.live_rows(self.corpus), self.dir / 'x.gz')
        b = C.write_manifest(C.live_rows(self.corpus), self.dir / 'y.gz')
        self.assertEqual(a, b)

    def test_an_unreadable_manifest_is_not_zero(self):
        rc, lines = C.check(self.corpus, self.dir / 'missing.gz')
        self.assertEqual(rc, 3)
        self.assertIn('unread is not zero', lines[0])


class TheCommittedManifestIsCurrent(unittest.TestCase):
    def test_the_manifest_matches_the_corpus(self):
        rc, lines = C.check()
        self.assertEqual(rc, 0, '\n'.join(lines))

    def test_pointer_is_a_subset_of_memory(self):
        rows = C.read_manifest()
        mem = {r[3] for r in rows if 'memory' in r[2]}
        ptr = {r[3] for r in rows if 'pointer' in r[2]}
        self.assertTrue(ptr <= mem, 'a pointer case without memory would be a new population')
        self.assertGreater(len(ptr), 0)  # a subset claim over an empty set is vacuous

    def test_the_doc_quotes_the_manifest_its_counts_and_its_hash(self):
        n = C.counts(C.read_manifest())
        sha = hashlib.sha256(C.MANIFEST.read_bytes()).hexdigest()
        text = (ROOT / 'docs' / 'capture-protocol.md').read_text()
        self.assertIn(f"{n['memory']:,}", text)
        self.assertIn(f"{n['pointer']:,}", text)
        self.assertIn(sha, text)


if __name__ == '__main__':
    unittest.main()
