#!/usr/bin/env python3
"""Block-leader census that does not confuse an exit with a missing leader.

`blocks.py` counts every static jump target that is not an instruction boundary inside the function's
declared extent as "unplaceable".  Its decode window *is* the extent, so a tail jump into a neighbour
is invisible as a boundary and gets counted as a defect of the function.  For 0x00414040 all three
"unplaced" targets (0x41447d, 0x414481, 0x4144ad) are past the declared end 0x414470 -- the function
has 66 blocks and zero genuinely unplaceable leaders.  The tier-wide 42.6% was measured this way.

This tool separates three populations that must never be added together:
  * internal unplaced leaders -- a static target inside the extent that is not an instruction boundary
    (a real defect: the block cannot be enumerated, so full coverage cannot be claimed)
  * exits -- static targets outside the extent; attributed to whichever catalogued function owns the
    address, or to `unowned` if no entry does.  An exit is a fact about the caller, never a defect of
    the callee, and it is never counted in a coverage denominator.
  * indirect transfers -- no static edge exists; counted per function, never assumed away.

    python3 -P tools/leaders.py --elf ../data/bb/elf/eboot.elf --tier
"""
import argparse
import bisect
import collections
import csv
import sys

import capstone

FILE_BIAS = 0x3FC000


def decode(blob, guest, size):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    return md, list(md.disasm(blob[guest - FILE_BIAS:guest - FILE_BIAS + size], guest))


def analyse(blob, guest, size, owner):
    """Return dict: blocks' inputs (internal unplaced leaders), exits by owner, indirect count."""
    md, insns = decode(blob, guest, size)
    if not insns:
        return None
    boundaries = {i.address for i in insns}
    end = guest + size
    unplaced = []
    exits = collections.Counter()
    indirect = 0
    for i in insns:
        if not i.group(capstone.CS_GRP_JUMP):
            continue
        tgt = None
        for op in i.operands:
            if op.type == capstone.x86.X86_OP_IMM:
                tgt = op.imm
        if tgt is None:
            indirect += 1
            continue
        if guest <= tgt < end:
            if tgt not in boundaries:
                unplaced.append((i.address, tgt))
        else:
            exits[owner(tgt)] += 1
    return {"insns": len(insns), "unplaced": unplaced, "exits": exits,
            "indirect": indirect, "decoded": sum(i.size for i in insns)}


def load(path):
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["address"], 16), int(r["size"])))
    rows.sort()
    return rows, [a for a, _ in rows]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--functions", default="symbols/ghidra_functions.csv")
    ap.add_argument("--tier-min", type=int, default=1024)
    ap.add_argument("--address", action="append", default=[])
    ap.add_argument("--tier", action="store_true")
    args = ap.parse_args(argv)

    blob = open(args.elf, "rb").read()
    rows, starts = load(args.functions)

    def owner(addr):
        k = bisect.bisect_right(starts, addr) - 1
        if k >= 0 and rows[k][0] <= addr < rows[k][0] + rows[k][1]:
            return "in-entry"
        return "unowned"

    targets = [(int(a, 16), dict(rows).get(int(a, 16), 0)) for a in args.address]
    if args.tier:
        targets += [(a, s) for a, s in rows if s > args.tier_min]

    tot = unpl = with_exit = unowned = indirect_fns = 0
    ex_owner = collections.Counter()
    worst = []
    for guest, size in targets:
        if not size:
            print(f"{guest:#010x} not in {args.functions}", file=sys.stderr)
            continue
        r = analyse(blob, guest, size, owner)
        if r is None:
            continue
        tot += 1
        if r["unplaced"]:
            unpl += 1
        if r["exits"]:
            with_exit += 1
            ex_owner.update(r["exits"])
            if r["exits"]["unowned"]:
                unowned += 1
                worst.append((r["exits"]["unowned"], guest, size, dict(r["exits"])))
        if r["indirect"]:
            indirect_fns += 1
        if args.address:
            print(f"{guest:#010x} size {size} insns {r['insns']} decoded {r['decoded']}/{size} "
                  f"internal-unplaced {len(r['unplaced'])} "
                  f"indirect {r['indirect']} exits {dict(r['exits'])}")
            for a, t in r["unplaced"][:5]:
                print(f"    internal unplaced: {a:#x} -> {t:#x} (+{t - guest})")
    print(f"entries {tot}")
    print(f"  with >=1 genuinely internal unplaced leader: {unpl} ({100.0 * unpl / tot:.1f}%)")
    print(f"  with >=1 exit (static target outside extent): {with_exit} "
          f"({100.0 * with_exit / tot:.1f}%)  of which some exit lands unowned: {unowned}")
    print(f"  exit targets by owner: {dict(ex_owner)}")
    print(f"  with >=1 indirect jump: {indirect_fns} ({100.0 * indirect_fns / tot:.1f}%)")
    worst.sort(reverse=True)
    for n, guest, size, ex in worst[:5]:
        print(f"  unowned exits: {guest:#x} size {size} {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
