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

THE TABLE IS THE FAMILY, THE FRONTIER IS CANDIDATES. After the batch landed, `frontier()` no longer
contains these rows at all (6,288 -> 6,210 when the 78 landed): a landed family is not a candidate. So the
authority is `symbols/chain_family.csv`, 78 committed rows carrying every field a row needs, and `--check`
re-derives EACH FIELD OF EACH ROW from the ELF and compares -- load_disp, load_target, where, store_k2,
store_width, imm. No shape string is consulted: the shape was a lossy re-encoding of the table, and asking
a candidate list for a family that has left it is how five reds were born from one zero. Regeneration still
exists, as `--rescan`, and it REFUSES to write when the frontier yields nothing while the table holds rows:
a family of zero members against a table of 78 is a truncation wearing a regeneration's name.
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
    # ONE LAW, THREE STATES. `owed` is derived from the FAMILY's landed set, not by comparing a global
    # after-state to a global live count: that subtraction was an enumeration in disguise, right at 78
    # and wrong at 1. The byte names are the same partition as landed/transcribed -- a row can carry a
    # body without carrying evidence, and one `live_bytes` would have to pick which it means.
    # NOT `E.landed_rows()`: that is a NAME filter over functions.csv, and it returns the pilot row
    # whose status is still 'original' -- a body that exists with no evidence behind it. Using it as
    # "the family's landed set" moved owed from 78 to 77 and the byte total by exactly one body's 18 B,
    # which is the 647 retraction (a name filter standing in for a set) one tier down. Landed means
    # `in land`, and land is the status predicate.
    # `rows` is the CATALOGUE: 157,757 rows, no `name` column, so a name predicate over it is empty BY
    # CONSTRUCTION and `owed` read 78 on a tree where all 78 were landed and recorded. A zero from a predicate
    # that cannot be satisfied is not a measurement -- the 647 retraction, one column over. Names come from the
    # file that has them; membership in `land` comes from the status predicate; the two are joined on the
    # address, and the refusal prints BOTH populations so the next reader sees the disagreement.
    _fam_rows = list(catalogue.read_rows(f'{root}/symbols/functions.csv'))
    fam = {r['address'] for r in _fam_rows
           if str(r.get('name', '')).startswith('leaf_chain_deref_') and r['address'] in land}
    owed = PREREG['rows'] - len(fam)
    if owed not in (0, PREREG['rows']):
        out.append(f'batch: landed {live_landed} -> pre-registered {BATCH["landed_after"]} is {owed} rows, '
                   f'not 0 or {PREREG["rows"]}')
    owed_b = PREREG['bytes'] - sum(int(r['size']) for r in rows if r['address'] in fam)
    from landed import byte_totals
    bt = byte_totals(f'{root}/symbols/functions.csv')
    # TWO STATES, NO THIRD. The pre-registration names a before-state and an after-state, so the live
    # (rows, bytes_landed) pair must BE one of them. Without this, a delta on a row that is NOT in the
    # family leaves `owed == 0`, and every owed-keyed check below becomes unfirable -- which is exactly
    # how a planted row delta of -1 and a planted byte delta of +1 both printed "pre-registered exactly".
    # `owed` asks how much of the batch remains; this asks whether the tree is the tree the constants
    # describe. Different questions, and the second is the one a reader believes.
    _before = (BATCH['landed_after'] - PREREG['rows'], BATCH['bytes_before'])
    _after = (BATCH['landed_after'], BATCH['bytes_after'])
    if (live_landed, bt['landed']) not in (_before, _after):
        out.append(f'batch: live {live_landed} rows / {bt["landed"]:,} bytes_landed is neither the '
                   f'pre-registered before-state ({_before[0]} / {_before[1]:,}) nor its after-state '
                   f'({_after[0]} / {_after[1]:,})')
    # `owed` is what the batch still owes, so the predicate only holds while the batch is UNLANDED: adding it to
    # a live count that already includes the batch double-counts, and the sentence then reports a disagreement
    # on a correct post-record tree. A check whose applicability has an precondition must state it, not assume
    # the tree is the tree it was written against.
    if owed and (live_landed + owed != BATCH['landed_after'] or bt['landed'] + owed_b != BATCH['bytes_after']):
        out.append(f'batch: fam {len(fam)} of {len(_fam_rows)} rows in symbols/functions.csv | owed {owed} rows / '
                   f'{owed_b} bytes | landed {live_landed} -- disagrees with the measured '
                   f'before-state ({live_landed} rows / {bt["landed"]} bytes landed) plus after-state')
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
        print(f'batch: live {live_landed} rows / bytes_landed {bt["landed"]:,} is neither the pre-registered before-state '
              f'nor its after-state')
    elif owed == PREREG['rows']:
        # The byte pair is printed BOTH ways on one line: the number that was carried wrong once is exactly
        # the number a reader will carry next, so the before-value is measured here rather than remembered.
        print(f'batch: owed {owed} row(s) / {owed_b} B / {owed_p} branch-free; pre-registered after-state '
              f'{BATCH["landed_after"]} rows, bytes_landed {bt["landed"]:,} (transcribed {bt["transcribed"]:,}) -> {BATCH["bytes_after"]:,}, '
              f'SCOPE {BATCH["scope_after"]}%, '
              f'PROGRESS {BATCH["progress_free_landed_after"]}/{BATCH["progress_free_total"]} = '
              f'{BATCH["progress_after"]}%, verified {BATCH["verified_after"]}')
    else:
        print(f'batch: complete at {live_landed} rows / bytes_landed {bt["landed"]:,} '
              f'(transcribed {bt["transcribed"]:,}); pre-registered exactly')
    return out


