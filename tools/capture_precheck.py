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

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "symbols" / "capture_candidates.txt"
TABLE = ROOT / "symbols" / "capture_ok.csv"
ELF = ROOT.parent / "data" / "bb" / "elf" / "eboot.elf"
EBOOT_BASE = 0x400000          # image = guest - EBOOT_BASE
FILE_BIAS = 0x3fc000           # file  = guest - FILE_BIAS

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


def _body_size(address: int) -> int:
    """The catalogued length of the body, from the table that already owns that fact."""
    with (ROOT / "symbols" / "functions.csv").open() as rows:
        header = next(rows).rstrip("\n").split(",")
        size_at = header.index("size")
        addr_at = header.index("address")
        for row in rows:
            fields = row.rstrip("\n").split(",")
            if int(fields[addr_at], 16) == address:
                return int(fields[size_at])
    raise SystemExit(f"no catalogued body at 0x{address:08x}")


def table_rows() -> list[tuple[str, str, str]]:
    """`address,xmm_used,scanned_sha256` for every capture candidate, keyed on the body's own bytes.

    Content, not address and not mtime: a body edited after scanning changes its hash, so the row stops matching
    and the capture refuses -- the same expiry-by-content trick that makes a shape approval invalidate itself.
    An address-keyed table goes stale silently; this one cannot.
    """
    elf = ELF.read_bytes()
    rows = []
    for line in CANDIDATES.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        address = int(line.strip(), 16)
        code = elf[address - FILE_BIAS : address - FILE_BIAS + _body_size(address)]
        ok, why = verdict(code)
        rows.append((f"0x{address:08x}", "none" if ok else why.split(" ")[0], hashlib.sha256(code).hexdigest()))
    return rows


def write_table() -> str:
    return "address,xmm_used,scanned_sha256\n" + "".join(",".join(r) + "\n" for r in table_rows())


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--table":
        sys.stdout.write(write_table())
        return 0
    if len(argv) != 2:
        print("usage: capture_precheck.py <hex bytes> | --table", file=sys.stderr)
        return 2
    ok, why = verdict(bytes.fromhex(argv[1]))
    print(why, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
