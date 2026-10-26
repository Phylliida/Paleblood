"""Falsify one pilot body before the family it pilots.

A green pilot proves the path executes. It cannot tell you whether the comparison is CAPABLE of
disagreeing -- that distinction cost this campaign the 117 void survivors and eleven rip_load greens.
So each mutant names, in PREREG below, the channel expected to fire, and the expectation is printed
BEFORE the mutant runs. A mutant whose channel is silent is not a survivor: it means the pilot is
asserting the harness, and the family is cancelled rather than deferred.
"""
import json
import os
import subprocess
import sys

# the prologue of a file is its FIRST import, not its first line: `-P` removes the script's
# directory from sys.path, so a sibling import above this line needs environment help to start.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mutate

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAMILY = os.path.join(ROOT, 'game', 'leaf', 'chain_deref_family.cpp')
LIB = os.path.join(ROOT, 'build-release', 'game', 'libbbgame.so')
ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
from case_dir import case_dir
# The pilot's address is an ANSWER, not an input: it is whatever `pilot_choice` selects from the family's
# landed members, so it is derived here rather than copied. A copy is a second source of truth that agrees
# on the day it is written and silently describes a different member the first time the rule or the table
# moves -- and the agnostic gate refuses the literal anyway, which is the same rule stated as a gate.
import emit_leaf_family as _E
_chosen, _key, _shared = _E.pilot_choice(_E.members('chain_deref', landed=True))
ADDRESS = '%#010x' % _chosen['address']
SYMBOL = 'bb_leaf_chain_deref_%08x' % _chosen['address']
CASE = case_dir('chain_deref').find(_chosen['address'])
if CASE is None:
    raise SystemExit(f'pilot_mutants: no case file at either declared layout for {_chosen["address"]:#x}')

# name -> (old text, new text, channel, the sentence the channel must confirm)
PREREG = {
    'store_disp_plus4': ('constexpr std::uintptr_t kStoreDisp = 0xf0;',
                         'constexpr std::uintptr_t kStoreDisp = 0xf4;',
                         'mem', 'the sentinel at 0xf0 is left untouched, so mem must differ from the '
                                'baseline (which zeroed it)'),
    'imm_0_to_1': ('constexpr std::uint64_t kImm = 0x0;', 'constexpr std::uint64_t kImm = 0x1;',
                   'mem', 'the sentinel at 0xf0 is overwritten with 01000000, so mem must differ at '
                          'exactly those four bytes'),
    'load_disp_plus4': ('constexpr std::uintptr_t kSlot = 0x5962878;',
                        'constexpr std::uintptr_t kSlot = 0x596287c;',
                        'rax', 'the qword at slot+4 is not the seeded pointer: rax must differ, and the '
                               'store must fault or differ with it'),
}


def build():
    subprocess.run(['cmake', '--build', os.path.join(ROOT, 'build-release'), '--target', 'bbgame',
                    '-j8'], check=True, capture_output=True)


def run():
    proc = subprocess.run([sys.executable, '-P', os.path.join(HERE, 'harness.py'), '--elf', ELF,
                           '--case', CASE, '--address', ADDRESS, '--replacement', SYMBOL,
                           '--lib', LIB], capture_output=True, text=True)
    if proc.returncode == 0:
        return 0, json.loads(proc.stdout)
    return proc.returncode, {'stderr': proc.stderr.strip().splitlines()[-1:] or ['(no output)']}


def channel_of(rc, result):
    if rc != 0:
        return {'fault': True, 'rax': None, 'writes': None, 'why': result.get('stderr')}
    # A FAULT IS A KEY'S ABSENCE, NOT AN RC. The load_disp_plus4 mutant faults the child and the
    # harness still returns 0 with a result carrying no 'ret' -- reading result['ret'] raised here,
    # which is the third mutant finding a defect in the READER rather than in the body.
    if 'ret' not in result:
        return {'fault': True, 'rax': None, 'writes': None,
                'why': {k: result[k] for k in result if k in ('errors', 'bad_input', 'exit')}}
    return {'fault': False, 'rax': result['ret'].get('rax'), 'writes': result['writes']}


def main():
    original = open(FAMILY).read()
    build()
    base_rc, base_result = run()
    base = channel_of(base_rc, base_result)
    print(f'baseline rc={base_rc} rax={base["rax"]} writes={json.dumps(base["writes"])}')
    assert base_rc == 0 and base['writes'], 'the pilot has no memory witness before any mutant runs'
    failures = 0
    try:
        for name, (old, new, channel, why) in PREREG.items():
            if new == 'skipped':
                continue
            print(f'\n{name}: EXPECT {channel} to fire -- {why}')
            mutated = mutate.mutate_text(original, old, new, FAMILY)
            open(FAMILY, 'w').write(mutated)
            try:
                build()
                rc, result = run()
                got = channel_of(rc, result)
            finally:
                open(FAMILY, 'w').write(original)
            if channel == 'mem':
                fired = got['fault'] or got['writes'] != base['writes']
            else:
                fired = got['fault'] or got['rax'] != base['rax']
            verdict = 'FIRED' if fired else 'SILENT -- the pilot is asserting the harness'
            print(f'  {name}: rc={rc} rax={got["rax"]} writes={json.dumps(got["writes"])} -> {verdict}')
            failures += 0 if fired else 1
    finally:
        open(FAMILY, 'w').write(original)
    build()
    print(f'\n{len(PREREG) - 1} pre-registered channel(s), {failures} silent')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
