# SPDX-License-Identifier: GPL-2.0-or-later
"""tools/harness.py and verify.py compare on a synthetic image: no game data needed.

The image holds one function at offset 0 (PS4 address 0x400000):

    f(out): calls import 0 (via its GOT slot) with (7, &local); local += *glob_ptr;
            *out = local; glob2 = (uint32)local

Data page at 0x1000: got0 (import 0), glob = 0x100, glob_ptr -> glob (base-relative relocation),
glob2. A correct native replacement must give the same result, a broken one must not.
"""
import base64
import hashlib
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
sys.path.insert(0, TOOLS)
import harness  # noqa: E402
import verify  # noqa: E402
import automation_pipeline  # noqa: E402
import differential  # noqa: E402
import instruction_trace  # noqa: E402
from pathlib import Path

# Most of this module's cases need the instruction tracer, so a missing Capstone used to show up as
# two dozen unrelated failures spread over the trace tests. Ask once, at import, and report the
# single cause against the class that needs it. Use the project interpreter (docs/ONBOARDING.md, section 0).
try:
    instruction_trace.Capstone()
    TRACE_PROBLEM = None
except instruction_trace.TraceUnavailable as error:
    TRACE_PROBLEM = (f'instruction tracing unavailable ({error}); install Capstone 5 for the '
                     f'interpreter running the tests, e.g. ../.venvs/paleblood/bin/pip install capstone, '
                     f'and run the suite with that interpreter')

CODE = bytes.fromhex('534889fb4883ec10bf070000004889e6ff15ea0f0000488b0424488b0def0f0000'
                     '4803014889038905eb0f00004883c4105bc3')
# At 0x400800: return [rsp+8] + [rsp+16] + [rsp+24] (three stack arguments).
STACK_CODE = bytes.fromhex('488b442408' '4803442410' '4803442418' 'c3')
DATA = bytes.fromhex('0000000000000000000100000000000008100000000000000000000000000000')
SIZE = 0x1020

REPLACEMENT_C = r'''
#include <stdint.h>
typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;
                 int (*install_hook)(uint64_t, uint64_t, const void *); } host_t;
static unsigned char *img;
int bbgame_init(const host_t *h) { img = h->image; return 0; }
typedef int (*import_fn)(int, uint64_t *);
void replacement(uint64_t *out)
{
    uint64_t local;
    (*(import_fn *)(img + 0x1000))(7, &local);
    local += **(uint64_t **)(img + 0x1010);
    BRANCH
    OUT_WRITE
    GLOBAL_WRITE
}
'''


def nid(name):
    digest = hashlib.sha1(name.encode() + bytes.fromhex('518d64a635ded8c1e6b039b1c3e55230')).digest()[:8][::-1]
    return base64.b64encode(digest).decode().rstrip('=').replace('/', '-')


