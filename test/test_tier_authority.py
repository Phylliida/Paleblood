import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import tier_authority as T


class TierAuthorityTest(unittest.TestCase):
    def test_1ab_grants_nothing_today(self):
        """The proposal exists and is not in force -- the door must say so, not that it is missing."""
        self.assertFalse(T.grants("1ab"))
        self.assertIn("NOT IN FORCE", T.why("1ab"))

    def test_a_ratified_heading_is_granted(self):
        self.assertTrue(T.grants("1j"))
        self.assertIn("granted", T.why("1j"))

    def test_the_body_quoting_the_status_word_grants_nothing(self):
        """THE PLANTED NEGATIVE, and it is not hypothetical: 1ab's body carried this word for one commit."""
        doc = ("### 9z. PROPOSED, NOT IN FORCE -- a rule\n"
               "\n"
               "Until this line is RATIFIED nothing happens. ratified. Ratified.\n")
        self.assertFalse(T.grants("9z", doc))
        self.assertIsNotNone(T.heading_line("9z", doc))

    def test_the_status_must_be_on_the_heading_line(self):
        self.assertTrue(T.grants("9z", "### 9z. a rule -- RATIFIED 2026-01-01\nbody\n"))

    def test_an_id_that_is_a_prefix_of_another_grants_nothing(self):
        doc = "### 1abc. a rule -- RATIFIED\n"
        self.assertFalse(T.grants("1ab", doc))
        self.assertTrue(T.grants("1abc", doc))

    def test_an_absent_id_refuses(self):
        self.assertFalse(T.grants("9nope", "### 1a. x -- RATIFIED\n"))


if __name__ == "__main__":
    unittest.main()
