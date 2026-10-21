#!/usr/bin/env python3
"""Reachable instruction set of one entry, by recursive descent from its address.

Why this exists: an entry's `size` in symbols/ghidra_functions.csv is a *lower bound* on
its body (docs/ab-large-functions.md, amendment 7).  Declared ends truncate the instruction
at 742 branch targets, and static exits reach a median 17 B, up to +61 B, past the declared
end into bytes no entry owns.  So the body to translate is the descent set -- not the
declared extent -- and sizing work against the declared extent sizes it against a bound
already proved wrong.

Successors: fall-through always continues except after `ret`/`jmp`; a jmp/cc-jump adds its
static target; a call adds nothing (its target is a callee, not this body) but keeps the
fall-through.  Indirect transfers have no static edge and are counted, never assumed away.
Never invents an instruction: an address that does not decode is reported and stops.
"""
import argparse
import bisect
import collections
import os
import sys

import capstone

FILE_BIAS = 0x3fc000
_J = capstone.CS_GRP_JUMP
_C = capstone.CS_GRP_CALL
_R = capstone.CS_GRP_RET
_IMM = capstone.x86.X86_OP_IMM
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _md():
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    return md


def one(md, blob, addr):
    off = addr - FILE_BIAS
    if off < 0 or off >= len(blob):
        return None
    for i in md.disasm(blob[off:off + 15], addr):
        return i
    return None


def static_target(i):
    t = None
    for op in i.operands:
        if op.type == _IMM:
            t = op.imm
    return t


def descent(blob, entry, window, max_insns=200000):
    """Return dict with the reachable instruction set and the edges that leave `window`."""
    md = _md()
    lo, hi = window
    seen = {}
    leaders = set()
    pending = [entry]
    indirect = collections.Counter()
    calls = collections.Counter()
    undecodable = []
    out_of_window = collections.Counter()
    while pending:
        a = pending.pop()
        if a in seen or not (lo <= a < hi):
            if not (lo <= a < hi) and a not in seen:
                out_of_window[a] += 1
            continue
        leaders.add(a)
        cur = a
        while True:
            if cur in seen or not (lo <= cur < hi) or len(seen) >= max_insns:
                if not (lo <= cur < hi) and cur not in seen:
                    out_of_window[cur] += 1
                break
            i = one(md, blob, cur)
            if i is None:
                undecodable.append(cur)
                break
            seen[cur] = i
            nxt = cur + i.size
            if i.group(_R):
                break
            if i.group(_C):
                t = static_target(i)
                if t is None:
                    indirect['call'] += 1
                else:
                    calls[t] += 1
                cur = nxt          # a call returns: the body continues
                continue
            if i.group(_J):
                t = static_target(i)
                if t is None:
                    indirect['jump'] += 1
                else:
                    pending.append(t)
                if i.mnemonic == 'jmp':
                    break
                cur = nxt          # conditional: fall-through too
                continue
            cur = nxt
    return {'insns': seen, 'leaders': leaders, 'indirect': indirect, 'calls': calls,
            'undecodable': undecodable, 'out_of_window': out_of_window}


def block_leaders(seen, entry):
    """Basic-block leaders: entry, every static branch target, every instruction after a
    transfer.  Distinct from descent()'s worklist, which never re-pushes a fall-through."""
    leads = {entry}
    for a, i in seen.items():
        nxt = a + i.size
        if i.group(_J):
            t = static_target(i)
            if t is not None and t in seen:
                leads.add(t)
        if (i.group(_J) or i.group(_C) or i.group(_R)) and nxt in seen:
            leads.add(nxt)
    return leads


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--elf', default=os.environ.get('BB_ELF'))
    ap.add_argument('--address', required=True, action='append')
    ap.add_argument('--window', type=lambda s: int(s, 0), default=0x4000,
                    help='expand this many bytes either side of the declared extent')
    a = ap.parse_args(argv)
    if not a.elf:
        ap.error('--elf or $BB_ELF is required')
    blob = open(a.elf, 'rb').read()
    rows = []
    import csv
    with open(os.path.join(_ROOT, 'symbols', 'ghidra_functions.csv'), newline='') as f:
        for r in csv.DictReader(f):
            rows.append((int(r['address'], 16), int(r['size'])))
    rows.sort()
    starts = [x[0] for x in rows]
    by_start = dict(rows)

    def owner(t):
        k = bisect.bisect_right(starts, t) - 1
        if k >= 0 and starts[k] <= t < rows[k][0] + rows[k][1]:
            return f'{rows[k][0]:#010x}'
        return 'unowned'

    rc = 0
    for spec in a.address:
        entry = int(spec, 16)
        size = by_start.get(entry)
        if size is None:
            print(f'{entry:#010x}: not in the partition', file=sys.stderr)
            rc = 2
            continue
        end = entry + size
        d = descent(blob, entry, (entry - a.window, end + a.window))
        seen = d['insns']
        reach = sorted(seen)
        inside = [x for x in reach if entry <= x < end]
        outside = [x for x in reach if not (entry <= x < end)]
        span = (reach[0], max(x + seen[x].size for x in reach))
        owners = collections.Counter(owner(x) for x in outside)
        print(f'\n{entry:#010x} declared {size} B  [{entry:#x}, {end:#x})')
        blocks = block_leaders(seen, entry)
        print(f'  descent: {len(reach)} instructions, {len(blocks)} basic blocks, '
              f'{sum(i.size for i in seen.values())} B of instructions, '
              f'span [{span[0]:#x}, {span[1]:#x}) = {span[1] - entry} B from entry')
        print(f'  inside the declared extent: {len(inside)} instructions; '
              f'outside: {len(outside)} instructions, owned by {dict(owners)}')
        if outside:
            print(f'  out-of-extent instructions: {outside[0]:#x} .. {outside[-1]:#x}')
        print(f'  indirect transfers: {dict(d["indirect"]) or "none"}')
        print(f'  calls: {len(d["calls"])} distinct targets; '
              f'undecodable addresses reached: {[hex(x) for x in d["undecodable"]] or "none"}')
        if d['out_of_window']:
            print(f'  left the window: {[hex(x) for x in d["out_of_window"]]}')
        if d['undecodable']:
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
