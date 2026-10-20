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
    # shape the recorder uses for host memory, and the one the harness has to accept.
    assert case['buffers'] == {'b0': {'size': 16}, 'b1': {'size': 16}}, case
    assert case['memory'] == [{'addr': 'buf:b0+0', 'bytes': '44332211'},
                              {'addr': 'buf:b1+0', 'bytes': '07000000'}], case
    assert case['stubs'] == [] and case['imports'] == [], case

    with tempfile.TemporaryDirectory(prefix='pb-recorder-replay-') as root:
        boot = os.path.join(root, 'synthetic.elf')
        code = bytes.fromhex('8b06 0fafc2 8907 c3')  # *out = *input * factor; return *out
        image = code + bytes(0x1000 - len(code))
        with open(boot, 'wb') as stream:
            stream.write(ps4elf.build(segments=[(0, image, len(image), 5)], symbols=[],
                                      relocations=[], jump_slots=[]))

        cases = os.path.join(root, 'captures', case['capture']['function'])
        os.makedirs(os.path.join(cases, 'edge'))
        for directory in (cases, os.path.join(cases, 'edge')):
            with open(os.path.join(directory, 'synthetic_run_1_0000.json'), 'w', encoding='utf-8') as stream:
                json.dump(case, stream, sort_keys=True)

        source = os.path.join(root, 'replacement.c')
        with open(source, 'w', encoding='utf-8') as stream:
            stream.write(r'''#include <stdint.h>
typedef struct { uint32_t version; unsigned char *image; uint64_t image_size;
                 int (*install_hook)(uint64_t, uint64_t, const void *); } host_t;
int bbgame_init(const host_t *host) { (void)host; return 0; }
int32_t replacement(int32_t *out, const int32_t *input, int32_t factor)
{ *out = *input * factor; return *out; }
''')
        library = os.path.join(root, 'replacement.so')
        subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2', '-o', library, source],
                       check=True)

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
        assert original['writes'] == [{'addr': 'buf:b0+0x0', 'bytes': '2a000000'}], original['writes']

        # tools/promote.py reads a capture library as <name>/ (recorded) and <name>/edge/. The
        # recorder writes <BB_CAPTURE_DIR>/<function>/, so a recorded set lands there directly and
        # only the edge set has to be added; check the gate promote.py applies, not just the claim.
        assert promote.cases(cases) == 1, promote.cases(cases)
        assert promote.cases(os.path.join(cases, 'edge')) == 1

    print('recorder case replayed: 1/1 passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