def boot_image():
    """The synthetic executable: code (with the stack-argument function at 0x800) and a data page
    whose first word is the import's slot and whose word at +0x10 points at +0x8."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps4elf
    code = bytearray(0x1000)
    code[:len(CODE)] = CODE
    code[0x800:0x800 + len(STACK_CODE)] = STACK_CODE
    code[0x900:0x906] = bytes.fromhex('b807000000c3')
    code[0x910:0x912] = bytes.fromhex('ebfe')
    code[0x920:0x928] = bytes.fromhex('48c7c707000000c3')
    code[0x930:0x936] = bytes.fromhex('ba09000000c3')
    # Deliberately writes one byte beyond an eight-byte declared buffer. The payload remains
    # mapped, so the deterministic redzone check must report the exact overflow offset.
    code[0x940:0x945] = bytes.fromhex('c6470801c3')
    # Explicit guest memory operands for the instruction tracer: load then a same-value store.
    code[0x950:0x955] = bytes.fromhex('8b07 8906 c3')
    # One-byte out-of-bounds read and same-value write into the mapped redzone.
    code[0x960:0x969] = bytes.fromhex('0fb64704 884704 c3')
    # Unaligned 32-bit read, followed by return.
    code[0x970:0x976] = bytes.fromhex('8b4701 c3')
    # Aliased and overlapping pointer test: read two bytes, then write two at rsi.
    code[0x980:0x987] = bytes.fromhex('66 8b07 66 8906 c3')
    code[0x990:0x993] = bytes.fromhex('8b07 c3')
    # POP memory destinations use the incremented RSP. Save the real return stack, point RSP
    # at a fixture buffer, pop into an RSP-relative destination, restore RSP, then return.
    code[0x9a0:0x9a0 + 13] = bytes.fromhex('48 89e0 48 89fc 8f0424 4889c4 c3')
    code[0x9b0:0x9b0 + 14] = bytes.fromhex('48 89e0 48 89fc 8f442408 4889c4 c3')
    # SIB: [rsp + rcx*8 + 8], with rcx=1, so destination is entry RSP + 24.
    code[0x9c0:0x9c0 + 19] = bytes.fromhex('48 89e0 48 89fc b901000000 8f44cc08 4889c4 c3')
    # PUSH [rsp] reads from pre-decrement RSP and stores at RSP-8. Used to guard the
    # neighboring stack-instruction semantics while POP's special case is corrected.
    code[0x9e0:0x9e0 + 17] = bytes.fromhex('48 89e0 48 83c708 48 89fc ff3424 4889c4 c3')
    # Unsupported-memory fixtures stop before execution and must produce actionable gaps.
    code[0xa00:0xa02] = bytes.fromhex('a4c3')                         # movsb
    code[0xa10:0xa13] = bytes.fromhex('f3a4c3')                       # rep movsb
    code[0xa20:0xa23] = bytes.fromhex('f2aec3')                       # repne scasb
    code[0xa28:0xa2b] = bytes.fromhex('f3a6c3')                       # repe cmpsb
    code[0xa30:0xa35] = bytes.fromhex('c5fe6f07c3')                   # vmovdqu ymm0, [rdi]
    code[0xa40:0xa47] = bytes.fromhex('62f17f086f07c3')               # evex vmovdqu8
    code[0xa50:0xa53] = bytes.fromhex('0f05c3')                       # syscall
    code[0xa60:0xa63] = bytes.fromhex('d7c3')                         # xlatb
    code[0xa70:0xa74] = bytes.fromhex('0fae07c3')                      # fxsave [rdi]
    code[0xa80:0xa85] = bytes.fromhex('f00fc107c3')                   # lock xadd [rdi], eax
    code[0xa90:0xa9e] = bytes.fromhex('4889e2 4889fc 6650 6658 4889d4 c3')
    code[0xab0:0xab5] = bytes.fromhex('f20f1007c3')                   # scalar SSE movsd xmm0, [rdi]
    code[0xac0:0xac5] = bytes.fromhex('660ff7c1c3')                   # maskmovdqu [rdi], xmm1 implicit
    code[0xad0:0xad6] = bytes.fromhex('660f38f807c3')                 # movdir64b: implicit dest via RAX
    code[0xae0:0xae4] = bytes.fromhex('0f1c07c3')                     # cldemote [rdi], unclassified access
    code[0xaf0:0xaf3] = bytes.fromhex('0fa0c3')                       # push fs, width is not inferred
    code[0xaf8:0xafb] = bytes.fromhex('0fa1c3')                       # pop fs changes segment state
    code[0xb00:0xb05] = bytes.fromhex('c5f9f7c1c3')                   # vmaskmovdqu uses implicit RDI
    code[0xb10:0xb15] = bytes.fromhex('480fc70fc3')                   # cmpxchg16b [rdi], implicit atomic
    code[0xb20:0xb26] = bytes.fromhex('f3480faec7c3')                 # rdfsbase rdi, changes address state
    code[0xb30:0xb34] = bytes.fromhex('0fc7f0c3')                     # rdrand eax, nondeterministic
    code[0xb40:0xb46] = bytes.fromhex('f3480faee8c3')                 # incsspq rax, implicit shadow stack
    # A guest function calls a local import thunk; the thunk jumps through the imported GOT
    # slot to the harness bridge, matching the eboot -> sceKernelClockGettime boundary shape.
    code[0xb50:0xb61] = bytes.fromhex('4883ec084889fee8140000004883c408c3')
    code[0xb70:0xb76] = bytes.fromhex('ff258a040000')                 # jmp [rip + 0x48a] -> 0x1000
    # Preserve the buffer pointer and loop counter around 33 calls to the same import thunk.
    repeated_import = bytes.fromhex('53 4154 4883ec08 4989fc bb21000000 '
                                    '4c89e7 4c89e6 e8d6ffffff ffcb 75f1 '
                                    '4883c408 415c 5b c3')
    code[0xb80:0xb80 + len(repeated_import)] = repeated_import
    # Conditional paths with stable direct branch targets for CFG coverage tests.
    code[0xc00:0xc11] = bytes.fromhex('83ff00 7406 b801000000 c3 b802000000 c3')
    # A two-iteration loop covers both the taken and fallthrough outcomes of JNZ.
    code[0xc20:0xc2a] = bytes.fromhex('b902000000 ffc9 75fc c3')
    # Project-owned address arithmetic: an undeclared address expression is not a load.
    code[0xc40:0xc45] = bytes.fromhex('8d447707 c3')                 # lea eax, [rdi+rsi*2+7]
    # A real dereference through the computed address must still be checked.
    code[0xc50:0xc58] = bytes.fromhex('488d4708 0fb600 c3')
    code[0xc60:0xc68] = bytes.fromhex('8d047509000000 c3')         # lea eax, [rsi*2+9], no base
    # Float argument path: load a known pattern into xmm0, then call the stub at 0xd20, so a
    # case can compare a saved float register against a value guest code actually loaded.
    # The frame is not decoration: the stub prologue ends in `sub rsp, 8; call rax`, so it
    # needs rsp == 8 (mod 16) on entry, and a leaf-style caller would enter it with 0 and
    # hand the Python dispatcher a misaligned stack, which faults on an aligned SSE spill.
    code[0xd00:0xd17] = bytes.fromhex('b80000803f 660f6ec0 4883ec08 e80e000000 4883c408 c3')
    code[0xd20:0xd21] = bytes.fromhex('c3')
    return ps4elf.build(
        segments=[(0, bytes(code), 0x1000, 5), (0x1000, DATA, 0x20, 6)],
        symbols=[(nid('testImport') + '#A#A', ps4elf.STT_FUNC, None)],
        relocations=[(0x1010, ps4elf.R_X86_64_RELATIVE, 0, 0x1008)],
        jump_slots=[(0x1000, ps4elf.R_X86_64_JUMP_SLOT, 1, 0)])


CASE = {
    'schema': 1, 'address': '0x00400000', 'id': 'synthetic', 'returns': 'void',
    'args': {'rdi': 'buf:out'},
    'buffers': {'out': {'size': 8}},
    'imports': [{'name': 'testImport', 'argc': 2, 'ret': 0,
                 'writes': [{'arg': 1, 'offset': 0, 'bytes': struct.pack('<Q', 0x1234).hex()}]}],
}


@unittest.skipIf(TRACE_PROBLEM is not None, TRACE_PROBLEM or '')
@unittest.skipUnless(sys.platform == 'linux' and shutil.which(os.environ.get('CC', 'cc')),
                     'needs Linux x86-64 and a C compiler')
class Harness(unittest.TestCase):
    def test_original_preflight_traces_native_fixture_and_skips_abi_manifest(self):
        directory = Path(self.d) / 'preflight'
        directory.mkdir()
        case = {'schema': 1, 'address': '0x00400900', 'id': 'input-id', 'returns': 'i64',
                'args': {}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        (directory / 'fixture.json').write_text(json.dumps(case))
        (directory / 'abi.json').write_text(json.dumps({'calling_convention': 'synthetic metadata'}))
        result = differential.run_original(Path(self.boot), directory, case['address'], 5, True, 100)
        self.assertEqual(len(result['cases']), 1)
        execution, = result['cases']
        self.assertEqual(execution['id'], 'fixture')
        self.assertEqual(execution['ret']['rax'], '0x7')
        self.assertTrue(execution['instruction_trace']['complete'])
        self.assertEqual(execution['instruction_trace']['instructions'], 2)
        self.assertTrue(execution['instruction_trace']['control_flow_coverage']['feedback_eligible'])

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.boot = os.path.join(self.d, 'eboot.elf')
        with open(self.boot, 'wb') as f:
            f.write(boot_image())
        self.case = os.path.join(self.d, 'case.json')
        with open(self.case, 'w') as f:
            json.dump(CASE, f)

    def tearDown(self):
        shutil.rmtree(self.d)

    def side(self, lib=None):
        return self.side_case(self.case, lib, '0x00400000')

    def side_case(self, case_path, lib=None, address='0x00400000'):
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot,
               '--case', case_path, '--address', address]
        if lib:
            cmd += ['--replacement', 'replacement', '--lib', lib]
        if getattr(self, 'trace_instructions', False):
            cmd += ['--trace-instructions', '--trace-instruction-limit', '10000']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def traced_case(self, case, address):
        path = os.path.join(self.d, f'trace-{address}.json')
        with open(path, 'w') as stream:
            json.dump(case, stream)
        self.trace_instructions = True
        try:
            return self.side_case(path, address=address)
        finally:
            self.trace_instructions = False

    def test_instruction_trace_records_unaligned_read_and_same_value_write(self):
        case = {'schema': 1, 'address': '0x00400950', 'id': 'read-write', 'returns': 'void',
                'args': {'rdi': 'buf:source', 'rsi': 'buf:output'},
                'buffers': {'source': {'size': 4, 'bytes': '78563412'},
                            'output': {'size': 8, 'bytes': '7856341200000000'}},
                'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, '0x00400950')
        trace = result['instruction_trace']
        self.assertTrue(trace['complete'], trace)
        buffer_events = [event for event in trace['events'] if event['region'].startswith('buf:')]
        self.assertEqual([(event['access'], event['width']) for event in buffer_events],
                         [('read', 4), ('write', 4)])
        self.assertEqual(buffer_events[0]['region'], 'buf:source')
        self.assertEqual(buffer_events[1]['before'], buffer_events[1]['after'])
        self.assertTrue(buffer_events[1]['valid_region'])
        stack_event = next(event for event in trace['events'] if event['region'] == 'host_stack')
        self.assertEqual((stack_event['access'], stack_event['width']), ('read', 8))

    def test_instruction_trace_marks_one_byte_out_of_bounds_read_and_write(self):
        case = {'schema': 1, 'address': '0x00400960', 'id': 'oob', 'returns': 'void',
                'args': {'rdi': 'buf:source', 'rsi': 'buf:output'},
                'buffers': {'source': {'size': 4, 'bytes': 'aabbccdd'},
                            'output': {'size': 4, 'bytes': '00000000'}},
                'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, '0x00400960')
        events = [event for event in result['instruction_trace']['events'] if event['region'] != 'host_stack']
        self.assertEqual([(event['access'], event['width'], event['valid_region'])
                          for event in events], [('read', 1, False), ('write', 1, False)])
        self.assertEqual(events[0]['region'], 'unmapped_or_undeclared')
        self.assertEqual(events[1]['before'], events[1]['after'])

    def test_instruction_trace_tracks_aliasing_and_unaligned_access(self):
        case = {'schema': 1, 'address': '0x00400970', 'id': 'unaligned', 'returns': 'i32',
                'args': {'rdi': 'buf:shared+0x1'},
                'buffers': {'shared': {'size': 8, 'bytes': '00 78563412 000000'.replace(' ', '')}},
                'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, '0x00400970')
        event = next(event for event in result['instruction_trace']['events'] if event['region'] == 'buf:shared')
        self.assertEqual((event['access'], event['width'], event['region_offset']), ('read', 4, '+0x2'))
        alias = dict(case, address='0x00400980', id='alias', returns='void',
                     args={'rdi': 'buf:shared', 'rsi': 'buf:shared'})
        aliased = [event for event in self.traced_case(alias, '0x00400980')['instruction_trace']['events']
                   if event['region'] == 'buf:shared']
        self.assertEqual([(event['access'], event['width']) for event in aliased],
                         [('read', 2), ('write', 2)])
        self.assertEqual(aliased[0]['address'], aliased[1]['address'])
        overlapping = dict(alias, id='overlap', args={'rdi': 'buf:shared', 'rsi': 'buf:shared+0x1'})
        overlapped = [event for event in self.traced_case(overlapping, '0x00400980')['instruction_trace']['events']
                      if event['region'] == 'buf:shared']
        self.assertEqual([event['region_offset'] for event in overlapped], ['+0x0', '+0x1'])

    def _rsp_fixture(self, address, size, args=None):
        case = {'schema': 1, 'address': address, 'id': f'pop-rsp-{address}', 'returns': 'void',
                'args': {'rdi': 'buf:stack', **(args or {})},
                'buffers': {'stack': {'size': size, 'bytes': '8877665544332211' + '00' * (size - 8)}},
                'memory': [], 'imports': [], 'stubs': []}
        return self.traced_case(case, address)

    def _stack_buffer_events(self, result):
        return [event for event in result['instruction_trace']['events']
                if event['region'] == 'buf:stack']

    def _unsupported_instruction_case(self, address, args=None):
        case = {'schema': 1, 'address': address, 'id': f'unsupported-{address}', 'returns': 'void',
                'args': args or {'rdi': 'buf:memory', 'rsi': 'buf:source', 'rcx': 1},
                'buffers': {'memory': {'size': 128}, 'source': {'size': 128}},
                'memory': [], 'imports': [], 'stubs': []}
        return self.traced_case(case, address)

    def _assert_incomplete_instruction(self, address, capability, mnemonic):
        result = self._unsupported_instruction_case(address)
        trace = result['instruction_trace']
        self.assertFalse(trace['complete'], trace)
        self.assertEqual(trace['stop_reason'], 'unsupported_instruction')
        self.assertEqual(trace['instructions'], 0, 'unsupported instruction must not execute')
        gap = trace['gaps'][0]
        self.assertEqual(trace['control_flow_coverage']['status'], 'unavailable')
        self.assertFalse(trace['control_flow_coverage']['feedback_eligible'])
        self.assertEqual(gap['mnemonic'], mnemonic)
        self.assertEqual(gap['capability'], capability)
        self.assertIn('0x', gap['instruction'])
        compared = verify.compare(
            {'schema': 1, 'address': address, 'cases': [{'id': 'same', **result}]},
            {'schema': 1, 'address': address, 'cases': [{'id': 'same', **result}]})
        self.assertEqual(compared['failed'], 1)
        self.assertIn(gap['instruction'], compared['failures'][0]['diffs'][0])
        self.assertIn(mnemonic, compared['failures'][0]['diffs'][0])
        self.assertIn(capability, compared['failures'][0]['diffs'][0])
        self.assertIn(gap['reason'], compared['failures'][0]['diffs'][0])
        return trace

    def test_pop_rsp_uses_post_increment_destination_and_pre_increment_stack_read(self):
        result = self._rsp_fixture('0x004009a0', 16)
        events = self._stack_buffer_events(result)
        self.assertTrue(result['instruction_trace']['complete'], result['instruction_trace'])
        self.assertEqual([(event['access'], event['region_offset'], event['width']) for event in events],
                         [('read', '+0x0', 8), ('write', '+0x8', 8)])
        self.assertEqual(events[1]['before'], '0000000000000000')
        self.assertEqual(events[1]['after'], '8877665544332211')
        self.assertTrue(all(event['valid_region'] for event in events))

    def test_harness_import_transition_is_named_and_never_complete(self):
        case = dict(CASE, address='0x00400b50', id='import-thunk')
        result = self.traced_case(case, '0x00400b50')
        trace = result['instruction_trace']
        self.assertFalse(trace['complete'], trace)
        self.assertEqual(trace['skipped_host_calls'], 1)
        self.assertEqual(trace['control_flow_coverage']['status'], 'partial')
        self.assertFalse(trace['control_flow_coverage']['feedback_eligible'])
        transition, = trace['external_transitions']
        self.assertEqual(transition['kind'], 'harness_import_dispatch')
        self.assertEqual(transition['symbol'], 'testImport')
        self.assertEqual(transition['trace_status'], 'incomplete')
        self.assertEqual(transition['instruction'], 'guest:0x400b70')
        self.assertIn('C/Python dispatcher is outside guest instruction tracing', transition['reason'])
        boundary_gap, = [gap for gap in trace['gaps']
                         if gap['capability'] == 'control_flow' and
                         'enters the harness import trampoline' in gap['reason']]
        self.assertEqual(boundary_gap['mnemonic'], 'jmp')
        self.assertEqual(int(boundary_gap['instruction'], 16) - 0x800000000 + 0x400000,
                         0x400b70)
        self.assertFalse(any(gap['mnemonic'] == 'mov' and gap['reason'] == boundary_gap['reason']
                             for gap in trace['gaps']), trace['gaps'])
        observation, = trace['import_observations']
        self.assertEqual(observation['status'], 'returned')
        self.assertEqual(observation['identity'], 'original')
        self.assertEqual(observation['symbol'], 'testImport')
        self.assertEqual(observation['return_location'], 'guest:0x400b5c')
        self.assertFalse(observation['instruction_coverage'])
        self.assertFalse(observation['memory_access_coverage'])
        self.assertFalse(observation['cfg_feedback_eligible'])
        out, = [item for item in observation['memory'] if item['region'] == 'buf:out']
        self.assertEqual(out['before'], '0000000000000000')
        self.assertEqual(out['after'], '3412000000000000')
        self.assertEqual(out['changed_offsets'], [0, 1])
        self.assertIn('same-value writes', observation['unobserved'])

        failed_side = {'cases': [{'id': result['id'], 'instruction_trace': trace}]}
        comparison = {'cases': 1, 'passed': 1, 'failed': 0}
        with self.assertRaisesRegex(automation_pipeline.PipelineError, 'incomplete instruction trace'):
            automation_pipeline.assert_result_sufficient(
                {'comparison': comparison, 'original': failed_side, 'replacement': failed_side}, 1)

    def test_import_snapshot_observes_same_value_write_only_as_unchanged_bytes(self):
        case = dict(CASE, address='0x00400b50', id='same-value-import',
                    imports=[{'name': 'testImport', 'argc': 2, 'ret': 9,
                              'writes': [{'arg': 1, 'bytes': '00' * 8}]}])
        result = self.traced_case(case, '0x00400b50')
        trace = result['instruction_trace']
        observation, = trace['import_observations']
        out, = [item for item in observation['memory'] if item['region'] == 'buf:out']
        self.assertEqual(out['changed_offsets'], [])
        self.assertEqual(observation['registers_after']['rax'], '0x9')
        self.assertTrue(any(item['source'] == 'import_write' for item in result['access_trace']))
        self.assertFalse(trace['complete'])
        self.assertFalse(trace['control_flow_coverage']['feedback_eligible'])
        self.assertTrue(any('untraced external execution' in difference
                            for difference in verify.compare_case(result, result)))

    def test_import_observation_limit_does_not_restore_trace_completeness(self):
        case = dict(CASE, address='0x00400b80', id='many-imports',
                    imports=[{'name': 'testImport', 'argc': 2, 'ret': 0} for _ in range(33)])
        trace = self.traced_case(case, '0x00400b80')['instruction_trace']
        self.assertEqual(trace['skipped_host_calls'], 33)
        self.assertEqual(len(trace['import_observations']), 32)
        self.assertTrue(trace['import_observations_truncated'])
        self.assertTrue(all(item['status'] == 'returned' for item in trace['import_observations']))
        self.assertFalse(trace['complete'])
        self.assertFalse(trace['control_flow_coverage']['feedback_eligible'])

    def test_import_observation_keeps_replacement_execution_identity(self):
        self.trace_instructions = True
        try:
            result = self.side(self.build())
        finally:
            self.trace_instructions = False
        observation, = result['instruction_trace']['import_observations']
        self.assertEqual(observation['identity'], 'replacement')
        self.assertEqual(observation['status'], 'returned')
        self.assertEqual(observation['symbol'], 'testImport')
        self.assertFalse(result['instruction_trace']['complete'])

    def test_pop_rsp_displacement_uses_incremented_stack_pointer(self):
        result = self._rsp_fixture('0x004009b0', 24)
        events = self._stack_buffer_events(result)
        self.assertTrue(result['instruction_trace']['complete'], result['instruction_trace'])
        self.assertEqual([(event['access'], event['region_offset']) for event in events],
                         [('read', '+0x0'), ('write', '+0x10')])
        self.assertTrue(events[1]['valid_region'])

    def test_pop_rsp_sib_index_and_displacement_use_incremented_base(self):
        result = self._rsp_fixture('0x004009c0', 32)
        events = self._stack_buffer_events(result)
        self.assertTrue(result['instruction_trace']['complete'], result['instruction_trace'])
        self.assertEqual([(event['access'], event['region_offset']) for event in events],
                         [('read', '+0x0'), ('write', '+0x18')])
        self.assertTrue(events[1]['valid_region'])

    def test_pop_rsp_actual_out_of_bounds_destination_fails_closed(self):
        result = self._rsp_fixture('0x004009a0', 8)
        trace = result['instruction_trace']
        events = [event for event in result['instruction_trace']['events']
                  if event['region'] == 'buf:stack' or event.get('bounds_violation')]
        self.assertFalse(trace['complete'], trace)
        self.assertEqual([(event['access'], event['region'], event['valid_region'])
                          for event in events], [('read', 'buf:stack', True),
                                                ('write', 'unmapped_or_undeclared', False)])
        # Before this fix both events were attributed to +0x0, making the destination look in-bounds.
        self.assertEqual(int(events[1]['address'], 16), int(events[0]['address'], 16) + 8)
        compared = verify.compare(
            {'schema': 1, 'address': '0x004009a0', 'cases': [result]},
            {'schema': 1, 'address': '0x004009a0', 'cases': [result]})
        self.assertEqual(compared['failed'], 1)
        self.assertTrue(any('instruction memory bounds violation' in diff
                            for diff in compared['failures'][0]['diffs']))

    def test_push_rsp_source_keeps_pre_decrement_address(self):
        result = self._rsp_fixture('0x004009e0', 16)
        events = self._stack_buffer_events(result)
        self.assertTrue(result['instruction_trace']['complete'], result['instruction_trace'])
        # The source uses pre-decrement RSP; the implicit destination is one word below it.
        self.assertEqual([(event['access'], event['region_offset']) for event in events[:2]],
                         [('read', '+0x8'), ('write', '+0x0')])

    def test_string_and_repeat_memory_forms_fail_closed_with_diagnostics(self):
        self._assert_incomplete_instruction('0x00400a00', 'string_memory', 'movsb')
        self._assert_incomplete_instruction('0x00400a10', 'repeat_string_memory', 'rep movsb')
        self._assert_incomplete_instruction('0x00400a20', 'repeat_string_memory', 'repne scasb')
        self._assert_incomplete_instruction('0x00400a28', 'repeat_string_memory', 'repe cmpsb')

    def test_lea_outside_declared_regions_is_address_arithmetic_not_a_read(self):
        import instruction_trace
        decoder = instruction_trace.Capstone()
        decoded = decoder.decode(0x400c40, bytes.fromhex('8d447707'))
        self.assertTrue(decoded['address_calculation'])
        self.assertEqual(decoded['operands'], [])
        self.assertEqual(len(decoded['address_operands']), 1)
        issue = instruction_trace._instruction_support_issue({**decoded, 'address_calculation': False})
        self.assertEqual(issue[0], 'address_calculation')
        case = {'schema': 1, 'address': '0x00400c40', 'id': 'lea-only', 'returns': 'i32',
                'args': {'rdi': '0x0', 'rsi': '0x1'}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, case['address'])
        self.assertEqual(result['ret']['rax'], '0x9')
        trace = result['instruction_trace']
        self.assertTrue(trace['complete'], trace)
        self.assertEqual([event['mnemonic'] for event in trace['events']], ['ret'])
        self.assertTrue(trace['control_flow_coverage']['feedback_eligible'])
        indexed = self.traced_case({**case, 'address': '0x00400c60'}, '0x00400c60')
        self.assertEqual(indexed['ret']['rax'], '0xb')
        self.assertTrue(indexed['instruction_trace']['complete'], indexed['instruction_trace'])
        self.assertEqual([event['mnemonic'] for event in indexed['instruction_trace']['events']], ['ret'])

    def test_real_load_through_lea_result_still_fails_bounds_checks(self):
        case = {'schema': 1, 'address': '0x00400c50', 'id': 'lea-then-load', 'returns': 'i32',
                'args': {'rdi': 'buf:data'}, 'buffers': {'data': {'size': 4, 'bytes': '00000000'}},
                'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, case['address'])
        trace = result['instruction_trace']
        self.assertFalse(trace['complete'])
        self.assertFalse(any(event['mnemonic'] == 'lea' for event in trace['events']))
        self.assertTrue(any(event['mnemonic'] == 'movzx' and event.get('bounds_violation') for event in trace['events']))
        self.assertFalse(trace['control_flow_coverage']['feedback_eligible'])
        self.assertTrue(any('instruction memory bounds violation' in diff for diff in verify.compare_case(result, result)))

    def test_vex_and_evex_memory_operands_fail_before_execution(self):
        self._assert_incomplete_instruction('0x00400a30', 'vex_evex_memory', 'vmovdqu')
        self._assert_incomplete_instruction('0x00400a40', 'vex_evex_memory', 'vmovdqu8')

    def test_system_and_special_implicit_memory_operations_fail_closed(self):
        self._assert_incomplete_instruction('0x00400a50', 'system_instruction', 'syscall')
        self._assert_incomplete_instruction('0x00400a60', 'special_memory_operation', 'xlatb')
        self._assert_incomplete_instruction('0x00400a70', 'special_memory_operation', 'fxsave')
        self._assert_incomplete_instruction('0x00400a80', 'atomic_memory', 'lock xadd')
        self._assert_incomplete_instruction('0x00400ac0', 'special_memory_operation', 'maskmovdqu')
        self._assert_incomplete_instruction('0x00400ad0', 'special_memory_operation', 'movdir64b')
        self._assert_incomplete_instruction('0x00400ae0', 'special_memory_operation', 'cldemote')
        self._assert_incomplete_instruction('0x00400af0', 'stack_segment_state', 'push')
        self._assert_incomplete_instruction('0x00400af8', 'stack_segment_state', 'pop')
        self._assert_incomplete_instruction('0x00400b00', 'special_memory_operation', 'vmaskmovdqu')
        self._assert_incomplete_instruction('0x00400b10', 'atomic_memory', 'cmpxchg16b')
        self._assert_incomplete_instruction('0x00400b20', 'system_instruction', 'rdfsbase')
        self._assert_incomplete_instruction('0x00400b30', 'nondeterministic_instruction', 'rdrand')
        self._assert_incomplete_instruction('0x00400b40', 'system_instruction', 'incsspq')

    def test_16_bit_register_push_and_pop_trace_exact_stack_width(self):
        case = {'schema': 1, 'address': '0x00400a90', 'id': 'stack-width-16', 'returns': 'void',
                'args': {'rdi': 'buf:stack+0x2'},
                'buffers': {'stack': {'size': 4, 'bytes': '00000000'}},
                'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, '0x00400a90')
        events = self._stack_buffer_events(result)
        self.assertTrue(result['instruction_trace']['complete'], result['instruction_trace'])
        self.assertEqual([(event['access'], event['width'], event['region_offset']) for event in events],
                         [('write', 2, '+0x0'), ('read', 2, '+0x0')])

    def test_scalar_sse_movsd_memory_operand_is_not_misclassified_as_string(self):
        case = {'schema': 1, 'address': '0x00400ab0', 'id': 'scalar-movsd', 'returns': 'void',
                'args': {'rdi': 'buf:memory'},
                'buffers': {'memory': {'size': 8, 'bytes': '8877665544332211'}},
                'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, '0x00400ab0')
        self.assertTrue(result['instruction_trace']['complete'], result['instruction_trace'])
        events = [event for event in result['instruction_trace']['events']
                  if event['region'] == 'buf:memory']
        self.assertEqual([(event['access'], event['width']) for event in events], [('read', 8)])

    def test_control_flow_coverage_reports_fixture_branch_paths(self):
        fixtures = [
            {'schema': 1, 'address': '0x00400c00', 'id': 'branch-zero', 'returns': 'i32',
             'args': {'rdi': '0x0'}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []},
            {'schema': 1, 'address': '0x00400c00', 'id': 'branch-nonzero', 'returns': 'i32',
             'args': {'rdi': '0x1'}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []},
        ]
        coverages = {}
        for case in fixtures:
            result = self.traced_case(case, '0x00400c00')
            coverage = result['instruction_trace']['control_flow_coverage']
            self.assertEqual(coverage['status'], 'complete', coverage)
            self.assertTrue(coverage['feedback_eligible'], coverage)
            coverages[case['id']] = coverage
        zero_edges = [edge for edge in coverages['branch-zero']['edges']
                      if edge['kind'] == 'conditional']
        nonzero_edges = [edge for edge in coverages['branch-nonzero']['edges']
                         if edge['kind'] == 'conditional']
        self.assertEqual([(edge['branch_instruction'], edge['outcome']) for edge in zero_edges],
                         [('guest:0x400c03', 'taken')])
        self.assertEqual([(edge['branch_instruction'], edge['outcome']) for edge in nonzero_edges],
                         [('guest:0x400c03', 'fallthrough')])
        self.assertIn('guest:0x400c0b', {block['address'] for block in coverages['branch-zero']['blocks']})
        self.assertIn('guest:0x400c05', {block['address'] for block in coverages['branch-nonzero']['blocks']})

    def test_control_flow_coverage_reports_loop_backedge_and_exit(self):
        case = {'schema': 1, 'address': '0x00400c20', 'id': 'loop-two', 'returns': 'void',
                'args': {}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        result = self.traced_case(case, '0x00400c20')
        coverage = result['instruction_trace']['control_flow_coverage']
        self.assertEqual(coverage['status'], 'complete', coverage)
        loop_edges = [edge for edge in coverage['edges'] if edge['branch_instruction'] == 'guest:0x400c27']
        self.assertEqual({edge['outcome'] for edge in loop_edges}, {'taken', 'fallthrough'})
        taken = next(edge for edge in loop_edges if edge['outcome'] == 'taken')
        self.assertEqual((taken['to'], taken['hits']), ('guest:0x400c25', 1))

    def test_linear_path_has_complete_zero_conditional_coverage(self):
        case = {'schema': 1, 'address': '0x00400900', 'id': 'linear', 'returns': 'i32',
                'args': {}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        coverage = self.traced_case(case, '0x00400900')['instruction_trace']['control_flow_coverage']
        self.assertEqual(coverage['status'], 'complete', coverage)
        self.assertTrue(coverage['feedback_eligible'])
        self.assertTrue(coverage['blocks'])
        self.assertFalse([edge for edge in coverage['edges'] if edge['kind'] == 'conditional'])

    def test_wrong_branch_mutation_fails_comparison_and_changes_covered_edge(self):
        case = {'schema': 1, 'address': '0x00400c00', 'id': 'branch-mutation', 'returns': 'i32',
                'args': {'rdi': '0x0'}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        path = os.path.join(self.d, 'branch-mutation.json')
        with open(path, 'w') as stream:
            json.dump(case, stream)
        source = os.path.join(self.d, 'branch-mutation.c')
        library = os.path.join(self.d, 'branch-mutation.so')
        with open(source, 'w') as stream:
            stream.write('#include <stdint.h>\n'
                         'typedef struct { uint32_t version; unsigned char *image; uint64_t image_size; '
                         'int (*install_hook)(uint64_t,uint64_t,const void *); } host_t;\n'
                         'int bbgame_init(const host_t *host) { (void)host; return 0; }\n'
                         'uint32_t replacement(uint32_t value) { return value ? 2u : 1u; }\n')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O0', '-o', library, source], check=True)
        self.trace_instructions = True
        try:
            original = self.side_case(path, address='0x00400c00')
            replacement = self.side_case(path, library, '0x00400c00')
        finally:
            self.trace_instructions = False
        compared = verify.compare(
            {'schema': 1, 'address': '0x00400c00', 'cases': [original]},
            {'schema': 1, 'address': '0x00400c00', 'cases': [replacement]})
        self.assertEqual(compared['failed'], 1)
        original_coverage = original['instruction_trace']['control_flow_coverage']
        replacement_coverage = replacement['instruction_trace']['control_flow_coverage']
        self.assertEqual(original_coverage['status'], 'complete')
        self.assertEqual(replacement_coverage['status'], 'complete')
        self.assertNotEqual(original_coverage['edges'], replacement_coverage['edges'])

    def test_first_divergence_diagnostic_allows_equivalent_instruction_paths(self):
        case = {'schema': 1, 'address': '0x00400990', 'id': 'different-path', 'returns': 'i32',
                'args': {'rdi': 'buf:value'}, 'buffers': {'value': {'size': 4, 'bytes': '78563412'}},
                'memory': [], 'imports': [], 'stubs': []}
        path = os.path.join(self.d, 'different-path.json')
        with open(path, 'w') as stream:
            json.dump(case, stream)
        replacement_source = os.path.join(self.d, 'different-path.c')
        replacement_lib = os.path.join(self.d, 'different-path.so')
        with open(replacement_source, 'w') as stream:
            stream.write('#include <stdint.h>\n'
                         'typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;\n'
                         'int (*install_hook)(uint64_t,uint64_t,const void *); } host_t;\n'
                         'int bbgame_init(const host_t *host) { (void)host; return 0; }\n'
                         'uint32_t replacement(volatile uint32_t *value) { uint32_t first=*value; '
                         '(void)*value; return first; }\n')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', replacement_lib,
                        replacement_source], check=True)
        self.trace_instructions = True
        try:
            original = self.side_case(path, address='0x00400990')
            replacement = self.side_case(path, replacement_lib, '0x00400990')
        finally:
            self.trace_instructions = False
        compared = verify.compare(
            {'schema': 1, 'address': '0x00400990', 'cases': [original]},
            {'schema': 1, 'address': '0x00400990', 'cases': [replacement]})
        self.assertEqual(compared['failed'], 0)
        divergence = compared['instruction_diagnostics'][0]['first_divergence']
        self.assertEqual(divergence['classification'], 'bounded_memory_trace_difference')
        self.assertFalse(divergence['observable_result_mismatch'])
        self.assertIn('state_before', divergence['replacement'])

        with open(replacement_source, 'w') as stream:
            stream.write('#include <stdint.h>\n'
                         'typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;\n'
                         'int (*install_hook)(uint64_t,uint64_t,const void *); } host_t;\n'
                         'int bbgame_init(const host_t *host) { (void)host; return 0; }\n'
                         'uint32_t replacement(volatile uint32_t *value) { return *value + 1; }\n')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', replacement_lib,
                        replacement_source], check=True)
        self.trace_instructions = True
        try:
            mutated = self.side_case(path, replacement_lib, '0x00400990')
        finally:
            self.trace_instructions = False
        rejected = verify.compare(
            {'schema': 1, 'address': '0x00400990', 'cases': [original]},
            {'schema': 1, 'address': '0x00400990', 'cases': [mutated]})
        self.assertEqual(rejected['failed'], 1)
        mismatch = rejected['instruction_diagnostics'][0]['first_divergence']
        self.assertTrue(mismatch['observable_result_mismatch'])

    def build(self, broken=False, mutation=None):
        src = os.path.join(self.d, 'r.c')
        with open(src, 'w') as f:
            source = REPLACEMENT_C.replace('BRANCH', 'local = local == 0x1334 ? 1 : local;' if mutation == 'branch' else '')
            source = source.replace('OUT_WRITE', '' if mutation == 'missing-write' else '*out = local ' + ('+ 1' if broken else '') + ';')
            source = source.replace('GLOBAL_WRITE',
                                    '*(uint16_t *)(img + 0x1018) = (uint16_t)local;' if mutation == 'narrow-write'
                                    else '*(uint32_t *)(img + 0x1018) = (uint32_t)local;')
            f.write(source)
        lib = os.path.join(self.d, f'r{int(broken)}-{mutation or "plain"}.so')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', lib, src], check=True)
        return lib

    def test_original_runs(self):
        r = self.side()
        self.assertEqual(r['calls'], [{'import': 'testImport', 'args': ['0x7', 'stack'],
                                       'scripted_write_targets': ['stack']}])
        self.assertIn({'addr': 'buf:out+0x0', 'bytes': '3413'}, r['writes'])
        self.assertIn({'addr': '0x00401018', 'bytes': '3413'}, r['writes'])
        self.assertTrue(all(v == 'kept' for v in r['preserved'].values()))
        self.assertTrue(any(event['access'] == 'write' and event['source'] == 'import_write'
                            for event in r['access_trace']))
        self.assertIn('not instrumented', r['access_trace_scope'])

    def test_byte_precise_redzone_reports_guest_buffer_overrun(self):
        case = {'schema': 1, 'address': '0x00400940', 'id': 'redzone', 'returns': 'void',
                'args': {'rdi': 'buf:out'}, 'buffers': {'out': {'size': 8}},
                'memory': [], 'imports': [], 'stubs': []}
        path = os.path.join(self.d, 'redzone.json')
        with open(path, 'w') as stream:
            json.dump(case, stream)
        result = self.side_case(path, address='0x00400940')
        self.assertEqual(result['redzone_writes'], [{'buffer': 'out', 'first_offset': 8, 'changed_bytes': 1}])
        self.assertTrue(any('redzone modified' in error for error in result['errors']))

    def compare(self, broken):
        res = lambda r: {'schema': 1, 'address': '0x00400000', 'cases': [r]}
        return verify.compare(res(self.side()), res(self.side(self.build(broken))))

    def test_correct_replacement_matches(self):
        self.assertEqual(self.compare(False)['failed'], 0)

    def test_broken_replacement_fails(self):
        out = self.compare(True)
        self.assertEqual(out['failed'], 1)
        self.assertIn('buf:out+0x0', out['failures'][0]['diffs'][0])

    def test_mutation_matrix_rejects_branch_and_memory_write_errors(self):
        out = self.compare(False)
        self.assertEqual(out['failed'], 0)
        for mutation in ('branch', 'missing-write', 'narrow-write'):
            with self.subTest(mutation=mutation):
                case_path = self.case
                if mutation == 'narrow-write':
                    case = dict(CASE, memory=[{'addr': '0x00401018', 'bytes': 'aabbccdd'}])
                    case_path = os.path.join(self.d, 'narrow.json')
                    with open(case_path, 'w') as stream:
                        json.dump(case, stream)
                original = self.side_case(case_path)
                replacement = self.side_case(case_path, self.build(mutation=mutation))
                summary = verify.compare(
                    {'schema': 1, 'address': '0x00400000', 'cases': [original]},
                    {'schema': 1, 'address': '0x00400000', 'cases': [replacement]},
                )
                self.assertEqual(summary['failed'], 1)

    def test_wrong_return_mutation_is_detected_on_original_instructions(self):
        case = {'schema': 1, 'address': '0x00400900', 'id': 'return', 'returns': 'i32',
                'args': {}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        case_path = os.path.join(self.d, 'return.json')
        with open(case_path, 'w') as stream:
            json.dump(case, stream)
        source = os.path.join(self.d, 'return.c')
        library = os.path.join(self.d, 'return.so')
        with open(source, 'w') as stream:
            stream.write('#include <stdint.h>\n'
                         'typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;\n'
                         'int (*install_hook)(uint64_t,uint64_t,const void *); } host_t;\n'
                         'int bbgame_init(const host_t *h) { (void)h; return 0; }\n'
                         'int replacement(void) { return 8; }\n')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', library, source], check=True)
        original = verify.run_side(self.boot, case_path, '0x00400900', None, None)
        replacement = verify.run_side(self.boot, case_path, '0x00400900', 'replacement', library)
        summary = verify.compare(
            {'schema': 1, 'address': case['address'], 'cases': [original]},
            {'schema': 1, 'address': case['address'], 'cases': [replacement]},
        )
        self.assertEqual(summary['failed'], 1)
        self.assertTrue(any('ret.rax' in item for item in summary['failures'][0]['diffs']))

    def test_opted_in_caller_saved_register_is_compared(self):
        case = {'schema': 1, 'address': '0x00400920', 'id': 'caller-saved', 'returns': 'void',
                'observe_registers': ['rdi'], 'args': {}, 'buffers': {}, 'memory': [],
                'imports': [], 'stubs': []}
        case_path = os.path.join(self.d, 'register.json')
        with open(case_path, 'w') as stream:
            json.dump(case, stream)
        original = self.side_case(case_path, address='0x00400920')
        self.assertEqual(original['registers']['rdi'], '0x7')
        self.assertEqual(original['observed_registers'], ['rdi'])
        case.update(address='0x00400930', observe_registers=['rdx'])
        with open(case_path, 'w') as stream:
            json.dump(case, stream)
        original = self.side_case(case_path, address='0x00400930')
        self.assertEqual(original['registers']['rdx'], '0x9')

    def test_case_can_enter_with_a_value_in_rax(self):
        # The trampoline used to emit `xor eax, eax` immediately before the call, so every case
        # entered with a clean rax: an original that clears eax (most functions returning an int)
        # was indistinguishable from a replacement that leaves it alone. All 528
        # engine_zero_init_* members were exactly that mistake.
        case = {'schema': 1, 'address': '0x00400920', 'id': 'entry-rax', 'returns': 'void',
                'observe_registers': ['rax'], 'args': {'rax': '0xdeadbeef'}, 'buffers': {},
                'memory': [], 'imports': [], 'stubs': []}
        case_path = os.path.join(self.d, 'entry_rax.json')
        with open(case_path, 'w') as stream:
            json.dump(case, stream)
        # 0x400920 is `mov rdi, 7; ret`: it never touches rax, so what comes back went in.
        self.assertEqual(self.side_case(case_path, address='0x00400920')['registers']['rax'],
                         '0xdeadbeef')
        del case['args']['rax']
        with open(case_path, 'w') as stream:
            json.dump(case, stream)
        # Omitting rax keeps the trampoline's old behaviour, so no existing case changes meaning.
        self.assertEqual(self.side_case(case_path, address='0x00400920')['registers']['rax'], '0x0')

    def test_original_instruction_timeout_is_bounded(self):
        case = {'schema': 1, 'address': '0x00400910', 'id': 'infinite-loop', 'returns': 'void',
                'args': {}, 'buffers': {}, 'memory': [], 'imports': [], 'stubs': []}
        case_path = os.path.join(self.d, 'timeout.json')
        with open(case_path, 'w') as stream:
            json.dump(case, stream)
        result = verify.run_side(self.boot, case_path, case['address'], None, None, timeout=1)
        self.assertEqual(result['fault'], 'timeout after 1 s')

    def test_run_counts_cases_with_repeated_ids(self):
        caps = os.path.join(self.d, 'caps')
        os.makedirs(caps)
        for n in ('a', 'b'):
            with open(os.path.join(caps, f'{n}.json'), 'w') as f:
                json.dump(CASE, f)            # both files carry id 'synthetic'
        lib = self.build(False)
        results = verify.run_cases(self.boot, caps, '0x00400000', 'replacement', lib)
        res = lambda side: {'schema': 1, 'address': '0x00400000', 'cases': results[side]}
        out = verify.compare(res('original'), res('replacement'))
        self.assertEqual((out['cases'], out['failed']), (2, 0))

    def test_capture_provenance_is_optional_but_bound_when_present(self):
        caps = os.path.join(self.d, 'caps')
        os.makedirs(caps)
        path = os.path.join(caps, 'capture.json')
        captured = dict(CASE, capture={'function': 'synthetic_function', 'run_id': 'test-run_1'})
        with open(path, 'w') as f:
            json.dump(captured, f)
        lib = self.build(False)
        results = verify.run_cases(self.boot, caps, '0x00400000', 'replacement', lib,
                                   function='synthetic_function')
        self.assertEqual(len(results['original']), 1)
        with self.assertRaisesRegex(verify.BadInput, 'records .+, not'):
            verify.run_cases(self.boot, caps, '0x00400000', 'replacement', lib,
                             function='different_function')
        captured['capture'] = {'function': 'synthetic_function', 'run_id': '../escape'}
        with open(path, 'w') as f:
            json.dump(captured, f)
        with self.assertRaisesRegex(verify.BadInput, 'invalid capture run_id'):
            verify.run_cases(self.boot, caps, '0x00400000', 'replacement', lib,
                             function='synthetic_function')

    def test_legacy_capture_without_provenance_replays(self):
        caps = os.path.join(self.d, 'caps')
        os.makedirs(caps)
        with open(os.path.join(caps, 'legacy.json'), 'w') as f:
            json.dump(CASE, f)
        results = verify.run_cases(self.boot, caps, '0x00400000', 'replacement', self.build(False),
                                   function='synthetic_function')
        self.assertEqual(len(results['original']), 1)

    def test_direct_harness_rejects_wrong_case_address(self):
        wrong = dict(CASE, address='0x00400800')
        with open(self.case, 'w') as f:
            json.dump(wrong, f)
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot,
               '--case', self.case, '--address', '0x00400000']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 3)
        self.assertIn('case is for 0x00400800', r.stderr)

    def test_a_saved_float_register_is_read_from_the_guest(self):
        # code[0xd00] loads 0x3f800000 into xmm0 and calls the stub at 0xd20, so a pattern that
        # matches proves the field reads a register rather than whatever the block held.
        case = dict(CASE, address='0x00400d00', id='float-arg', returns='i64',
                    args={}, buffers={}, imports=[],
                    stubs=[{'address': '0x00400d20', 'argc': 0, 'argf32': [0]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side_case(self.case, None, '0x00400d00')
        self.assertNotIn('fault', r)                    # a guest fault is a payload field, not a status
        self.assertEqual(r['calls'][0]['argf32'], ['0000803f'])

    def test_an_argf32_index_that_names_no_saved_register_is_refused(self):
        # The stub block saves exactly xmm0 (+64) and xmm1 (+80). Index 2 reads at +96, which is
        # the next stub slot and therefore identical on both sides: without the refusal the case
        # compares equal on bytes nothing saved and passes with a value it never set.
        case = dict(CASE, address='0x00400d00', id='float-slot-two', returns='i64',
                    args={}, buffers={}, imports=[],
                    stubs=[{'address': '0x00400d20', 'argc': 0, 'argf32': [2]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot,
               '--case', self.case, '--address', '0x00400d00']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 3)
        self.assertIn('argf32 index 2 names no saved register', r.stderr)
        # One line: the refusal travels to the parent as the payload main() writes, so a
        # second, unrelated parse error must not appear after the real diagnostic.
        self.assertNotIn('Expecting value', r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_an_import_argf32_index_that_names_no_saved_register_is_refused(self):
        case = dict(CASE, address='0x00400b50', id='float-import-slot-two',
                    imports=[{'name': 'testImport', 'argc': 2, 'argf32': [2]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot,
               '--case', self.case, '--address', '0x00400b50']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 3)
        self.assertIn('argf32 index 2 names no saved register', r.stderr)
        # One line: the refusal travels to the parent as the payload main() writes, so a
        # second, unrelated parse error must not appear after the real diagnostic.
        self.assertNotIn('Expecting value', r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_stub_replaces_a_game_function(self):
        # Stub f itself at 0x400000 and call it through... the harness calls the stub directly.
        case = dict(CASE, stubs=[{'address': '0x00400000', 'ret': 5}], returns='i64', imports=[])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side()
        self.assertEqual(r['ret'], {'rax': '0x5'})
        self.assertEqual(r['calls'], [{'call': '0x00400000', 'args': []}])
        self.assertEqual(r['writes'], [])

    def test_series_entry_writes_one_value_per_call(self):
        # The function reads the first 8 bytes the import writes: the timeval's seconds.
        case = dict(CASE, imports=[{'name': 'testImport', 'argc': 2, 'ret': 0,
                                    'series': {'arg': 1, 'format': 'timeval_us',
                                               'values': [0x1234 * 1_000_000 + 7]}}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side()
        self.assertIn({'addr': 'buf:out+0x0', 'bytes': '3413'}, r['writes'])
        self.assertNotIn('errors', r)

    def test_scripted_write_can_name_its_target(self):
        # The shape ../data/cases/wait/*.json specified and never ran: a write that lands at an
        # address the case names, because the import receives no pointer to write through. The
        # target is a buffer the fixture's own code never touches: `out` is written by the guest
        # after the call returns, so a write there would be clobbered before the snapshot.
        case = dict(CASE, buffers={'out': {'size': 8}, 'side': {'size': 8}},
                    imports=[{'name': 'testImport', 'argc': 1, 'ret': 0,
                              'writes': [{'target': 'buf:side+0x0', 'bytes': '0200000000000000'}]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side()
        # The observed write diff reports the bytes that changed, so a store of 2 over a zeroed
        # buffer is one byte: `writes` is a diff, not a transcription of what was written.
        self.assertIn({'addr': 'buf:side+0x0', 'bytes': '02'}, r['writes'])
        self.assertEqual(r['calls'][0]['scripted_write_targets'], ['buf:side+0x0'])
        self.assertNotIn('errors', r)

    def test_scripted_write_target_applies_to_a_stub(self):
        case = dict(CASE, stubs=[{'address': '0x00400000', 'argc': 1, 'ret': 5,
                                  'writes': [{'target': 'buf:out+0x0', 'bytes': '05000000'}]}],
                    returns='i64', imports=[])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side()
        self.assertEqual(r['ret'], {'rax': '0x5'})
        self.assertIn({'addr': 'buf:out+0x0', 'bytes': '05'}, r['writes'])
        self.assertEqual(r['calls'][0]['scripted_write_targets'], ['buf:out+0x0'])

    def test_a_truncated_import_write_is_reported(self):
        # `size` says how long the write should have been: a capture that lost bytes is an
        # incomplete recording, and the harness says so rather than writing a short store that
        # happens to succeed.
        # The fixture calls testImport(7, rsp), so args[1] is the stack -- a legal write target,
        # which is what lets this test reach the size check instead of failing region validation.
        case = dict(CASE, imports=[{'name': 'testImport', 'argc': 2, 'ret': 0,
                                    'writes': [{'arg': 1, 'offset': 0, 'size': 8, 'bytes': '0200'}]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side()
        self.assertIn('testImport: write of 2 bytes, the case says 8', r.get('errors', []))

    def test_a_truncated_stub_write_is_reported(self):
        # This path had no size check until scripted_write was shared: the stub branch took
        # bytes.fromhex and memmove'd it, so a truncated recording served a short store silently.
        # The import branch had checked since it was written, which is how the asymmetry hid.
        case = dict(CASE, stubs=[{'address': '0x00400000', 'argc': 1, 'ret': 5,
                                  'writes': [{'arg': 0, 'offset': 0, 'size': 8, 'bytes': '0500'}]}],
                    returns='i64', imports=[])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        r = self.side()
        # r.get: on a harness without the check the result carries no `errors` at all, and the
        # failure should say the message is missing, not raise KeyError from the test itself.
        self.assertIn('0x00400000: write of 2 bytes, the case says 8', r.get('errors', []))

    def test_a_reported_error_fails_the_comparison_even_when_both_sides_agree(self):
        # A truncated write produces the same message on both sides, so a comparison that looked
        # only at whether the two results were equal would pass it. compare_case turns every
        # recorded error into a diff for that reason: a case the harness could not serve is not
        # a case the original and the replacement agreed on.
        result = {'ret': {'rax': '0x0'}, 'writes': [], 'calls': [],
                  'errors': ['testImport: write of 2 bytes, the case says 8']}
        diffs = verify.compare_case(result, dict(result), {'schema': 1})
        self.assertTrue(any('write of 2 bytes' in d for d in diffs), diffs)

    def test_a_register_is_not_a_write_target(self):
        case = dict(CASE, imports=[{'name': 'testImport', 'argc': 2, 'ret': 0,
                                    'writes': [{'target': 'rdi', 'bytes': '00'}]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot,
               '--case', self.case, '--address', '0x00400000']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn('a register is not a target', r.stderr)

    def test_a_scripted_write_outside_every_writable_region_is_refused(self):
        # 0x00400100 is inside the read+execute segment: nameable, so the case is legal-looking,
        # and refused for a write rather than silently scribbling on the image.
        case = dict(CASE, imports=[{'name': 'testImport', 'argc': 2, 'ret': 0,
                                    'writes': [{'target': 'guest:0x00400100', 'bytes': '00'}]}])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot,
               '--case', self.case, '--address', '0x00400000']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn('0x00400100', r.stderr)
        self.assertIn('outside declared readable/writable regions', r.stderr)

    def test_stack_arguments(self):
        case = dict(CASE, address='0x00400800', args={}, stack=['0x1', '0x20', '0x300'], returns='i64', imports=[])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        cmd = [sys.executable, os.path.join(TOOLS, 'harness.py'), '--elf', self.boot, '--case', self.case,
               '--address', '0x00400800']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out['ret'], {'rax': '0x321'})
        self.assertEqual(out['preserved']['rsp'], 'kept')

    def test_unscripted_import_is_reported(self):
        case = dict(CASE, imports=[])
        with open(self.case, 'w') as f:
            json.dump(case, f)
        self.assertIn('errors', self.side())


@unittest.skipUnless(shutil.which("cc"), "needs a C compiler to build a stand-in library")
class ReplacementLibrary(unittest.TestCase):
    """A library that initialises but does not export the replacement is a build problem, and it
    must say so. Before this, the missing symbol reached the child as a bare AttributeError and
    the run ended `exit 1`, which reads exactly like the replacement faulting."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.lib = os.path.join(cls.dir.name, "libnomatch.so")
        source = os.path.join(cls.dir.name, "nomatch.c")
        with open(source, "w") as f:
            f.write("int bbgame_init(void *host) { (void)host; return 0; }\n"
                    "int bb_unrelated_symbol(void) { return 1; }\n")
        subprocess.run(["cc", "-shared", "-fPIC", "-o", cls.lib, source], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_a_missing_symbol_names_the_library_and_the_symbol(self):
        with self.assertRaises(harness.BadInput) as caught:
            harness.load_replacement(self.lib, "bb_not_here", 0x1000)
        message = str(caught.exception)
        self.assertIn("does not export bb_not_here", message)
        self.assertIn(os.path.basename(self.lib), message)

    def test_a_present_symbol_resolves(self):
        address = harness.load_replacement(self.lib, "bb_unrelated_symbol", 0x1000)
        self.assertTrue(address)


class RegionValidation(unittest.TestCase):
    """check_memory decides which addresses a case may name, and on what terms.

    The image is described the way boot['loads'] reports one: (vaddr, memsz, flags) with the
    vaddr as an offset from the image base. Flags are 1 execute, 2 write, 4 read, so the first
    segment is read+execute and the second writable, which is the real layout: constants live
    in the executable segment, mutable state does not.
    """

    LOADS = [(0x0000, 0x1000, 5), (0x1000, 0x1000, 6)]
    SIZE = 0x2000

    def region(self, buffers=None, stack_top=0):
        run = harness.Run({'loads': self.LOADS, 'size': self.SIZE}, {})
        run.buffers.update(buffers or {})
        run.block[19] = stack_top
        return run

    def test_guest_write_into_executable_segment_is_refused(self):
        run = self.region()
        with self.assertRaises(harness.BadInput):
            run.check_memory(harness.IMAGE + 0x20, 0x10, write=True)

    def test_guest_write_into_writable_segment_is_allowed_and_traced(self):
        run = self.region()
        run.check_memory(harness.IMAGE + 0x1010, 0x10, write=True)
        self.assertEqual(run.access_trace[0]['region'], 'guest_image')
        self.assertEqual(run.access_trace[0]['address'], '0x00401010')

    def test_preset_may_seed_the_executable_segment(self):
        run = self.region()
        run.check_memory(harness.IMAGE + 0x20, 0x10, write=True, source='fixture_setup')
        self.assertEqual(run.access_trace, [])

    def test_preset_outside_every_segment_is_refused(self):
        run = self.region()
        with self.assertRaises(harness.BadInput):
            run.check_memory(harness.IMAGE + self.SIZE + 0x10, 0x10, write=True, source='fixture_setup')

    def test_preset_straddling_a_segment_end_is_refused(self):
        run = self.region()
        with self.assertRaises(harness.BadInput):
            run.check_memory(harness.IMAGE + 0x0ff8, 0x10, write=True, source='fixture_setup')

    def test_preset_inside_a_buffer_is_allowed_and_not_traced(self):
        run = self.region({'region': (harness.IMAGE + 0x3000, 0xd0)})
        run.check_memory(harness.IMAGE + 0x3000, 0xd0, write=True, source='fixture_setup')
        self.assertEqual(run.access_trace, [])

    def test_buffer_access_is_traced_for_the_program(self):
        run = self.region({'region': (harness.IMAGE + 0x3000, 0xd0)})
        run.check_memory(harness.IMAGE + 0x3050, 0x10, write=True)
        self.assertEqual(run.access_trace[0]['region'], 'buf:region+0x0')

    def test_stack_window_is_allowed(self):
        top = harness.IMAGE + 0x8000
        run = self.region(stack_top=top)
        run.check_memory(top - 0x10, 0x8, write=True)
        self.assertEqual(run.access_trace[0]['region'], 'stack')


class SlotCopyRegion(unittest.TestCase):
    """The overlap case must declare room for the stores the member actually makes.

    The addresses stay in game/engine/slot_copy_cases.py, which is where this repository keeps
    them; this test only reads the generator's constants and the cases it produced.
    """

    CASES = Path(ROOT).parent / 'data' / 'cases' / 'slot_copy'

    def overlaps(self):
        if not self.CASES.is_dir():
            self.skipTest(f'no generated cases at {self.CASES}')
        return sorted(self.CASES.glob('*/overlap_*.json'))

    def test_overlap_regions_cover_the_destination_span(self):
        sys.path.insert(0, os.path.join(ROOT, 'game', 'engine'))
        import slot_copy_cases
        found = self.overlaps()
        self.assertTrue(found)
        for path in found:
            case = json.loads(path.read_text())
            region = case['buffers']['region']['size']
            destination = int(case['args']['rdi'].split('+')[1], 16)
            with self.subTest(case=str(path.parent.name)):
                # The destination is placed OVERLAP_SHIFT past the source and the member stores
                # across its whole span, so the region has to hold both.
                self.assertGreaterEqual(region, destination + slot_copy_cases.DEST_SPAN)

    def test_one_store_past_the_region_is_refused(self):
        for path in self.overlaps():
            region = json.loads(path.read_text())['buffers']['region']['size']
            run = harness.Run({'loads': [], 'size': 0x100}, {})
            run.buffers['region'] = (harness.IMAGE + 0x3000, region)
            last = harness.IMAGE + 0x3000 + region - 0x10
            run.check_memory(last, 0x10, write=True)
            with self.assertRaises(harness.BadInput):
                run.check_memory(last + 0x10, 0x10, write=True)


if __name__ == '__main__':
    unittest.main()
