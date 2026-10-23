"""A declared-absence row must name something that exists.

symbols/verification_unrecordable.csv keys on `function`; symbols/functions.csv keys on `name`.
Two spellings of one concept in one directory, so a row that is remembered rather than written
joins to nothing and the file still looks populated. This gate makes the emit -> name -> join order
a property: the six rows the probe will add can only land after the emitter has written the names,
because before that they do not resolve.
"""
import csv
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNREC = os.path.join(ROOT, 'symbols', 'verification_unrecordable.csv')
FUNCS = os.path.join(ROOT, 'symbols', 'functions.csv')


def unresolved(unrec_path, funcs_path):
    names = {r['name'] for r in csv.DictReader(open(funcs_path))}
    out = []
    for r in csv.DictReader(open(unrec_path)):
        if r['function'] not in names:
            out.append(r['function'])
    return out


class UnrecordableRowsNameSomething(unittest.TestCase):
    def test_every_row_resolves_to_a_catalogue_name(self):
        bad = unresolved(UNREC, FUNCS)
        self.assertEqual(bad, [], f'verification_unrecordable.csv names {len(bad)} function(s) that '
                                  f'functions.csv does not have: {bad[:5]}')

    def test_the_check_can_fail(self):
        with tempfile.TemporaryDirectory(prefix='unrec-') as d:
            u = os.path.join(d, 'u.csv')
            f = os.path.join(d, 'f.csv')
            open(u, 'w').write('function,reason,date\nnot_a_real_function,synthetic,2026-01-01\n')
            open(f, 'w').write('address,size,name,system,status,notes\n'
                               '00400020,7,real_function,x,original,\n')
            self.assertEqual(unresolved(u, f), ['not_a_real_function'])


if __name__ == '__main__':
    unittest.main()
