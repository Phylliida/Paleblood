#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""One reader for `symbols/install_mode.csv`: no other tool may compose its path.

A grep for the filename counts mentions. It sees `TABLES = (..., 'install_mode.csv', ...)` and a
message quoting the name, and it cannot see that a loop over `TABLES` builds
`os.path.join(root, 'symbols', name)` and opens it. That is the shape that made
`record_bytes_family` a second writer of the mode table while the literal appeared nowhere near the
`open`. The path is private to `install_mode.py`; every other tool asks `install_mode.rows()`.

The check is an AST dataflow, deliberately small: a name is tainted when it is assigned from a
container holding the target, a loop over a tainted container taints its targets, and a join or
pathlib division tainted by one of those names taints its result. A read call whose argument is
tainted is a finding. A call that merely mentions the name is not.
"""
import ast
import os
import sys

TARGET = 'install_mode.csv'
PATH_CALLS = {'open', 'read_rows', 'DictReader', 'DictWriter', 'write_table', 'atomic_write',
              'write_text', 'write_bytes'}


def _names(node):
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        out = set()
        for elt in node.elts:
            out |= _names(elt)
        return out
    return set()


def _holds_target(node):
    return any(isinstance(n, ast.Constant) and n.value == TARGET for n in ast.walk(node))


def _tainted(node, tainted):
    if _holds_target(node):
        return True
    return any(isinstance(n, ast.Name) and n.id in tainted for n in ast.walk(node))


def _function_name(parents, node):
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return '<module>'


def scan_text(source, filename='<text>'):
    tree = ast.parse(source, filename=filename)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    tainted = set()
    for _ in range(16):
        grown = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _tainted(node.value, tainted):
                for tgt in node.targets:
                    grown |= _names(tgt)
            elif isinstance(node, ast.AnnAssign) and node.value is not None and _tainted(node.value, tainted):
                grown |= _names(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor)) and _tainted(node.iter, tainted):
                grown |= _names(node.target)
        new = grown - tainted
        if not new:
            break
        tainted |= new
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else '')
        if name not in PATH_CALLS:
            continue
        # `csv.DictReader(open(path))` is one read; the inner `open` is the call that holds the path.
        if name in ('DictReader', 'DictWriter') and any(
                isinstance(arg, ast.Call) and
                (arg.func.id if isinstance(arg.func, ast.Name) else
                 arg.func.attr if isinstance(arg.func, ast.Attribute) else '') in PATH_CALLS
                for arg in node.args):
            continue
        subject = [node.func.value] if isinstance(node.func, ast.Attribute) else []
        if any(_tainted(arg, tainted) for arg in subject + list(node.args)):
            out.append((node.lineno, _function_name(parents, node), name))
    return out


def scan_file(path):
    with open(path) as f:
        return scan_text(f.read(), path)


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = 0
    for name in sorted(os.listdir(os.path.join(root, 'tools'))):
        if not name.endswith('.py') or name == 'install_mode.py':
            continue
        for line, func, call in scan_file(os.path.join(root, 'tools', name)):
            print(f'{name}:{line}: {func}() {call}() reads {TARGET} through a composed path -- '
                  f'ask install_mode.rows() instead', file=sys.stderr)
            bad += 1
    if bad:
        print(f'table paths: {bad} finding(s)', file=sys.stderr)
        return 1
    print('table paths: ok (install_mode.csv has one reader)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
