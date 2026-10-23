"""The chain family: 78 members whose store target exists only if the case seeds the slot.

WHY THIS EXISTS. `leaf_shape_census.py` found 6,288 addressable frontier rows in 29 shapes and one
dominant shape -- `mov rax,[rip+K] ; mov [rax+K],K3 ; ret`, 78 rows, 1,320 B -- that no template in
`emit_leaf_family.py` names. It is also the first shape whose store address is computed from a
value LOADED OUT OF THE IMAGE: the qword at the load target is zero in the shipped bytes (the slot
is in the zero-fill tail), so the store degenerates to address K2 and the family is not testable
from the shipped image at all. The case has to write the slot, which makes this the first family
whose members are gated on a fixture rather than on the binary.

PRE-REGISTRATION, written before any case was authored and checked on every run: **78 rows, 1,320 B,
78/78 SEEDING REQUIRED, 0 rows whose shipped value discriminates, 78 distinct (load K, store K2,
immediate K3) triples, 47 distinct store K2, sizes {15: 28, 18: 50}.** If this scan disagrees with any
of them this tool REFUSES and prints both numbers -- a population that moved is a different family,
not a formatting difference, and 78 distinct triples is why cases cannot be shared between members
by coincidence.

TWO LINKS, and only the second one costs a fault. Link one: the slot at `load_target` holds a value
the case wrote. Link two: that value, plus the store offset, plus the store width, lies inside the
case's own writable buffer. A case that writes `0x1` into the slot satisfies link one and faults at
the store; the differential then reports a mismatch that is a fixture defect. The seeding gate
asserts both, and this file carries the per-row constants link two needs (store_k2, store_width).

The size line is itself a retraction: I first wrote `{10: 78}` from the rip_load family's population
(`sizes {10: 161}`), which is a different family whose members are all ten bytes. This one is not.

SELECTOR. The shape string is `leaf_shape_census.shape_of`'s, imported and never copied, so the two
tools cannot disagree about which rows belong to this family. `--elf` defaults to the carried path
because a path constant no argument can vary gives a refusal nobody can execute.
"""
import argparse
import collections
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import capstone

import atomicio
import leaf_shape_census as S

CSV_OUT = os.path.join(S.ROOT, 'symbols', 'chain_family.csv')
COLUMNS = ('address', 'size', 'load_disp', 'load_target', 'where', 'store_k2', 'store_width', 'imm')
PREREG = {'rows': 78, 'bytes': 1320, 'seeding_required': 78, 'discriminating': 0,
          'distinct_triples': 78, 'distinct_store_k2': 47}

# The BATCH's arithmetic, pre-registered before a single body is emitted. Each constant is derived from an
# artifact, never copied from a report, and each is checked against the live tree on --check. Before the
# batch the live state is exactly these minus the batch; after it, exactly these. A disagreement after the
# run IS the finding -- and one already has a history: BYTES_BEFORE was quoted as 322,675 in a report, a
# figure my own record had withdrawn, and the measured value is 322,746. Off by 71, carried from a number
# nobody re-derived.
BATCH = {
    'landed_after': 38096,        # 38,018 measured + 78 rows
    'bytes_before': 322746,       # sum of sizes over landed rows of symbols/functions.csv, measured
    'bytes_after': 324066,        # + 1,320 B, PREREG['bytes']
    'scope_after': 24.15,         # 38,096 / 157,757 = 24.1485
    'progress_free_landed_after': 36924,   # 36,846 branch-free landed (measured) + 78
    'progress_free_total': 43734,
    'progress_after': 84.43,      # 36,924 / 43,734 = 84.4286
    'verified_after': 21,         # unchanged: these rows land as edge, and byte evidence is not behaviour
}


def batch_problems(root='.'):
    """The batch's five constants against the live tree. Before the run they differ by exactly the batch.

    A pre-registration that cannot say `not yet` is a wish; this one prints the owed delta and refuses only
    on a disagreement that the batch cannot explain.
    """
    import catalogue, landed
    rows = catalogue.read_rows(f'{root}/symbols/functions.csv')
    land = landed.landed_addresses(f'{root}/symbols/functions.csv')  # ONE root: rows, membership, band
    L = [r for r in rows if r['address'] in land]
    live_landed, live_bytes = len(L), sum(int(r['size']) for r in L)
    gz = f'{root}/symbols/branch_band.csv.gz'
    band = list(catalogue.read_rows(gz))
    fl = sum(1 for r in band if r['branch'] == '0' and r['landed'] == 'True')
    free = sum(1 for r in band if r['branch'] == '0')
    out = []
    owed = BATCH['landed_after'] - live_landed
    if owed not in (0, PREREG['rows']):
        out.append(f'batch: landed {live_landed} -> pre-registered {BATCH["landed_after"]} is {owed} rows, '
                   f'not 0 or {PREREG["rows"]}')
    owed_b = BATCH['bytes_after'] - live_bytes
    if owed_b not in (0, PREREG['bytes']):
        out.append(f'batch: bytes {live_bytes} -> pre-registered {BATCH["bytes_after"]} owes {owed_b}, '
                   f'not 0 or {PREREG["bytes"]} (measured {BATCH["bytes_before"]} + {PREREG["bytes"]})')
    owed_p = BATCH['progress_free_landed_after'] - fl
    if owed_p not in (0, PREREG['rows']):
        out.append(f'batch: branch-free landed {fl} -> pre-registered '
                   f'{BATCH["progress_free_landed_after"]} is {owed_p} rows, not 0 or {PREREG["rows"]}')
    # The sentence is chosen by `out`, never by the branch that computed it: my first version printed
    # "complete ... pre-registered exactly" while returning two problems, because the else-branch meant
    # "not before the batch" and I read it as "after".
    if out:
        print(f'batch: live {live_landed} rows / {live_bytes} B is neither the pre-registered before-state '
              f'nor its after-state')
    elif owed == PREREG['rows']:
        # The byte pair is printed BOTH ways on one line: the number that was carried wrong once is exactly
        # the number a reader will carry next, so the before-value is measured here rather than remembered.
        print(f'batch: owed {owed} row(s) / {owed_b} B / {owed_p} branch-free; pre-registered after-state '
              f'{BATCH["landed_after"]} rows, bytes {live_bytes:,} -> {BATCH["bytes_after"]:,}, '
              f'SCOPE {BATCH["scope_after"]}%, '
              f'PROGRESS {BATCH["progress_free_landed_after"]}/{BATCH["progress_free_total"]} = '
              f'{BATCH["progress_after"]}%, verified {BATCH["verified_after"]}')
    else:
        print(f'batch: complete at {live_landed} rows / {live_bytes} B; pre-registered exactly')
    return out


