"""Harvest mutant evidence for a whole family BEFORE it is recorded, scoped per function block.

`pilot_mutants` anchors on `kStoreDisp = 0xf0;`, which occurs three times in a 78-body translation unit: its
guard covers the pilot only. And the moment the family is recorded, editing that TU to plant a mutant
invalidates every member by source_hash -- mutation evidence gathered after the record is not evidence about
the recorded bytes. So this runs before, on a stratified sample, and says so: sample strength, not family.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from case_dir import case_dir
from catalogue import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TU = os.path.join(ROOT, 'game', 'leaf', 'chain_deref_family.cpp')
LIB = os.path.join(ROOT, 'build-release', 'game', 'libbbgame.so')
ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
PREFIX = 'bb_leaf_chain_deref_'
MARK = 'bb_leaf_chain_deref_'


def block_of(text, addr):
    """The member's function, signature to the next member's signature. Text-scoping, not line numbers."""
    start = text.index(f'{PREFIX}{addr:08x}(')
    start = text.rindex('extern', 0, start)
    # FROM THE OPENING BRACE, not from start+1: the member's own symbol appears inside its own
    # signature, so searching from start+1 ended the block at its first line and every 'block'
    # was one signature -- which reads as a parse of nothing rather than as a bug.
    nxt = text.find(MARK, text.index('{', start) + 1)
    return text[start:nxt if nxt > 0 else len(text)]


def const(block, name):
    # Match the NAME, not the type: `std::uint(?:ptr|64)_t` matched kImm but nothing else, and a
    # type-specific pattern turns a schema variant into a silent None.
    m = re.search(rf'{name} = (0x[0-9a-f]+);', block)
    return int(m.group(1), 16) if m else None


def run(addr):
    case = os.path.join(case_dir('chain_deref'), f'{addr:08x}', 'case.json')
    args = [sys.executable, '-P', os.path.join(ROOT, 'tools', 'harness.py'), '--elf', ELF,
            '--case', case, '--address', f'{addr:#010x}', '--replacement', PREFIX + f'{addr:08x}',
            '--lib', LIB]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        return p.returncode, None, None, (p.stderr.strip().splitlines() or ['(none)'])[-1]
    r = json.loads(p.stdout)
    if 'ret' not in r:
        return 0, None, None, 'nokey'
    return 0, r['ret'].get('rax'), r.get('writes'), ''


def build():
    subprocess.run(['cmake', '--build', os.path.join(ROOT, 'build-release'), '--target', 'bbgame', '-j8'],
                   check=True, capture_output=True)


def main(argv):
    rows = [r for r in read_rows(os.path.join(ROOT, 'symbols', 'chain_family.csv'))]
    addrs = sorted((r['address'] if isinstance(r['address'], int) else int(r['address'], 0)) for r in rows)
    canon = open(TU).read()
    imm = {a: const(block_of(canon, a), 'kImm') for a in addrs}
    # STRATIFIED, not the first eight: the two ends, one immediate-zero and one immediate-nonzero, and four
    # spread across the family. A sample that is the first eight is the --limit 1 defect with more rows.
    picked = []
    zero = [a for a in addrs if imm[a] == 0]
    nz = [a for a in addrs if imm[a] not in (0, None)]
    if not zero or not nz:
        print('mutate_family: REFUSED -- no immediate-zero or immediate-nonzero member found; the stratification '
              'cannot be satisfied, so this is a finding about the parse and not an empty sample', file=sys.stderr)
        return 2
    for a in (addrs[0], addrs[-1], zero[0], nz[0],
              addrs[len(addrs) // 8], addrs[len(addrs) // 3], addrs[2 * len(addrs) // 3], addrs[7 * len(addrs) // 8]):
        if a not in picked:
            picked.append(a)
    picked = picked[:8]
    print(f'sample {len(picked)} of {len(addrs)}: ' + ', '.join(f'{a:#010x}' for a in picked))
    base = {}
    for a in picked:
        base[a] = run(a)
    print(f'baselines: ' + ', '.join(f'{a:#010x}=rc{base[a][0]} rax={base[a][1]} writes={len(base[a][2] or [])}'
                                     for a in picked))
    results = []
    try:
        for a in picked:
            blk = block_of(canon, a)
            for name, (pat, sub) in {
                'store_disp_plus4': (r'(constexpr std::uintptr_t kStoreDisp = )(0x[0-9a-f]+);',
                                     lambda m: f'{m.group(1)}{int(m.group(2), 16) + 4:#x};'),
                'imm_negate': (r'(constexpr std::uint64_t kImm = )(0x[0-9a-f]+);',
                               lambda m: f'{m.group(1)}{(int(m.group(2), 16) ^ 1):#x};'),
            }.items():
                old = re.search(pat, blk)
                if not old:
                    print(f'{a:#010x} {name}: anchor absent -- skipped, not counted')
                    continue
                new = sub(old)
                if new == old.group(0):
                    print(f'{a:#010x} {name}: mutant equals original -- not a test, skipped')
                    continue
                expect = ('mem', 'the store target moves, so the sentinel must survive untouched and writes '
                                 'must differ from the baseline') if name == 'store_disp_plus4' else \
                         ('mem', 'the stored immediate changes, so the four/one byte(s) at the store target '
                                 'must differ from the baseline')
                print(f'{a:#010x} {name}: EXPECT {expect[0]} to fire -- {expect[1]}')
                mutated = blk.replace(old.group(0), new, 1)
                text = canon.replace(blk, mutated, 1)
                assert text != canon, 'mutation did not change the TU'
                open(TU, 'w').write(text)
                build()
                rc, rax, writes, detail = run(a)
                b_rc, b_rax, b_writes, _ = base[a]
                ch = []
                if rc != b_rc:
                    ch.append('fault')
                if json.dumps(writes, sort_keys=True) != json.dumps(b_writes, sort_keys=True):
                    ch.append('mem')
                if rax != b_rax:
                    ch.append('rax')
                fired = expect[0] in ch
                print(f'  -> rc={rc} channels {ch or "SILENT"} :: {"FIRED" if fired else "SILENT"}'
                      f'{"" if fired else "  <-- a mutant nobody can see is not a survivor"}')
                results.append((a, name, ch, fired, detail))
                open(TU, 'w').write(canon)
    finally:
        open(TU, 'w').write(canon)
        build()
    silent = [r for r in results if not r[3]]
    print(f'\n{len(results)} mutant(s) ran, {len(results) - len(silent)} fired on the declared channel, '
          f'{len(silent)} silent; sample of {len(picked)} of {len(addrs)} members')
    print('TU restored byte-identical:', open(TU).read() == canon)
    return 0 if results and not silent else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
