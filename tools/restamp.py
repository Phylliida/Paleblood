"""Re-stamp the derived artifacts a record moves -- and prove each one idempotent BEFORE writing anything.

Seven suite tests went red after the chain_deref record and every one of them said "stale photograph": a
committed table that describes the tree as it was before 78 rows landed. The remedy a reader reaches for is
regenerate-and-rerun, and that reflex is the defect: after a few records red stops meaning "broken" and starts
meaning "yesterday". So the regeneration belongs INSIDE the record protocol, with three rules.

1. THE ONLY ASSERTION AVAILABLE ON A STALE ARTIFACT IS IDEMPOTENCE, never equality with the committed file --
   equality with a stale file is exactly the red we are removing. Run the regenerator twice; the second output
   must be byte-identical to the first. That is the property a non-deterministic generator fails (dict order,
   time.time(), an uninitialised default), and it is checkable before the first re-stamp. AFTER the first
   re-stamp, equality with the committed file becomes available and both should then hold.

2. STAGE, THEN COMMIT. Every regenerated text is computed and compared in memory/temp first; the artifacts are
   written only after every one of them agreed. A regenerator that fails halfway otherwise leaves the ledger
   recorded, two photographs new and three stale -- a state that reads as "the record worked" from progress.py
   and as three impossible-looking reds from the suite. The only way to know a write would succeed is to do all
   of it but the write.

3. A STAMP THAT CANNOT RUN SAYS SO IN THE RECORD'S OWN OUTPUT -- "recorded; could not re-stamp: X" -- and it is
   never left for the suite to discover tomorrow.

Costs are declared because two of the stamps are minutes: branch_census is ~116 s and derive is ~290 s, and a
table that hides its cost is a table that gets run at the wrong moment.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import time
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
PY = sys.executable

# artifact, argv (no {out}: the artifact path is substituted where the tool accepts one), cost in seconds, note
STAMPS = [
    {'artifact': 'symbols/capture_ok.csv',
     'argv': ['capture_precheck.py', '--table'],
     'cost': 2,
     'stages': True,
     'stdout': True,
     'note': 'stdout IS the stage: write_table() to stdout, so no --out is needed and the tree is never written'},
    {'artifact': 'symbols/leaf_frontier.csv',
     'argv': ['leaf_frontier.py', '--out', '{out}'],
     'cost': 200,
     'stages': True,
     'note': 'accepts --out'},
    {'artifact': 'symbols/branch_band.csv.gz',
     'argv': ['branch_census.py', '--out', '{out}'],
     'cost': 116,
     'stages': True,
     'note': 'always gzip bytes, whatever the name says'},
    {'artifact': 'symbols/derived.json',
     'argv': ['derive.py', '--out', '{out}'],
     'cost': 290,
     'stages': True,
     'note': 'three capstone censuses'},
]


def run(argv: list[str], timeout: float) -> tuple[int, bytes, str]:
    """Run one tool; return (rc, captured bytes of the artifact if the tool wrote to {out}, stderr)."""
    env = dict(os.environ, PYTHONPATH=TOOLS + os.pathsep + '.')
    env.setdefault('BB_LOADER', os.path.join(ROOT, 'build-release', 'runtime', 'libpbloader.so'))
    script = argv[0] if os.path.isabs(argv[0]) else os.path.join(TOOLS, argv[0])
    try:
        proc = subprocess.run([PY, '-P', script] + argv[1:], cwd=ROOT, env=env, capture_output=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        # A CRASH IS NOT A REFUSAL. The first version let TimeoutExpired escape as a traceback, which reads as
        # a bug in this file when it is a measurement: this stamp costs more than the table said.
        return 124, b'', f'timed out after {timeout:g} s -- the declared cost is wrong'
    return proc.returncode, proc.stdout, proc.stderr.decode('utf-8', 'replace')


def stamp_once(spec: dict, workdir: str, timeout: float) -> tuple[bytes | None, str]:
    """Produce one artifact's bytes in `workdir` without touching the repository."""
    out = os.path.join(workdir, os.path.basename(spec['artifact']))
    argv = [a.replace('{out}', out) for a in spec['argv']]
    rc, stdout, err = run(argv, timeout)
    if rc != 0:
        return None, f'rc={rc}: {err.strip().splitlines()[-1][:120] if err.strip() else "no stderr"}'
    if spec.get('stdout'):
        # The tool's own stdout is the artifact. Stageable by construction: nothing in the tree is opened.
        if not stdout:
            return None, 'tool printed nothing on stdout, so there is nothing to stage'
        return stdout, ''
    if os.path.isfile(out):
        return open(out, 'rb').read(), ''
    if spec['artifact'] and os.path.isfile(os.path.join(ROOT, spec['artifact'])):
        # the tool writes its own path rather than {out}; read the tree copy it just rewrote
        return open(os.path.join(ROOT, spec['artifact']), 'rb').read(), ''
    return None, 'tool produced no artifact'


