#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Readability lint for game/ (STYLE.md): fails on transcription patterns.

usage: check_readable.py [--root DIR] [--base REF | --base-list FILE] [FILE...]

Checks every C and C++ file under game/ (or the files given) for:
  - calls by address: rt::fn<, a cast of an address literal, an address literal in an expression
  - offset access: get<...>(p, N) / put<...>(p, N) / ptr_at(p, N) with a number, p[0x..] indexing
  - recording code: rec. , capture JSON ("schema", "stubs", "argmem"), rt_capture_*
  - SSE intrinsics (_mm_*) outside game/engine/
  - magic numbers: numeric literals other than 0 and 1 outside a named-constant declaration
    (constexpr / const / enum / static_assert / alignas / padding members / RT_ORIGINAL /
    RT_GLOBAL lines)
Comments and string literals are ignored, except that capture JSON in strings counts.

Files written before the rule are listed in tools/readable_allowlist.txt and skipped. The list may
only shrink: an entry that is no longer needed (the file passes, or is gone) is an error, and with
--base REF (CI: the target branch) or --base-list FILE (pre-commit: HEAD's list) an entry that is
not in that list is an error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWLIST = 'tools/readable_allowlist.txt'
CACHE = '.readable-cache.json'   # content-hash cache; gitignored, per worktree
SOURCES = ('.c', '.cc', '.cpp', '.h', '.hpp')

NUMBER = re.compile(r'(?<![\w.])(0[xX][0-9a-fA-F]+[uUlL]*|\d+\.\d*(?:[eE][-+]?\d+)?[fF]?|\d*\.\d+(?:[eE][-+]?\d+)?[fF]?|\d+[uUlL]*)(?![\w.])')
ALLOWED_NUMBERS = {'0', '1', '0u', '1u', '0.0f', '1.0f', '0.0', '1.0', '0.f', '1.f', '0ull', '1ull', '0ul', '1ul'}
DECLARATION = re.compile(r'^\s*(?:(?:static|inline|extern)\s+)*(?:constexpr\b|const\s+\w[\w:<>, *&]*\s+\w+\s*(?:\[[^\]]*\])?\s*=)'
                         r'|^\s*static_assert\b|^\s*enum\b|\balignas\s*\(|^\s*RT_(?:ORIGINAL|GLOBAL)\s*\('
                         r'|^\s*(?:uint8_t|char|unsigned char|std::byte|void\s*\*)\s*unknown_\w+\s*\[|^\s*#')
RULES = (
    ('call by address', re.compile(r'\brt::fn\s*<')),
    ('call by address', re.compile(r'reinterpret_cast\s*<[^>]*\(\s*\*\s*\)[^>]*>\s*\(\s*0[xX][0-9a-fA-F]+')),
    ('call by address', re.compile(r'\(\s*\w[\w\s*]*\(\s*\*\s*\)\s*\([^)]*\)\s*\)\s*0[xX][0-9a-fA-F]+')),
    ('offset access', re.compile(r'\b(?:get|put)\s*<[^>]+>\s*\([^;]*,\s*(?:0[xX][0-9a-fA-F]+|\d+)')),
    ('offset access', re.compile(r'\bptr_at\s*\([^;]*,\s*(?:0[xX][0-9a-fA-F]+|\d+)')),
    ('offset access', re.compile(r'\w\s*\[\s*0[xX][0-9a-fA-F]+\s*\]')),
    ('recording code', re.compile(r'\brec\.')),
    ('recording code', re.compile(r'\brt_capture_\w+')),
)
JSON_IN_STRING = re.compile(r'\\"(?:schema|stubs|argmem|argc|buffers|memory|writes)\\"')
INTRINSIC = re.compile(r'\b_mm(?:256|512)?_\w+')
PADDING = re.compile(r'^\s*(?:uint8_t|char|unsigned char|std::byte|void\s*\*)\s*unknown_\w+\s*\[[^\]]*\]\s*;')


def strip(text: str) -> tuple[str, str]:
    """(code without comments and strings, the string literals' contents), same line structure."""
    code, strings = [], []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            code.append(''.join(ch for ch in text[i:j] if ch == '\n'))
            i = j
        elif c in '"\'':
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == '\\' else 1
            strings.append(text[i + 1:j])
            code.append(c + c + ''.join(ch for ch in text[i:j] if ch == '\n'))
            i = j + 1
        else:
            code.append(c)
            i += 1
    return ''.join(code), '\n'.join(strings)


def problems(path: str, text: str) -> list[str]:
    rel = path
    in_engine = rel.replace(os.sep, '/').startswith('game/engine/')
    code, strings = strip(text)
    out = []
    if JSON_IN_STRING.search(strings) or JSON_IN_STRING.search(text):
        out.append(f'{rel}: recording code (capture JSON in a string)')
    in_declaration = False      # a named-constant declaration continues until its ';'
    for number, line in enumerate(code.splitlines(), 1):
        for what, rx in RULES:
            if rx.search(line) and not (what == 'offset access' and PADDING.search(line)):
                out.append(f'{rel}:{number}: {what}: {line.strip()[:100]}')
        if not in_engine and INTRINSIC.search(line):
            out.append(f'{rel}:{number}: SSE intrinsic outside game/engine/: {line.strip()[:100]}')
        starts = bool(DECLARATION.search(line))
        if starts or in_declaration:
            in_declaration = (in_declaration or starts) and ';' not in line and not line.lstrip().startswith('#')
            continue
        for m in NUMBER.finditer(line):
            if m.group(1).lower() not in ALLOWED_NUMBERS:
                out.append(f'{rel}:{number}: magic number {m.group(1)} (name it: constexpr, enum or a struct field): '
                           f'{line.strip()[:100]}')
                break
    return out


def read_allowlist(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith('#')]


def game_files(root: str) -> list[str]:
    out = []
    for dp, _, fns in os.walk(os.path.join(root, 'game')):
        for fn in fns:
            if fn.endswith(SOURCES):
                out.append(os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, '/'))
    return sorted(out)


