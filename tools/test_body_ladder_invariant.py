"""Every replacement body has exactly one ladder row, and every ladder row has a body.

The join is a set comparison over integers, not a substring match over a fixed-width hex
field: `0x1b09110` contains `0x1709110` as a suffix and is a different function, which is how
three separate theories about a missing ladder row were manufactured from one grep.

Coverage is stated rather than implied.  Bodies are discovered by the generated naming
convention `bb_<family>_<8 hex digits>`; a hand-written body is named for the function and
carries no address, so it is invisible here by construction.  The count of ladder rows with no
discovered body is therefore printed by status, and asserted, so a new gap cannot hide inside
a number that "looks about right".
"""
import csv
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = re.compile(r'\bbb_[A-Za-z0-9_]*_([0-9a-f]{8})\b')
# Ladder rows with no generated body: 1 `original` plus hand-named bodies.  Both counts are
# asserted separately because they are different subjects -- an original needs no body, a
# hand-named body has one under a name this scan cannot see.
EXPECTED_UNMATCHED = {'original': 1, 'edge-verified': 19, 'verified': 8}


def bodies():
    found = set()
    for path in glob.glob(os.path.join(ROOT, 'game', '**', '*.cpp'), recursive=True):
        with open(path) as f:
            for m in BODY.finditer(f.read()):
                found.add(int(m.group(1), 16))
    return found


def ladder():
    with open(os.path.join(ROOT, 'symbols', 'functions.csv')) as f:
        return list(csv.DictReader(f))


class BodyLadderInvariant(unittest.TestCase):
    def test_every_discovered_body_has_a_ladder_row(self):
        rows = {int(r['address'], 16) for r in ladder()}
        missing = sorted(bodies() - rows)
        self.assertEqual([], [hex(a) for a in missing],
                         f'{len(missing)} bodies under game/ have no ladder row')

    def test_ladder_rows_without_a_generated_body_are_the_known_population(self):
        found = bodies()
        counts = {}
        for r in ladder():
            if int(r['address'], 16) not in found:
                counts[r['status']] = counts.get(r['status'], 0) + 1
        self.assertEqual(EXPECTED_UNMATCHED, counts,
                         f'ladder rows with no discovered body: {counts} '
                         f'(a new row here is either a hand-named body or a missing generator)')


if __name__ == '__main__':
    unittest.main()
