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
