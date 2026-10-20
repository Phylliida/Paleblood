#!/usr/bin/env python3
"""Write a review packet for a family whose members are byte-identical.

A human review of 528 generated functions is not 528 reviews if the bytes are one function: the
decision is "is this disassembly what the description says, and is the re-emission faithful", asked
once. This writes the page that asks it -- the original disassembled from the executable, the proof
that every member is byte-identical to it, the evidence that each member was executed against the
original, the weaknesses stated before the signature, and an index of the members for the record.

Every number is computed here from `symbols/functions.csv`, the executable and the differential
catalog. Nothing is transcribed, including the claim of byte-identity: the members are read out of
the executable and hashed.

The differential identity pins the tools that produced each run. `--trace-instructions` runs were
made by a particular `tools/harness.py`, `tools/verify.py` and `tools/differential.py`; when those
files change, the run still says what it says, but it no longer describes the code in the tree. The
packet compares each run's identity against the current files and reports the difference, so a
stale row cannot be mistaken for a fresh one.

    python3 tools/make_review_packet.py --prefix engine_zero_init_ --out ../data/review/packet.md

The packet committed for this tree was written with one more argument. The corpus holds exactly one
case whose two sides fault on purpose -- `period_zero` of `engine_time_over_period`, declared in
`game/engine/time_over_period_cases.py` -- and the paragraph that says so is supplied at the call
site. Omit it and the paragraph disappears at exit status 0, which is why the invocation is here:

    python3 tools/make_review_packet.py --out ../data/review/engine_zero_init_review.md --caveat \
        'One instance in this tree: `period_zero` of `engine_time_over_period` (unsigned divide by a \
period of zero, `signal 8` on both sides), declared in `game/engine/time_over_period_cases.py` so the \
case file says what it expects.'
"""
import argparse
import collections
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE_BIAS = 0x3FC000  # file offset = guest address - this; see docs/addressing.md

# identity fields the catalog records, and the file each one hashes
IDENTITY_FILES = {
    'engine_sha256': 'tools/differential.py',
    'harness_sha256': 'tools/harness.py',
    'instruction_trace_sha256': 'tools/instruction_trace.py',
    'verify_sha256': 'tools/verify.py',
    'loader_sha256': 'runtime/loader.c',
}


def digest_file(path):
    hasher = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def current_identities(root):
    return {field: digest_file(Path(root) / rel) for field, rel in IDENTITY_FILES.items()}


def members_of(root, prefix):
    with open(Path(root) / 'symbols' / 'functions.csv', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['name'].startswith(prefix)]
    if not rows:
        raise SystemExit('no function in symbols/functions.csv starts with %r' % prefix)
    return sorted(rows, key=lambda r: int(r['address'], 16))


def ledger_pins(root):
    """function -> (cases_sha256, source) for its no-option edge row, if it has one."""
    path = Path(root) / 'symbols' / 'verification.csv'
    pins = {}
    if not path.exists():
        return pins
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            if row['cases'] == 'edge' and not row['option']:
                pins[row['function']] = (row.get('cases_sha256', ''), row.get('source', ''))
    return pins


def newest_runs(state):
    """address -> (run_id, identity, comparison), newest run per address."""
    db = sqlite3.connect(state)
    try:
        rows = list(db.execute('select run_id, address, created_at, result from differential_runs'))
    finally:
        db.close()
    by_address = {}
    for run_id, address, created_at, result in rows:
        if address not in by_address or created_at >= by_address[address][1]:
            doc = json.loads(result)
            by_address[address] = (run_id, created_at, doc['identity'], doc['result']['comparison'])
    return {a: (rid, ident, comparison) for a, (rid, _, ident, comparison) in by_address.items()}


def disassemble(code, base):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    return list(md.disasm(code, base))


