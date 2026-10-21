"""An unresolved import must not look like a resolved one.

A boot run on 2026-10-19 rewrote `symbols/module_functions.csv` with raw NIDs
(`uCkgJOrYUL4#F#G`) because `boot.py` keys a module function's status on `(module, offset)` and
only overwrites the `symbol` column: structure survived, meaning did not, and every gate stayed
green. `boot.py` now preserves resolved names when it rewrites, but a guard inside one writer
only protects the file that writer knows about. This test is the invariant, independent of any
writer and of the run that produces the files.

The rule is the one that makes the marker meaningful: a raw NID is allowed only where the row
already says, in another column, that the name is unknown (`provider=runtime-unresolved`).
Everywhere else a NID in a name field is a resolution failure wearing a symbol's clothes.
"""

import csv
import pathlib
import re
import unittest

SYMBOLS = pathlib.Path(__file__).resolve().parents[1] / 'symbols'

# The `#X#Y` group marker is the only thing a resolved name cannot contain - the 11-character
# body alone reclassifies ordinary names that happen to be 11 characters (`localtime_s`,
# `strncasecmp`, `__cxa_throw`), which is how a residue of "3 unresolved rows" survived a slice
# after the file was already repaired. The markers are not consistently uppercase (`#q#q`), and
# assuming they were made the first version of this pattern miss 202 of 223 damaged rows.
UNRESOLVED = re.compile(r'^[A-Za-z0-9_+\-]{11}(#[A-Za-z])+$')
DECLARED = 'runtime-unresolved'


def violations(path):
    with path.open(newline='') as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            if row.get('provider') == DECLARED:
                continue
            for column, value in row.items():
                if value and UNRESOLVED.match(value):
                    yield (f'{path.name}:{n} {column}={value} '
                           f'({row.get("module", "")}{row.get("offset", row.get("address", ""))})')


class SymbolNamesTest(unittest.TestCase):
    def test_a_raw_nid_only_appears_where_the_row_says_it_is_unknown(self):
        bad = [line for path in sorted(SYMBOLS.glob('*.csv')) for line in violations(path)]
        self.assertEqual([], bad, 'a raw NID is standing in for a symbol name on a row that does '
                                  'not declare itself unresolved; the run that wrote it could not '
                                  'resolve the import and should have kept the name or dropped '
                                  'the row (boot.py preserve())')

    def test_the_invariant_still_recognises_the_shape_it_was_written_for(self):
        # Without this, a regex that stopped matching would report a clean tree forever - the
        # same way `'approve'` reported zero approvals on a table holding thirty.
        for nid in ('uCkgJOrYUL4#F#G', '-ULUBK21QgE#F#G', 'T72hz6ffq08#p#J', 'k+AXqu2-eBc#I#J'):
            self.assertTrue(UNRESOLVED.match(nid), nid)
        for name in ('localtime_s', 'strncasecmp', '__cxa_throw', 'sceFiosDHOpen', 'memcpy'):
            self.assertFalse(UNRESOLVED.match(name), name)


if __name__ == '__main__':
    unittest.main()
