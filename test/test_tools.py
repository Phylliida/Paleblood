# SPDX-License-Identifier: GPL-2.0-or-later
import contextlib
import csv
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
PY = sys.executable


def run(script, *args, cwd=None):
    return subprocess.run([PY, os.path.join(TOOLS, script), *args], capture_output=True, text=True, cwd=cwd)


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        for s in ('frame_timing', 'camera'):
            os.makedirs(os.path.join(self.d, 'game', s))
        write_csv(f'{self.d}/symbols/ghidra_functions.csv', ['address', 'size'],
                  [['0x00401000', '100'], ['0x00402000', '50'], ['0x00403000', '10']])
        write_csv(f'{self.d}/symbols/functions.csv',
                  ['address', 'size', 'name', 'system', 'status', 'notes'],
                  [['0x00401000', '100', 'frame_timing_update', 'frame_timing', 'verified', ''],
                   ['0x00402000', '50', 'camera_follow', 'camera', 'original', '']])
        # Every replacement declares where it came from; the real tree's file has 600+ rows and
        # the burndown's hand/generated split is read from it, so a fixture tree that skips it is
        # a tree validate_functions.py is right to refuse.
        write_csv(f'{self.d}/symbols/replacement_origins.csv', ['address', 'origin'],
                  [['0x00401000', 'hand']])
        write_csv(f'{self.d}/game/hooks.csv', ['address', 'replacement', 'system'],
                  [['0x00401000', 'bb_frame_timing_update', 'frame_timing']])
        # 294c0ca0b6c6086e is evidence_hash over the two ledger rows below (both pinning
        # aa01000000000000); source_hash is 'unavailable' because no file here defines the
        # replacement. Written as literals rather than computed, so a change to either hashing
        # rule shows up in the tests that read this fixture instead of moving with them.
        write_csv(f'{self.d}/symbols/reviews.csv',
                  ['address', 'name', 'date', 'reviewer', 'verdict', 'scope', 'source_hash', 'cases_sha256',
                   'notes'],
                  [['0x00401000', 'frame_timing_update', '2026-01-01', 'independent session', 'approved',
                    'function', 'unavailable', '294c0ca0b6c6086e', '']])
        # a clean, current verification record (no source file here, so the source hash is empty)
        write_csv(f'{self.d}/symbols/verification.csv',
                  ['function', 'cases', 'option', 'total', 'passed', 'failed', 'quarantined', 'source',
                   'cases_sha256', 'date'],
                  [['frame_timing_update', 'recorded', '', '3', '3', '0', '0', '', 'aa01000000000000',
                    '2026-01-01'],
                   ['frame_timing_update', 'edge', '', '2', '2', '0', '0', '', 'aa01000000000000',
                    '2026-01-01']])
        with open(f'{self.d}/README.md', 'w') as f:
            f.write('<!-- target:start -->\n<!-- target:end -->\n<!-- progress:start -->\n<!-- progress:end -->\n')

    def tearDown(self):
        shutil.rmtree(self.d)


class Progress(Fixture):
    def test_numbers_come_from_csv(self):
        d = json.loads(run('progress.py', '--root', self.d).stdout)
        self.assertEqual(d['total'], {'functions': 3, 'bytes': 160})
        self.assertEqual(d['replaced']['functions'], 1)
        self.assertEqual(d['replaced']['bytes'], 100)
        self.assertEqual(d['replaced']['bytes_pct'], 62.5)
        self.assertEqual(d['systems']['camera']['replaced'], 0)

    def test_slices_cover_the_export(self):
        d = json.loads(run('progress.py', '--root', self.d).stdout)
        self.assertEqual(len(d['slices']), 64)
        self.assertEqual(sum(x['functions'] for x in d['slices']), 3)
        self.assertEqual(sum(x['bytes'] for x in d['slices']), 160)
        self.assertEqual(sum(x['verified_bytes'] for x in d['slices']), 100)

    def test_deterministic(self):
        a = run('progress.py', '--root', self.d).stdout
        self.assertEqual(a, run('progress.py', '--root', self.d).stdout)

    def test_readme_check(self):
        self.assertEqual(run('progress.py', '--root', self.d, '--check').returncode, 1)
        self.assertEqual(run('progress.py', '--root', self.d, '--update-readme').returncode, 0)
        self.assertEqual(run('progress.py', '--root', self.d, '--check').returncode, 0)
        p = f'{self.d}/README.md'
        txt = open(p).read().replace('62.50%', '99.00%')
        open(p, 'w').write(txt)
        self.assertEqual(run('progress.py', '--root', self.d, '--check').returncode, 1)

    def test_burndown_reconciles_cumulative_and_exclusive(self):
        """The ladder is cumulative: 'edge-verified' includes 'verified'. The burndown line prints
        both readings, and this pins the relation between them -- an edge-only row counts in the
        cumulative rung and not in the verified one, and the exclusive buckets sum to the tracked
        total. Reading "623 edge-verified" beside "21 verified" as disjoint buckets is the mistake
        this test exists to make impossible."""
        write_csv(f'{self.d}/symbols/ghidra_functions.csv', ['address', 'size'],
                  [['0x00401000', '100'], ['0x00402000', '50'], ['0x00403000', '10'],
                   ['0x00404000', '7']])
        write_csv(f'{self.d}/symbols/functions.csv',
                  ['address', 'size', 'name', 'system', 'status', 'notes'],
                  [['0x00401000', '100', 'a', 'frame_timing', 'verified', ''],
                   ['0x00402000', '50', 'b', 'camera', 'edge-verified', ''],
                   ['0x00403000', '10', 'c', 'camera', 'original', ''],
                   ['0x00404000', '7', 'd', 'camera', 'original', '']])
        d = json.loads(run('progress.py', '--root', self.d).stdout)
        self.assertEqual(d['verified']['functions'], 1)
        self.assertEqual(d['edge_verified']['functions'], 2)
        self.assertEqual(d['edge_verified']['bytes'], 150)
        self.assertEqual(d['statuses'], {'verified': 1, 'edge-verified': 1, 'original': 2})
        self.assertEqual(sum(d['statuses'].values()), d['tracked']['functions'])
        line = run('progress.py', '--root', self.d, '--burndown').stdout
        self.assertIn('incl. verified', line)
        self.assertIn('1 edge-verified + 2 original + 1 verified', line)

    def test_burndown_reports_evidence_that_cannot_be_rerun(self):
        """A ledger row whose `cases_sha256` is 'unavailable' records a comparison whose inputs
        are not in the tree. Counting those functions beside the rung is what stops the headline
        from claiming more than the tree can reproduce; this pins the relation, not the numbers
        (they move every session): un-rerunnable functions are a subset of the ledger's, and the
        verified subset is a subset of the verified rung."""
        write_csv(f'{self.d}/symbols/ghidra_functions.csv', ['address', 'size'],
                  [['0x00401000', '100'], ['0x00402000', '50']])
        write_csv(f'{self.d}/symbols/functions.csv',
                  ['address', 'size', 'name', 'system', 'status', 'notes'],
                  [['0x00401000', '100', 'a', 'frame_timing', 'verified', ''],
                   ['0x00402000', '50', 'b', 'camera', 'edge-verified', '']])
        write_csv(f'{self.d}/symbols/verification.csv',
                  ['function', 'cases', 'option', 'total', 'passed', 'failed', 'quarantined', 'source',
                   'cases_sha256', 'date'],
                  [['a', 'recorded', '', '3', '3', '0', '0', '', 'unavailable', '2026-01-01'],
                   ['b', 'edge', '', '2', '2', '0', '0', '', 'aa01000000000000', '2026-01-01']])
        d = json.loads(run('progress.py', '--root', self.d).stdout)
        led = d['ledger']
        self.assertEqual((led['functions'], led['unrerunnable']), (2, 1))
        self.assertEqual((led['verified'], led['unrerunnable_verified']), (1, 1))
        self.assertLessEqual(led['unrerunnable'], led['functions'])
        self.assertLessEqual(led['unrerunnable_verified'], led['verified'])
        line = run('progress.py', '--root', self.d, '--burndown').stdout
        self.assertIn('re-runnable evidence 1 of 2 (verified 0 of 1)', line)
        # The sentence a reader meets next to the rung, and the one that must not vanish when
        # README is regenerated: render it through the real path rather than asserting on prose.
        with open(f'{self.d}/README.md', 'w') as f:
            for name in ('status', 'progress', 'target'):
                f.write(f'<!-- {name}:start -->\nold\n<!-- {name}:end -->\n')
        run('progress.py', '--root', self.d, '--update-readme')
        with open(f'{self.d}/README.md') as f:
            readme = f.read()
        self.assertIn('cannot be re-run', readme)
        self.assertIn('At the top rung that is 1 of 1', readme)

    def test_empty_export(self):
        write_csv(f'{self.d}/symbols/ghidra_functions.csv', ['address', 'size'], [])
        d = json.loads(run('progress.py', '--root', self.d).stdout)
        self.assertIsNone(d['replaced']['bytes_pct'])