def scan(elf=None, max_insns=3):
    """One pass over the committed frontier. Returns rows, each carrying what its case must satisfy."""
    elf = elf or S.ELF
    md = open(elf, 'rb').read()
    segs = S.load_segments(md)
    # detail=True is a PRECONDITION of S.shape_of, not decoration: it reads i.operands, and without
    # details capstone raises CsError on the first use. Importing a predicate does not import its
    # preconditions -- the census builds its disassembler this way, so this one must too.
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    want = ('mov rax,[rip+K] ; mov [rax+K],K ; ret')
    out = []
    for addr, size in S.frontier():
        ins = list(cs.disasm(md[addr - S.BIAS:addr - S.BIAS + size], addr))
        if len(ins) < 2 or S.shape_of(ins, max_insns) != want:
            continue
        load = next((op for op in ins[0].operands if op.type == capstone.x86.X86_OP_MEM), None)
        if load is None or not load.mem.base:
            continue
        tgt = addr + ins[0].size + load.mem.disp
        mem = next((op for op in ins[1].operands if op.type == capstone.x86.X86_OP_MEM), None)
        imm = next((op for op in ins[1].operands if op.type == capstone.x86.X86_OP_IMM), None)
        if mem is None or imm is None:
            continue
        out.append({'address': addr, 'size': size, 'load_disp': load.mem.disp, 'load_target': tgt,
                    'where': S.classify_target(segs, tgt), 'store_k2': mem.mem.disp,
                    'store_width': mem.size, 'imm': imm.imm})
    return out


def summarise(rows):
    triples = {(r['load_disp'], r['store_k2'], r['imm']) for r in rows}
    return {'rows': len(rows),
            'bytes': sum(r['size'] for r in rows),
            'seeding_required': sum(1 for r in rows if r['where'] == 'zerofill'),
            'discriminating': sum(1 for r in rows if r['where'] == 'filesz'),
            'distinct_triples': len(triples),
            'distinct_store_k2': len({r['store_k2'] for r in rows})}


def to_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator='\n')
    w.writeheader()
    for r in rows:
        w.writerow({**r, 'address': hex(r['address']), 'load_disp': hex(r['load_disp']),
                    'load_target': hex(r['load_target']), 'store_k2': hex(r['store_k2']),
                    'imm': hex(r['imm'])})
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--elf', default=S.ELF)
    ap.add_argument('--out', default=CSV_OUT)
    ap.add_argument('--check', action='store_true', help='exit 1 if the committed table is stale')
    a = ap.parse_args(argv)
    rows = scan(a.elf)
    got = summarise(rows)
    print(f"chain family: {got['rows']} rows | {got['bytes']} B | sizes "
          f"{dict(sorted(collections.Counter(r['size'] for r in rows).items()))} | "
          f"seeding required {got['seeding_required']}/{got['rows']} | "
          f"discriminating from the shipped image {got['discriminating']} | "
          f"distinct (load K, store K2, imm) {got['distinct_triples']} | "
          f"distinct store K2 {got['distinct_store_k2']}")
    bad = [f'{k}: pre-registered {v}, scan says {got[k]}' for k, v in PREREG.items() if got[k] != v]
    bad += batch_problems(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if bad:
        for line in bad:
            print(f'REFUSED {line}', file=sys.stderr)
        print('refusing to write: the population moved, so this is a different family', file=sys.stderr)
        return 1
    text = to_text(rows)
    if a.check:
        cur = open(a.out).read() if os.path.isfile(a.out) else ''
        if cur != text:
            print(f'chain family: {a.out} is stale -- run tools/chain_family.py', file=sys.stderr)
            return 1
        print(f'chain family: {a.out} reproduced byte-for-byte')
        return 0
    atomicio.atomic_write(a.out, text)
    print(f'chain family: wrote {a.out} ({len(text)} B)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
