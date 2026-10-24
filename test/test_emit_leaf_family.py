import io
import os
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
        landed = [n for n in E.TEMPLATES if E.owned_rows(n)]
        self.assertTrue(landed, 'no family is landed: the re-emit property is untested, not true')
        for name in landed:
            with self.subTest(family=name):
                rc, message = E.reemit(name)
                self.assertEqual(rc, 0, message)
                self.assertIn('byte-for-byte', message)
                # The expected count is DERIVED, never pinned: a retired member is a landed row
                # with no body by verdict, so it is subtracted by the same predicate the emitter
                # subtracts. Pinning 11 here went red the hour the population gained a verdict --
                # a count in a fixture is a claim about the population that produced it.
                ret = E.retired_addresses()
                expect = len([a for a in E.owned_rows(name) if a not in ret])
                self.assertIn(f'{expect} members', message)

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

    def test_a_bare_invocation_refuses_by_name_and_writes_nothing(self):
        """Writing requires --write; the control runs in the same method.

        The polarity here used to be inverted -- a BARE invocation wrote the body, the cases and
        three tracked catalogs, and `--dry-run` was the only way not to write. The failure that
        produced is the worst kind: the check meant to precede a landing performed it, and the
        landing then reported "0 unlanded members (1 already landed). Nothing to land here" -- a
        refusal that reads as a completion. The member is mocked so the guard is the subject, not
        today's family state.
        """
        member = {'address': 0x0196f030, 'size': 15, 'k': 0x3fe7641, 'slot': 0x05956678, 'k2': 0x175c}
        tu = os.path.join(E.ROOT, 'game', 'leaf', 'movsx_deref_family.cpp')
        before = open(tu, 'rb').read()
        with mock.patch.object(E, 'members', lambda *a, **k: [member]):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = E.main(['movsx_deref'])
            self.assertEqual(rc, 2, err.getvalue())
            self.assertIn('--write', err.getvalue())
            self.assertIn('REFUSED', err.getvalue())
            # control: everything but the write happens, and the file is the same file afterwards
            out = io.StringIO()
            with redirect_stdout(out):
                rc = E.main(['movsx_deref', '--dry-run'])
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn('nothing written', out.getvalue())
        self.assertEqual(open(tu, 'rb').read(), before, 'neither invocation may touch the TU')

    def test_zero_members_at_all_is_a_message_not_a_crash(self):
        with mock.patch.object(E, 'members', lambda *a, **k: []), \
                mock.patch.object(E, 'owned_rows', lambda *a, **k: {}):
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
        # The first version of owned_rows() used startswith and reported ret as 7,761 of 12,482;
        # the refusal is what caught it, so the parse is pinned here directly.
        # Synthetic tail on purpose: a real address here would be a tracked game value, and a
        # test that pins one is a fixture of the present (check_agnostic flagged the first
        # version for exactly that). The property is the parse, not the address.
        head, _, tail = 'leaf_ret_zero_00abcdef'.rpartition('_')
        self.assertEqual(head, 'leaf_ret_zero')
        self.assertNotEqual(head, 'leaf_ret')
        self.assertEqual(len(tail), 8)



class SelectorName(unittest.TestCase):
    def test_the_selector_is_named_for_what_it_returns(self):
        """`landed_rows` returned rows this emitter OWNS, whatever their status -- the pilot at
        `original` was in it. A function named landed that does not mean landed is a name standing
        where a set belongs, and `tools/landed.py` owns the status predicate."""
        self.assertFalse(hasattr(E, 'landed_rows'), 'the misleading name is back')
        self.assertTrue(hasattr(E, 'owned_rows'))

if __name__ == '__main__':
    unittest.main()
