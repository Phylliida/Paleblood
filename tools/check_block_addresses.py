#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Static coverage for a translated large function: every block leader must be named.

A large function's body is emitted as one labelled block per basic block, each carrying its guest
address in a comment, so that the source itself records which addresses it covers.  This asserts
that the set of leaders the descent computes for a member is exactly the set of addresses the
source names -- so coverage can be claimed before any case exists, and without running anything.

It compares *addresses*, not sizes.  A body can carry every instruction and still omit a block, and
a label can be mistyped while still looking present; a size comparison sees neither.

  rc 0  every leader appears, once, in ascending order
  rc 1  a leader is missing, duplicated, or out of order
  rc 2  precondition: no such source, or the address is not in the partition

The leaders come from tools/descent.py, which walks from the entry and is allowed to leave the
declared extent -- declared sizes are lower bounds, so the declared extent is not the denominator.
"""

import argparse
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import descent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDRESS = re.compile(r'0x([0-9a-fA-F]{8})\b')


def partition():
    """address -> declared size, from the Ghidra partition (the census, not a re-derivation)."""
    out = {}
    path = os.path.join(ROOT, 'symbols', 'ghidra_functions.csv')
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            out[int(row['address'], 16)] = int(row['size'])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--elf', default=os.environ.get('BB_ELF'),
                    help='the executable (eboot.elf); default $BB_ELF')
    ap.add_argument('--address', required=True, help='the member, e.g. 0x00414040')
    ap.add_argument('--source', required=True, help='the translated body to check')
    ap.add_argument('--window', type=lambda s: int(s, 0), default=0x4000,
                    help='expand this many bytes either side of the declared extent')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if not a.elf:
        ap.error('--elf or $BB_ELF is required')

    entry = int(a.address, 16)
    size = partition().get(entry)
    if size is None:
        print(f'check_block_addresses: {entry:#010x} is not in symbols/ghidra_functions.csv',
              file=sys.stderr)
        return 2
    if not os.path.exists(a.source):
        print(f'check_block_addresses: no such source: {a.source}', file=sys.stderr)
        return 2

    blob = open(a.elf, 'rb').read()
    d = descent.descent(blob, entry, (entry - a.window, entry + size + a.window))
    leaders = sorted(descent.block_leaders(d['insns'], entry))

    text = open(a.source, encoding='utf-8').read()
    found = collections.Counter(int(h, 16) for h in ADDRESS.findall(text))

    missing = [l for l in leaders if not found[l]]
    doubled = [(l, found[l]) for l in leaders if found[l] > 1]
    order = []
    for l in leaders:
        m = re.search(rf'0x{l:08x}\b', text, re.IGNORECASE)
        if m:
            order.append((m.start(), l))
    out_of_order = [lb for (pa, _), (pb, lb) in zip(order, order[1:]) if pb <= pa]

    summary = {
        'address': f'{entry:#010x}',
        'declared_bytes': size,
        'instructions': len(d['insns']),
        'blocks': len(leaders),
        'named': len(order),
        'missing': [f'{l:#010x}' for l in missing],
        'duplicated': [{'address': f'{l:#010x}', 'count': n} for l, n in doubled],
        'out_of_order': [f'{l:#010x}' for l in out_of_order],
    }
    if a.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f'{entry:#010x}  declared {size} B  instructions {len(d["insns"])}  '
              f'blocks {len(leaders)}  named {len(order)}  missing {len(missing)}  '
              f'duplicated {len(doubled)}  out of order {len(out_of_order)}')
        for l in missing[:20]:
            print(f'  missing      {l:#010x}')
        if len(missing) > 20:
            print(f'  ... and {len(missing) - 20} more')
        for l in out_of_order[:20]:
            print(f'  out of order {l:#010x}')
        for l, n in doubled[:20]:
            print(f'  duplicated   {l:#010x} x{n}')
    return 1 if (missing or doubled or out_of_order) else 0


if __name__ == '__main__':
    sys.exit(main())
