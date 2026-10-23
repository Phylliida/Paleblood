#!/usr/bin/env python3
"""Joins the runtime's registration table to the bind lines the boot actually resolves, as (NID, library).

The join key must be the tuple the runtime uses. boot.c:474-479 binds on
`!strncmp(name, nid, RT_NID_SIZE) && !strcmp(library, s->library)` -- NID and library label -- so a join
on the symbol name alone is coarser than the lookup it tests and its zero is worthless in both
directions. memset proved it: registered under libSceLibcInternal, imported under libc, refused; a
name-only join matched the wrong label and reported zero missing about the row the boot was refusing.

The denominator is docs/bind-order-eboot.txt (one row per module-table binding), not
symbols/import_names.csv (one row per NID), because only the bind file has a label per binding.

rc: 0 every named binding has a body under its own label; 1 at least one does not; 3 an input is missing.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIND = ROOT / "docs/bind-order-eboot.txt"
CSV = ROOT / "symbols/import_names.csv"
SYSLIB = ROOT / "runtime/syslib"
REGISTRATION = re.compile(r'RT_SYSLIB(?:_MODELLED|_NOOP|_UNRESOLVED)?\(\s*"([^"]+)"\s*,\s*(\w+)\s*,')
BIND_ROW = re.compile(r"^bind\s+(\d+)\s+(\S+?)#\S*\s+(\S+)\s*$")
# The file carries a second, non-import row shape: `bind 4 module_stop (none)`. It is classified, never
# bucketed -- the entries have no NID and no library, so they are not part of this join's population, and
# a parser that quietly skipped them would report a denominator it had invented.
MODULE_ROW = re.compile(r"^bind\s+(\d+)\s+(module_start|module_stop)\s+\(none\)\s*$")


def bindings():
    if not BIND.exists():
        sys.exit(f"refusal: {BIND} is missing")
    out, module_rows = [], 0
    for n, line in enumerate(BIND.read_text().splitlines(), 1):
        if not line.strip():
            continue
        m = BIND_ROW.match(line)
        if m:
            out.append((int(m.group(1)), m.group(2), m.group(3)))
        elif MODULE_ROW.match(line):
            module_rows += 1
        else:
            sys.exit(f"refusal: {BIND}:{n} does not parse as an import or a module row: {line!r}")
    print(f"bind file: {len(out)} import rows, {module_rows} module rows (not in this population)")
    return out


def names():
    if not CSV.exists():
        sys.exit(f"refusal: {CSV} is missing")
    table = {}
    for line in CSV.read_text().splitlines():
        fields = line.split(",")
        if len(fields) == 5:
            table[fields[0]] = fields[3]
    return table


def registered():
    table = set()
    files = sorted(SYSLIB.glob("*.c"))
    if not files:
        sys.exit(f"refusal: no syslib sources under {SYSLIB}")
    for path in files:
        for library, symbol in REGISTRATION.findall(path.read_text()):
            table.add((library, symbol))
    return table


def main():
    rows, name_of, table = bindings(), names(), registered()
    named = [(i, nid, lib) for i, nid, lib in rows if name_of.get(nid) and name_of[nid] != nid]
    served = [(i, nid, lib) for i, nid, lib in named if (lib, name_of[nid]) in table]
    missing = [(i, nid, lib) for i, nid, lib in named if (lib, name_of[nid]) not in table]
    # Controls: both labels of memset's NID must be served, or the join cannot see labels at all.
    # (library, symbol), the order the table holds -- the first version of this control compared
    # ("memset", lib) and refused, which is the only reason the reversed key was visible at all.
    controls = {lib: (lib, "memset") in table for lib in ("libc", "libSceLibcInternal")}
    print(f"bind rows {len(rows)}  named {len(named)}  unnamed {len(rows) - len(named)}  "
          f"registered (library, symbol) {len(table)}")
    print(f"controls: memset served under {controls}")
    if not all(controls.values()):
        print("refusal: a control label is not served; the join cannot see what it tests")
        return 3
    for i, nid, lib in missing[:20]:
        print(f"  named, no body under its label: bind {i} {nid} {name_of[nid]} {lib}")
    print(f"served {len(served)}  missing {len(missing)}  (of {len(named)} named bindings)")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
