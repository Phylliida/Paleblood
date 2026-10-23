#!/usr/bin/env python3
"""Write the byte tier's rows at `original` in ONE pass, before any evidence exists.

    python3 -P tools/land_bytes_band.py            # dry run: counts and dup check, writes nothing
    python3 -P tools/land_bytes_band.py --apply    # append, sort, write, re-read

The population comes from emit_byte_leaves.transcribable(), which is the same function the emitter
writes bodies from and the same tooth set census_band.py counts with -- so the three cannot disagree
about what the band is. `original` is the honest status for a body with no evidence yet: the row
exists, the claim does not. Evidence arrives per batch through record_bytes_family.py, which flips.

No cases are written here and none exist for this tier: byte evidence is the digest of the shipped
bytes (check_asm_bytes.py). A case file would be differential-tier cost for byte-tier evidence.
"""
import csv
import sys

import emit_byte_leaves as E
import record_bytes_family as R

FUNCTIONS = 'symbols/functions.csv'
# THE APPLY OWES THREE TABLES, NOT ONE. The first version wrote functions.csv and left the other two
# to nobody: validate_functions refused every band row with "no replacement_origins.csv row" and
# test_install_mode refused with "absent installation record". Both guards were right -- an
# edge-verified row with no installation record is a claim about a body nothing can place -- so the
# writer grows the tables it owes rather than a repair tool growing beside it. Mode is `host`: these
# bodies are naked asm inside libbbgame, reached through the host patch mechanism, and no guest
# hook is installed for them (the 14-byte jump belongs to hook rows).
INSTALL = 'symbols/install_mode.csv'
ORIGINS = 'symbols/replacement_origins.csv'


def _append_rows(path, rows, key, value_field):
    """Append ADDRESS-KEYED rows, refuse on a conflicting value, sort, re-read."""
    have = list(csv.DictReader(open(path)))
    seen = {r['address']: r[value_field] for r in have}
    clash = [(a, v) for a, v in rows if a in seen and seen[a] != v]
    if clash:
        raise SystemExit(f'refused: {path} already records {clash[0][0]} as '
                         f'{clash[0][1]!r}, refusing to write {rows[0][1]!r}')
    add = [{'address': a, value_field: v} for a, v in rows if a not in seen]
    merged = have + [{'address': a, value_field: v} for a, v in add and
                     [(r['address'], r[value_field]) for r in add]]
    merged.sort(key=lambda r: int(r['address'], 16) if r['address'].startswith('0x') else 0)
    dup = sum(1 for a, b in zip(merged, merged[1:]) if a['address'] == b['address'])
    if dup:
        raise SystemExit(f'refused: {path} merge would create {dup} duplicate addresses')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['address', value_field], lineterminator='\n')
        w.writeheader()
        w.writerows(merged)
    back = {r['address'] for r in csv.DictReader(open(path))}
    missing = [r['address'] for r in add if r['address'] not in back]
    if missing:
        raise SystemExit(f'wrote, re-read, and {len(missing)} rows are absent in {path}')
    print(f'{path}: +{len(add)} rows ({value_field}={rows[0][1]}), {len(merged)} total')


def main(argv):
    apply = '--apply' in argv
    # decisions.md:243 still reads `### 1j - PROPOSED, NOT IN FORCE`. The rows below presuppose the
    # ratifier said yes to byte transcription, so this writer refuses rather than bookkeeping a tier
    # nobody has authorised -- and it refuses BEFORE transcribable(), so the refusal costs nothing.
    if not E.authorised(open(E.DECISION).read()):
        raise SystemExit('refused: decisions.md has no ratified `### 1j.` -- ask 7 is still '
                         'PROPOSED (line 243). The band cannot be written, let alone recorded, '
                         'until the ratifier answers it.')
    ms, refused = E.transcribable()
    print(f'band: {len(ms)} members, {sum(m["size"] for m in ms)} B; refused '
          f'{sum(refused.values())} ({dict(refused)})')

    rows = list(csv.DictReader(open(FUNCTIONS)))
    fields = list(rows[0].keys())
    have = {r['address'].lower() for r in rows}
    have_names = {r['name'] for r in rows}
    clash = [m for m in ms if f'0x{m["address"]:08x}' in have]
    if clash:
        raise SystemExit(f'refused: {len(clash)} members already have rows '
                         f'(first: leaf_bytes_{clash[0]["address"]:08x}); this writer only ever '
                         f'creates rows at `original`')
    new = [{'address': f'0x{m["address"]:08x}', 'size': str(m['size']),
            'name': f'leaf_bytes_{m["address"]:08x}', 'system': 'leaf', 'status': 'original',
            'notes': ''} for m in ms]
    bad = [r['name'] for r in new if r['name'] in have_names]
    if bad:
        raise SystemExit(f'refused: {len(bad)} names already exist (first: {bad[0]})')

    merged = rows + new
    merged.sort(key=lambda r: int(r['address'], 16))
    dup = sum(1 for a, b in zip(merged, merged[1:]) if a['address'] == b['address'])
    print(f'functions.csv: {len(rows)} -> {len(merged)} rows, adjacent dup {dup}, '
          f'sorted on address ({merged[0]["address"]} .. {merged[-1]["address"]})')
    if dup:
        raise SystemExit('refused: the merge would create duplicate addresses')
    if not apply:
        print('dry run: nothing written')
        return 0

    with open(FUNCTIONS, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(merged)
    back = list(csv.DictReader(open(FUNCTIONS)))
    got = {r['name'] for r in back}
    missing = [r['name'] for r in new if r['name'] not in got]
    if missing:
        raise SystemExit(f'wrote, re-read, and {len(missing)} rows are absent (first: '
                         f'{missing[0]}) -- the write is not the table')
    print(f'wrote {len(new)} rows at `original`; re-read confirms all of them present')
    print(f'  now: {len(back)} functions | '
          f'{sum(1 for r in back if r["status"] == "original")} at original')
    # The band was written to functions.csv by the run before this one, so the two row-level tables
    # are grown for the members that are ALREADY there rather than for a fresh emission: the
    # population is the table, not the census, so a second run cannot disagree with the first about
    # which rows owe a record.
    present = [r for r in back if r['name'].startswith('leaf_bytes_')]
    # The population is checked against the BODY, not against the census: transcribable() returns
    # what is not yet landed, so after a landing it is empty by construction and the first version of
    # this check compared 4,034 rows against a worklist that had just finished its work. The emitted
    # file is the artifact that knows which bodies exist, and it knows by construction rather than by
    # a number of mine.
    with open(E.BODY) as fh:
        in_body = sum(1 for line in fh if 'void bb_leaf_bytes_' in line)
    if len(present) != in_body:
        raise SystemExit(f'refused: {len(present)} leaf_bytes rows in the table, {in_body} bodies in '
                         f'{E.BODY} -- the table and the body disagree, and wiring the missing ones '
                         'would wire a population nobody emitted')
    addrs = [(r['address'], 'host') for r in present]
    _append_rows(INSTALL, addrs, 'address', 'mode')
    _append_rows(ORIGINS, [(a, 'generated') for a, _ in addrs], 'address', 'origin')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
