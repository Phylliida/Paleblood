"""The frontier's shape census: the identity that must hold whatever the table says.

The table itself is expected to change -- families get emitted and rows leave the frontier -- so
nothing here pins a shape or a count. What is pinned is the arithmetic: every frontier row is
accounted for as decoded, over the instruction bound, or undecoded, and none is silently dropped.
That is the defect this census exists to avoid, and the same one that made a 16508 histogram of a
fallback literal look like a measurement.
"""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, 'tools', 'leaf_shape_census.py')
PY = sys.executable


def run(*args):
    p = subprocess.run([PY, '-P', TOOL, *args], capture_output=True, text=True, cwd='/tmp',
                       env={k: v for k, v in os.environ.items() if k != 'PYTHONPATH'})
    return p.returncode, p.stdout, p.stderr


class LeafShapeCensus(unittest.TestCase):
    def test_every_frontier_row_is_accounted_for(self):
        rc, out, err = run()
        self.assertEqual(rc, 0, err)
        m = re.search(r'frontier (\d+) addressable rows \| decoded (\d+) \| over \d+ '
                      r'insns (\d+) \(counted, not dropped\) \| undecoded (\d+)', out)
        self.assertIsNotNone(m, out.splitlines()[0] if out else '<empty stdout>')
        total, decoded, over, undecoded = (int(x) for x in m.groups())
        self.assertEqual(decoded + over + undecoded, total,
                         f'{decoded} + {over} + {undecoded} != {total}: a row is missing')
        self.assertGreater(total, 0, 'an empty frontier is a moved population, not a clean census')

    def test_the_population_is_the_committed_frontier(self):
        rows = [r for r in open(os.path.join(ROOT, 'symbols', 'leaf_frontier.csv'), newline='')
                .read().splitlines() if r]
        addressable = sum(1 for r in rows if r.split(',')[2] == 'addressable')
        rc, out, err = run()
        self.assertEqual(rc, 0, err)
        self.assertIn(f'frontier {addressable} addressable rows', out,
                      'the tool and the artifact disagree about the population it names')

    def test_missing_bytes_are_a_refusal_not_an_empty_census(self):
        rc, out, err = run('--elf', '/tmp/does-not-exist-eboot.elf')
        self.assertEqual(rc, 3, f'expected the refusal arm, got rc={rc}\n{out}\n{err}')
        self.assertIn('nothing can be decoded and nothing is claimed', err)
        self.assertEqual(out, '', 'a refusal that prints a table anyway is not a refusal')


if __name__ == '__main__':
    unittest.main()
