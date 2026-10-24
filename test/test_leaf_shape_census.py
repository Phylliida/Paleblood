"""The frontier's shape census: the identity that must hold whatever the table says.

The table itself is expected to change -- families get emitted and rows leave the frontier -- so
nothing here pins a shape or a count. What is pinned is the arithmetic: every frontier row is
accounted for as decoded, over the instruction bound, or undecoded, and none is silently dropped.
That is the defect this census exists to avoid, and the same one that made a 16508 histogram of a
fallback literal look like a measurement.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
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
        # The equation form is the point: a number lifted out of an `=` must take its terms with it.
        m = re.search(r'frontier (\d+) addressable rows = (\d+) decoded .*?\+ (\d+) over the bound '
                      r'.*?\+ (\d+) undecoded', out)
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



    def test_every_row_of_the_file_is_in_a_named_bucket(self):
        """The population the loader DROPS is printed, not left to subtraction.

        frontier() keeps `addressable` rows only; whatever it drops must appear as a counted bucket,
        because a population that requires the reader to subtract two other numbers will be
        subtracted wrong -- 6,888 - 6,809 = 79 was that reflex, and it landed nowhere.
        """
        rc, out, err = run()
        self.assertEqual(rc, 0, err)
        line = next((l for l in out.splitlines() if l.startswith('population ')), None)
        self.assertIsNotNone(line, 'the census does not print its whole population:\n' + out[:400])
        buckets = {k: int(v) for v, k in re.findall(r'(\d+) (\w[\w-]*)', line)}
        self.assertIn('total', buckets, line)
        named = sum(v for k, v in buckets.items() if k != 'total')
        self.assertEqual(named, buckets['total'],
                         f'{buckets}: a row is in no bucket, so a reader must subtract to find it')
        rows = [r for r in open(os.path.join(ROOT, 'symbols', 'leaf_frontier.csv'), newline='')
                .read().splitlines() if r]
        self.assertEqual(buckets['addressable'],
                         sum(1 for r in rows if r.split(',')[2] == 'addressable'),
                         'the bucket and the artifact disagree about one population')
        self.assertGreater(buckets['total'], buckets['addressable'],
                           'nothing was dropped: either the file changed or the drop is unnamed again')

    def test_targets_json_is_records_only(self):
        """stdout is a record stream and nothing else: no summary, no header, no line filter needed."""
        rc, out, err = run()
        self.assertEqual(rc, 0, err)
        shapes = [m.group(2) for m in (re.match(r'\s*\d+\s+\d+\s+(\S+)\s+(\S.*?)\s*$', l)
                                       for l in out.splitlines()) if m]
        self.assertTrue(shapes, f'the census printed no shape table:\n{out[:400]}')
        last = None
        for shape in shapes[:6]:                      # single-instruction shapes refuse by design
            rc, out2, err2 = run('--targets-for', shape, '--targets-json')
            last = (shape, rc, out2, err2)
            if rc == 0:
                break
        shape, rc, out2, err2 = last
        self.assertEqual(rc, 0, f'no shape produced targets; last {shape!r}:\n{err2}')
        recs = [json.loads(l) for l in out2.splitlines() if l]
        m = re.search(r'rows (\d+) \|', err2)
        self.assertIsNotNone(m, 'the summary must still be printed -- on stderr:\n' + err2)
        self.assertEqual(len(recs), int(m.group(1)),
                         'the stream and the summary disagree about how many members were printed')
        self.assertNotIn('shape ', out2, 'a summary line leaked into the record stream')
        for r in recs:
            self.assertEqual(sorted(r), ['address', 'load_target', 'size', 'src', 'store_k', 'where'])
        self.assertIn('population ', err2, 'the dumped population must carry its own buckets')


    def test_a_headerless_frontier_is_refused_and_the_real_one_is_its_control(self):
        """A reader that requires a header refuses a first record that is data.

        csv.DictReader eats such a record silently, which cost one population here and made the
        shortfall read as a finding. The control is in the same method: same reader, real file.
        """
        src = os.path.join(ROOT, 'symbols', 'leaf_frontier.csv')
        lines = [l for l in open(src, newline='').read().splitlines() if l]
        self.assertEqual(lines[0], 'address,size,class')
        with tempfile.TemporaryDirectory() as td:
            bare = os.path.join(td, 'bare.csv')
            open(bare, 'w').write('\n'.join(lines[1:]) + '\n')
            rc, out, err = run('--frontier', bare)
            self.assertEqual(rc, 2, f'{out}\n{err}')
            self.assertIn('first record is', err)
            self.assertIn('short by one row', err)
        rc, out, err = run('--frontier', src)
        self.assertEqual(rc, 0, f'{out}\n{err}')

if __name__ == '__main__':
    unittest.main()