class Validate(Fixture):
    def test_ok(self):
        r = run('validate_functions.py', '--root', self.d)
        self.assertEqual(r.returncode, 0, r.stderr)

    def rewrite(self, **kw):
        rows = list(csv.reader(open(f'{self.d}/symbols/functions.csv')))
        return rows

    def test_rejects(self):
        cases = {
            'bad status': lambda r: r[1].__setitem__(4, 'done'),
            'bad name prefix': lambda r: r[1].__setitem__(2, 'camera_update'),
            'unknown system': lambda r: r[1].__setitem__(3, 'physics'),
            'not in export': lambda r: (r[1].__setitem__(0, '0x00409000')),
            'size mismatch': lambda r: r[1].__setitem__(1, '99'),
            'long note': lambda r: r[1].__setitem__(5, 'x' * 201),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                rows = list(csv.reader(open(f'{self.d}/symbols/functions.csv')))
                mutate(rows)
                write_csv(f'{self.d}/symbols/functions.csv', rows[0], rows[1:])
                self.assertEqual(run('validate_functions.py', '--root', self.d).returncode, 1)
                self.setUp()

    def test_rejects_address_below_image_base(self):
        write_csv(f'{self.d}/symbols/ghidra_functions.csv', ['address', 'size'], [['0x00001000', '100']])
        r = run('validate_functions.py', '--root', self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn('below the image base', r.stderr)

    def test_replaced_needs_hook(self):
        write_csv(f'{self.d}/game/hooks.csv', ['address', 'replacement', 'system'], [])
        r = run('validate_functions.py', '--root', self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no game/hooks.csv entry', r.stderr)

    def test_hook_for_original_rejected(self):
        write_csv(f'{self.d}/game/hooks.csv', ['address', 'replacement', 'system'],
                  [['0x00401000', 'bb_frame_timing_update', 'frame_timing'],
                   ['0x00402000', 'bb_camera_follow', 'camera']])
        r = run('validate_functions.py', '--root', self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("only replaced, edge-verified or verified", r.stderr)


class Merge(Fixture):
    def rows(self, *rows):
        p = f'{self.d}/rows.csv'
        write_csv(p, ['address', 'size', 'name', 'system', 'status', 'notes'], list(rows))
        return p

    def test_adds_sorted_and_validates(self):
        r = run('merge_functions.py', self.rows(['0x00403000', '10', 'camera_shake', 'camera', 'original', '']),
                '--root', self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        addrs = [row['address'] for row in csv.DictReader(open(f'{self.d}/symbols/functions.csv'))]
        self.assertEqual(addrs, sorted(addrs))
        self.assertIn('0x00403000', addrs)

    def test_conflict_writes_nothing(self):
        before = open(f'{self.d}/symbols/functions.csv').read()
        r = run('merge_functions.py', self.rows(['0x00402000', '50', 'camera_other', 'camera', 'original', '']),
                '--root', self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn('conflicting', r.stderr)
        self.assertEqual(before, open(f'{self.d}/symbols/functions.csv').read())

    def test_invalid_row_restores(self):
        before = open(f'{self.d}/symbols/functions.csv').read()
        r = run('merge_functions.py', self.rows(['0x00403000', '11', 'camera_shake', 'camera', 'original', '']),
                '--root', self.d)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(before, open(f'{self.d}/symbols/functions.csv').read())


class GameData(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        git = lambda *a: subprocess.run(['git', '-C', self.d, *a], check=True, capture_output=True)
        git('init', '-q')
        git('config', 'user.name', 't')
        git('config', 'user.email', 't@example.invalid')
        self.git = git

    def tearDown(self):
        shutil.rmtree(self.d)

    def check(self, name, data):
        with open(os.path.join(self.d, name), 'wb') as f:
            f.write(data)
        self.git('add', '-f', name)
        return run('check_no_game_data.py', '--staged', '--root', self.d)

    def test_elf_magic_under_innocent_name(self):
        self.assertEqual(self.check('notes.txt', b'\x7fELF' + b'\0' * 60).returncode, 1)

    def test_self_magic(self):
        self.assertEqual(self.check('a.dat', b'\x4f\x15\x3d\x1d' + b'\0' * 60).returncode, 1)

    def test_extension(self):
        self.assertEqual(self.check('x.prx', b'hello').returncode, 1)

    def test_target_hash(self):
        import hashlib
        data = b'plain text that happens to be listed'
        with open(os.path.join(self.d, 'target.sha256'), 'w') as f:
            f.write(hashlib.sha256(data).hexdigest() + '  x\n')
        self.assertEqual(self.check('blob.txt', data).returncode, 1)

    def test_decompiler_dump(self):
        dump = b'\n'.join(b'  undefined8 local_%d;' % i for i in range(25))
        self.assertEqual(self.check('src.c', dump).returncode, 1)

    def test_oversize(self):
        self.assertEqual(self.check('big.txt', b'a' * (2 * 1024 * 1024 + 1)).returncode, 1)

    def test_submodule_link_is_skipped(self):
        sub = tempfile.mkdtemp()
        try:
            g = lambda *a: subprocess.run(['git', '-C', sub, *a], check=True, capture_output=True)
            g('init', '-q'); g('config', 'user.name', 't'); g('config', 'user.email', 't@example.invalid')
            g('commit', '-q', '--allow-empty', '-m', 'x')
            head = subprocess.run(['git', '-C', sub, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            self.git('update-index', '--add', '--cacheinfo', f'160000,{head},vendored')
            r = run('check_no_game_data.py', '--staged', '--root', self.d)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            shutil.rmtree(sub)

    def test_clean_source_passes(self):
        r = self.check('ok.c', b'int main(void) { return 0; }\n')
        self.assertEqual(r.returncode, 0, r.stderr)

    PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 40

    def test_image_refused(self):
        self.assertEqual(self.check('shot.png', self.PNG).returncode, 1)

    def test_image_by_contents_under_other_name(self):
        self.assertEqual(self.check('notes.dat', self.PNG).returncode, 1)
        self.assertEqual(self.check('clip.txt', b'\0\0\0\x18ftypmp42' + b'\0' * 40).returncode, 1)

    def test_svg_refused(self):
        self.assertEqual(self.check('art.txt', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>').returncode, 1)

    def allow(self, text):
        os.makedirs(os.path.join(self.d, 'docs', 'assets'), exist_ok=True)
        with open(os.path.join(self.d, 'docs', 'assets', 'ALLOWLIST'), 'w') as f:
            f.write(text)
        self.git('add', '-f', 'docs/assets/ALLOWLIST')

    def test_allowlisted_tool_output_passes(self):
        self.allow('docs/assets/verify.gif  # tools/verify.py run, terminal recording\n')
        r = self.check('docs/assets/verify.gif', b'GIF89a' + b'\0' * 40)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_allowlist_needs_a_producer_and_the_assets_directory(self):
        self.allow('docs/assets/verify.gif\n')
        self.assertEqual(self.check('docs/assets/verify.gif', b'GIF89a' + b'\0' * 40).returncode, 1)
        self.allow('docs/shot.png  # a tool\n')
        os.makedirs(os.path.join(self.d, 'docs'), exist_ok=True)
        self.assertEqual(self.check('docs/shot.png', self.PNG).returncode, 1)

    def test_unlisted_file_in_assets_refused(self):
        self.allow('docs/assets/verify.gif  # tools/verify.py run\n')
        self.assertEqual(self.check('docs/assets/other.png', self.PNG).returncode, 1)


class Agnostic(Fixture):
    def test_flags_tracked_name_and_address(self):
        os.makedirs(f'{self.d}/runtime')
        open(f'{self.d}/runtime/a.c', 'w').write('int ok;\n')
        self.assertEqual(run('check_agnostic.py', '--root', self.d).returncode, 0)
        open(f'{self.d}/runtime/a.c', 'w').write('/* see frame_timing_update */\n')
        self.assertEqual(run('check_agnostic.py', '--root', self.d).returncode, 1)
        open(f'{self.d}/runtime/a.c', 'w').write('int a = 0x00402000;\n')
        self.assertEqual(run('check_agnostic.py', '--root', self.d).returncode, 1)


class PatchOverlap(Fixture):
    def write_patches(self, lines):
        path = os.path.join(self.d, 'patches.xml')
        body = ''.join(f'<Line Type="{t}" Address="{a}" Value="{v}"/>' for t, a, v in lines)
        with open(path, 'w') as f:
            f.write(f'<Patch><Metadata Name="Test patch"><PatchList>{body}</PatchList></Metadata></Patch>')
        return path

    def test_line_in_hooked_function_is_reported(self):
        r = run('patch_overlap.py', self.write_patches([('bytes', '0x00401010', '9090')]), '--root', self.d)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('Test patch: 1 line(s) in hooked 0x00401000 frame_timing_update', r.stdout)

    def test_lines_elsewhere_pass_and_map_lists_them(self):
        path = self.write_patches([('bytes32', '0x00402004', '0x1'), ('bytes', '0x00409000', '90')])
        r = run('patch_overlap.py', path, '--root', self.d, '--map')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('0x00402004 +4   0x00402000 camera_follow', r.stdout)
        self.assertIn('outside any function', r.stdout)

    def test_last_byte_inside_counts(self):
        # A 4-byte write starting just before the hooked function still lands in it.
        r = run('patch_overlap.py', self.write_patches([('bytes', '0x00400ffe', '90909090')]), '--root', self.d)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class PatchBytes(unittest.TestCase):
    def test_line_types_decode_as_written(self):
        sys.path.insert(0, TOOLS)
        from patch_overlap import patch_bytes
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'p.xml')
            with open(path, 'w') as f:
                f.write('<Patch><Metadata Name="A"><PatchList>'
                        '<Line Type="bytes" Address="0x10" Value="9090C3"/>'
                        '<Line Type="bytes32" Address="0x20" Value="0x3C888889"/>'
                        '<Line Type="float32" Address="0x30" Value="0.5"/>'
                        '</PatchList></Metadata><Metadata Name="B"><PatchList>'
                        '<Line Type="bytes" Address="0x40" Value="CC"/></PatchList></Metadata></Patch>')
            self.assertEqual(patch_bytes(path, 'A'), [(0x10, bytes.fromhex('9090c3')),
                                                      (0x20, bytes.fromhex('8988883c')),
                                                      (0x30, bytes.fromhex('0000003f'))])
            with self.assertRaises(ValueError):
                patch_bytes(path, 'missing')
        finally:
            shutil.rmtree(d)


class SessionReport(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, TOOLS)
        import session_report
        self.sr = session_report

    def test_function_changes(self):
        before = {'0x1': {'address': '0x1', 'name': 'a', 'system': 's', 'status': 'original'},
                  '0x2': {'address': '0x2', 'name': 'b', 'system': 's', 'status': 'replaced'}}
        after = dict(before)
        after['0x1'] = dict(before['0x1'], status='verified')
        after['0x2'] = dict(before['0x2'], status='verified')
        after['0x3'] = {'address': '0x3', 'name': 'c', 'system': 's', 'status': 'original'}
        ch = self.sr.function_changes(before, after)
        self.assertEqual([x['address'] for x in ch['named']], ['0x3'])
        self.assertEqual([x['address'] for x in ch['replaced']], ['0x1'])
        self.assertEqual([x['address'] for x in ch['verified']], ['0x1', '0x2'])

    def test_body_round_trip_and_failures(self):
        report = {'schema': 1, 'base': 'origin/main', 'branch': 'x', 'commits': 1,
                  'functions': {'named': [], 'replaced': [], 'verified': []},
                  'verify': [{'function': 'f', 'cases': 3, 'passed': 3, 'failed': 0}],
                  'captures': [], 'findings': ['a'], 'questions': []}
        body = 'text\n' + self.sr.render(report)
        self.assertEqual(self.sr.check_body(body), [])
        self.assertTrue(self.sr.check_body('no report here'))
        report['verify'][0]['failed'] = 1
        self.assertTrue(any('failing' in e for e in self.sr.check_body(self.sr.render(report))))


class Verify(unittest.TestCase):
    def test_self_test(self):
        self.assertEqual(run('verify.py', '--self-test').returncode, 0)

    def test_run_without_executable_is_bad_input(self):
        saved = {k: os.environ.pop(k, None) for k in ('BB_ELF', 'BB_DATA_ROOT')}
        os.environ['BB_DATA_ROOT'] = tempfile.mkdtemp()
        try:
            self.assertEqual(run('verify.py', 'run', '--function', 'x_y', '--captures', '/nonexistent').returncode, 3)
        finally:
            shutil.rmtree(os.environ.pop('BB_DATA_ROOT'))
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_compare_files(self):
        d = tempfile.mkdtemp()
        res = {'schema': 1, 'address': '0x1', 'cases': [{'id': 'a', 'ret': {'rax': '0x1'}}]}
        for n in ('o', 'r'):
            with open(f'{d}/{n}.json', 'w') as f:
                json.dump(res, f)
        self.assertEqual(run('verify.py', 'compare', f'{d}/o.json', f'{d}/r.json').returncode, 0)
        res['cases'][0]['ret']['rax'] = '0x2'
        json.dump(res, open(f'{d}/r.json', 'w'))
        self.assertEqual(run('verify.py', 'compare', f'{d}/o.json', f'{d}/r.json').returncode, 1)
        self.assertEqual(run('verify.py', 'compare', f'{d}/o.json', f'{d}/missing.json').returncode, 3)
        shutil.rmtree(d)


class Loader(unittest.TestCase):
    """runtime/loader.c through libpbloader.so, on a synthetic executable."""

    def test_maps_relocates_and_binds(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        sys.path.insert(0, os.path.join(ROOT, 'test'))
        import ctypes
        import harness
        import ps4elf
        code = bytes(range(0x20)) * 8 + bytes.fromhex('64488b042500000000') + bytes(7)
        data = ps4elf.build(
            segments=[(0, code, len(code), 5), (0x200, bytes(0x20), 0x100, 6)],
            symbols=[('local', ps4elf.STT_FUNC, 0x40), ('FUNCNID#A#B', ps4elf.STT_FUNC, None),
                     ('DATANID#C#D', ps4elf.STT_OBJECT, None)],
            relocations=[(0x200, ps4elf.R_X86_64_RELATIVE, 0, 0x80), (0x208, ps4elf.R_X86_64_64, 1, 4),
                         (0x210, ps4elf.R_X86_64_64, 3, 8)],
            jump_slots=[(0x218, ps4elf.R_X86_64_JUMP_SLOT, 2, 0)], entry=0x10)
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'eboot.elf')
            with open(path, 'wb') as f:
                f.write(data)
            exe = harness.open_executable(path)
            self.assertEqual((exe['size'], exe['entry']), (0x300, 0x10))
            self.assertEqual(exe['loads'], [(0, len(code), 5), (0x200, 0x100, 6)])
            self.assertEqual(exe['names'], ['DATANID#C#D', 'FUNCNID#A#B'])
            buf = ctypes.create_string_buffer(exe['size'])
            base = ctypes.addressof(buf)
            bind = harness.LOADER_BIND(lambda u, i, k: (0xD000 + 0x100 * i) if k == 1 else (0xF000 + 0x10 * i))
            err = ctypes.create_string_buffer(256)
            self.assertEqual(exe['loader'].rt_elf_map(exe['handle'], base, bind, None, err, 256), 0, err.value)
            img = buf.raw
            word = lambda off: struct.unpack_from('<Q', img, off)[0]
            self.assertEqual(img[:0x100], bytes(range(0x20)) * 8)
            self.assertEqual(word(0x200), base + 0x80)          # local address
            self.assertEqual(word(0x208), base + 0x44)          # local symbol + addend
            self.assertEqual(word(0x210), 0xD000 + 8)           # imported data + addend
            self.assertEqual(word(0x218), 0xF000 + 0x10)        # imported function (index 1)
            self.assertEqual(img[0x220:], bytes(0xe0))          # zero-filled
            # Mapping is not rewriting: this sequence is the guest's own `mov rax, fs:[0]`, and the
            # old rt_elf_thread_pointer_to_gs() changed its prefix to 0x65 (gs) because %gs used to be
            # the guest thread pointer. %gs is now runtime state, so that rewrite made the guest read
            # &main_state as its TCB. The bytes must survive the map unchanged.
            self.assertEqual(buf.raw[0x100:0x109], bytes.fromhex('64488b042500000000'))
        finally:
            shutil.rmtree(d)


class Boot(unittest.TestCase):
    """runtime/boot.c (pbboot) on synthetic executables, and the NID it computes."""

    @classmethod
    def setUpClass(cls):
        # No default. `build/` held a two-day-old binary and this suite passed for days against an
        # artifact nobody had rebuilt; a two-element search is still a default and its second element
        # is that same stale path. Name the variable, refuse, and let ctest (which passes BB_PBBOOT)
        # and the caller say which artifact they mean.
        env = os.environ.get('BB_PBBOOT')
        if not env:
            raise RuntimeError(
                'BB_PBBOOT is unset: this class must be told which pbboot to test, because a default '
                'silently picks a stale binary. Set BB_PBBOOT to a built one, e.g.\n'
                '  ' + os.path.join(ROOT, 'build-release', 'runtime', 'pbboot') + '\n'
                '  ' + os.path.join(ROOT, 'build', 'runtime', 'pbboot') + '  (only if that is the tree you built)')
        if not os.path.exists(env):
            raise RuntimeError('BB_PBBOOT names a path that does not exist: %s' % env)
        cls.pbboot = env
        if not os.path.isfile(cls.pbboot):
            raise unittest.SkipTest('pbboot not built')
        sys.path.insert(0, os.path.join(ROOT, 'test'))
        sys.path.insert(0, os.path.join(ROOT, 'tools'))

    def boot(self, code: bytes, imports=(), rc=0):
        import ps4elf
        page = bytearray(0x1000)
        page[:len(code)] = code
        data = ps4elf.build(
            segments=[(0, bytes(page), 0x1000, 5), (0x1000, bytes(8 * max(1, len(imports))), 0x1000, 6)],
            symbols=[(n, ps4elf.STT_FUNC, None) for n in imports],
            relocations=[], jump_slots=[(0x1000 + 8 * i, ps4elf.R_X86_64_JUMP_SLOT, i + 1, 0) for i in range(len(imports))])
        d = tempfile.mkdtemp()
        try:
            with open(os.path.join(d, 'e.elf'), 'wb') as f:
                f.write(data)
            try:
                p = subprocess.run([self.pbboot, os.path.join(d, 'e.elf'), '--status', os.path.join(d, 's.json'),
                                    '--timeout', '5'], capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired as e:
                # A deadlock and a slow machine are indistinguishable unless the partial output is shown,
                # and the difference decides whether this is a product defect or a runner one.
                self.fail('pbboot did not exit within 60 s\n  stdout so far: %r\n  stderr so far: %r'
                          % ((e.stdout or b'').decode('utf-8', 'replace')[-2000:] if isinstance(e.stdout, bytes)
                             else (e.stdout or '')[-2000:],
                             (e.stderr or b'').decode('utf-8', 'replace')[-2000:] if isinstance(e.stderr, bytes)
                             else (e.stderr or '')[-2000:]))
            # boot.c reports its outcome in the exit code too (0 returned, 1 fault, 4 unbound
            # import, 2 timeout). Pinning it here is the point: the report and the code are two
            # statements of one fact and this suite had gone red on the second because the link
            # failure meant nobody ran it.
            self.assertEqual(p.returncode, rc, p.stderr)
            with open(os.path.join(d, 's.json')) as f:
                return json.load(f)
        finally:
            shutil.rmtree(d)

    def test_a_refusal_prints_the_loader_reason_not_only_the_missing_hash(self):
        """The swallow this pins is in boot.c's branch AFTER rt_elf_open_stream, so test_loader's
        green is not evidence about it: the loader can return the right sentence and the product
        still drop it. /sys reports a length it will not supply, which is the truncated: arm."""
        path = '/sys/kernel/uevent_seqnum'
        if not os.path.exists(path):
            self.skipTest('no /sys/kernel/uevent_seqnum on this host')
        p = subprocess.run([self.pbboot, path], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn('no hash computed; the loader refused before hashing', p.stderr)
        self.assertNotIn('no bytes read', p.stderr)   # the refusal did read 6 bytes; a zero-read claim refutes the next line
        self.assertIn('truncated: read ', p.stderr)
        self.assertIn('(nothing failed', p.stderr)

    def test_entry_returns(self):
        s = self.boot(b'\xc3')
        self.assertEqual((s['outcome'], s['milestone'], s['imports_total']), ('returned', 'loaded', 0))

    def test_first_unimplemented_import_is_named(self):
        import harness
        name = harness.nid('sceKernelOpen')
        # call [rip + (0x1000 - 6)]: the first import's slot; then ret
        s = self.boot(b'\xff\x15' + struct.pack('<i', 0x1000 - 6) + b'\xc3', [name + '#A#A'], rc=4)
        self.assertEqual(s['outcome'], 'unimplemented')
        self.assertEqual(s['first_unimplemented']['nid'], name)
        self.assertEqual(s['first_unimplemented']['caller'], 'eboot')
        self.assertEqual((s['milestone'], s['imports_called'], s['imports_remaining']), ('files', 1, 1))

    def test_fault_is_reported_with_offset(self):
        s = self.boot(b'\x90' * 4 + b'\x48\x8b\x04\x25\x00\x00\x00\x00', rc=1)    # mov rax, [0]
        self.assertEqual(s['outcome'], 'fault')
        # The renderer deliberately carries BOTH coordinates since the four-space work: the guest-relative
        # offset is what a disassembler and a catalogue disagree about, so a test that pins only the first
        # half blesses a value that stopped being the whole answer.
        self.assertEqual(s['fault']['at'], 'eboot+0x4 (catalogue 0x400004)')

    def test_imports_bind_to_a_bundled_module(self):
        import harness
        import ps4elf
        f = harness.nid('f') + '#B#A'
        code = bytearray(0x1000)
        code[:7] = b'\xff\x15' + struct.pack('<i', 0x1000 - 6) + b'\xc3'      # call [import slot]; ret
        exe = ps4elf.build(segments=[(0, bytes(code), 0x1000, 5), (0x1000, bytes(8), 0x1000, 6)],
                           symbols=[(f, ps4elf.STT_FUNC, None)], relocations=[],
                           jump_slots=[(0x1000, ps4elf.R_X86_64_JUMP_SLOT, 1, 0)],
                           libraries=[(ps4elf.DT_SCE_IMPORT_LIB, 'libfoo', 1)])
        mcode = bytearray(0x1000)
        mcode[0] = 0xc3                                       # the module's entry: ret
        mcode[0x40:0x46] = b'\xb8\x2a\x00\x00\x00\xc3'      # f: mov eax, 42; ret
        mod = ps4elf.build(segments=[(0, bytes(mcode), 0x1000, 5)], symbols=[(f, ps4elf.STT_FUNC, 0x40)],
                           relocations=[], libraries=[(ps4elf.DT_SCE_EXPORT_LIB, 'libfoo', 1)])
        d = tempfile.mkdtemp()
        try:
            for name, data in (('e.elf', exe), ('m.elf', mod)):
                with open(os.path.join(d, name), 'wb') as fh:
                    fh.write(data)
            p = subprocess.run([self.pbboot, os.path.join(d, 'e.elf'), '--module', os.path.join(d, 'm.elf'),
                                '--status', os.path.join(d, 's.json'), '--timeout', '5'],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            with open(os.path.join(d, 's.json')) as fh:
                s = json.load(fh)
            self.assertEqual((s['outcome'], s['imports_bundled'], s['imports_remaining']), ('returned', 1, 0))
            listing = subprocess.run([self.pbboot, os.path.join(d, 'e.elf'), '--module', os.path.join(d, 'm.elf'),
                                      '--imports'], capture_output=True, text=True, timeout=60).stdout.split('\t')
            self.assertEqual(listing[:2] + listing[3:6], ['eboot', 'libfoo', 'function', 'm.elf', '0x00000040'])
        finally:
            shutil.rmtree(d)

    def test_c_nid_matches_python(self):
        import ctypes
        import harness
        lib = harness.loader_library()
        out = ctypes.create_string_buffer(12)
        for name in ('sceKernelOpen', '_init_env', 'malloc', 'a'):
            lib.rt_nid(name.encode(), out)
            self.assertEqual(out.value.decode(), harness.nid(name))


class Statuses(unittest.TestCase):
    def test_progress_counts_edge_verified_and_runtime(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import progress
        d = tempfile.mkdtemp()
        try:
            os.mkdir(os.path.join(d, 'symbols'))
            with open(os.path.join(d, 'symbols', 'ghidra_functions.csv'), 'w') as f:
                f.write('address,size\n0x00400000,10\n0x00400010,10\n0x00400020,10\n0x00400030,10\n')
            with open(os.path.join(d, 'symbols', 'functions.csv'), 'w') as f:
                f.write('address,size,name,system,status,notes\n0x00400000,10,a_x,a,replaced,\n'
                        '0x00400010,10,a_y,a,edge-verified,\n0x00400020,10,a_z,a,verified,\n')
            with open(os.path.join(d, 'symbols', 'boot.json'), 'w') as f:
                json.dump({'outcome': 'unimplemented', 'milestone': 'entry', 'milestone_index': 1,
                           'milestones': ['loaded', 'entry', 'threads'], 'imports_total': 4, 'imports_implemented': 1,
                           'imports_bundled': 1, 'imports_unresolved': 1, 'imports_remaining': 2,
                           'first_unimplemented': {'caller': 'mod.elf', 'library': 'libc', 'symbol': 'f', 'nid': 'x'}}, f)
            r = progress.compute(d)
            self.assertEqual((r['replaced']['functions'], r['edge_verified']['functions'], r['verified']['functions']),
                             (3, 2, 1))
            self.assertEqual((r['runtime']['imports_pct'], r['runtime']['milestones']), (50.0, 2))
            table = progress.render_progress(r)
            self.assertIn('| Edge-verified | 2 (50.00%)', table)
            self.assertIn('| Furthest boot milestone | entry (1 of 2) |', table)
            self.assertIn("| System imports implemented | 2 of 4 (50.00%): 1 by the game's own modules, 1 by the runtime |", table)
            self.assertIn('| Other imports | 1 registered fail-loud diagnostics, 1 unbound |', table)
            self.assertIn('`f` (libc, called by mod.elf)', table)
        finally:
            shutil.rmtree(d)

    def test_boot_preserves_a_resolved_name_against_a_nid(self):
        """The invariant is on the output: recording may never turn a resolved import name into a
        raw NID. A run whose NID database resolves most names leaves the rest as NIDs, so a guard
        that only checks that one was supplied passes the degradation through."""
        import boot
        before = 'importer,library,symbol,kind,provider\nsceNet,sceNet,sceNetCtlGetInfo,function,\n'
        rows = [('sceNet', 'sceNet', 'ABCDEFGHijk#p#q', 'function', '')]
        out, error = boot.preserve(before, rows, False)
        self.assertIsNone(error)
        self.assertEqual(out[0][2], 'sceNetCtlGetInfo')

    def test_boot_does_not_write_a_nid_where_a_name_was(self):
        """When the names are used up the surplus row is not written: a dropped unresolved row is
        recoverable on the next run, a rewritten name is not."""
        import boot
        before = 'importer,library,symbol,kind,provider\nsceNet,sceNet,sceNetCtlGetInfo,function,\n'
        rows = [('sceNet', 'sceNet', 'ABCDEFGHijk#p#q', 'function', ''),
                ('sceNet', 'sceNet', 'LMNOPQRStuv#p#q', 'function', '')]
        out, error = boot.preserve(before, rows, False)
        self.assertIsNone(error)
        self.assertEqual([r[2] for r in out], ['sceNetCtlGetInfo'])

    def test_boot_records_a_new_nid_it_could_not_resolve(self):
        """An import the file has never seen is recorded as the NID it is; the '#library' suffix in
        the listing marks it unidentified, and that is a fact about this run, not a loss."""
        import boot
        before = 'importer,library,symbol,kind,provider\nsceNet,sceNet,sceNetCtlGetInfo,function,\n'
        rows = [('sceHttp', 'sceHttp', 'ABCDEFGHijk#K#L', 'function', '')]
        out, error = boot.preserve(before, rows, False)
        self.assertIsNone(error)
        self.assertEqual([r[2] for r in out], ['ABCDEFGHijk#K#L'])

    def test_boot_history_records_changes_and_milestones(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import boot
        d = tempfile.mkdtemp()
        try:
            os.mkdir(os.path.join(d, 'symbols'))
            st = {'outcome': 'unimplemented', 'phase': 'eboot', 'milestone': 'entry', 'milestone_index': 1,
                  'milestones': ['loaded', 'entry', 'files'],
                  'imports_total': 4, 'imports_implemented': 0, 'imports_bundled': 1, 'imports_remaining': 3, 'imports_called': 1,
                  'first_unimplemented': {'caller': 'eboot', 'library': 'libc', 'symbol': 'f', 'nid': 'x',
                                          'returns_to': 'eboot+0x101'}}
            self.assertIsNone(boot.record(st, d, '2026-01-01'))
            self.assertIsNone(boot.record(st, d, '2026-01-02'))            # unchanged: no new row
            moved = {**st, 'first_unimplemented': {**st['first_unimplemented'], 'returns_to': 'eboot+0x220'}}
            self.assertIsNone(boot.record(moved, d, '2026-01-03'))          # same import/counts, new call site
            fault = {'outcome': 'fault', 'phase': 'libc.elf', 'milestone': 'entry', 'milestone_index': 1,
                     'imports_total': 4, 'imports_implemented': 0, 'imports_bundled': 1, 'imports_remaining': 3,
                     'fault': {'at': 'libc.elf+0x455', 'signal': 11, 'address': '0x0'}}
            self.assertIsNone(boot.record(fault, d, '2026-01-04'))
            st2 = {**st, 'milestone': 'files', 'milestone_index': 2, 'imports_implemented': 1, 'imports_remaining': 2}
            self.assertEqual(boot.record(st2, d, '2026-01-05'), 'files')
            with open(os.path.join(d, 'symbols', 'boot_history.csv')) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 4)
            self.assertEqual([row['returns_to'] for row in rows], ['eboot+0x101', 'eboot+0x220', '', 'eboot+0x101'])
            self.assertEqual((rows[2]['outcome'], rows[2]['phase'], rows[2]['fault_at'], rows[2]['fault_signal'],
                              rows[2]['fault_address']), ('fault', 'libc.elf', 'libc.elf+0x455', '11', '0x0'))
            self.assertEqual((rows[0]['milestone'], rows[-1]['milestone']), ('entry', 'files'))
        finally:
            shutil.rmtree(d)

    def test_boot_history_preserves_legacy_rows_and_adds_diagnostics(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import boot
        d = tempfile.mkdtemp()
        try:
            os.mkdir(os.path.join(d, 'symbols'))
            path = os.path.join(d, 'symbols', 'boot_history.csv')
            legacy = ['date', 'milestone', 'milestone_index', 'imports_total', 'imports_bundled',
                      'imports_implemented', 'imports_remaining', 'stops_at']
            with open(path, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=legacy, lineterminator='\n')
                w.writeheader()
                w.writerow({'date': '2026-01-01', 'milestone': 'loaded', 'milestone_index': '0',
                            'imports_total': '4', 'imports_bundled': '1', 'imports_implemented': '0',
                            'imports_remaining': '3', 'stops_at': 'eboot->libc:f'})
            status = {'outcome': 'unimplemented', 'phase': 'eboot', 'milestone': 'loaded', 'milestone_index': 0,
                      'imports_total': 4, 'imports_bundled': 1, 'imports_implemented': 0, 'imports_remaining': 3,
                      'first_unimplemented': {'caller': 'eboot', 'library': 'libc', 'symbol': 'f',
                                              'returns_to': 'eboot+0x22'}}
            boot.record(status, d, '2026-01-02')
            with open(path, newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[0]['date'], rows[0]['stops_at'], rows[0]['returns_to']),
                             ('2026-01-01', 'eboot->libc:f', ''))
            self.assertEqual((rows[1]['outcome'], rows[1]['phase'], rows[1]['returns_to']),
                             ('unimplemented', 'eboot', 'eboot+0x22'))
        finally:
            shutil.rmtree(d)


class Readable(unittest.TestCase):
    """tools/check_readable.py (STYLE.md) and the review rule in validate_functions.py."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import check_readable
        self.c = check_readable

    def found(self, code, path='game/x/f.cpp'):
        return [p.split(': ', 1)[1].split(':')[0] if ': ' in p else p for p in self.c.problems(path, code)]

    def test_transcription_patterns_fail(self):
        bad = {
            'rt::fn<Void>(0x01234567)(p);': 'call by address',
            'int v = get<int32_t>(self, 0x2bc8);': 'offset access',
            'put<float>(self, 16, v);': 'offset access',
            'q = ptr_at(self, 0x10);': 'offset access',
            'self[0x2c90] |= flag;': 'offset access',
            'if (rec.on()) x = y;': 'recording code',
            'int n = rt_capture_begin(name);': 'recording code',
            'v = _mm_add_ps(a, b);': 'SSE intrinsic outside game/engine/',
            'x = y * 30;': 'magic number 30 (name it',
        }
        for code, what in bad.items():
            out = self.c.problems('game/x/f.cpp', code + '\n')
            self.assertTrue(any(what in p for p in out), (code, out))
        self.assertTrue(self.c.problems('game/x/f.cpp', 'const char *s = "{\\"schema\\": 1}";\n'))

    def test_readable_code_passes(self):
        code = (
            '// a comment with 0x1234 and rec. in it\n'
            'RT_ORIGINAL(0x02224090, ai_group_reset, void(AiGroup *, int32_t, int32_t));\n'
            'RT_GLOBAL(0x059401a0, ai_manager_instance, AiManager *);\n'
            'constexpr uint32_t debug_mark = 2,\n'
            '                   other = 0x40;\n'
            'struct AiOwner {\n'
            '    uint8_t unknown_0x0000[0x2bc8];\n'
            '    int32_t group_count;\n'
            '};\n'
            'static_assert(offsetof(AiOwner, group_count) == 0x2bc8);\n'
            'void f(AiOwner *o) { for (int32_t i = 0; i < o->group_count; i++) ai_group_reset(nullptr, 1, 0); }\n'
            'const char *name = "text 42";\n')
        self.assertEqual(self.c.problems('game/x/f.cpp', code), [])
        self.assertEqual(self.c.problems('game/engine/vector.h', 'inline V add(V a, V b) { return _mm_add_ps(a, b); }\n'), [])

    def make_root(self, files, allow, funcs=None, reviews=None):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'tools'))
        with open(os.path.join(d, 'tools', 'readable_allowlist.txt'), 'w') as f:
            f.write('# comment\n' + ''.join(a + '\n' for a in allow))
        for rel, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
            with open(os.path.join(d, rel), 'w') as f:
                f.write(text)
        return d

    def run_check(self, d, *extra):
        return subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check_readable.py'), '--root', d, *extra],
                              capture_output=True, text=True)

    def test_allowlist_only_shrinks(self):
        bad, good = 'int x = get<int>(p, 0x10);\n', 'int x = p->field;\n'
        d = self.make_root({'game/a/a.cpp': bad, 'game/a/b.cpp': good}, ['game/a/a.cpp'])
        try:
            self.assertEqual(self.run_check(d).returncode, 0)
            base = os.path.join(d, 'base.txt')
            with open(base, 'w') as f:
                f.write('')                                         # the base had no entries
            r = self.run_check(d, '--base-list', base)
            self.assertEqual(r.returncode, 1)
            self.assertIn('may only shrink', r.stderr)
            with open(os.path.join(d, 'game/a/a.cpp'), 'w') as f:
                f.write(good)                                       # fixed: the entry must go
            r = self.run_check(d)
            self.assertIn('passes now; remove it', r.stderr)
            with open(os.path.join(d, 'game/a/c.cpp'), 'w') as f:
                f.write(bad)                                        # a new file is never grandfathered
            self.assertEqual(self.run_check(d, 'game/a/c.cpp').returncode, 1)
        finally:
            shutil.rmtree(d)

    def test_verified_needs_an_approved_review_unless_grandfathered(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v
        d = self.make_root({'game/a/f.cpp': 'extern "C" void bb_a_f(void) {}\n'}, [])
        try:
            os.makedirs(os.path.join(d, 'symbols'))
            funcs = [{'address': '0x00400000', 'name': 'a_f', 'status': 'verified', '_line': 2}]
            self.assertTrue(v.check_reviews(d, funcs))
            source = v.verification.source_hash(d, 'a_f')
            self.assertTrue(source)
            with open(os.path.join(d, 'symbols', 'reviews.csv'), 'w') as f:
                f.write('address,name,date,reviewer,verdict,scope,source_hash,cases_sha256,notes\n'
                        f'0x00400000,a_f,2026-10-07,independent session,approved,function,{source},unavailable,\n')
            self.assertEqual(v.check_reviews(d, funcs), [])
            with open(os.path.join(d, 'tools', 'readable_allowlist.txt'), 'w') as f:
                f.write('game/a/f.cpp\n')
            os.remove(os.path.join(d, 'symbols', 'reviews.csv'))
            self.assertEqual(v.check_reviews(d, funcs), [])         # grandfathered
        finally:
            shutil.rmtree(d)


class ReviewPin(unittest.TestCase):
    """A review names the replacement and the evidence it approved.

    An approval without pins survives edits to both silently: the row still reads `approved` while
    describing code nobody looked at. `symbols/reviews.csv` is checked by tools/promote.py before it
    runs anything, so an unpinned approval would also have promoted a changed function on the
    strength of an older look.
    """

    def root(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, 'game', 'engine'))
        os.makedirs(os.path.join(d, 'symbols'))
        with open(os.path.join(d, 'game', 'engine', 'sample.cpp'), 'w') as f:
            f.write('extern "C" void bb_sample(\n    void *base)\n{\n    (void)base;\n}\n')
        with open(os.path.join(d, 'symbols', 'verification.csv'), 'w') as f:
            f.write('function,cases,option,total,passed,failed,quarantined,source,cases_sha256,date\n')
            f.write('sample,edge,,4,4,0,0,abcdef0123456789,1111222233334444,2026-10-19\n')
        return d

    def review(self, d, source, evidence):
        with open(os.path.join(d, 'symbols', 'reviews.csv'), 'w', newline='') as f:
            f.write('address,name,date,reviewer,verdict,scope,source_hash,cases_sha256,notes\n')
            f.write(f'0x00400020,sample,2026-10-19,independent session,approved,function,{source},{evidence},\n')

    def funcs(self):
        return [{'address': '0x00400020', 'name': 'sample', 'status': 'verified', '_line': 2}]

    def test_a_pinned_approval_passes(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v, verification
        d = self.root()
        self.review(d, verification.source_hash(d, 'sample'), verification.evidence_hash(d, 'sample'))
        self.assertEqual(v.check_reviews(d, self.funcs()), [])

    def test_an_edited_source_makes_the_approval_stale(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v, verification
        d = self.root()
        self.review(d, verification.source_hash(d, 'sample'), verification.evidence_hash(d, 'sample'))
        self.assertEqual(v.check_reviews(d, self.funcs()), [])
        with open(os.path.join(d, 'game', 'engine', 'sample.cpp'), 'a') as f:
            f.write('// a later readability change\n')
        errs = v.check_reviews(d, self.funcs())
        self.assertTrue(any('replacement source changed since this approval' in e for e in errs), errs)

    def test_changed_evidence_makes_the_approval_stale(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v, verification
        d = self.root()
        self.review(d, verification.source_hash(d, 'sample'), verification.evidence_hash(d, 'sample'))
        self.assertEqual(v.check_reviews(d, self.funcs()), [])
        ledger = os.path.join(d, 'symbols', 'verification.csv')
        with open(ledger, 'w') as f:
            f.write('function,cases,option,total,passed,failed,quarantined,source,cases_sha256,date\n')
            f.write('sample,edge,,4,4,0,0,abcdef0123456789,9999888877776666,2026-10-20\n')
        errs = v.check_reviews(d, self.funcs())
        self.assertTrue(any('evidence set changed since this approval' in e for e in errs), errs)

    def test_the_evidence_hash_does_not_depend_on_how_the_ledger_was_written(self):
        """A row's place in the file is when it was appended, not what was approved.

        Hashing file order made an approval stale when someone rewrote `verification.csv` in a
        different order, which changes how the file reads and not what it says. The hash is taken
        in the ledger's own canonical order (CASE_SETS rank, then option), so the same evidence
        written in any order is the same evidence -- and a changed pin is still a changed pin.
        """
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import verification
        d = self.root()
        header = ('function,cases,option,total,passed,failed,quarantined,source,cases_sha256,'
                  'date\n')
        rows = ['sample,recorded,,3,3,0,0,abcdef0123456789,aaaa1111bbbb2222,2026-10-19',
                'sample,edge,,4,4,0,0,abcdef0123456789,3333444455556666,2026-10-19',
                'sample,edge,30,4,4,0,0,abcdef0123456789,7777888899990000,2026-10-19']

        def write(order):
            with open(os.path.join(d, 'symbols', 'verification.csv'), 'w') as f:
                f.write(header + '\n'.join(order) + '\n')

        write(rows)
        canonical = verification.evidence_hash(d, 'sample')
        self.assertEqual(len(canonical), verification.SOURCE_HASH_LENGTH)
        # The same three rows, written bottom-up and with the option last instead of in the middle.
        write([rows[2], rows[0], rows[1]])
        self.assertEqual(verification.evidence_hash(d, 'sample'), canonical)
        # Still a claim about contents: one pin changes, the evidence changes.
        write([rows[0], rows[1], rows[2].replace('7777888899990000', '0000000000000001')])
        self.assertNotEqual(verification.evidence_hash(d, 'sample'), canonical)

    def test_an_approval_that_pins_nothing_is_refused(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v
        d = self.root()
        self.review(d, '', '')
        errs = v.check_reviews(d, self.funcs())
        self.assertTrue(any('without a source_hash' in e for e in errs), errs)
        self.assertTrue(any('without a cases_sha256' in e for e in errs), errs)

    def test_unavailable_is_the_word_for_evidence_that_is_not_here(self):
        """The same marker the ledger uses, in the same spirit: a person looked and said so."""
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v, verification
        d = self.root()
        self.review(d, verification.source_hash(d, 'sample'), 'unavailable')
        self.assertEqual(v.check_reviews(d, self.funcs()), [])

    def test_the_printed_row_is_one_the_checker_accepts(self):
        """A pin a person types is a pin a person can mistype."""
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import validate_functions as v
        d = self.root()
        with open(os.path.join(d, 'symbols', 'functions.csv'), 'w', newline='') as f:
            f.write('address,size,name,system,status,notes\n')
            f.write('0x00400020,126,sample,engine,verified,\n')
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(v.review_row(d, 'sample'), 0)
        row = next(ln for ln in printed.getvalue().splitlines() if ln.startswith('row'))[len('row'):].strip()
        with open(os.path.join(d, 'symbols', 'reviews.csv'), 'w', newline='') as f:
            f.write('address,name,date,reviewer,verdict,scope,source_hash,cases_sha256,notes\n')
            f.write(row.replace('<date>', '2026-10-19').replace('<reviewer>', 'independent session')
                       .replace('<notes>', '') + '\n')
        self.assertEqual(v.check_reviews(d, self.funcs()), [])


class FloatFlags(unittest.TestCase):
    """tools/check_float_flags.py on synthetic compilation databases."""

    def check(self, flags):
        d = tempfile.mkdtemp()
        try:
            src = os.path.join(ROOT, 'game', 'x', 'f.cpp')
            with open(os.path.join(d, 'compile_commands.json'), 'w') as f:
                json.dump([{'directory': d, 'file': src, 'command': 'c++ ' + ' '.join(flags) + ' -c ' + src}], f)
            return subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check_float_flags.py'), d],
                                  capture_output=True, text=True)
        finally:
            shutil.rmtree(d)

    def test_required_flags_pass(self):
        self.assertEqual(self.check(['-O3', '-ffp-contract=off', '-fno-fast-math']).returncode, 0)

    def test_fast_math_and_missing_flags_fail(self):
        for flags in (['-O3', '-ffp-contract=off', '-fno-fast-math', '-ffast-math'],
                      ['-Ofast', '-ffp-contract=off', '-fno-fast-math'],
                      ['-O3', '-ffp-contract=off', '-fno-fast-math', '-fassociative-math'],
                      ['-O3', '-fno-fast-math'],
                      ['-O3', '-ffp-contract=off']):
            r = self.check(flags)
            self.assertEqual(r.returncode, 1, flags)
            self.assertIn('float flags:', r.stderr)


class VerificationRecord(unittest.TestCase):
    """tools/verification.py: the record, the quarantine and the rule for verified."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import verification
        self.v = verification
        # This fixture is a scratch tree with no git history, so it says so out loud: record()
        # refuses to stamp a snapshot with a HEAD it could not read, and the opt-out writes
        # `no-head:<time>` rather than an empty first line that reads like a commit.
        self._no_head = os.environ.get('BB_ALLOW_NO_HEAD')
        os.environ['BB_ALLOW_NO_HEAD'] = '1'
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, 'game', 'x'))
        os.makedirs(os.path.join(self.root, 'symbols'))
        with open(os.path.join(self.root, 'game', 'x', 'helper.h'), 'w') as f:
            f.write('inline int helper() { return 1; }\n')
        with open(os.path.join(self.root, 'game', 'x', 'f.cpp'), 'w') as f:
            f.write('#include "helper.h"\nextern "C" void bb_x_f(void) { helper(); }\n')
        self.funcs = [{'name': 'x_f', 'status': 'verified', '_line': 2}]
        self.cases = os.path.join(self.root, 'cases')
        os.makedirs(self.cases)
        for name in ('a', 'b', 'e'):
            with open(os.path.join(self.cases, name + '.json'), 'w') as f:
                f.write('{"id": "%s", "address": "0x00400020"}\n' % name)

    def tearDown(self):
        shutil.rmtree(self.root)
        if self._no_head is None:
            os.environ.pop('BB_ALLOW_NO_HEAD', None)
        else:
            os.environ['BB_ALLOW_NO_HEAD'] = self._no_head

    def quarantine(self, *cases):
        self.v.write_csv(os.path.join(self.root, 'symbols', 'quarantine.csv'), self.v.QUARANTINE_HEADER,
                         [{'function': 'x_f', 'cases': 'recorded', 'option': '', 'case': c, 'reason': 'why',
                           'date': '2026-10-07'} for c in cases])

    def test_clean_record_allows_verified(self):
        self.v.record(self.root, 'x_f', 'recorded', '', ['a', 'b'], [], self.cases)
        self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        self.assertEqual(self.v.check(self.root, self.funcs), [])

    def test_missing_edge_refuses_verified(self):
        self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], self.cases)
        self.assertTrue(any('current edge result' in e for e in self.v.check(self.root, self.funcs)))

    def test_unexplained_failure_refuses_verified(self):
        self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], self.cases)
        self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        self.v.record(self.root, 'x_f', 'edge', '30', ['e', 'g'], ['g'], self.cases)
        self.assertTrue(any('unexplained failure' in e for e in self.v.check(self.root, self.funcs)))

    def test_quarantined_failure_with_reason_is_allowed(self):
        self.quarantine('b')
        row = self.v.record(self.root, 'x_f', 'recorded', '', ['a', 'b'], ['b'], self.cases)
        self.assertEqual((row['failed'], row['quarantined']), ('0', '1'))
        self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        self.assertEqual(self.v.check(self.root, self.funcs), [])

    def test_quarantine_needs_a_reason(self):
        self.v.write_csv(os.path.join(self.root, 'symbols', 'quarantine.csv'), self.v.QUARANTINE_HEADER,
                         [{'function': 'x_f', 'cases': 'recorded', 'option': '', 'case': 'b', 'reason': ' ',
                           'date': '2026-10-07'}])
        self.assertTrue(any('needs its reason' in e for e in self.v.check(self.root, self.funcs)))

    def test_the_row_pins_the_case_files_it_ran(self):
        """A row is the claim "this code agrees with the original on these inputs". The source
        hash pins the code; without a hash of the cases nothing pinned the other half, so editing
        a case silently made the row a claim about inputs nobody had run."""
        row = self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], self.cases)
        self.assertEqual(len(row['cases_sha256']), self.v.SOURCE_HASH_LENGTH)
        self.assertEqual(row['cases_sha256'], self.v.cases_hash(self.cases))
        with open(os.path.join(self.cases, 'a.json'), 'a') as f:
            f.write(' ')
        self.assertNotEqual(self.v.cases_hash(self.cases), row['cases_sha256'])

    def test_every_change_to_a_case_set_changes_its_hash(self):
        """Editing counts, and so do adding, removing and renaming: the ledger counts case files,
        so a file's name is part of what it is."""
        def state():
            return self.v.cases_hash(self.cases)
        edits = []
        with open(os.path.join(self.cases, 'b.json'), 'a') as f:
            f.write(' ')
        edits.append(state())
        os.rename(os.path.join(self.cases, 'b.json'), os.path.join(self.cases, 'c.json'))
        edits.append(state())
        os.remove(os.path.join(self.cases, 'c.json'))
        edits.append(state())
        with open(os.path.join(self.cases, 'd.json'), 'w') as f:
            f.write('{}')
        edits.append(state())
        self.assertEqual(len(set(edits)), 4, edits)

    def test_a_run_with_no_case_files_records_nothing(self):
        """Recording without being able to see the inputs would be a claim with nothing behind
        it -- the same fail-open as a matching fault that compares nothing."""
        empty = os.path.join(self.root, 'empty')
        os.makedirs(empty)
        with self.assertRaises(ValueError):
            self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], empty)
        os.makedirs(os.path.join(self.root, 'onlyabi'))
        with open(os.path.join(self.root, 'onlyabi', 'abi.json'), 'w') as f:
            f.write('{}')
        with self.assertRaises(ValueError):
            self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], os.path.join(self.root, 'onlyabi'))

    def test_a_row_that_does_not_pin_its_cases_cannot_verify(self):
        """Rows recorded before this field existed carry an empty one; they must be re-recorded
        rather than read as current."""
        self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], self.cases)
        self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        path = os.path.join(self.root, 'symbols', 'verification.csv')
        rows = self.v.read_csv(path, self.v.VERIFICATION_HEADER)
        for r in rows:
            r['cases_sha256'] = ''
        self.v.write_csv(path, self.v.VERIFICATION_HEADER, rows)
        self.assertTrue(any('pins its case files' in e for e in self.v.check(self.root, self.funcs)))

    def test_a_row_that_names_the_cases_as_elsewhere_is_not_held_to_a_hash(self):
        """A row recorded where the captures still existed cannot pin them here, and saying so is
        a different act from leaving the field blank: silence is an unanswered question, and the
        check has to be able to tell them apart."""
        self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], self.cases)
        self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        path = os.path.join(self.root, 'symbols', 'verification.csv')
        rows = self.v.read_csv(path, self.v.VERIFICATION_HEADER)
        for r in rows:
            r['cases_sha256'] = self.v.CASES_UNAVAILABLE
        self.v.write_csv(path, self.v.VERIFICATION_HEADER, rows)
        self.assertEqual(self.v.check(self.root, self.funcs), [])
        # One of them left blank is still an error: the marker is a claim, not a licence for the
        # other row to go silent.
        rows[0]['cases_sha256'] = ''
        self.v.write_csv(path, self.v.VERIFICATION_HEADER, rows)
        self.assertTrue(any('pins its case files' in e for e in self.v.check(self.root, self.funcs)))

    def test_record_never_writes_the_marker(self):
        """Only a person who looked can say the captures are elsewhere."""
        row = self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        self.assertRegex(row['cases_sha256'], r'^[0-9a-f]{%d}$' % self.v.SOURCE_HASH_LENGTH)

    def test_changed_header_makes_the_record_stale(self):
        self.v.record(self.root, 'x_f', 'recorded', '', ['a'], [], self.cases)
        self.v.record(self.root, 'x_f', 'edge', '', ['e'], [], self.cases)
        with open(os.path.join(self.root, 'game', 'x', 'helper.h'), 'a') as f:
            f.write('// changed\n')
        errs = self.v.check(self.root, self.funcs)
        self.assertTrue(any('is for other code' in e for e in errs))
        self.assertTrue(any('current recorded result' in e for e in errs))

    def test_edge_verified_is_not_held_to_the_rule(self):
        self.assertEqual(self.v.check(self.root, [dict(self.funcs[0], status='edge-verified')]), [])


