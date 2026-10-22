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

    def test_a_pointer_into_another_object_is_reported_not_prescripted(self):
        # The hazard: pbboot maps several objects, the harness maps one image, so a pointer into libc.elf
        # replays as the same number over eboot's bytes. It must be reported, never preset.
        # The ranges must not overlap: the first version of this fixture put libc.elf inside eboot's
        # range, and classification answered with the first match -- which is correct behaviour and a
        # defective table. Objects are a partition, so a table that is not one is the thing to fix.
        objects = [{'name': 'eboot', 'base': 0x400000, 'size': 0x800000},
                   {'name': 'libc.elf', 'base': 0x00e10000, 'size': 0x40000}]
        case = case_emit.emit_capture('0x00e01000',
                                      {'rdi': 0x400100, 'rsi': 0x00e10040, 'rdx': 0x10},
                                      objects, buffers={'eboot:0x400100': {'size': 8, 'bytes': '00' * 8}})
        self.assertEqual(case['args']['rdi'], 'buf:eboot:0x400100')
        self.assertEqual(case['args']['rdx'], '0x10')
        self.assertNotIn('rsi', case['args'])
        self.assertEqual(case['uncovered'], ['rsi: 0xe10040 in libc.elf'])
        self.assertEqual(case['id'], '0x00e01000')

    def test_an_unreconstructed_eboot_pointer_is_uncovered_not_invented(self):
        objects = [{'name': 'eboot', 'base': 0x400000, 'size': 0x2000000}]
        case = case_emit.emit_capture('0x00e01000', {'rdi': 0x400100}, objects)
        self.assertNotIn('rdi', case['args'])
        self.assertEqual(case['uncovered'], ['rdi: 0x400100 in eboot (no bytes captured)'])

    def test_the_object_table_is_read_from_a_file_and_must_be_a_partition(self):
        table = 'name,guest_start,size,kind\neboot,0x00400000,8388608,eboot\nlibc.elf,0x80400000,262144,module\n'
        with tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)) as d:
            path = os.path.join(d, 'objects.csv')
            open(path, 'w').write(table)
            objects = case_emit.load_objects(path)
        self.assertEqual([o['name'] for o in objects], ['eboot', 'libc.elf'])
        self.assertEqual(objects[1]['size'], 262144)
        self.assertEqual(case_emit.overlapping(objects), [])
        # and the defect the fixture above taught: an overlapping table is detected, not absorbed
        bad = case_emit.load_objects.__wrapped__ if hasattr(case_emit.load_objects, '__wrapped__') else None
        del bad
        overlapping = [{'name': 'a', 'base': 0x400000, 'size': 0x100000},
                       {'name': 'b', 'base': 0x480000, 'size': 0x100}]
        self.assertEqual(len(case_emit.overlapping(overlapping)), 1)

    def test_the_first_capture_target_is_hand_authored_and_that_travels_with_the_record(self):
        # The first target is one of the 21 `verified` rows and its origin is hand, so
        # the first runtime-witnessed event says nothing about the generated majority. The record must
        # carry that, or the count will imply something the event does not support.
        objects = [{'name': 'eboot', 'base': 0x400000, 'size': 0x2f00000}]
        case = case_emit.emit_capture('0x00e01000', {'rdi': 0x10}, objects,
                                      note='origin=hand; target is a verified row')
        self.assertIn('origin=hand', case['note'])


if __name__ == '__main__':
    unittest.main()
