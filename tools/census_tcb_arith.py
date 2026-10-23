#!/usr/bin/env python3
"""Does the guest reach module TLS through the TCB self-pointer?

The catalogue shows exactly one %fs displacement: 0. That is consistent with two opposite worlds --
  (a) no module TLS is touched at all, or
  (b) module TLS is reached the variant-II way: read tcb_self out of fs:0, then index off it in a GPR,
      which leaves fs:[-N] nowhere in the encoding.
Only a scan of what happens to the register holding fs:0 can tell them apart, and it is the difference
between "the layout is never consulted" and "the layout is consulted for every access".
"""
import csv, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_OP_IMM

BIN = "../data/bb/elf/eboot.elf"
FILE_BIAS = 0x3FC000
WINDOW = 16


def functions():
    for path in ("../data/ghidra_functions.csv", "symbols/ghidra_functions.csv"):
        try:
            with open(path, newline="") as f:
                return [(int(r["address"], 16), int(r["size"])) for r in csv.DictReader(f)]
        except FileNotFoundError:
            continue
    sys.exit("census_tcb_arith: no ghidra_functions.csv -- refusal, not a pass")


def main():
    image = open(BIN, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    fs_sites = 0
    fs_disp = {}
    tcb_reads = 0
    arith = []
    shapes = []
    offsets = {}
    for addr, size in functions():
        off = addr - FILE_BIAS
        if off < 0 or off >= len(image):
            continue
        code = image[off:off + min(size, 8192)]
        if b"\x64" not in code:
            continue
        insns = list(md.disasm(code, addr))
        for i, ins in enumerate(insns):
            if not any(m.type == X86_OP_MEM and ins.reg_name(m.mem.segment) == "fs" for m in ins.operands):
                continue
            fs_sites += 1
            d = ins.operands[0].mem.disp if ins.operands[0].type == X86_OP_MEM else 0
            fs_disp[d] = fs_disp.get(d, 0) + 1
            if d != 0:
                continue
            # Intel syntax: the destination is operand 0. A loader from fs:[0] is `mov reg, fs:[0]`, so
            # the memory operand is operand 1 -- reading operands[0].mem can never match, which is how
            # the first run of this tool printed 0 reads and looked like an absence.
            if not (len(ins.operands) == 2 and ins.operands[0].type == X86_OP_REG
                    and ins.operands[1].type == X86_OP_MEM):
                continue
            dst = ins.reg_name(ins.operands[0].reg)
            tcb_reads += 1
            if len(shapes) < 4:
                shapes.append(f"{ins.mnemonic} {ins.op_str}")
            for nxt in insns[i + 1:i + 1 + WINDOW]:
                hit = None
                for m in nxt.operands:
                    if m.type == X86_OP_MEM and nxt.reg_name(m.mem.base) == dst and m.mem.disp != 0:
                        hit = f"{nxt.mnemonic} {nxt.op_str} (disp {m.mem.disp:#x})"
                        offsets[m.mem.disp] = offsets.get(m.mem.disp, 0) + 1
                if hit is None and nxt.mnemonic in ("sub", "add", "lea") and dst in nxt.op_str and any(
                        o.type == X86_OP_IMM and o.imm < 0 for o in nxt.operands):
                    hit = f"{nxt.mnemonic} {nxt.op_str}"
                if hit:
                    arith.append((hex(ins.address), f"{ins.mnemonic} {ins.op_str}", hex(nxt.address), hit))
                    break
    print(f"fs sites: {fs_sites}; distinct displacements: { {hex(k): v for k, v in fs_disp.items()} }")
    print(f"fs:0 reads into a register: {tcb_reads}; of those, one followed by arithmetic off that register "
          f"inside {WINDOW} instructions: {len(arith)}")
    print("shapes seen:", shapes)
    top = sorted(offsets.items(), key=lambda kv: -kv[1])
    print(f"TCB-relative offsets reached through fs:[0]: {len(top)} distinct, {sum(offsets.values())} accesses")
    for disp, n in top[:12]:
        print(f"   {disp:+#x}: {n}")
    for row in arith[:12]:
        print("  ", row)


if __name__ == "__main__":
    main()