def check(only: list[str] | None, allow_slow: bool) -> int:
    """Idempotence only: two runs, byte-compare. Writes nothing to the repository except a tool that ignores {out}."""
    bad = 0
    for spec in STAMPS:
        if only and not any(o in spec['artifact'] for o in only):
            continue
        if not spec.get('stages', True):
            # A stamp that can only write the tree cannot be checked without writing the tree, and rule 2 says
            # the write comes after every assertion. So it is refused loudly here rather than staged badly.
            print(f'{spec["artifact"]}: could not re-stamp -- no way to produce it outside the repository '
                  f'({spec["note"]}); owed: give the tool a --out')
            continue
        if spec['cost'] > 30 and not allow_slow:
            print(f'{spec["artifact"]}: NOT CHECKED (declared cost {spec["cost"]} s; pass --allow-slow)')
            continue
        clock = time.monotonic()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, why_a = stamp_once(spec, a, timeout=spec['cost'] * 6)
            mid = time.monotonic()
            second, why_b = stamp_once(spec, b, timeout=spec['cost'] * 6)
        observed = time.monotonic() - clock
        # The claim is printed beside the measurement on EVERY run, and the tool never rewrites its own table:
        # a table that certifies its own estimate is the fixture-that-vendors-its-property defect with a
        # stopwatch. The disagreement staying visible is the whole remedy.
        claim = f'declared {spec["cost"]:g} s x2, observed {observed:.1f} s'
        if first is None or second is None:
            print(f'{spec["artifact"]}: could not re-stamp -- {why_a or why_b} ({claim})')
            bad += 1
            continue
        if first != second:
            at = next((i for i in range(min(len(first), len(second))) if first[i] != second[i]),
                      min(len(first), len(second)))
            print(f'{spec["artifact"]}: NOT IDEMPOTENT ({claim}) -- first difference at byte {at} '
                  f'({len(first)} vs {len(second)} B); a regenerator that does not reproduce itself '
                  f'cannot certify any tree')
            bad += 1
            continue
        committed = os.path.join(ROOT, spec['artifact'])
        agree = (os.path.isfile(committed) and open(committed, 'rb').read() == first)
        print(f'{spec["artifact"]}: idempotent ({len(first)} B) | {claim} | committed copy '
              f'{"agrees" if agree else "DIFFERS -- this is the stale photograph"} | {spec["note"]}')
    return 0 if bad == 0 else 1


def apply(only: list[str] | None, allow_slow: bool) -> int:
    """Stage every artifact, prove it idempotent, then write -- and read back what was written.

    atomic_write gives a whole file or the old one; the read-back gives the RIGHT file. A write that returns
    success and a read that returns the staged bytes are two different claims, and the second is the only one
    that survives the next process.
    """
    staged: list[tuple[dict, bytes]] = []
    for spec in STAMPS:
        if only and not any(o in spec['artifact'] for o in only):
            continue
        if spec['cost'] > 30 and not allow_slow:
            print(f'{spec["artifact"]}: NOT STAGED (declared {spec["cost"]} s; pass --allow-slow)')
            continue
        clock = time.monotonic()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, why_a = stamp_once(spec, a, timeout=spec['cost'] * 6)
            second, why_b = stamp_once(spec, b, timeout=spec['cost'] * 6)
        observed = time.monotonic() - clock
        claim = f'declared {spec["cost"]:g} s x2, observed {observed:.1f} s'
        if first is None or second is None or first != second:
            print(f'{spec["artifact"]}: REFUSED, nothing written -- '
                  f'{why_a or why_b or "not idempotent"} ({claim})')
            return 1
        print(f'{spec["artifact"]}: staged {len(first)} B, idempotent ({claim})')
        staged.append((spec, first))
    if not staged:
        print('restamp: nothing staged, nothing written')
        return 2
    sys.path.insert(0, TOOLS)
    from atomicio import atomic_write  # one writer, so a partial file is impossible
    wrote = 0
    for spec, text in staged:
        target = os.path.join(ROOT, spec['artifact'])
        already = os.path.isfile(target) and open(target, 'rb').read() == text
        if already:
            print(f'{spec["artifact"]}: already current, not rewritten')
            continue
        atomic_write(target, text)
        back = open(target, 'rb').read()
        if back != text:
            print(f'{spec["artifact"]}: WROTE AND READ BACK DIFFERENT BYTES '
                  f'({len(text)} staged, {len(back)} on disk) -- the file is not what was certified')
            return 1
        print(f'{spec["artifact"]}: written {len(back)} B, read back identical')
        wrote += 1
    print(f'restamp: {wrote} artifact(s) written, {len(staged) - wrote} already current')
    return 0


def main(argv: list[str]) -> int:
    only = [a for a in argv if not a.startswith('-')]
    allow_slow = '--allow-slow' in argv
    if '--apply' in argv:
        return apply(only, allow_slow)
    return check(only, allow_slow)


if __name__ == '__main__':
    try:
        import stacks
        stacks.arm()
    except ImportError:
        pass
    try:
        sys.exit(main(sys.argv[1:]))
    finally:
        try:
            import stacks
            stacks.cancel()
        except ImportError:
            pass
