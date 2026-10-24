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

    def _top_shape(self):
        """The most frequent shape in the census's OWN table. Never a literal: the chain family's 78
        rows left this frontier when they landed (6,288 -> 6,210) and the literal that named them
        stopped being a predicate and became a coincidence about position."""
        rc, out, err = run()
        self.assertEqual(rc, 0, f'{out}\n{err}')
        best = None
        for line in out.splitlines():
            m = re.match(r'\s*(\d+)\s+(\d+)\s+(\S+)\s+(\S.*?)\s*$', line)
            if not m:
                continue
            n = int(m.group(1))
            if best is None or n > best[0]:
                best = (n, m.group(2), m.group(4))
        self.assertIsNotNone(best, f'the census printed no shape table:\n{out}')
        return best

    def test_the_three_way_split_is_an_identity(self):
        n, _bytes, shape = self._top_shape()
        rc, out, err = run('--targets-for', shape)
        self.assertEqual(rc, 0, f'{out}\n{err}')
        m = re.search(r'rows (\d+) \| load target inside filesz (\d+) \| zero-fill tail (\d+) '
                      r'\| unmapped (\d+)', out)
        self.assertIsNotNone(m, out.splitlines()[1] if out else '<empty stdout>')
        total, filesz, zerofill, unmapped = (int(x) for x in m.groups())
        self.assertEqual(filesz + zerofill + unmapped, total,
                         'a target is unaccounted for: the split must partition the shape')
        self.assertGreater(total, 0, 'a shape filter matching nothing is not a measurement')

    def test_a_cross_segment_address_is_unmapped_not_zerofill(self):
        # Positive control on the classifier itself: code is file-backed, an address in the gap
        # between the two PT_LOADs is in no segment at all, and these must not be confused with
        # the zero-fill tail -- the difference decides whether a body may be authored.
        import sys as _s
        _s.path.insert(0, os.path.join(ROOT, 'tools'))
        import leaf_shape_census as S
        md = open(S.ELF, 'rb').read()
        segs = S.load_segments(md)
        self.assertEqual(S.classify_target(segs, 0x400000), 'filesz')
        self.assertEqual(S.classify_target(segs, 0x090dc000), 'unmapped')
        self.assertEqual(S.classify_target(segs, 0x5956678), 'zerofill')
        # the RW segment's reservations are what make a seeding case possible at all
        self.assertTrue(any(b <= 0x5956678 < b + m for b, f, m in segs),
                        'the seeded slot must lie inside some segment memsz, not past all of them')

    def test_missing_bytes_are_a_refusal_not_an_empty_census(self):
        rc, out, err = run('--elf', '/tmp/does-not-exist-eboot.elf')
        self.assertEqual(rc, 3, f'expected the refusal arm, got rc={rc}\n{out}\n{err}')
        self.assertIn('nothing can be decoded and nothing is claimed', err)
        self.assertEqual(out, '', 'a refusal that prints a table anyway is not a refusal')


if __name__ == '__main__':
    unittest.main()
