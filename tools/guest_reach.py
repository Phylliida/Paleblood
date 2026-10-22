#!/usr/bin/env python3
"""Is any installed hook on a path the guest can walk from the entry point?

The recorder has been called "blocked on boot" for thirty slices on the assumption that nothing
replaced is reached before the `scePthreadCreate` wall. That assumption had never been tested.
This walks the resolved call graph from the ELF entry point and answers, in call edges:

  reached     hook address(es) are callees on a path from entry, with their call depth
  unreached   none are -- and then the honest number is not "N edges away" but the count of
              unresolved indirect call sites on the frontier, because those are the routes by
              which a hook can still be called without appearing as a resolved callee

Scope, because the number is worth less without it: the graph is `direct` edges only. Indirect
edges are counted and reported for the frontier, because they are exactly the routes this walk
cannot see -- so `reached` is proof a hook can be called, and `far` is not proof it cannot.
"""

# Two address-space facts this tool must not get wrong, because both fail as a clean negative:
#   * `e_entry` is an OFFSET from the image base (loader.c:133), and the loader enters at
#     image + e_entry (boot.c:632). Formatting e_entry alone walks from 0xa0, finds one node, and
#     reports `far` about a graph it never entered. That was this tool's first run.
#   * guest addresses, the edges file's caller/callee keys, and file offsets are three spaces:
#     host = IMAGE + guest - EBOOT_BASE, file = guest - 0x3fc000. A base carried into the wrong
#     space reads as "nothing here", never as an error.
import argparse
import collections
import csv
import os
import struct
import sys

RT_EBOOT_BASE = 0x400000


def entry_point(elf):
    with open(elf, 'rb') as f:
        head = f.read(0x40)
    if head[:4] != b'\x7fELF' or head[4] != 2:
        raise SystemExit(f'{elf}: not a 64-bit ELF')
    return struct.unpack_from('<Q', head, 0x18)[0]


def load_edges(path):
    """caller -> [callee] for direct edges, plus per-caller unresolved-indirect counts."""
    direct, indirect = collections.defaultdict(list), collections.Counter()
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if r['kind'] == 'direct' and r['callee']:
                direct[r['caller']].append(r['callee'])
            elif r['kind'] == 'unresolved_indirect':
                indirect[r['caller']] += 1
    return direct, indirect


def bfs(entry, direct, hooks, limit=64):
    """Depth of every reachable address, stopping a few edges past the farthest hook we care about."""
    depth = {entry: 0}
    q = collections.deque([entry])
    hits, deep = {}, []
    unresolved = 0
    while q:
        node = q.popleft()
        d = depth[node]
        unresolved += indirect_count.get(node, 0)
        if d >= limit:
            deep.append(node)
            continue
        for callee in direct.get(node, ()):
            if callee in depth:
                continue
            depth[callee] = d + 1
            if callee in hooks:
                hits[callee] = d + 1
            q.append(callee)
    return depth, hits, deep, unresolved


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--elf', default='../data/bb/elf/eboot.elf')
    ap.add_argument('--edges', default='../data/exports/edges.csv')
    ap.add_argument('--limit', type=int, default=64)
    a = ap.parse_args(argv)
    # e_entry is an offset from the image base, and the loader enters at image + e_entry
    # (loader.c:133 -> boot.c:632). Formatting it alone would walk from 0xa0, find nothing,
    # and report `far` about a graph it never entered -- which is what the first run did.
    entry = f'0x{RT_EBOOT_BASE + entry_point(a.elf):08x}' 
    hooks = {}
    with open(os.path.join(a.root, 'game', 'hooks.csv'), newline='') as f:
        for r in csv.DictReader(f):
            hooks[r['address']] = r
    names = {}
    with open(os.path.join(a.root, 'symbols', 'functions.csv'), newline='') as f:
        for r in csv.DictReader(f):
            names[r['address']] = r['name']
    global indirect_count
    direct, indirect = load_edges(a.edges)
    indirect_count = indirect
    depth, hits, deep, unresolved = bfs(entry, direct, hooks, a.limit)
    print(f'entry {entry}: {len(depth)} addresses reachable over direct edges '
          f'({len(direct)} callers carry any); hooks installed {len(hooks)}')
    print(f'frontier stopped at depth {a.limit}: {len(deep)} nodes, '
          f'unresolved indirect edges from visited nodes: {unresolved}')
    if hits:
        print(f'reached: {len(hits)} hook address(es) are callees on a path from entry')
        for addr, d in sorted(hits.items(), key=lambda kv: (kv[1], kv[0]))[:10]:
            print(f'  depth {d:2d}  {addr}  {names.get(addr, "?")}')
        return 0
    # No hook is itself called on a walked path. The distance to the nearest replaced address is
    # not an edge count then, because the missing edges are exactly the indirect ones; report what
    # can be measured and name what cannot.
    reachable_hooks = len(hooks) - len(hits)
    print(f'unreached: none of the {len(hooks)} hook addresses is a resolved callee on a path from '
          f'entry; {reachable_hooks} hooks remain unmeasured through '
          f'{unresolved} unresolved indirect call sites on the frontier')
    print(f'note: an address gap (bytes between entry and the nearest hook) is not a path length; '
          f'the paths that could reach a hook run through the indirect sites above')
    return 0


indirect_count = {}


if __name__ == '__main__':
    raise SystemExit(main())
