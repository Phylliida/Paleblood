#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""runtime/, test/ and tools/ must contain nothing specific to the game: no
title identity, no tracked function names, no tracked addresses. All of that
lives under game/ and symbols/.

The first version of this check compiled one regex per tracked name and address and ran every
regex over every line -- about 44,000 patterns when the ledger held 21,130 functions, i.e. tens of
billions of searches. It had been written when the ledger held a few hundred rows, and it stopped
completing somewhere on the way to 21,130 without anything going red, because it is a ctest entry
whose only failure mode is "never finishes". It is now a token lookup: split each line on the same
word characters the original lookaround used, and ask a set. Same semantics, no patterns per value.

usage: check_agnostic.py [--root DIR]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import string
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The stack dump used to be armed HERE, at module scope, by a `try: import stacks; stacks.arm()`. Four test
# modules import this file, so merely READING it -- in the suite's own interpreter -- armed a repeating
# 60-second faulthandler dump for the whole run, which is where 37 MB of dumps and a missing verdict came
# from. A gate that arms a watchdog on import arms it in every process that looks at it. The arm belongs to
# the process that RUNS the gate, so it lives under __main__ and is cancelled on the way out.

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = ('runtime', 'test', 'tools')
SKIP_EXT = {'.pyc'}
TOKEN = re.compile(r'[0-9A-Za-z_]+')          # the class the old lookaround bounded on
TOKEN_CHARS = frozenset(string.ascii_letters + string.digits + '_')


def collect(root: str) -> tuple[dict[str, str], dict[str, str], list[tuple[str, re.Pattern]], int]:
    """Return (name -> label, address -> label, leftover substring patterns, patterns considered).

    A value made only of word characters becomes a set entry, because splitting a line on word
    characters reproduces exactly the word-boundary match the old lookaround expressed. Anything
    else keeps a compiled pattern -- there are no such values today, and the count is printed so
    that a future one is visible rather than silently dropped.
    """
    names: dict[str, str] = {}
    addresses: dict[str, str] = {}
    leftover: list[tuple[str, re.Pattern]] = []
    considered = 0
    path = os.path.join(root, 'game', 'agnostic_words.txt')
    if os.path.isfile(path):
        with open(path) as f:
            for ln in f:
                w = ln.strip()
                if w and not w.startswith('#'):
                    leftover.append((w, re.compile(re.escape(w), re.I)))
                    considered += 1
    sources = (('symbols/functions.csv', 'name', 'function name'),
               ('symbols/functions.csv', 'address', 'address'),
               ('game/hooks.csv', 'address', 'address'))
    for rel, col, label in sources:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue
        with open(p, newline='') as f:
            for r in csv.DictReader(f):
                v = r[col]
                considered += 1
                if set(v) - TOKEN_CHARS:
                    leftover.append((f'{label} {v}', re.compile(re.escape(v), re.I)))
                elif col == 'name':
                    names.setdefault(v.lower(), label)
                else:
                    addresses.setdefault(v.lower(), label)
    return names, addresses, leftover, considered


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=DEFAULT_ROOT)
    root = ap.parse_args().root
    names, addresses, leftover, considered = collect(root)
    errs: list[str] = []
    files = lines = 0
    for top in SCOPE:
        for dp, _, fs in os.walk(os.path.join(root, top)):
            if '__pycache__' in dp:
                continue
            for fn in fs:
                if os.path.splitext(fn)[1] in SKIP_EXT:
                    continue
                path = os.path.join(dp, fn)
                rel = os.path.relpath(path, root)
                try:
                    text = open(path, encoding='utf-8').read()
                except (UnicodeDecodeError, OSError):
                    continue
                files += 1
                for n, ln in enumerate(text.splitlines(), 1):
                    lines += 1
                    hit = {label for label, pat in leftover if pat.search(ln)}
                    for tok in TOKEN.findall(ln):
                        low = tok.lower()
                        found = names.get(low) or addresses.get(low)
                        if found:
                            hit.add(found)
                    for label in sorted(hit):
                        errs.append(f'{rel}:{n}: game-specific ({label})')
    for e in errs:
        print(f'agnostic: {e}', file=sys.stderr)
    print(f'agnostic: {considered} tracked values ({len(names)} names, {len(addresses)} addresses, '
          f'{len(leftover)} substring patterns) over {files} files, {lines} lines: '
          f'{len(errs)} finding(s)')
    return 1 if errs else 0


if __name__ == '__main__':
    try:
        import stacks
        stacks.arm()      # this process is about to do the work; its own frames are wanted
    except ImportError:
        pass
    try:
        sys.exit(main())
    finally:
        try:
            import stacks
            stacks.cancel()
        except ImportError:
            pass
