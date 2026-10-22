"""Refuse a capture wrapper for a body whose floats the snapshot call would clobber.

The capture wrapper saves six GPRs around the C snapshot call and **not** `xmm0-7`, which are caller-saved: the
call may destroy every one of them before the body sees them. For a body with no float arguments that costs
nothing, which is exactly why shipping it silently would be wrong -- the wrapper is generic and the next float
body gets garbage with every counter saying `installed`.

The policy is a refusal that names its reason, derived from the same disassembly the base-register census uses,
with the register ids imported from the module rather than remembered. When a float body becomes the target, the
answer is to save and restore `xmm0-7` and re-prove the capacity with the sentinel; until then this refuses.
"""
from __future__ import annotations

import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86_const import (
    X86_REG_XMM0, X86_REG_XMM1, X86_REG_XMM2, X86_REG_XMM3,
    X86_REG_XMM4, X86_REG_XMM5, X86_REG_XMM6, X86_REG_XMM7,
)

# Derived from the module, never from memory: the enum is not what a previous slice of mine thought it was.
VOLATILE_XMM = frozenset(range(X86_REG_XMM0, X86_REG_XMM7 + 1))


def scan(code: bytes) -> dict:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    xmm_seen: set[str] = set()
    bases: set[str] = set()
    for insn in md.disasm(code, 0):
        for op in insn.operands:
            if op.type == 1 and op.reg in VOLATILE_XMM:      # X86_OP_REG
                xmm_seen.add(md.reg_name(op.reg))
            if op.type == 3 and op.mem.base:                  # X86_OP_MEM
                bases.add(md.reg_name(op.mem.base))
    return {"xmm": xmm_seen, "bases": bases}


def verdict(code: bytes) -> tuple[bool, str]:
    if not code:
        # A zero-length body scans clean, and a scan that can pass on nothing is not a scan.
        return False, "no bytes to scan"
    found = scan(code)
    if found["xmm"]:
        names = ", ".join(sorted(found["xmm"]))
        return False, f"{names} used by body: the snapshot call may clobber caller-saved xmm0-7"
    return True, f"ok: no volatile xmm in {len(code)} bytes (bases: {', '.join(sorted(found['bases'])) or 'none'})"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: capture_precheck.py <hex bytes>", file=sys.stderr)
        return 2
    ok, why = verdict(bytes.fromhex(argv[1]))
    print(why, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
