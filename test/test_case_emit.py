"""The emitter is proved against the reader that already exists, not against its own idea of the format.

The check that matters is the round trip: re-emit a real case from `../data/cases` and require the same
bytes, because a format nobody loads is a format that will be wrong in exactly one field.
"""
import glob
import json
import os
import sys
import tempfile
import unittest

# `-P` keeps the working directory off sys.path, so the repository root is named explicitly rather than
# assumed: every other test in this suite that reaches into tools/ does the same.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools import case_emit

CASES = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cases')


class CaseEmit(unittest.TestCase):
    def test_a_real_case_survives_a_round_trip(self):
        paths = sorted(glob.glob(os.path.join(CASES, '**', '*.json'), recursive=True))[:40]
        self.assertTrue(paths, 'no cases to round-trip: the fixture tree moved')
        checked = 0
        for path in paths:
            original = case_emit.read(path)
            # Some fixture files predate the schema key or are not cases at all; the round trip is a
            # claim about the reader's format, so only files that carry one are compared -- and the
            # count below is asserted so a filter that skips everything cannot pass as a green.
            if 'schema' not in original or 'address' not in original or 'args' not in original:
                continue
            rebuilt = case_emit.emit(original['address'], original['args'],
                                     original.get('buffers'), original.get('returns', 'i64'))
            self.assertEqual(rebuilt['schema'], original['schema'], path)
            self.assertEqual(rebuilt['address'], original['address'], path)
            self.assertEqual(rebuilt['args'], original['args'], path)
            self.assertEqual(rebuilt.get('buffers', {}), original.get('buffers', {}), path)
            checked += 1
        self.assertGreater(checked, 10, f'only {checked} cases were actually compared')

    def test_the_pc_is_the_identifier_and_must_be_a_full_address(self):
        case = case_emit.emit('0x00e01000', {'rdi': '0x10'})
        self.assertEqual(case['id'], '0x00e01000')
        self.assertEqual(case['address'], case['id'])
        with self.assertRaises(ValueError):
            case_emit.emit('0x00e0100', {'rdi': '0x10'})

    def test_what_could_not_be_reconstructed_is_reported_not_invented(self):
        case = case_emit.emit('0x00e01000', {'rdi': 'buf:frame'}, {'frame': {'size': 8, 'bytes': '00' * 8}},
                              uncovered=['[rdi+0x8] read beyond the captured frame'])
        self.assertEqual(case['uncovered'], ['[rdi+0x8] read beyond the captured frame'])
        # and it is a real file the existing reader accepts
        with tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)) as d:
            path = os.path.join(d, 'c.json')
            case_emit.write(path, case)
            loaded = json.load(open(path))
            self.assertEqual(loaded, case)


if __name__ == '__main__':
    unittest.main()
