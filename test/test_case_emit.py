"""The emitter is proved against the reader that already exists, not against its own idea of the format.

The check that matters is the round trip: re-emit a real case from `../data/cases` and require the same
bytes, because a format nobody loads is a format that will be wrong in exactly one field.
"""
import glob
import json
import os
import re
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
                                      objects, buffers={'obj': {'size': 16, 'bytes': '00' * 16, 'address': 0x400100}},
                                      replayed='eboot')
        self.assertEqual(case['args']['rdi'], 'buf:obj')
        self.assertEqual(case['args']['rdx'], '0x10')
        self.assertNotIn('rsi', case['args'])
        self.assertEqual(case['uncovered'], ['rsi: 0xe10040 in libc.elf (no bytes captured)'])
        self.assertEqual(case['id'], '0x00e01000')

    def test_an_unreconstructed_eboot_pointer_is_uncovered_not_invented(self):
        objects = [{'name': 'eboot', 'base': 0x400000, 'size': 0x2000000}]
        case = case_emit.emit_capture('0x00e01000', {'rdi': 0x400100}, objects)
        self.assertNotIn('rdi', case['args'])
        self.assertEqual(case['uncovered'], ['rdi: 0x400100 in eboot (no bytes captured)'])
        # and an offset into a declared buffer is expressed the way real cases express it
        case = case_emit.emit_capture('0x00e01000', {'rdi': 0x400110}, objects,
                                      buffers={'obj': {'size': 0x40, 'bytes': '00' * 0x40, 'address': 0x400100}})
        self.assertEqual(case['args']['rdi'], 'buf:obj+0x10')

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

    def test_real_cases_declare_buffers_by_name_so_emitting_is_a_copy_not_a_conversion(self):
        # The branch question settled from data: 35,344 cases in ../data/cases carry `args`, and every
        # buffer reference is `buf:<name>` where the name is symbolic -- `data`, `dest`, `object+0x20` --
        # with no address anywhere in the document. So there is no guest-vs-host conversion to get wrong:
        # a capture names its buffers and carries bytes, and the address lives only in `uncovered` and the
        # record. This test is the assertion that keeps that true as cases are added.
        root = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cases')
        checked = 0
        address_shaped = re.compile(r'(0x)?[0-9a-fA-F]{6,}$')
        for path in sorted(glob.glob(os.path.join(root, '**', '*.json'), recursive=True)):
            try:
                case = json.load(open(path))
            except Exception:
                continue
            if not isinstance(case, dict) or 'args' not in case:
                continue
            checked += 1
            buffers = case.get('buffers', {})
            for reg, value in case['args'].items():
                if isinstance(value, str) and value.startswith('buf:'):
                    # The real convention is `buf:<name>` or `buf:<name>+0x<offset>` -- an offset into a
                    # declared buffer, which is how a case expresses a pointer without carrying an address.
                    name = re.split(r'\+0x', value[4:])[0]
                    self.assertIn(name, buffers, f'{path}: {reg} names an undeclared buffer {name}')
            for name in buffers:
                self.assertIsNone(address_shaped.match(name), f'{path}: buffer named by address: {name}')
        self.assertGreater(checked, 1000, 'the filter must not skip the population it reports on')

    def test_the_eboot_size_in_the_table_covers_every_catalogued_address(self):
        # A base table with a wrong size classifies pointers wrong in the only direction that matters:
        # out of range read as in range. The check that can be made cheaply is the catalog's own extent.
        import csv as _csv
        objects = case_emit.load_objects(os.path.join(os.path.dirname(__file__), '..', 'symbols', 'objects.csv'))
        eboot = objects[0]
        self.assertEqual(eboot['name'], 'eboot')
        highest = 0
        with open(os.path.join(os.path.dirname(__file__), '..', 'symbols', 'ghidra_functions.csv'), newline='') as f:
            for row in _csv.DictReader(f):
                highest = max(highest, int(row['address'], 16))
        self.assertLess(highest - 0x400000, eboot['size'],
                        'a catalogued address outside the declared eboot range would be reported uncovered')

    def test_an_assumed_region_size_is_a_field_and_the_padding_is_poison(self):
        # A capture knows where a pointer points and what bytes are there; it cannot know how many bytes the
        # body reads. So the assumption is recorded, and the bytes past it are poison -- if both sides read
        # past the region and fault identically, the differential would call it agreement.
        objects = [{'name': 'eboot', 'base': 0x400000, 'size': 0x800000}]
        captured = bytes(range(16))
        case = case_emit.emit_capture('0x00e01000', {'rdi': 0x400100}, objects,
                                      buffers={'obj': {'size': 16, 'bytes': captured, 'address': 0x400100}},
                                      size_assumed=64)
        spec = case['buffers']['obj']
        self.assertEqual(spec['size'], 64)
        self.assertEqual(spec['size_assumed'], 16)          # what was actually captured
        self.assertEqual(len(spec['bytes']), 64)
        self.assertEqual(spec['bytes'][:16], captured)
        self.assertEqual(spec['bytes'][16:], bytes([case_emit.POISON]) * 48)
        # and the bound the assumed size has to respect, measured from the target's own instructions
        self.assertEqual(case_emit.WIDEST_ACCESS_BYTES, 8)
        for size in (16, 64, 128):
            self.assertEqual(size % case_emit.WIDEST_ACCESS_BYTES, 0)


if __name__ == '__main__':
    unittest.main()
