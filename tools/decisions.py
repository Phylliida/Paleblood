"""Section ids in docs/decisions.md are load-bearing.

`symbols/derived.json`'s `authorised()` matches `startswith('### 1j.')`, so a duplicate id is an
ambiguity (a yes arriving under one of five `1j` headings is indistinguishable from no) and a citation to
an id with no heading is an invented symbol -- the same defect class as `harness.Memory` and `--limit`.

`KNOWN_DUPLICATES` is the historical population measured at the commit that introduced this check, and it
may only SHRINK: an id that has collapsed to one heading leaves the dict, and a new duplicate refuses.
"""

import os
import re

HEAD = re.compile(r'^###[ \t]*(1[a-z0-9]*(?:-[a-z0-9]+)?)\b', re.M)
CITE = re.compile(r'decisions[ \t]+(1[a-z0-9]*(?:-[a-z0-9]+)?)\b', re.I)

KNOWN_DUPLICATES = {'1h': 3, '1j': 5, '1k': 4}


def audit_decisions(root='.'):
    """(rc, detail). rc=1 on a new duplicate id or on any citation that resolves to nothing."""
    path = os.path.join(root, 'docs', 'decisions.md')
    try:
        text = open(path, errors='replace').read()
    except OSError as exc:
        return 1, f'decisions: unread ({exc}) -- unread is not zero'
    ids = HEAD.findall(text)
    have = set(ids)
    problems = []
    for i in sorted(have):
        n = ids.count(i)
        frozen = KNOWN_DUPLICATES.get(i, 1)
        if n > frozen:
            problems.append(f'docs/decisions.md: ### {i} appears {n}x, frozen at {frozen}')
    for i in sorted(KNOWN_DUPLICATES):
        if i not in have:
            problems.append(f'KNOWN_DUPLICATES still lists {i}, which no longer exists -- delete the entry')
    cites = 0
    for rel in ('tools', 'docs', 'symbols'):
        for dirpath, _, files in os.walk(os.path.join(root, rel)):
            for f in files:
                if not f.endswith(('.py', '.md', '.csv')):
                    continue
                fp = os.path.join(dirpath, f)
                try:
                    t = open(fp, errors='replace').read()
                except OSError:
                    continue
                for m in CITE.finditer(t):
                    cites += 1
                    if m.group(1) not in have:
                        problems.append(f'{os.path.relpath(fp, root)}: cites decisions {m.group(1)}, '
                                        f'which has no heading')
    if problems:
        return 1, 'decisions: REFUSED -- ' + '; '.join(problems)
    return 0, (f'decisions: ok ({len(have)} id(s), {len(KNOWN_DUPLICATES)} frozen duplicate id(s), '
               f'{cites} citation(s) resolve)')
