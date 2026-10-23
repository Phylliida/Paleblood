"""A sibling import must follow the path insert that makes `tools/` importable.

`python3 -P tools/x.py` does not put `tools/` on sys.path, so `from sibling import y` placed above the
`sys.path.insert(...)` line starts only when the *environment* supplies the path -- which is exactly how
`PYTHONPATH=tools` masked four loaders that could not start, and how this rule's own commit shipped an
emitter that died `ModuleNotFoundError` while its nine tests passed.

A rule about ordering loses to a shape; so this is an AST check. For each tools/*.py: let P be the
first `sys.path.insert(...)` line. Every top-level import naming a module that resolves to a file in
tools/ must sit below P. A sibling import with no path insert at all is the same refusal -- it only
works because something else put the path there.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def scan(root=None):
    root = Path(root) if root else ROOT
    tools = root if root.name == 'tools' else root / 'tools'
    if not tools.is_dir():
        return ['REFUSED: no tools directory']          # a refusal, not a pass
    siblings = {p.stem for p in tools.glob('*.py')}
    problems = []
    for path in sorted(tools.glob('*.py')):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as exc:
            problems.append(f'REFUSED {path.name}: cannot parse ({exc.msg})')
            continue
        inserts = [n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == 'insert' and isinstance(n.func.value, ast.Attribute)
                   and n.func.value.attr == 'path' and isinstance(n.func.value.value, ast.Name)
                   and n.func.value.value.id == 'sys']
        first = min(inserts) if inserts else None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split('.')[0]]
            elif isinstance(node, ast.Import):
                names = [a.name.split('.')[0] for a in node.names]
            else:
                continue
            for name in names:
                if name not in siblings or name == path.stem:
                    continue
                if first is None:
                    problems.append(f'REFUSED {path.name}:{node.lineno}: imports sibling {name!r} '
                                    f'with no sys.path.insert -- needs environment help to start')
                elif node.lineno < first:
                    problems.append(f'REFUSED {path.name}:{node.lineno}: imports sibling {name!r} '
                                    f'above the sys.path.insert at :{first} -- bare start dies')
    return problems


def main(argv):
    root = None
    if '--root' in argv:
        root = argv[argv.index('--root') + 1]
    problems = scan(root)
    # Shrink-only baseline, the same law as catalogue_allowlist.txt: a NEW violation refuses and a
    # STALE line refuses, so the list cannot quietly become a permission slip. The 41 lines here are
    # imports that today work only because plain `python3 tools/x.py` puts the script's own directory
    # on sys.path -- which `-P`, and any hook that runs the tool under an empty environment, does not.
    tdir = Path(root) if root else ROOT
    tdir = tdir if tdir.name == 'tools' else tdir / 'tools'
    base = tdir / 'import_order_allowlist.txt'
    allowed = {l.strip() for l in base.read_text().splitlines() if l.strip()} if base.exists() else set()
    keys = {}
    for p in problems:
        _, rest = p.split(' ', 1)
        where = rest.split(':', 2)
        keys[f'{where[0]}:{where[1]}'] = p
    new = sorted(k for k in keys if k not in allowed)
    stale = sorted(allowed - set(keys))
    for k in new:
        print(keys[k])
    for k in stale:
        print(f'REFUSED {k}: allowlisted but no longer violates -- prune the baseline')
    if new or stale:
        return 1
    if keys:
        print(f'import order: ok ({len(keys)} grandfathered site(s), may only shrink)')
    else:
        print('import order: ok (every sibling import follows the path insert)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