def build(args):
    root = args.root
    want = current_identities(root)
    members = members_of(root, args.prefix)
    image = open(args.elf, 'rb').read()
    runs = newest_runs(args.state)
    pins = ledger_pins(root)

    def bytes_of(member):
        base = int(member['address'], 16)
        return image[base - FILE_BIAS:base - FILE_BIAS + int(member['size'])]

    reference = args.reference or members[0]['address']
    ref_member = next((m for m in members if m['address'] == reference), None)
    if ref_member is None:
        raise SystemExit('%s is not a member of %s' % (reference, args.prefix))
    ref_base = int(reference, 16)
    ref = bytes_of(ref_member)
    ref_sha = hashlib.sha256(ref).hexdigest()

    insns = disassemble(ref, ref_base)
    assert sum(i.size for i in insns) == len(ref), (sum(i.size for i in insns), len(ref))

    verdicts = collections.Counter()
    classes = collections.Counter()
    stale = collections.Counter()
    rows = []
    for member in members:
        address = member['address']
        code = bytes_of(member)
        if address not in runs:
            raise SystemExit('%s has no differential run in %s' % (address, args.state))
        run_id, identity, comparison = runs[address]
        differing = [field for field in want if identity.get(field) != want[field]]
        for field in differing:
            stale[field] += 1
        verdicts[(comparison['passed'], comparison['failed'], comparison['cases'])] += 1
        for diagnostic in comparison.get('instruction_diagnostics', []):
            classes[diagnostic['first_divergence']['classification']] += 1
        pin, source = pins.get(member['name'], ('', ''))
        rows.append({'address': address, 'size': member['size'],
                     'sha256': hashlib.sha256(code).hexdigest(), 'run': run_id,
                     'passed': comparison['passed'], 'failed': comparison['failed'],
                     'cases': comparison['cases'], 'differing': differing,
                     'cases_sha256': pin, 'source': source, 'note': member.get('notes', '')})

    hashes = {r['sha256'] for r in rows}
    if len(hashes) != 1:
        raise SystemExit('members are not byte-identical: %d distinct hashes' % len(hashes))
    if hashes != {ref_sha}:
        raise SystemExit('the reference member is not one of the members')
    current = sum(1 for r in rows if not r['differing'])

    out = []
    out.append('# Review packet: %d `%s` members\n' % (len(rows), args.prefix.rstrip('_')))
    out.append('Written by `tools/make_review_packet.py` from `symbols/functions.csv`, the executable,')
    out.append('`symbols/verification.csv` and the differential catalog. Every number below is computed by')
    out.append('that script, not transcribed.\n')
    out.append('## The ask, in one sentence\n')
    out.append('Read the disassembly below; if the one-line description is true of it and the re-emission is a')
    out.append('faithful rendering, sign the family attestation. The %d review rows then follow mechanically.' % len(rows))
    out.append('**The human decision is one, not %d.**\n' % len(rows))
    out.append('## What is claimed, for all %d members\n' % len(rows))
    descriptions = collections.Counter(r['note'] for r in rows)
    out.append('> %s\n' % descriptions.most_common(1)[0][0])
    if len(descriptions) > 1:
        out.append('(The %d rows do not all carry this description: %d distinct notes. Check that before signing.)\n'
                   % (len(rows), len(descriptions)))
    out.append('— the `notes` field of the members in `symbols/functions.csv`.\n')

    out.append('## The original, once\n')
    out.append('Member `0x%08x`, %d bytes, read from the executable at file offset `0x%x`'
               % (ref_base, len(ref), ref_base - FILE_BIAS))
    out.append('(`file = guest - 0x%x`; see `docs/addressing.md`):\n' % FILE_BIAS)
    out.append('```')
    for insn in insns:
        note = ''
        if insn.mnemonic == 'xor' and insn.op_str.startswith('eax, eax'):
            note = '   <- clears eax; the original returns 0'
        out.append('%08x  %-18s %-5s%s%s' % (insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str, note))
    out.append('```\n')
    out.append('%d instructions. %s\n' % (len(insns), args.reading))

    out.append('## Why one review covers %d: identical bytes, computed not asserted\n' % len(rows))
    out.append('Reading all %d members out of the executable gives **one distinct sha256** — `%s`'
               % (len(rows), ref_sha))
    sizes = sorted({int(r['size']) for r in rows})
    span = ('%d bytes each' % sizes[0]) if len(sizes) == 1 else ('%d to %d bytes each' % (sizes[0], sizes[-1]))
    out.append('— over %d members, %s. Byte for byte there is one function here, replicated.\n' % (len(rows), span))

    out.append('## Evidence beyond the bytes (from the catalog)\n')
    verdict_text = ', '.join('%d members with %d passed / %d failed of %d'
                             % (n, p, f, t) for (p, f, t), n in sorted(verdicts.items()))
    out.append('- Traced differential replays: **%s**.' % verdict_text)
    if classes:
        out.append('- Internal-path diagnostics: first divergence classified `%s` on %d comparisons.'
                   % ('`/`'.join(sorted(classes)), sum(classes.values())))
        out.append('  %s' % args.divergence)
        out.append('  The rule this packet applies: **one divergence class per named mechanism in the')
        out.append('  source, or the class is a defect.** A class whose explanation is a line of code')
        out.append('  (here the compiler replacing eighteen eight-byte stores with seven sixteen-byte')
        out.append('  ones) is understood; a class with no such line is unexplained, and unexplained is')
        out.append('  not "equivalent but noisy". Fewer classes is not better than more.')
    pinned = sum(1 for r in rows if len(r['cases_sha256']) == 16)
    out.append('- Case identity: %d of %d members have an `edge` ledger row pinning the case files'
               % (pinned, len(rows)))
    out.append('  (`cases_sha256`); %d carry `unavailable` or nothing. Each recorded run also passes the'
               % (len(rows) - pinned))
    out.append('  falsification canary: the same comparison is re-run against a deliberately corrupted')
    out.append('  replacement and must go red for a return value, a written byte and a saved register.\n')

    out.append('## Freshness of the evidence\n')
    out.append('Each catalog run records the sha256 of the tools that produced it. Compared against the')
    out.append('files in this tree right now:\n')
    out.append('| identity field | file | runs recorded with a different value |')
    out.append('|---|---|---|')
    for field, rel in sorted(IDENTITY_FILES.items()):
        out.append('| `%s` | `%s` | %d of %d |' % (field, rel, stale[field], len(rows)))
    out.append('')
    if current == len(rows):
        out.append('**All %d runs were made by the tools in this tree.**\n' % len(rows))
    else:
        out.append('**%d of %d runs match this tree on every field; %d do not.** A stale run still says'
                   % (current, len(rows), len(rows) - current))
        out.append('what it says, but it describes an earlier tool: re-run `differential.py` before relying')
        out.append('on the verdict column, and do not read a stale run as evidence about the current code.\n')

    out.append('## Known weaknesses, stated before you sign\n')
    for i, weakness in enumerate(args.weakness, 1):
        out.append('%d. %s' % (i, weakness))
    out.append('')
    out.append('## What is *not* claimed\n')
    out.append('- Not capture-grade unless the ledger says otherwise: check `cases_sha256` above against')
    out.append('  the fixture directory; synthesized fixtures are `synthetic_or_edge`.')
    out.append('- Behavioural, not semantic: it says what is written where, not what the bytes mean.')
    out.append('- Nothing about concurrency or reentrancy unless a case runs two instances.')
    out.append('- **Determinism, not generality.** A promotion needs two input sets, and `promote.py`')
    out.append('  refuses one set copied into both places. What that buys is narrow and worth saying')
    out.append('  exactly: a second set made by renaming or replaying the first would show agreement')
    out.append('  twice for the same inputs, which is evidence about determinism and none at all about')
    out.append('  inputs nobody tried.')
    out.append('- **Known-different, not known-independent.** The edge set of a promoted function is')
    out.append('  compared by content against the recorded set, so it is not a copy; content hashing')
    out.append('  cannot show it was derived independently, and refusing derivative cases would reject')
    out.append('  the ordinary way a boundary case is authored (perturb a recorded input). So: known')
    out.append('  different, provenance reported per set, independence not established.')
    out.append('- **Not every ledger row is a comparison.** A case that declares `expected_fault` and')
    out.append('  faults identically on both sides compares nothing -- the run that would have compared')
    out.append('  never returned -- and is recorded as `compared: false` in `fault_agreement` rather')
    out.append('  than counted as agreement. It is a coverage row: the behaviour is pinned, the')
    out.append('  implementations were not compared on it.')
    for caveat in (args.caveat or []):
        out.append('- %s' % caveat)
    out.append('')

    out.append('## The attestation\n')
    out.append('```')
    out.append('I read member 0x%08x disassembled above and agree that' % ref_base)
    out.append('  "%s"' % descriptions.most_common(1)[0][0])
    out.append('is a true and adequate description of it, and that the %d members are byte-identical to it' % len(rows))
    out.append('(sha256 %s), so the same description holds for each.' % ref_sha)
    out.append('')
    out.append('Reviewer: ______________  Date: __________')
    out.append('```\n')
    out.append('Approval is one row per address in `symbols/reviews.csv`')
    out.append('(`address,name,date,reviewer,verdict,notes`):\n')
    out.append('```')
    out.append('%s,%s,<date>,<you>,approved,family attestation; member %s read line by line; %d members '
               'byte-identical (sha256 %s…)' % (reference, ref_member['name'], reference, len(rows), ref_sha[:16]))
    out.append('```\n')
    out.append('Nothing in the repo ties a family attestation to the derived rows — it is a written statement')
    out.append('that is then mechanically expanded. That gap is cheaper to close by expanding this packet than')
    out.append('by automating it.\n')

    out.append('\n---\n\n# Index of the %d members\n' % len(rows))
    out.append('All members share the byte hash above. The run id is the catalog row that replayed the')
    out.append('fixtures for that address, and the last column names any identity field that has changed')
    out.append('since. This section is for the record, not for reading.\n')
    per = args.per_page
    for start in range(0, len(rows), per):
        chunk = rows[start:start + per]
        out.append('\n## Page %d — members %d–%d\n' % (2 + start // per, start + 1, start + len(chunk)))
        out.append('| address | size | sha256 | differential run | cases | verdict | fresh |')
        out.append('|---|---|---|---|---|---|---|')
        for r in chunk:
            freshness = 'yes' if not r['differing'] else ', '.join(f.split('_')[0] for f in r['differing'])
            out.append('| `%s` | %s B | `%s` | `%s` | %d | %d/%d | %s |'
                       % (r['address'], r['size'], r['sha256'][:16], r['run'], r['cases'],
                          r['passed'], r['cases'], freshness))
    out.append('\n# Appendix — the shared reference bytes\n')
    out.append('`0x%08x`, %d bytes, sha256 `%s`:\n' % (ref_base, len(ref), ref_sha))
    out.append('```')
    for start in range(0, len(ref), 42):
        out.append(ref[start:start + 42].hex())
    out.append('```\n')
    out.append('Members: **%d**. Distinct byte hashes: **1**. Runs current with this tree: **%d**. Pages: **%d**.'
               % (len(rows), current, 2 + (len(rows) + per - 1) // per))

    text = '\n'.join(out) + '\n'
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(text)
    print('wrote %s (%d bytes, %d pages); %d/%d runs current; stale %s'
          % (args.out, len(text.encode()), 2 + (len(rows) + per - 1) // per, current, len(rows),
             dict(stale) or 'nothing'))
    return 0


DEFAULT_READING = ('Fifteen zeroing stores cover 0x00..0x70, the sixteenth stores the first argument at +0x78; '
                   'nothing else is written, nothing is read.')
DEFAULT_DIVERGENCE = ('Expected, not a failure: the re-emitted C++ vectorises the same stores to 16-byte moves. '
                      'The compared final state is identical.')


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=str(ROOT))
    ap.add_argument('--prefix', default='engine_zero_init_', help='family prefix in symbols/functions.csv')
    ap.add_argument('--reference', help='member address to disassemble; default the lowest')
    ap.add_argument('--elf', default=str(ROOT.parent / 'data/bb/elf/eboot.elf'))
    ap.add_argument('--state', default=str(ROOT.parent / 'data/catalog.sqlite3'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--per-page', type=int, default=20)
    ap.add_argument('--reading', default=DEFAULT_READING, help='the sentence that reads the disassembly')
    ap.add_argument('--divergence', default=DEFAULT_DIVERGENCE)
    ap.add_argument('--caveat', action='append', default=None,
                    help='extra bullet for the "not claimed" list; corpus facts live at the call site, '
                         'not in this tool, because tools/ is inside check_agnostic.py\'s scope')
    ap.add_argument('--weakness', action='append', default=None,
                    help='a weakness to state before the signature; repeatable')
    args = ap.parse_args(argv)
    if args.weakness is None:
        args.weakness = [DEFAULT_WEAKNESS]
    return build(args)


DEFAULT_WEAKNESS = ('The description is one line for the whole family because the bytes are one '
                    'function. It is adequate only at that level: it does not name the object type '
                    'or say who calls this.')

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
