#!/usr/bin/env python3
"""Refuse externs in .c files, in two tiers, each wanting the OPPOSITE direction.

Data (`extern int32_t x;`) -- the class this campaign paid for (`volatile uint32_t` vs `extern
volatile int32_t`, linker-invisible, resolved by luck of which units got linked): **absolute zero**.

Functions and linker symbols (`extern int f(void);`, `extern const T __start_s[];`) -- eleven exist
today, overwhelmingly weak accessors and section bounds. They are listed in tools/extern_roster.txt and
the roster is enforced in BOTH directions, the same predicate the DictReader allowlist uses:

  * a declaration in the tree that is not in the roster   -> REFUSED (a new extern cannot slip in)
  * a roster entry that no longer appears in the tree     -> REFUSED (a stale justification cannot sit
                                                             there collecting trust)

The second half is the one that is usually a sentence instead of a check. Without it the list becomes a
place a future reader assumes someone justified.

Comments are stripped before scanning: a docstring-style comment saying "extern uint32_t rt_x" is not a
declaration, and a gate that fires on prose gets an exemption added instead of a fix.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ROSTER = ROOT / "tools" / "extern_roster.txt"
DECL = re.compile(r"^\s*extern\s+(?P<rest>.+?;)\s*$")
NAME_FN = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
NAME_DATA = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\[|=|;)")
EXEMPT_NAMES = {"__attribute__", "__asm__"}


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def classify(src):
    """[(kind, name)] for one source TEXT -- the unit the tests feed strings to."""
    out = []
    for line in strip_comments(src).splitlines():
        m = DECL.match(line)
        if not m:
            continue
        rest = m.group("rest")
        fn = NAME_FN.search(rest)
        data = NAME_DATA.search(rest)
        # A function declaration has '(' before the first ';'/']' terminator; an array symbol does not.
        if fn and (data is None or fn.start() < data.start()):
            name = fn.group(1)
            out.append(("function", name))
        elif data:
            name = data.group(1)
            if name not in EXEMPT_NAMES:
                out.append(("data", name))
    return out


def scan_tree():
    found = {}
    for p in sorted((ROOT / "runtime").rglob("*.c")):
        rel = str(p.relative_to(ROOT))
        for kind, name in classify(p.read_text(errors="replace")):
            found.setdefault((kind, name), []).append(rel)
    return found


def main():
    found = scan_tree()
    errors = []
    for (kind, name), where in sorted(found.items()):
        if kind == "data":
            errors.append(f"REFUSED {where[0]}: `extern` data declaration `{name}` -- belongs in a header")
    roster = set()
    if ROSTER.exists():
        roster = {l.strip() for l in ROSTER.read_text().splitlines()
                  if l.strip() and not l.startswith("#")}
    functions = {name for (kind, name) in found if kind == "function"}
    new = sorted(functions - roster)
    stale = sorted(roster - functions)
    for name in new:
        errors.append(f"REFUSED: function extern `{name}` in a .c file is not in tools/extern_roster.txt")
    for name in stale:
        errors.append(f"REFUSED: roster entry `{name}` no longer appears in any .c file -- prune it")
    if errors:
        for e in errors:
            print(e)
        print(f"externs: {len(new)} new, {len(stale)} stale, "
              f"{sum(1 for k, _ in found if k == 'data')} data -- refusing")
        return 1
    print(f"externs: ok (data 0 · {len(functions)} function/symbol declaration(s), all rostered and present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
