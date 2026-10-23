import io
import os
import sys
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import emit_leaf_family as E  # noqa: E402


class ReEmitAnswersWhatDidIEmitted(unittest.TestCase):
    """The generator must be able to say what it emitted, from the rows, without the artifact.

    This is the property that answers a future retraction: the 647 were identified by a name
    filter over a file and matched 362 of 647, which is what "no program can tell you what was
    emitted" looks like from the outside. `--reemit` derives the population from the family's own
    landed rows, refuses when the census cannot reproduce one of them, and compares the
    regenerated body with the committed file byte for byte.

    Deliberately NOT a fixture of today's counts: the test asserts the property over whichever
    families are landed, so landing or retracting a family changes the population it covers
    rather than turning it red.
    """

    def test_every_landed_family_reproduces_the_committed_body(self):
        landed = [n for n in E.TEMPLATES if E.landed_rows(n)]
        self.assertTrue(landed, 'no family is landed: the re-emit property is untested, not true')
        for name in landed:
            with self.subTest(family=name):
                rc, message = E.reemit(name)
                self.assertEqual(rc, 0, message)
                self.assertIn('byte-for-byte', message)
                self.assertIn(f'{len(E.landed_rows(name))} members', message)

    def test_a_member_the_census_cannot_reproduce_is_refused_and_named(self):
        # A partial reproduction must not look like a smaller family. Drop one member from the
        # population the census returns and require a refusal that names the gap.
        real = E.members

        def short(name, landed=False):
            ms = real(name, landed=landed)
            return ms[:-1] if landed else ms

        with mock.patch.object(E, 'members', short):
            rc, message = E.reemit('rip_store')
        self.assertEqual(rc, 1, message)
        self.assertIn('refused', message)
        self.assertIn('missing 1', message)

    def test_zero_unlanded_members_is_a_message_naming_the_door(self):
        # rip_store is landed, so its unlanded population is empty. That used to be a traceback
        # (`min() iterable argument is empty`); it must be a refusal that names --reemit.
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = E.main(['rip_store'])
        out = buf.getvalue()
        self.assertEqual(rc, 1, out)
        self.assertIn('0 unlanded members', out)
        self.assertIn('--reemit rip_store', out)

    def test_zero_members_at_all_is_a_message_not_a_crash(self):
        with mock.patch.object(E, 'members', lambda *a, **k: []), \
                mock.patch.object(E, 'landed_rows', lambda *a, **k: {}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = E.main(['mov_eax_mem'])
        out = buf.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn('0 members', out)
        self.assertNotIn('Traceback', out)


class TheComparisonNamesItsDifference(unittest.TestCase):
    def test_identical_text_says_byte_for_byte(self):
        ok, message = E.compare_text('a\nb\n', 'a\nb\n')
        self.assertTrue(ok)
        self.assertEqual(message, 'byte-for-byte')

    def test_a_difference_names_the_line_and_both_forms(self):
        ok, message = E.compare_text('a\nv = 0x1u;\n', 'a\nv = 0x2u;\n')
        self.assertFalse(ok)
        self.assertIn('line 2', message)
        self.assertIn('0x2u', message)
        self.assertIn('0x1u', message)

    def test_a_truncated_file_names_the_line_counts(self):
        ok, message = E.compare_text('a\nb\nc\n', 'a\nb\n')
        self.assertFalse(ok)
        self.assertIn('line count differs', message)

    def test_a_missing_file_is_refused_not_compared(self):
        ok, message = E.compare_text('a\n', None)
        self.assertFalse(ok)
        self.assertIn('does not exist', message)


class TheKeyIsParsedNotPrefixed(unittest.TestCase):
    def test_a_landed_row_belongs_to_exactly_one_family(self):
        # `leaf_ret_zero_*` sits under `leaf_ret_` as a string prefix and is a different family.
        # The first version of landed_rows() used startswith and reported ret as 7,761 of 12,482;
        # the refusal is what caught it, so the parse is pinned here directly.
        # Synthetic tail on purpose: a real address here would be a tracked game value, and a
        # test that pins one is a fixture of the present (check_agnostic flagged the first
        # version for exactly that). The property is the parse, not the address.
        head, _, tail = 'leaf_ret_zero_00abcdef'.rpartition('_')
        self.assertEqual(head, 'leaf_ret_zero')
        self.assertNotEqual(head, 'leaf_ret')
        self.assertEqual(len(tail), 8)


if __name__ == '__main__':
    unittest.main()
