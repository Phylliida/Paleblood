#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Replay a case written by the production recorder (runtime/include/runtime/recorder.hpp).

test/test_capture_poc.cpp proves that a case from its own test-only serializer replays. The
recorder that a replacement will actually call had no such proof: test/test_capture.cpp checks the
JSON it writes, and nothing replayed it. This runs that recorder over a synthetic function, then
replays the case through the same verifier that tools/promote.py calls, so the serializer's output
format is known to be a replayable case rather than merely a plausible document.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote
import ps4elf
import verify


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit('usage: capture_recorder_replay.py TEST_CAPTURE_EXECUTABLE')
    emitted = subprocess.run([sys.argv[1], '--emit'], check=True, capture_output=True, text=True)
    case = json.loads(emitted.stdout)

    # The recorder's own claims about the call it observed.
    assert case['schema'] == 1, case
    assert case['address'] == '0x00400000', case
    assert case['capture']['function'] == 'capture_recorder_replay', case
    assert case['capture']['run_id'] == 'synthetic_run_1', case
    assert case['args'] == {'rdi': 'buf:b0', 'rsi': 'buf:b1', 'rdx': '0x00000006'}, case
    # Buffers are declared with a size and their initial bytes are separate memory entries: the
    # shape the recorder uses for host memory, and the one the harness has to accept. The field is
    # at 0x14, so b0 grows to 0x20: 0x14 + 4 rounds up to the next multiple of 16.
    assert case['buffers'] == {'b0': {'size': 0x20}, 'b1': {'size': 16}}, case
    # The offset is hex with the 0x prefix. It used to be `std::to_string(off)`, a bare decimal,
    # which tools/verify.py's split_addr read base 16: 0x14 went out as "20" and would have come
    # back as 0x20. Both ends have to name a displacement the same way.
    assert case['memory'] == [{'addr': 'buf:b0+0x14', 'bytes': '44332211'},
                              {'addr': 'buf:b1+0x0', 'bytes': '07000000'}], case
    assert case['stubs'] == [] and case['imports'] == [], case

    with tempfile.TemporaryDirectory(prefix='pb-recorder-replay-') as root:
        boot = os.path.join(root, 'synthetic.elf')
        # mov eax,[rsi]; imul eax,edx; mov [rdi+0x14],eax; ret -- the store's displacement is the
        # ground truth for the recorded offset, read out of the instruction encoding rather than
        # from the recorder or the verifier.
        code = bytes.fromhex('8b06 0fafc2 894714 c3')
        store_displacement = code[-2]
        assert store_displacement == 0x14, hex(store_displacement)
        image = code + bytes(0x1000 - len(code))
        with open(boot, 'wb') as stream:
            stream.write(ps4elf.build(segments=[(0, image, len(image), 5)], symbols=[],
                                      relocations=[], jump_slots=[]))

        # The recorder writes <BB_CAPTURE_DIR>/<function>/, so this is the recorded set and only
        # the recorded set; nothing here invents an edge set to sit beside it.
        cases = os.path.join(root, 'captures', case['capture']['function'])
        os.makedirs(cases)
        with open(os.path.join(cases, 'synthetic_run_1_0000.json'), 'w', encoding='utf-8') as stream:
            json.dump(case, stream, sort_keys=True)

        source = os.path.join(root, 'replacement.c')
        with open(source, 'w', encoding='utf-8') as stream:
            stream.write(r'''#include <stdint.h>
typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;
                 int (*install_hook)(uint64_t, uint64_t, const void *); } host_t;
int bbgame_init(const host_t *host) { (void)host; return 0; }
int32_t replacement(int32_t *out, const int32_t *input, int32_t factor)
{ *(int32_t *)((char *)out + 0x14) = *input * factor; return *input * factor; }
''')
        library = os.path.join(root, 'replacement.so')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', library, source],
                       check=True)
        # The same function storing four bytes early. The verifier has to notice a difference at
        # 0x14, not agree because neither side touched offset 0.
        wrong_source = os.path.join(root, 'wrong.c')
        with open(wrong_source, 'w', encoding='utf-8') as stream:
            stream.write(r'''#include <stdint.h>
typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;
                 int (*install_hook)(uint64_t, uint64_t, const void *); } host_t;
int bbgame_init(const host_t *host) { (void)host; return 0; }
int32_t replacement(int32_t *out, const int32_t *input, int32_t factor)
{ *(int32_t *)((char *)out + 0x10) = *input * factor; return *input * factor; }
''')
        wrong_library = os.path.join(root, 'wrong.so')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', wrong_library,
                        wrong_source], check=True)

        sides = verify.run_cases(boot, cases, '0x00400000', 'replacement', library,
                                 function=case['capture']['function'])
        report = verify.compare(
            {'schema': 1, 'address': '0x00400000', 'cases': sides['original']},
            {'schema': 1, 'address': '0x00400000', 'cases': sides['replacement']})
        assert (report['cases'], report['passed'], report['failed']) == (1, 1, 0), report

        # Agreement alone would hold even if the recorded bytes were dropped: both sides would read
        # zeros and match. The scripted call reads 7, multiplies by the recorded 6, and writes 42,
        # so the original side's own result proves the case's memory entries reached the guest.
        original = sides['original'][0]
        assert original['ret'] == {'rax': '0x2a'}, original['ret']
        assert original['writes'] == [{'addr': 'buf:b0+0x14', 'bytes': '2a000000'}], original['writes']
        # The address the harness reported carries the displacement the instruction encodes.
        assert original['writes'][0]['addr'].endswith('+0x%x' % store_displacement)

        # A case written by an older recorder carries a bare decimal offset; it has to mean the
        # same field, not a field further on.
        assert verify.split_addr('buf:b0+20') == ('buf:b0', 0x14), verify.split_addr('buf:b0+20')
        assert verify.split_addr('buf:b0+0x14') == ('buf:b0', 0x14)

        # A replacement that stores four bytes early must fail, naming 0x14: the comparison is
        # sensitive to the offset itself, not only to both sides agreeing somewhere.
        wrong = verify.run_cases(boot, cases, '0x00400000', 'replacement', wrong_library,
                                 function=case['capture']['function'])
        failed = verify.compare(
            {'schema': 1, 'address': '0x00400000', 'cases': wrong['original']},
            {'schema': 1, 'address': '0x00400000', 'cases': wrong['replacement']})
        assert (failed['cases'], failed['passed'], failed['failed']) == (1, 0, 1), failed
        assert '0x14' in json.dumps(failed['failures']), failed

        # tools/promote.py reads a capture library as <name>/ (recorded) and <name>/edge/. The
        # recorder produces only the first, so the gate promote.py applies is two cases: a recorded
        # set it can see, and no edge set beside it. This test used to write the same case into both
        # directories so the gate would pass -- a copy answering a requirement that exists to
        # guarantee two independent provenances. promote.py now refuses that copy, and the honest
        # statement of what this test proves is narrower: the recorder's output replays through the
        # comparison engine; it cannot, by itself, promote anything.
        assert promote.cases(cases) == 1, promote.cases(cases)

        # The other half of the gate has no author in this tree: the recorder observes whatever the
        # game did, so it cannot invent the boundary case a promotion needs beside it. This writes
        # one the way such a case is actually authored -- take a recorded input and move it
        # somewhere the recording never went -- and then shows the gate both refusing a copy and
        # accepting the perturbation. Without this, promote.py's content comparison has no live
        # caller: the previous assertions only reach it through a directory with no edge set at
        # all, which is the branch that skips it.
        edge = os.path.join(cases, 'edge')
        os.makedirs(edge)
        perturbed = json.loads(json.dumps(case))
        perturbed['id'] = 'perturbed_input_0001'
        # No `capture` block: the game never made this call, and claiming it did would report the
        # edge set as gameplay in promote.provenance.
        del perturbed['capture']
        perturbed['memory'] = [{'addr': 'buf:b0+0x14', 'bytes': '44332211'},
                               {'addr': 'buf:b1+0x0', 'bytes': '09000000'}]
        with open(os.path.join(edge, 'perturbed_input_0001.json'), 'w', encoding='utf-8') as stream:
            json.dump(perturbed, stream, sort_keys=True)

        # case_contents reads one directory's own *.json, so the recorded set is still the single
        # recorder case and the edge set is the single perturbed one.
        recorded_contents = promote.case_contents(cases)
        edge_contents = promote.case_contents(edge)
        assert len(recorded_contents) == len(edge_contents) == 1, (recorded_contents, edge_contents)
        assert promote.duplicate_sets(recorded_contents, recorded_contents) is not None, \
            'a copy of the recorded set must still be refused'
        assert promote.duplicate_sets(recorded_contents, edge_contents) is None, \
            'a perturbed input is a second provenance'

        # And the perturbation is a real one: the guest reads 9, not 7, so the case cannot agree
        # with the original for the reason the recorded case does.
        edge_sides = verify.run_cases(boot, edge, '0x00400000', 'replacement', library,
                                      function=case['capture']['function'])
        edge_report = verify.compare(
            {'schema': 1, 'address': '0x00400000', 'cases': edge_sides['original']},
            {'schema': 1, 'address': '0x00400000', 'cases': edge_sides['replacement']})
        assert (edge_report['cases'], edge_report['passed'], edge_report['failed']) == (1, 1, 0), edge_report
        assert edge_sides['original'][0]['ret'] == {'rax': '0x36'}, edge_sides['original'][0]['ret']
        assert edge_sides['original'][0]['writes'] == [{'addr': 'buf:b0+0x14', 'bytes': '36000000'}], \
            edge_sides['original'][0]['writes']

    print('recorder case replayed: 1/1 passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
