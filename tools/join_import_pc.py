"""Join the boot's import-pc rows to the function extent that owns them.

WHY A TOOL AND NOT A PARAGRAPH: runtime/boot.c:276 promised "the join prints PC outside every function
extent: N" and no code printed it; the pc column it would have read was meanwhile filled from [r12]
(see docs/decisions.md, `49 8b 04 24`). So this join is born WITH its fixture: the control runs on the
catalogue's own first row and on three synthetic cases before any honest pc is interpreted.

CONVERSION, PRINTED NOT ASSUMED: the guest image is mapped at IMAGE and eboot links at EBOOT_BASE, so a
pc in image space converts as v = pc - IMAGE + EBOOT_BASE. Both constants are printed on every run: an
off-by-a-base join reads exactly like a body that cannot be attributed.

OWNERSHIP RULE, stated because nesting exists (2-4 extents contain some of these pcs): the owner is the
SMALLEST containing extent; ties break on the lower address; owners>1 is printed rather than hidden,
because a corpus that nests is a fact about the catalogue and not a defect of the join.

THE SCAN WINDOW IS EXACT, not a constant: candidates start at or after (v - max_size), found by bisect.
An arbitrary window (my first attempt used 7 rows) cannot see an extent that starts far behind v, and it
silently lost index 0 -- caught by the control, which is why the control is a shipped case and not a
one-off in a shell.
"""
import argparse
import bisect
import csv
import re
import sys

IMAGE = 0x800000000
EBOOT_BASE = 0x400000
PC_ROW = re.compile(r"^\s+#(\d+) pc (0x[0-9a-fA-F]+) count (\d+)\s*$")


def load_extents(path):
    out = [(int(r["address"], 16), int(r["size"], 16)) for r in csv.DictReader(open(path))]
    if not out:
        raise ValueError("extent table is empty")
    out.sort()
    return out


def owners(extents, v):
    """Every extent containing v. extents must be sorted by address."""
    starts = [a for a, _ in extents]
    widest = max(s for _, s in extents)
    lo = bisect.bisect_left(starts, v - widest)
    hi = bisect.bisect_right(starts, v)
    return [(a, s) for a, s in extents[lo:hi] if a <= v < a + s]


def owner(extents, v):
    """The smallest containing extent (ties: lower address), or None."""
    c = owners(extents, v)
    return min(c, key=lambda e: (e[1], e[0])) if c else None


def parse_rows(text):
    return [{"index": int(m.group(1)), "pc": int(m.group(2), 16), "count": int(m.group(3))}
            for m in (PC_ROW.match(l) for l in text.splitlines()) if m]


def self_test():
    """Three synthetic cases with known owners, and the catalogue's first row on the real table."""
    table = [(0x1000, 0x100), (0x1020, 0x20), (0x2000, 0x40)]
    cases = [(0x1000, (0x1000, 0x100), 1, "a pc at an extent's first byte is owned by it"),
             (0x1030, (0x1020, 0x20), 2, "nested: the smaller extent wins"),
             (0x1500, None, 0, "a hole is a stray")]
    bad = []
    for v, want, want_n, why in cases:
        got, n = owner(table, v), len(owners(table, v))
        if got != want or n != want_n:
            bad.append(f"{why}: {v:#x} -> {got} owners {n}, expected {want} owners {want_n}")
    real = load_extents("symbols/ghidra_functions.csv")
    first = real[0][0]
    if owner(real, first) != (first, real[0][1]):
        bad.append(f"control: the catalogue's own first row {first:#x} is not owned by itself")
    for b in bad:
        print("self-test FAIL:", b)
    print(f"self-test: {len(cases) + 1} cases, {len(bad)} failed")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--functions", default="symbols/ghidra_functions.csv")
    ap.add_argument("--boot-err", default="/dev/stdin")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    try:
        extents = load_extents(a.functions)
    except (OSError, ValueError, KeyError) as e:
        print(f"refusal: cannot load extents from {a.functions}: {e}", file=sys.stderr)
        return 3
    if owner(extents, extents[0][0]) != extents[0]:
        print("refusal: the join cannot own the catalogue's first row -- the rule is broken, not the data",
              file=sys.stderr)
        return 3
    rows = parse_rows(open(a.boot_err).read())
    print(f"conversion: v = pc - {IMAGE:#x} + {EBOOT_BASE:#x}; extents {len(extents)}")
    if not rows:
        print("refusal: no `#N pc 0x.. count N` rows parsed -- an empty join is indistinguishable "
              "from a boot that entered nothing", file=sys.stderr)
        return 3
    strays = nested = 0
    for r in rows:
        v = r["pc"] - IMAGE + EBOOT_BASE
        c = owners(extents, v)
        o = owner(extents, v)
        if not o:
            strays += 1
            print(f"  #{r['index']:>3} pc {r['pc']:#011x} -> {v:#09x} STRAY (count {r['count']})")
            continue
        if len(c) > 1:
            nested += 1
        print(f"  #{r['index']:>3} pc {r['pc']:#011x} -> {v:#09x} owner {o[0]:#09x}+{o[1]} "
              f"owners {len(c)} count {r['count']}")
    print(f"joined {len(rows)} rows: {strays} strays, {nested} with owners>1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
