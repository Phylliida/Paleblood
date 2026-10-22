"""Numbers in prose are claims; a claim that cannot be wrong is the species this repo keeps retiring.

Every entry below is a number a document asks a reader to act on, paired with the tree's own recomputation of
it. If the tree moves and the document does not, this test fails -- the same contract test_approval_request.py
gives the approval sheet, extended to the family counts and the rodata extents the checklist is written from.
"""

import csv
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (document, the number as the document writes it, the source of truth)
# Two populations wear similar numbers on purpose: the ledger counts rows (8,073 `lea rax,[rip+K]` members),
# while docs/pool-census.md counts *leaf bodies* in the <=16-byte pool (8,072, one member ending in jmp). Claims
# below are only where a document quotes the ledger count, so this test cannot itself merge two populations.
FAMILY_CLAIMS = [
    ("docs/pool-census.md", "4,721", "leaf_ret_zero"),
    ("docs/gates.md", "2,978", "leaf_mov_eax_k"),
    ("docs/approval-request.md", "3,619", "leaf_mov_rax"),
    ("docs/decisions-owed.md", "3,619", "leaf_mov_rax"),
]

RODATA_CLAIMS = [
    ("game/large/rodata_pairs_02fc5120.h", "768 bytes = 384"),
    ("game/large/rodata_pairs_02fc4a40.h", "1,760 bytes = 880"),
]


def family_count(prefix):
    n = 0
    with open(ROOT / "symbols" / "functions.csv") as fh:
        for row in csv.DictReader(fh):
            if row["name"].startswith(prefix + "_"):
                n += 1
    return n


def declared_words(header):
    """Count the words the header actually declares, independent of any comment about them."""
    text = (ROOT / header).read_text()
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)          # block comments, non-greedy
    body = "\n".join(line.split("//")[0] for line in body.splitlines())   # line comments, per line
    return len(re.findall(r"0x[0-9a-fA-F]+", body))


class DocNumbersMatchTheTree(unittest.TestCase):
    def test_family_counts(self):
        for doc, quoted, prefix in FAMILY_CLAIMS:
            with self.subTest(doc=doc, prefix=prefix):
                truth = "{:,}".format(family_count(prefix))
                self.assertEqual(truth, quoted, "%s now says %s, the tree says %s" % (prefix, quoted, truth))
                self.assertIn(quoted, (ROOT / doc).read_text(), "%s no longer quotes %s" % (doc, quoted))

    def test_rodata_declared_extents(self):
        checklist = (ROOT / "docs" / "generator-checklist.md").read_text()
        for header, phrase in RODATA_CLAIMS:
            with self.subTest(header=header):
                words = declared_words(header)
                truth = "{:,} bytes = {}".format(words * 2, words)
                self.assertEqual(truth, phrase, "%s declares %s" % (header, truth))
                self.assertIn(phrase, checklist, "the checklist no longer states %r" % phrase)


if __name__ == "__main__":
    unittest.main()
