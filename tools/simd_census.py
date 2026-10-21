#!/usr/bin/env python3
"""SIMD density census over the >1024-byte tier.

Why this exists: the pilot's candidate class was chosen on size and call count, and the first
candidate decompiled to 591 live XMM temporaries -- auto-vectorised float code that check_readable.py
forbids outside game/engine/.  Size was never the axis that decides whether a body can be written.
This tool measures the axis that does, as a distribution rather than a binary, because "zero SIMD" is
a filter on a continuous variable and its complement is not "untranslatable".

    python3 -P tools/simd_census.py --elf ../data/bb/elf/eboot.elf

Prints, for every tier entry (declared size > 1024), the instruction count, the SIMD instruction count
and the density; then the density distribution, then counts at several thresholds.  A known-positive
control (a function whose draft is dense in XMM temporaries) is scanned first and its count printed
beside the expected magnitude: an allow-list census that has never been shown to find a known
positive is a lower bound wearing a measurement's clothes.

file = guest - 0x3fc000.  Capstone only, detail not needed here (mnemonics only).
"""
import argparse
import collections
import csv
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

# Legacy SSE/SSE2 mnemonics that do not end in ps/pd/ss/sd and are not covered by the p* prefix rule.
EXPLICIT = {
    "movaps", "movups", "movapd", "movupd", "movdqa", "movdqu", "movq", "movd",
    "movlhps", "movhlps", "movhps", "movlps", "movhpd", "movlpd", "lddqu",
    "movntps", "movntpd", "movntdq", "movntq", "movnti",
    "shufps", "shufpd", "unpcklps", "unpckhps", "unpcklpd", "unpckhpd",
    "pmovmskb", "maskmovdqu", "maskmovq", "emms",
}
# x86 string I/O ends in "sd"/"ss"-like suffixes and is not SIMD; never let a suffix rule catch it.
NEVER = {"insb", "insw", "insd", "outsb", "outsw", "outsd", "push", "pop", "pushfq", "popfq"}
P_PREFIX = (
    "padd", "psub", "pmul", "pand", "por", "pxor", "pcmpeq", "pcmpgt", "psll", "psrl", "psra",
    "pshuf", "punpck", "pack", "pmov", "pextr", "pinsr", "pblend", "ptest", "palignr", "pmadd",
    "pabs", "psign", "phadd", "phsub", "pavg", "psad", "pmax", "pmin", "pmaskmov",
)


def is_simd(mnem):
    m = mnem.lower()
    if m in NEVER:
        return False
    if m in EXPLICIT:
        return True
    if m.startswith("v"):
        return True  # VEX encoding is SIMD by construction
    if m.endswith(("ps", "pd", "ss", "sd", "dq", "qu", "dqa", "dqu")):
        return True
    return m.startswith(P_PREFIX)


def scan(md, code, base):
    ins = simd = 0
    for i in md.disasm(code, base):
        ins += 1
        if is_simd(i.mnemonic):
            simd += 1
    return ins, simd


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--functions", default="symbols/ghidra_functions.csv")
    ap.add_argument("--tier-min", type=int, default=1024, help="tier is size > this")
    ap.add_argument("--control", default="0x00b46d20",
                    help="known-positive: a draft dense in XMM temporaries")
    args = ap.parse_args(argv)

    with open(args.elf, "rb") as fh:
        blob = fh.read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)

    rows = []
    with open(args.functions, newline="") as fh:
        for r in csv.DictReader(fh):
            a = int(r["address"], 16)
            size = int(r["size"])
            if size > args.tier_min:
                rows.append((a, size))
    rows.sort()

    # Positive control first, printed beside its expected magnitude.
    ca = int(args.control, 16)
    csize = next((s for a, s in rows if a == ca), None)
    if csize is None:
        print(f"control: {args.control} is not in the tier; control NOT run", file=sys.stderr)
        return 2
    off = ca - 0x3FC000
    ci, cs = scan(md, blob[off:off + csize], ca)
    print(f"control {args.control}: {ci} instructions, {cs} SIMD, density {cs / ci:.3f}"
          f" (expected: large -- its draft holds 591 XMM temporaries)")
    if cs < 50:
        print("control FAILED: a function known to be dense in vector code was counted as sparse;"
              " the allow-list is wrong and nothing below may be reported", file=sys.stderr)
        return 1

    dens = []
    zero = le2 = 0
    calls_le2 = collections.Counter()
    for a, size in rows:
        off = a - 0x3FC000
        ins, simd = scan(md, blob[off:off + size], a)
        if not ins:
            continue
        d = simd / ins
        dens.append((d, a, ins, simd, size))
        ncall = sum(1 for i in md.disasm(blob[off:off + size], a) if i.mnemonic == "call")
        if simd == 0:
            zero += 1
            if ncall <= 2:
                le2 += 1
    dens.sort()
    n = len(dens)
    print(f"tier entries scanned: {n} (size > {args.tier_min})")
    print(f"zero SIMD: {zero} ({100.0 * zero / n:.1f}%), of those <=2 calls: {le2}")
    qs = [0.10, 0.25, 0.50, 0.75, 0.90, 0.99]
    print("density percentiles: " + ", ".join(
        f"p{int(q * 100)}={dens[min(n - 1, int(q * n))][0]:.3f}" for q in qs))
    buckets = [(0.0, 0.0), (0.0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.25), (0.25, 1.01)]
    labels = ["density = 0", "0 < d <= 0.02", "0.02 < d <= 0.05", "0.05 < d <= 0.10",
              "0.10 < d <= 0.25", "d > 0.25"]
    for (lo, hi), lab in zip(buckets, labels):
        c = sum(1 for d, *_ in dens if (d == 0.0 if hi == 0.0 else lo < d <= hi))
        print(f"  {lab:<18} {c:6d} ({100.0 * c / n:5.1f}%)")
    for thr in (0.02, 0.05, 0.10, 0.25):
        c = sum(1 for d, *_ in dens if d <= thr)
        c2 = sum(1 for d, a, ins, simd, size in dens if d <= thr
                 and sum(1 for i in md.disasm(blob[a - 0x3FC000:a - 0x3FC000 + size], a)
                         if i.mnemonic == "call") <= 2)
        print(f"  density <= {thr:<5} {c:6d} ({100.0 * c / n:5.1f}%)   with <=2 calls {c2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
