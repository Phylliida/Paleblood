#!/usr/bin/env python3
"""Joins the `implemented` claims in symbols/import_names.csv to the runtime's registration table.

KNOWN LIMITATION, measured on the row that motivated it: this join is by SYMBOL NAME, and the runtime's
lookup (boot.c:474-479) is by (NID, LIBRARY LABEL). memset was registered under libSceLibcInternal and
refused when the guest imported it under libc; this tool, run before that was fixed, matched the wrong
label and reported zero missing -- it would have blessed the broken row. A join that can see library
labels needs bind-order-eboot.txt (one row per module-table binding, 848) and not the csv (one row per
NID, 748). Until then this tool's zero means "every claimed symbol has a body under some label".

A status column is a claim about intent; only a join to the artifact makes it a measurement. memset was
found by being refused at the thing its row claimed was done, which means the column had never been
checked against the runtime -- and the rows nobody has been refused at are not evidence that they are
right. This tool checks every one of them.

rc: 0 every implemented row has a registered body; 1 at least one does not; 3 an input is missing.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "symbols/import_names.csv"
SYSLIB = ROOT / "runtime/syslib"
REGISTRATION = re.compile(r'RT_SYSLIB\(\s*"([^"]+)"\s*,\s*(\w+)\s*,')


def registered():
    """Every body the runtime registers, as {symbol: [libraries]}."""
    table = {}
    files = sorted(SYSLIB.glob("*.c"))
    if not files:
        sys.exit(f"refusal: no syslib sources under {SYSLIB}")
    for path in files:
        for library, symbol in REGISTRATION.findall(path.read_text()):
            table.setdefault(symbol, []).append(f"{library} ({path.name})")
    return table


def rows():
    if not CSV.exists():
        sys.exit(f"refusal: {CSV} is missing")
    out = []
    for line in CSV.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) != 5:
            sys.exit(f"refusal: {CSV} line {line!r} has {len(fields)} fields, not 5")
        out.append(fields)
    return out


def main():
    table, all_rows = registered(), rows()
    implemented = [r for r in all_rows if r[4] == "implemented"]
    matched = [r for r in implemented if r[3] in table]
    missing = [r for r in implemented if r[3] not in table]
    print(f"rows {len(all_rows)}  registered bodies {len(table)}  claimed implemented {len(implemented)}")
    # A join that can only ever return zero is not a measurement: prove a hit is reachable.
    control = "memset" in table
    print(f"control: memset registered -> {control}")
    if not control:
        print("refusal: the join cannot produce a hit; the table was not parsed")
        return 3
    for nid, library, ordinal, name, _ in missing:
        print(f"  claimed implemented, no body: {name}  {nid} {library}:{ordinal}")
    labels = {r[1] for r in implemented}
    print(f"join key: symbol name only; library labels in play {len(labels)} (see the limitation above)")
    print(f"matched {len(matched)}  missing {len(missing)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