class Promotion(unittest.TestCase):
    """tools/promote.py keeps generated verification results out of the capture library."""

    def test_verification_output_is_temporary_and_outside_capture_directory(self):
        from unittest import mock
        from types import SimpleNamespace

        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import promote
        with tempfile.TemporaryDirectory(prefix='capture-library-') as captures:
            capture_dir = os.path.join(captures, 'sample_function')
            os.mkdir(capture_dir)
            for name in ('case_a.json', 'case_b.json'):
                with open(os.path.join(capture_dir, name), 'w') as f:
                    json.dump({}, f)
            observed = {}

            def verify(cmd, **kwargs):
                out = cmd[cmd.index('--out') + 1]
                observed['out'] = out
                observed['capture_dir'] = cmd[cmd.index('--captures') + 1]
                self.assertTrue(os.path.isdir(out))
                return SimpleNamespace(returncode=0,
                                       stdout=json.dumps({'cases': 2, 'passed': 2, 'failed': 0}),
                                       stderr='')

            with mock.patch.object(promote.subprocess, 'run', side_effect=verify):
                self.assertEqual(promote.passes('sample_function', capture_dir, None), (True, '2/2 passed'))
            self.assertEqual(observed['capture_dir'], capture_dir)
            self.assertNotEqual(os.path.commonpath([capture_dir, observed['out']]), capture_dir)
            self.assertFalse(os.path.exists(observed['out']))

    def test_another_functions_quarantined_cases_do_not_block_a_promotion(self):
        """symbols/quarantine.csv is cross-checked against the whole function list, not one row.

        promotion reads this function's complaints out of the rule that validate_functions.py runs.
        Handing that rule a single function reports every other function's quarantined cases as
        "is not in symbols/functions.csv", so a non-empty quarantine file refused every promotion.
        """
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import promote
        import verification

        with tempfile.TemporaryDirectory(prefix='promote-root-') as root:
            symbols = os.path.join(root, 'symbols')
            os.mkdir(symbols)
            functions = os.path.join(symbols, 'functions.csv')
            with open(functions, 'w', newline='') as f:
                f.write('address,size,name,system,status,description\n')
                f.write('0x00400020,126,sample_function,engine,edge-verified,being promoted\n')
                f.write('0x00400100,64,other_function,engine,verified,somebody else\n')
            with open(os.path.join(symbols, 'quarantine.csv'), 'w', newline='') as f:
                f.write('function,cases,option,case,reason,date\n')
                f.write('other_function,option-recorded,uncapped,a_case,recorded before the option changed,2026-10-07\n')
            with open(os.path.join(symbols, 'verification.csv'), 'w', newline='') as f:
                f.write('function,cases,option,total,passed,failed,quarantined,source,cases_sha256,date\n')

            # The trap, so the fix stays a fix: one row in, and the other function's quarantine
            # row is reported as missing from the file it is demonstrably in.
            trap = verification.check(root, [{'address': '0x00400020', 'name': 'sample_function',
                                              'status': 'verified', '_line': 2}])
            self.assertTrue(any('other_function is not in symbols/functions.csv' in e for e in trap),
                            trap)

            self.assertEqual(promote.problems_for(root, functions, 'sample_function', 2), [])

    def test_a_copy_of_the_recorded_cases_is_not_a_second_provenance(self):
        """Two case directories are two input sets only when their contents differ.

        promote.py promotes on agreement over two provenances: what the game recorded, and cases
        written for boundaries the recording missed. A requirement read off the directory layout is
        satisfied by one case written into both places, and then the promotion claims a second
        observation it never made. The comparison is over contents, so a renamed copy is still
        caught; a different input in either set is still permitted.
        """
        sys.path.insert(0, TOOLS)
        import promote
        with tempfile.TemporaryDirectory(prefix='capture-library-') as captures:
            recorded = os.path.join(captures, 'sample_function')
            edge = os.path.join(recorded, 'edge')
            os.makedirs(edge)
            case = {'address': '0x00400020', 'args': {'rdi': '0x1'}, 'returns': {'rax': '0x1'}}
            with open(os.path.join(recorded, 'case_a.json'), 'w') as f:
                json.dump(case, f)
            with open(os.path.join(edge, 'renamed.json'), 'w') as f:
                json.dump(case, f)
            copied = promote.case_contents(recorded), promote.case_contents(edge)
            self.assertIn('copy of the recorded set', promote.duplicate_sets(*copied), copied)
            with open(os.path.join(edge, 'renamed.json'), 'w') as f:
                json.dump(dict(case, args={'rdi': '0x2'}), f)
            self.assertIsNone(promote.duplicate_sets(promote.case_contents(recorded),
                                                    promote.case_contents(edge)))

    def test_an_edge_set_that_adds_no_input_is_not_a_second_provenance(self):
        """Equality is the easy case; a subset is the same defect one member at a time.

        An edge set whose every case is also recorded exercised nothing the recording had not, and
        a recorded set contained in the edge set leaves one provenance plus extras. Both passed the
        equality check. An empty set passes it too, by making anything else look different."""
        sys.path.insert(0, TOOLS)
        import promote
        with tempfile.TemporaryDirectory(prefix='capture-library-') as captures:
            recorded = os.path.join(captures, 'sample_function')
            edge = os.path.join(recorded, 'edge')
            os.makedirs(edge)
            for directory, names in ((recorded, ('a', 'b', 'c')), (edge, ('x', 'y'))):
                for name in names:
                    with open(os.path.join(directory, f'{name}.json'), 'w') as f:
                        json.dump({'case': name}, f)
            whole = promote.case_contents(recorded)
            self.assertEqual(len(whole), 3)
            self.assertIn('exercises no input', promote.duplicate_sets(whole, whole[1:]))
            self.assertIn('one input set with extra edge members',
                          promote.duplicate_sets(whole[1:], whole))
            self.assertIsNone(promote.duplicate_sets(whole, promote.case_contents(edge)))
            self.assertIn('empty', promote.duplicate_sets([], promote.case_contents(edge)))
            self.assertIn('empty', promote.duplicate_sets(whole, []))

    def test_promotion_refuses_a_copied_case_set_before_running_anything(self):
        """The refusal is a gate, not a note printed beside a successful run."""
        from types import SimpleNamespace
        from unittest import mock
        sys.path.insert(0, TOOLS)
        import promote
        with tempfile.TemporaryDirectory(prefix='promote-root-') as root:
            symbols = os.path.join(root, 'symbols')
            os.mkdir(symbols)
            functions = os.path.join(symbols, 'functions.csv')
            with open(functions, 'w', newline='') as f:
                f.write('address,size,name,system,status,description\n')
                f.write('0x00400020,126,sample_function,engine,edge-verified,being promoted\n')
            recorded = os.path.join(root, 'captures', 'sample_function')
            edge = os.path.join(recorded, 'edge')
            os.makedirs(edge)
            for directory in (recorded, edge):
                with open(os.path.join(directory, 'case_a.json'), 'w') as f:
                    json.dump({'address': '0x00400020'}, f)
            ran = []

            def verify(cmd, **kwargs):
                ran.append(cmd)
                return SimpleNamespace(returncode=0, stdout=json.dumps(
                    {'cases': 1, 'passed': 1, 'failed': 0, 'recorded': {'failed': 0, 'quarantined': 0}}),
                    stderr='')

            stderr = io.StringIO()
            with mock.patch.object(promote.subprocess, 'run', side_effect=verify), \
                    contextlib.redirect_stderr(stderr):
                # The tier is named here because a default is not a premise: this test is about
                # the copied-case-set refusal, and inheriting the default made it a test of
                # whichever tier happened to be default that week.
                rc = promote.main(['--to', 'verified', '--captures', os.path.join(root, 'captures')],
                                  root=root)
            # rc alone would also be 1 if the review gate refused it, which is a different reason;
            # the message is what makes this a test of the copy.
            self.assertIn('copy of the recorded set', stderr.getvalue())
            self.assertEqual(rc, 1)
            self.assertEqual(ran, [], 'the copy was refused only after comparisons had run')
            with open(functions, newline='') as f:
                self.assertIn('edge-verified', f.read())

    def test_each_case_set_reports_whether_the_game_recorded_it(self):
        """A reviewer needs to see what the gate accepted, not only that it passed.

        Every case in this checkout is hand-written (no case file carries `capture`), so this is
        reported rather than required; requiring it would refuse every promotion in the tree. The
        reading is the same one tools/differential.py records as capture_provenance.
        """
        sys.path.insert(0, TOOLS)
        import promote
        with tempfile.TemporaryDirectory(prefix='capture-library-') as captures:
            for name in ('written_by_hand.json', 'from_the_game.json'):
                with open(os.path.join(captures, name), 'w') as f:
                    json.dump({'address': '0x00400020'}, f)
            with open(os.path.join(captures, 'abi.json'), 'w') as f:
                json.dump({'input_regions': []}, f)
            self.assertEqual(promote.provenance(captures), 'synthetic 2')
            with open(os.path.join(captures, 'from_the_game.json'), 'w') as f:
                json.dump({'address': '0x00400020',
                           'capture': {'function': 'sample_function', 'run_id': 'run_1'}}, f)
            self.assertEqual(promote.provenance(captures), 'gameplay 1/2')


if __name__ == '__main__':
    unittest.main()
