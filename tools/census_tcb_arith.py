#!/usr/bin/env python3
"""What does the guest do with the pointer in fs:[0]?

Two wrong answers have come out of this tool, both from predicates rather than from the guest:
  * a load's destination is operand 0 in Intel syntax, so `mov reg, fs:[0]` has its memory operand at
    [1] -- filtering operands[0].mem printed 0 reads for seven slices;
  * `add rax, [rip+K]` writes the holder register *and reads it*, so ending the window on any write to it
    truncated the chain at instruction one and printed 0 again.
So the chain is walked with an indirection depth, the matched shapes are printed before any count, and a
zero has to survive being read. Offsets at depth 0 are TCB fields; offsets at depth >= 1 are fields of
something the TCB points at, and conflating the two is how the first version's ranking was wrong.
"""
import csv, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_OP_IMM

BIN = "../data/bb/elf/eboot.elf"
FILE_BIAS = 0x3FC000
WINDOW = 24


def functions():
    for path in ("../data/ghidra_functions.csv", "symbols/ghidra_functions.csv"):
        try:
            with open(path, newline="") as f:
                return [(int(r["address"], 16), int(r["size"])) for r in csv.DictReader(f)]
        except FileNotFoundError:
            continue
    sys.exit("census_tcb_arith: no ghidra_functions.csv -- refusal, not a pass")


# Mnemonics whose destination is written without being read. Everything else (add, sub, and, xor, shl,
# imul, lea aside) reads its destination -- and `add rax, [rip+K]` is the second instruction of the idiom
# this scan exists to follow, so treating it as a clobber truncated every chain at instruction one and
# printed a second zero from a predicate. Named explicitly, because a default here decides the census.
PURE_WRITE = {"mov", "movabs", "movzx", "movsx", "movsxd", "pop"}


def writes_without_reading(ins, name):
    if not ins.operands or ins.operands[0].type != X86_OP_REG or ins.reg_name(ins.operands[0].reg) != name:
        return False
    return ins.mnemonic in PURE_WRITE


def main():
    image = open(BIN, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    fs_sites = 0
    fs_disp = {}
    tcb_reads = 0
    shapes = []
    off = {}                   # (depth, disp) -> count ; depth 0 is the TCB itself
    stores = {}
    store_shapes = []
    chains = []
    for addr, size in functions():
        o = addr - FILE_BIAS
        if o < 0 or o >= len(image):
            continue
        code = image[o:o + min(size, 8192)]
        if b"\x64" not in code:
            continue
        insns = list(md.disasm(code, addr))
        for i, ins in enumerate(insns):
            if not any(m.type == X86_OP_MEM and ins.reg_name(m.mem.segment) == "fs" for m in ins.operands):
                continue
            fs_sites += 1
            fs_disp[ins.operands[-1].mem.disp if ins.operands[-1].type == X86_OP_MEM else -1] = \
                fs_disp.get(ins.operands[-1].mem.disp if ins.operands[-1].type == X86_OP_MEM else -1, 0) + 1
            if not (len(ins.operands) == 2 and ins.operands[0].type == X86_OP_REG
                    and ins.operands[1].type == X86_OP_MEM):
                continue
            dst = ins.reg_name(ins.operands[0].reg)
            tcb_reads += 1
            if len(shapes) < 3:
                shapes.append(f"{ins.mnemonic} {ins.op_str}")
            depth = 0
            walk = [f"{ins.mnemonic} {ins.op_str}"]
            for nxt in insns[i + 1:i + 1 + WINDOW]:
                if not nxt.operands:
                    continue
                d0 = nxt.operands[0]
                if writes_without_reading(nxt, dst):
                    hop = any(m.type == X86_OP_MEM and nxt.reg_name(m.mem.base) == dst for m in nxt.operands)
                    if not hop:
                        break                  # a value that is not derived from fs:0: another subject
                    depth = min(depth + 1, 3) if nxt.mnemonic in ("mov", "movabs") else depth
                for m in nxt.operands:
                    if m.type == X86_OP_MEM and nxt.reg_name(m.mem.base) == dst and m.mem.disp != 0:
                        off[(depth, m.mem.disp)] = off.get((depth, m.mem.disp), 0) + 1
                        if d0.type == X86_OP_MEM and len(store_shapes) < 4:
                            store_shapes.append(f"depth {depth}: {nxt.mnemonic} {nxt.op_str}")
                        if d0.type == X86_OP_MEM:
                            stores[(depth, m.mem.disp)] = stores.get((depth, m.mem.disp), 0) + 1
                        if len(walk) < 5:
                            walk.append(f"{nxt.mnemonic} {nxt.op_str}")
                if len(walk) < 5 and d0.type == X86_OP_REG and nxt.reg_name(d0.reg) == dst:
                    walk.append(f"{nxt.mnemonic} {nxt.op_str}")
            if len(chains) < 6 and len(walk) > 2:
                chains.append((hex(ins.address), walk))
    print("shapes matched FIRST:", shapes)
    print("store shapes matched FIRST:", store_shapes)
    print(f"fs sites: {fs_sites}; displacements: { {hex(k): v for k, v in fs_disp.items()} }")
    print(f"fs:0 -> register reads: {tcb_reads}")
    for depth in (0, 1, 2, 3):
        rows = sorted(((d, n) for (dep, d), n in off.items() if dep == depth), key=lambda kv: -kv[1])
        if not rows:
            print(f"  depth {depth}: no offset accesses")
            continue
        meaning = "TCB fields" if depth == 0 else f"fields of an object the TCB points at (hop {depth})"
        print(f"  depth {depth} ({meaning}): {len(rows)} distinct, {sum(n for _, n in rows)} accesses; "
              f"top {[(hex(d), n) for d, n in rows[:6]]}")
        print(f"    of which written here: "
              f"{[(hex(d), stores.get((depth, d), 0)) for d, n in rows[:6] if stores.get((depth, d))]}")
    print("sample chains:")
    for a, w in chains:
        print("  ", a, "->", " ; ".join(w))


if __name__ == "__main__":
    main()
