"""Record a byte-evidence family: digest it, refuse on any mismatch, derive `source`, sort tables.

`record_many` derives nothing -- it accepted 793 rows whose `source` was a tool name where a source
hash belongs, and `check_pins` called all 793 stale. A bulk writer that trusts its caller is a guard
on the input that walked away, so this writer computes what it can and refuses when it cannot:

  * the digest comes from `check_asm_bytes.py`, run as a subprocess, parsed strictly;
  * rc != 0 or matched != members refuses, before a single row is written;
  * `source` is `verification.source_hash()` per function, and an empty hash refuses;
  * address-keyed tables are sorted after the flip, because the append is what breaks the order.

Batching (`--batch N`) exists for families big enough that one digest cannot localise a failure:
each batch carries its own digest, so a bad member decays its batch and names it. Rows still cannot
be cherry-picked inside a batch.
"""
import argparse
import csv
import datetime
import os
import subprocess
import sys
import tempfile

import progress as P
import verification as V

TABLES = ('functions.csv', 'install_mode.csv', 'replacement_origins.csv', 'verification.csv')


def sort_address_keyed(root):
    for name in TABLES[:3]:
        path = os.path.join(root, 'symbols', name)
        rows = list(csv.DictReader(open(path)))
        fields = list(rows[0].keys())
        rows.sort(key=lambda r: int(r['address'], 16))
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
            w.writeheader()
            w.writerows(rows)


def digest(root, lib, elf, members):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        for m in members:
            # the digest tool resolves a SYMBOL, and the harness prepends `bb_`; the ladder name
            # does not carry it, so the writer adds it here rather than in the table
            f.write(f'bb_{m["function"]} {m["address"]} {m["size"]}\n')
        path = f.name
    try:
        r = subprocess.run([sys.executable, '-P', os.path.join('tools', 'check_asm_bytes.py'),
                            '--lib', lib, '--elf', elf, '--digest-members', path],
                           capture_output=True, text=True)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise SystemExit(f'refused: digest rc={r.returncode}\n{r.stdout}{r.stderr}')
    f = dict(tok.split('=', 1) for tok in r.stdout.split() if '=' in tok)
    if int(f['members']) != len(members) or int(f['matched']) != len(members):
        raise SystemExit(f'refused: only {f["matched"]} of {f["members"]} are byte-identical '
                         f'({len(members)} asked for) -- a row citing this digest would claim '
                         'equality it does not have')
    return f['digest']


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', required=True, help='name prefix, e.g. leaf_mov_al_mem_')
    ap.add_argument('--root', default='.')
    ap.add_argument('--lib', default='build-release/game/libbbgame.so')
    ap.add_argument('--elf', default='../data/bb/elf/eboot.elf')
    ap.add_argument('--batch', type=int, default=0, help='members per digest; 0 = one family digest')
    ap.add_argument('--dry-run', action='store_true')
    o = ap.parse_args(argv)

    fpath = os.path.join(o.root, 'symbols', 'functions.csv')
    all_rows = list(csv.DictReader(open(fpath)))
    fam = [r for r in all_rows if r['name'].startswith(o.family)]
    if not fam:
        raise SystemExit(f'refused: no rows in functions.csv start with {o.family}')
    bad = [r['name'] for r in fam if r['status'] != 'original']
    if bad:
        raise SystemExit(f'refused: {len(bad)} rows are already past `original` ({bad[0]}...)')
    members = [{'function': r['name'], 'address': r['address'], 'size': r['size']} for r in fam]
    sizes = {}
    for m in members:
        sizes[int(m['size'])] = sizes.get(int(m['size']), 0) + 1
    added = sum(k * v for k, v in sizes.items())
    print(f'{o.family}: {len(members)} members | sizes {sizes} -> +{added} B')

    step = o.batch or len(members)
    batches = [members[i:i + step] for i in range(0, len(members), step)]
    digests = []
    for i, b in enumerate(batches):
        d = digest(o.root, o.lib, o.elf, b)
        digests.append(d)
        print(f'  batch {i + 1}/{len(batches)}: {len(b)} members digest={d}')
    if o.dry_run:
        print('  dry run: nothing written')
        return 0

    today = datetime.date.today().isoformat()
    new = []
    for b, d in zip(batches, digests):
        for m in b:
            src = V.source_hash(o.root, m['function'])
            if not src:
                raise SystemExit(f'refused: no source hash for {m["function"]}')
            new.append({'function': m['function'], 'cases': 'bytes', 'option': '',
                        'total': '1', 'passed': '1', 'failed': '0', 'quarantined': '0',
                        'source': src, 'cases_sha256': d, 'date': today})
    V.record_many(o.root, new)
    print(f'  ledger: +{len(new)} rows, source derived per function')

    flipped = 0
    for r in all_rows:
        if r['name'].startswith(o.family):
            r['status'] = 'edge-verified'
            flipped += 1
    fields = list(all_rows[0].keys())
    with open(fpath, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(all_rows)
    sort_address_keyed(o.root)
    print(f'  functions.csv: {flipped} flipped to edge-verified; tables sorted')

    d = P.ledger(o.root)
    print(f'  now: {d["functions"]} functions | {d["byte_backed"]} byte-identical / '
          f'{d["differential_backed"]} differential | ledger {d["rows"]} rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