def rules_fingerprint() -> str:
    """sha256 over everything that decides a verdict for a given file's text.

    The checker's own source and the allowlist (which gates whether a file's problems are
    reported and whether an entry is stale) are the only inputs. A rules change forces a
    full pass; a cache that cannot be invalidated must not exist."""
    h = hashlib.sha256()
    here = os.path.abspath(__file__)
    with open(here, 'rb') as f:
        h.update(f.read())
    h.update(b'\0' + ALLOWLIST.encode() + b'\0')
    with open(os.path.join(ROOT, ALLOWLIST), 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


class Cache:
    """path -> (sha256(text), problems) with a rules fingerprint header.

    Semantics are unchanged because problems() is a pure function of (path, text) and the
    only other inputs are the allowlist, which the fingerprint covers."""

    def __init__(self, root: str, enabled: bool = True):
        self.root, self.enabled = root, enabled
        self.path = os.path.join(root, CACHE)
        self.rules = rules_fingerprint()
        self.files: dict[str, list] = {}
        self.scanned = self.cached = 0
        self.why = ''
        if enabled:
            try:
                with open(self.path) as f:
                    blob = json.load(f)
            except (OSError, ValueError):
                self.why = 'no cache' if not os.path.exists(self.path) else 'unreadable cache'
                return
            if blob.get('rules') != self.rules:
                self.why = 'rules changed'
                return
            self.files = {k: v for k, v in blob.get('files', {}).items()
                          if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)}

    def problems(self, rel: str, text: str) -> list[str]:
        digest = hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()
        hit = self.files.get(rel)
        if hit is not None and hit[0] == digest:
            self.cached += 1
            return list(hit[1])
        self.scanned += 1
        found = problems(rel, text)
        self.files[rel] = [digest, found]
        return found

    def save(self) -> None:
        if not self.enabled:
            return
        blob = {'rules': self.rules, 'files': self.files}
        os.makedirs(self.root, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix='.readable-cache.')
        with os.fdopen(fd, 'w') as f:
            json.dump(blob, f, sort_keys=True)
        os.replace(tmp, self.path)

    def summary(self) -> str:
        head = self.why or 'valid'
        return f'scanned {self.scanned}, cached {self.cached} ({head})'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--base', help='git ref whose allowlist this one may not grow beyond')
    ap.add_argument('--base-list', help='a file with the allowlist this one may not grow beyond')
    ap.add_argument('--no-cache', action='store_true', help='ignore and do not write the cache')
    ap.add_argument('files', nargs='*')
    a = ap.parse_args()
    root = a.root
    with open(os.path.join(root, ALLOWLIST)) as f:
        allow = read_allowlist(f.read())
    errors = []
    if len(set(allow)) != len(allow):
        errors.append(f'{ALLOWLIST}: duplicate entries')
    base = None
    if a.base:
        r = subprocess.run(['git', '-C', root, 'show', f'{a.base}:{ALLOWLIST}'], capture_output=True, text=True)
        base = r.stdout if r.returncode == 0 else None
    elif a.base_list and os.path.isfile(a.base_list):
        with open(a.base_list) as f:
            base = f.read()
    if base is not None:
        grown = sorted(set(allow) - set(read_allowlist(base)))
        for g in grown:
            errors.append(f'{ALLOWLIST}: {g} was added; the list may only shrink (make the file readable instead)')
    cache = Cache(root, enabled=not a.no_cache)
    every = game_files(root)
    targets = [f.replace(os.sep, '/') for f in a.files] if a.files else every
    for rel in targets:
        if not rel.startswith('game/') or not rel.endswith(SOURCES):
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, errors='replace') as f:
            found = cache.problems(rel, f.read())
        if rel in allow:
            continue
        errors += found
    if not a.files:
        for rel in allow:
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                errors.append(f'{ALLOWLIST}: {rel} no longer exists; remove it from the list')
                continue
            with open(path, errors='replace') as f:
                if not cache.problems(rel, f.read()):
                    errors.append(f'{ALLOWLIST}: {rel} passes now; remove it from the list')
    cache.save()
    for e in errors:
        print(f'readable: {e}', file=sys.stderr)
    if errors:
        print(f'readable: {len(errors)} problem(s); see STYLE.md · {cache.summary()}', file=sys.stderr)
        return 1
    remaining = sum(1 for r in allow)
    print(f'readable: ok ({remaining} grandfathered file(s) left in {ALLOWLIST}) · {cache.summary()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
