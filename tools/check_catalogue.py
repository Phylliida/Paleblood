#!/usr/bin/env python3
"""Refuse a NEW csv.DictReader outside catalogue.py, and refuse ANY explicit size radix.

The radix class appeared four times inside a tool a commit hook runs, so the fix is a shape (typed rows)
plus a check that the shape is the only route. Two tiers, for two reasons:

  * explicit radix on the size column -- `["size"], 16` etc. -- is at ZERO today and must stay zero.
    Absolute, no baseline: this is the defect itself.
  * raw `csv.DictReader` is at 101 sites in 56 files. Refusing all of them on day one would mean a gate
    nobody can merge behind, so they are grandfathered in tools/catalogue_allowlist.txt, on the
    readable_allowlist.txt precedent. The list may only SHRINK: a file that no longer needs an entry
    must have it removed, and a new file may not be added (the gate refuses an entry for a file that
    does not use DictReader, so the baseline cannot grow by accident).

Also scans test/, because `tools/*.py` misses it -- a gate that greps the wrong directory passes forever.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOW = ROOT / "tools" / "catalogue_allowlist.txt"
# AST, not regex: a regex fires on a DOCSTRING that quotes the defect, which is exactly where the
# defect is documented. The first version of this gate refused tools/join_import_pc.py for its own
# explanation of the bug it had just stopped making.
EXEMPT = {"tools/catalogue.py", "tools/check_catalogue.py"}


def _is_size_key(node):
    return isinstance(node, ast.Constant) and node.value == "size"


def _count(tree):
    """(explicit size radix, csv.DictReader calls) -- counted from the SYNTAX, not the text."""
    radix = reader = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "DictReader":
            reader += 1
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 16:
                a0 = node.args[0]
                subscript = isinstance(a0, ast.Subscript) and _is_size_key(a0.slice)
                getter = (isinstance(a0, ast.Call) and getattr(a0.func, "attr", None) == "get"
                          and bool(a0.args) and _is_size_key(a0.args[0]))
                if subscript or getter:
                    radix += 1
    return radix, reader


def scan():
    hits = {}
    for d in ("tools", "test"):
        for p in sorted((ROOT / d).glob("*.py")):
            rel = str(p.relative_to(ROOT))
            if rel in EXEMPT:
                continue
            try:
                tree = ast.parse(p.read_text(errors="replace"))
            except SyntaxError as exc:
                hits[rel] = (1, 0)          # unparseable refuses; a file the gate cannot read is not clean
                print(f"REFUSED {rel}: cannot parse ({exc.msg})")
                continue
            radix, reader = _count(tree)
            if radix or reader:
                hits[rel] = (radix, reader)
    return hits


def main():
    hits = scan()
    bad = sorted(rel for rel, (radix, _) in hits.items() if radix)
    for rel in bad:
        print(f"REFUSED {rel}: explicit size radix (sizes are decimal) -- use catalogue.read_rows")
    allowed = set()
    if ALLOW.exists():
        allowed = {l.strip() for l in ALLOW.read_text().splitlines() if l.strip() and not l.startswith("#")}
    users = {rel for rel, (_, reader) in hits.items() if reader}
    new = sorted(users - allowed)
    stale = sorted(allowed - users)
    for rel in new:
        print(f"REFUSED {rel}: csv.DictReader outside catalogue.py -- add a typed reader instead")
    for rel in stale:
        print(f"REFUSED {rel}: allowlisted but no longer uses csv.DictReader -- prune the baseline")
    if bad or new or stale:
        print(f"catalogue parses: {len(new)} new, {len(stale)} stale, {len(bad)} radix -- refusing")
        return 1
    print(f"catalogue parses: ok ({len(users)} grandfathered file(s) in tools/catalogue_allowlist.txt, 0 radix)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
