"""One shape per verdict, and the progress line must come from the gate rather than be recomputed.

The functional case is the one that pays: a root containing a raw `csv.DictReader` in a file the
allowlist does not name must make progress's clause say REFUSED -- about THAT root. Before this, the
clause called the scanner with no root and answered about this tree while the caller had asked about
another, which is the two-roots defect on the same output line for the second time.
"""
import os
import sys
import tempfile
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
sys.path.insert(0, TOOLS)

import gateline as G
import progress as P

REPO = os.path.dirname(TOOLS)


class TheShapeOfAVerdict(unittest.TestCase):
    def test_ok_carries_the_detail_the_check_returned(self):
        self.assertEqual(G.gate_line('parses', 0, '55 files'), 'parses: ok (55 files)')

    def test_a_refusal_carries_its_rc(self):
        self.assertEqual(G.gate_line('parses', 1, '1 new'), 'parses: REFUSED (rc=1) -- 1 new')

    def test_no_rc_prints_not_checked_never_a_zero(self):
        self.assertEqual(G.gate_line('parses', None), 'parses: not checked')


class TheProgressClauseIsTheGateVerdict(unittest.TestCase):
    def test_a_rogue_root_is_refused_about_that_root(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'tools'))
            os.makedirs(os.path.join(d, 'test'))
            with open(os.path.join(d, 'tools', 'rogue.py'), 'w') as f:
                f.write('import csv\ndef g():\n    return list(csv.DictReader(open("x")))\n')
            clause = P._parses_clause(d)
            self.assertIn('REFUSED (rc=1)', clause)
            self.assertIn('1 new', clause)   # the gate's own count, quoted -- not recomputed here

    def test_the_real_tree_is_ok_and_quotes_the_gate(self):
        self.assertIn('parses: ok (', P._parses_clause(REPO))


if __name__ == '__main__':
    unittest.main()
