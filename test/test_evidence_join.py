"""The join that certifies every reported number, and its counterexample.

A negative test must assert its own precondition: a counterexample that never
constructs the condition it tests passes by testing nothing.
"""
import csv
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import progress  # noqa: E402

FUNCS = ('address,size,name,system,status,notes\n'
         '0x10,4,alpha,sys,edge-verified,\n'
         '0x20,4,beta,sys,original,\n')
LEDGER = ('function,cases_sha256\n'
          'alpha,deadbeef\n')


class Root:
    def __init__(self, funcs=FUNCS, ledger=LEDGER):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        os.makedirs(os.path.join(self.dir, 'symbols'))
        self.write('functions.csv', funcs)
        if ledger is not None:
            self.write('verification.csv', ledger)

    def write(self, name, text):
        with open(os.path.join(self.dir, 'symbols', name), 'w', newline='') as f:
            f.write(text)

    def run(self):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            rc = progress.evidence_join(self.dir)
        finally:
            sys.stdout = old
        return rc, buf.getvalue()


class EvidenceJoin(unittest.TestCase):
    def test_backed_claim_passes(self):
        rc, out = Root().run()
        self.assertEqual(rc, 0, out)
        self.assertIn('unbacked 0', out)
        self.assertIn('ledger-backed 1', out)

    def test_unbacked_claim_fails_and_names_the_address(self):
        root = Root()
        with open(os.path.join(root.dir, 'symbols', 'verification.csv'), newline='') as f:
            rows = list(csv.DictReader(f))
        keep = [r for r in rows if r['function'] != 'alpha']
        removed = len(rows) - len(keep)
        root.write('verification.csv', 'function,cases_sha256\n')
        after = sum(1 for r in keep if r['function'] == 'alpha')
        # Precondition: the counterexample must actually destroy the evidence.
        self.assertEqual(removed, 1)
        self.assertEqual(after, 0)
        rc, out = root.run()
        self.assertEqual(rc, 1, out)
        self.assertIn('unbacked 1', out)
        self.assertIn('0x10', out)
        self.assertIn('FAIL', out)

    def test_unreadable_ledger_is_a_failure_not_a_pass(self):
        rc, out = Root(ledger=None).run()
        self.assertEqual(rc, 1, out)
        self.assertIn('cannot read the ledger', out)


if __name__ == '__main__':
    unittest.main()