# The family's shape, at module scope because it is a NAME and not a private spelling: a landed family
# leaves the candidate frontier (6,288 -> 6,210 when its 78 members landed), so the only way to assert
# "this shape is not a candidate any more" is to be able to name it from outside this function.
WANT = 'mov rax,[rip+K] ; mov [rax+K],K ; ret'


def candidates(elf=None, max_insns=3):
    """One pass over the committed frontier: CANDIDATES ONLY, and empty for a landed family.

    This is the function whose zero was misread five times. It is not the family's population; `table()`
    is. Kept because a future unlanded family of this shape needs it, and because its emptiness is now an
    ASSERTION rather than a mystery: see test_the_family_shape_has_left_the_candidate_frontier.
    """
    elf = elf or S.ELF
    md = open(elf, 'rb').read()
    segs = S.load_segments(md)
    # detail=True is a PRECONDITION of S.shape_of, not decoration: it reads i.operands, and without
    # details capstone raises CsError on the first use. Importing a predicate does not import its
    # preconditions -- the census builds its disassembler this way, so this one must too.
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    want = WANT
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


def table(path=None):
    """The FAMILY: the committed table, parsed. The authority, because the frontier no longer holds it."""
    import catalogue   # the TYPED reader: a raw csv.DictReader here was refused by check_catalogue, and
    path = path or CSV_OUT   # the refusal's demanded fix is right -- one reader, so the radix rule has one home
    rows = []
    for r in catalogue.read_rows(path):
        # read_rows returns int `address`/`size` and leaves EVERY OTHER column a string: int(x, 16) on its
        # typed address raised TypeError, and a pipe reported tail's rc, so the breakage shipped and was
        # amended rather than followed up. The four hex columns are parsed here and nowhere else.
        rows.append({'address': r['address'], 'size': r['size'],
                     'load_disp': int(r['load_disp'], 16), 'load_target': int(r['load_target'], 16),
                     'where': r['where'], 'store_k2': int(r['store_k2'], 16),
                     'store_width': int(r['store_width']), 'imm': int(r['imm'], 16)})
    return rows


