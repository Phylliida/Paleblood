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
    # The address column is hex and the size column is DECIMAL in ghidra_functions.csv. Parsing the
    # size as hex inflates every extent by up to 156 bytes, which widens every owners() window and
    # silently converts independent entries into "nested" ones -- the exact class of error that
    # reported a leaf frontier of 139 rows. One decode of one known row settles the radix.
    out = [(int(r["address"], 16), int(r["size"])) for r in csv.DictReader(open(path))]
    if not out:
        raise ValueError("extent table is empty")
    out.sort()
    return out


def owners(extents, v):
    """Every extent containing v. extents must be sorted by address.
    NOTE: on this catalogue the tie branch cannot fire. Sizes are decimal, extents are disjoint
    (a + size <= next address at every one of 157,756 adjacent pairs, 0 true overlaps, 0 duplicate
    starts), so `owners` is 1 for every catalogued address and `ambiguous` is a guard against a
    catalogue that does not exist here -- not evidence that ownership is usually unique by luck.
    """
    starts = [a for a, _ in extents]
    widest = max(s for _, s in extents)
    lo = bisect.bisect_left(starts, v - widest)
    hi = bisect.bisect_right(starts, v)
    return [(a, s) for a, s in extents[lo:hi] if a <= v < a + s]


def resolve(extents, v):
    """(owner, kind), kind in {owned, ambiguous, stray}.

    A TIE IS NOT BROKEN. Two catalogued extents of the same size both containing v contradict each other
    about the binary, and breaking the tie on the lower address would be breaking it on file order -- a
    property of the catalogue's layout, not of the code that ran. So a tie returns (None, "ambiguous") and
    is counted separately: owners=2 printed as though a choice had been made is the defect this refuses.
    """
    c = owners(extents, v)
    if not c:
        return None, "stray"
    smallest = [e for e in c if e[1] == min(s for _, s in c)]
    return (smallest[0], "owned") if len(smallest) == 1 else (None, "ambiguous")


def owner(extents, v):
    """The smallest containing extent, or None (also None when the answer is ambiguous)."""
    return resolve(extents, v)[0]


def parse_rows(text):
    return [{"index": int(m.group(1)), "pc": int(m.group(2), 16), "count": int(m.group(3))}
            for m in (PC_ROW.match(l) for l in text.splitlines()) if m]


def self_test():
    """Three synthetic cases with known owners, and the catalogue's first row on the real table."""
    table = [(0x1000, 0x100), (0x1020, 0x20), (0x2000, 0x40)]
    tie = [(0x0FF0, 0x40), (0x1000, 0x40)]
    cases = [(table, 0x1000, (0x1000, 0x100), 1, "a pc at an extent's first byte is owned by it"),
             (table, 0x1030, (0x1020, 0x20), 2, "nested: the smaller extent wins"),
             (table, 0x1500, None, 0, "a hole is a stray"),
             (tie, 0x1005, None, 2, "an equal-size tie refuses to pick (lower address is file order)")]
    bad = []
    for tbl, v, want, want_n, why in cases:
        got, n = owner(tbl, v), len(owners(tbl, v))
        kind = resolve(tbl, v)[1]
        want_kind = "stray" if want_n == 0 else "ambiguous" if want is None else "owned"
        if got != want or n != want_n or kind != want_kind:
            bad.append(f"{why}: {v:#x} -> {got} kind {kind} owners {n}, "
                       f"expected {want} kind {want_kind} owners {want_n}")
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
    ap.add_argument("--boot-err", default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--vaddr", action="append", default=[], metavar="V",
                    help="ask about a guest vaddr directly (the ladder's addresses are already vaddrs, "
                         "not pcs: converting them would be a base error wearing a query's clothes)")
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
    if a.boot_err is None:
        # A query and a join are two subjects. Asking about one vaddr must not require boot rows: a
        # refusal that fires on the path that does not need it teaches the reader to ignore refusals.
        if not a.vaddr:
            print("refusal: nothing to do -- give --boot-err for a join or --vaddr for a query",
                  file=sys.stderr)
            return 3
        for text in a.vaddr:
            v = int(text, 0)
            o, kind = resolve(extents, v)
            c = owners(extents, v)
            print(f"vaddr {v:#09x}: {kind} owners {len(c)} smallest "
                  f"{('none' if o is None else f'{o[0]:#09x}+{o[1]}')}"
                  + "".join(f"\n    contains {x[0]:#09x}+{x[1]}" for x in c))
        return 0

    for text in a.vaddr:
        v = int(text, 0)
        o, kind = resolve(extents, v)
        c = owners(extents, v)
        print(f"vaddr {v:#09x}: {kind} owners {len(c)} smallest "
              f"{('none' if o is None else f'{o[0]:#09x}+{o[1]}')}"
              + ("".join(f"\n    contains {x[0]:#09x}+{x[1]}" for x in c) if c else ""))

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
