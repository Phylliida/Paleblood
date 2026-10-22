#!/usr/bin/env python3
"""Does the guest use fs:/gs: segment overrides? Static, one pass over the catalog partition.

The main thread runs guest code with glibc's own %fs, so a guest `mov rax, fs:[0]` reads glibc's TCB and
nothing in the boot so far would have said so. Counts and names addresses; no boot involved.

Decoding is per catalog entry (the Ghidra partition), never a linear sweep: a sweep desyncs and its
instruction counts are not comparable to anything else here.
"""
import csv, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT = "../data/bb/elf/eboot.elf"
FILE_BIAS = 0x3fc000
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = False

blob = open(EBOOT, "rb").read()
fs_hits, gs_hits, n, decode_fail = [], [], 0, 0
with open("symbols/ghidra_functions.csv", newline="") as f:
    for row in csv.DictReader(f):
        n += 1
        a = int(row["address"], 16) if not row["address"].startswith("0x") else int(row["address"], 16)
        size = int(row["size"]) if row.get("size") else 0
        off = a - FILE_BIAS
        if size <= 0 or off < 0 or off + size > len(blob):
            continue
        body = blob[off:off + size]
        for ins in md.disasm(body, a):
            if not ins.bytes:
                continue
            if ins.bytes[0] == 0x64:
                fs_hits.append((ins.address, ins.mnemonic + " " + ins.op_str))
            elif ins.bytes[0] == 0x65:
                gs_hits.append((ins.address, ins.mnemonic + " " + ins.op_str))
print(f"catalog entries scanned: {n}")
print(f"fs: (0x64) instructions: {len(fs_hits)}")
print(f"gs: (0x65) instructions: {len(gs_hits)}")
for addr, text in fs_hits[:10]:
    print(f"  fs  {addr:#x}  {text}")
for addr, text in gs_hits[:5]:
    print(f"  gs  {addr:#x}  {text}")