def verify(elf, rows):
    """Re-derive each row's own fields from the ELF and compare. Equality against the ROW, no shape string.

    The row is the unit: a shape string that fails to match says nothing about which row is wrong, which is
    why the old check could only print one number. Every mismatch here names the address, the field, the
    row's value and the ELF's.
    """
    md = open(elf, 'rb').read()
    segs = S.load_segments(md)
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True   # a precondition of reading operands, not decoration
    out = []
    for r in rows:
        addr = r['address']
        ins = list(cs.disasm(md[addr - S.BIAS:addr - S.BIAS + r['size']], addr))
        if len(ins) < 2:
            out.append(f"0x{addr:08x}: decodes to {len(ins)} instruction(s), the row needs at least 2")
            continue
        body = ins[:-1] if ins[-1].mnemonic == 'ret' else ins
        load = next((op for op in body[0].operands if op.type == capstone.x86.X86_OP_MEM), None)
        if load is None:
            out.append(f"0x{addr:08x}: instruction 1 has no memory operand")
            continue
        tgt = addr + body[0].size + load.mem.disp
        if load.mem.disp != r['load_disp']:
            out.append(f"0x{addr:08x}: load_disp row 0x{r['load_disp']:x} != ELF 0x{load.mem.disp:x}")
        if tgt != r['load_target']:
            out.append(f"0x{addr:08x}: load_target row 0x{r['load_target']:x} != ELF 0x{tgt:x}")
        where = S.classify_target(segs, tgt)
        if where != r['where']:
            out.append(f"0x{addr:08x}: where row {r['where']} != ELF {where} for target 0x{tgt:x}")
        mem = next((op for op in body[1].operands if op.type == capstone.x86.X86_OP_MEM), None)
        imm = next((op for op in body[1].operands if op.type == capstone.x86.X86_OP_IMM), None)
        if mem is None or imm is None:
            out.append(f"0x{addr:08x}: instruction 2 carries no store+K (mem={mem is not None}, "
                       f"imm={imm is not None})")
            continue
        if mem.mem.disp != r['store_k2']:
            out.append(f"0x{addr:08x}: store_k2 row 0x{r['store_k2']:x} != ELF 0x{mem.mem.disp:x}")
        if mem.size != r['store_width']:
            out.append(f"0x{addr:08x}: store_width row {r['store_width']} != ELF {mem.size}")
        if imm.imm != r['imm']:
            out.append(f"0x{addr:08x}: imm row 0x{r['imm']:x} != ELF 0x{imm.imm:x}")
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
    ap.add_argument('--check', action='store_true',
                    help='exit 1 unless the committed table reproduces byte-for-byte AND every row verifies')
    ap.add_argument('--rescan', action='store_true',
                    help='regenerate the table from the CANDIDATE frontier (refuses to empty a landed family)')
    ap.add_argument('--write', action='store_true', help='with --rescan: perform the write')
    a = ap.parse_args(argv)

    # ORDER: the truncation guard must be REACHABLE WITHOUT READING THE FILE IT GUARDS. My first version read
    # the table first, so `--rescan --write --out <new>` died in a FileNotFoundError traceback before the
    # refusal written for it could fire -- a guard above the diagnostic it serves, in the tool that prints
    # that sentence. Presence is decided first; absence refuses (rc=3) everywhere except a rescan.
    exists = os.path.isfile(a.out)
    rows = table(a.out) if exists else []   # THE FAMILY -- the committed table, never a scan
    cand = candidates(a.elf)                # THE CANDIDATES -- what is still on the frontier
    if not exists and not a.rescan:
        print(f'chain family: {a.out} is absent -- absence refuses (nothing to verify; '
              f'--rescan --write creates it)', file=sys.stderr)
        return 3
    got = summarise(rows)
    print(f"chain family: {got['rows']} rows | {got['bytes']} B | sizes "
          f"{dict(sorted(collections.Counter(r['size'] for r in rows).items()))} | "
          f"seeding required {got['seeding_required']}/{got['rows']} | "
          f"discriminating from the shipped image {got['discriminating']} | "
          f"distinct (load K, store K2, imm) {got['distinct_triples']} | "
          f"distinct store K2 {got['distinct_store_k2']}")
    print(f"candidates on the frontier: {len(cand)}" + (
        '' if cand else f" -- the family is landed, so '{WANT}' is not a candidate any more"))
    bad = [f'{k}: pre-registered {v}, measured {got[k]}' for k, v in PREREG.items() if got[k] != v]
    bad += verify(a.elf, rows)

    if a.rescan:
        if not cand:
            print(f'REFUSED rescan: the frontier yields 0 candidates while the table holds {len(rows)} '
                  f'row(s) -- that is a truncation, not a regeneration', file=sys.stderr)
            return 1
        cgot = summarise(cand)
        cbad = [f'{k}: pre-registered {v}, rescan says {cgot[k]}' for k, v in PREREG.items()
                if cgot[k] != v]
        if cbad:
            for line in cbad:
                print(f'REFUSED {line}', file=sys.stderr)
            print('refusing to write: the population moved, so this is a different family', file=sys.stderr)
            return 1
        if not a.write:
            print(f'rescan: would write {cgot["rows"]} row(s) / {cgot["bytes"]} B (no --write: nothing done)')
            return 0
        atomicio.atomic_write(a.out, to_text(cand))
        print(f'chain family: wrote {a.out} ({cgot["rows"]} rows / {cgot["bytes"]} B)')
        return 0

    bad += batch_problems(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if a.check:
        cur = open(a.out).read() if os.path.isfile(a.out) else ''
        if cur != to_text(rows):
            print(f'chain family: {a.out} is stale -- the rows do not round-trip', file=sys.stderr)
            return 1
        if bad:
            for line in bad:
                print(f'REFUSED {line}', file=sys.stderr)
            print('refusing: the table and the ELF disagree, so this is not the family it claims',
                  file=sys.stderr)
            return 1
        print(f'chain family: {a.out} reproduced byte-for-byte; {len(rows)} row(s) verified field-by-field')
        return 0
    if bad:
        for line in bad:
            print(f'REFUSED {line}', file=sys.stderr)
        print('refusing: the table and the ELF disagree, so this is not the family it claims',
              file=sys.stderr)
        return 1
    print('chain family: table and ELF agree on every row (nothing written; --rescan --write regenerates)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
