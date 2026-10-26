#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""One read of `symbols/install_mode.csv`, and no second spelling of it.

A row with `mode` `host` says a replacement is verified as a host symbol rather than installed by a
`game/hooks.csv` entry. Two readers used to answer that question -- `validate_functions` built a
frozenset once, and `verification.replacement_symbol` scanned the file per lookup -- so the two
could disagree about what a non-`original` row means. This module is the only reader; the CSV path
is private to it.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atomicio  # noqa: E402  -- write beside, fsync, replace; never truncate first
import catalogue  # noqa: E402  -- typed reader: address/size are ints, one radix law

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (path, mtime_ns, size) -> tuple of rows. One entry: the table as it stands on disk. A cached
# answer keyed on a stale path is the defect; keying on mtime and size makes a rewrite visible.
_cache: dict = {}


def _path(root):
    return pathlib.Path(root or ROOT).resolve() / 'symbols' / 'install_mode.csv'


def rows(root=None):
    """Every row, read once per (path, mtime, size). An absent table is an empty tuple, not a failure."""
    path = _path(root)
    if not path.exists():
        return ()
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    got = tuple(catalogue.read_rows(path))
    _cache.clear()             # one entry: the table as it stands on disk
    _cache[key] = got
    return got


def host_addresses(root=None):
    """Addresses declared installed as host calls rather than by a game hook. Addresses are ints."""
    return frozenset(row['address'] for row in rows(root) if row.get('mode') == 'host')


def is_host(root, address):
    addr = address if isinstance(address, int) else catalogue.parse_address(address)
    return addr in host_addresses(root)


def replacement_for(root, name, address):
    """`bb_<name>` for a host-mode row, otherwise None. Hook rows are the caller's first lookup."""
    if is_host(root, address):
        return 'bb_' + name
    return None


def append_host(root, addresses):
    """Add host-mode rows, refusing any address already recorded as something else.

    Writers used to append this table with their own csv.DictWriter, so each one carried its own
    duplicate/clash policy. The table's shape is this module's private fact: callers hand over
    addresses, never a path and never a row.
    """
    addrs = sorted({int(a, 16) if isinstance(a, str) else int(a) for a in addresses})
    path = _path(root)
    have = {row['address']: row['mode'] for row in rows(root)}
    clash = [a for a in addrs if a in have and have[a] != 'host']
    if clash:
        raise SystemExit(f'refused: {path} already records 0x{clash[0]:08x} as '
                         f'{have[clash[0]]!r}, refusing to write it as host')
    add = [a for a in addrs if a not in have]
    if not add:
        return 0
    merged = dict(have)
    for a in add:
        merged[a] = 'host'
    text = 'address,mode\n' + ''.join(f'0x{a:08x},{merged[a]}\n' for a in sorted(merged))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomicio.atomic_write(path, text)
    _cache.clear()
    back = {row['address'] for row in rows(root)}
    missing = [a for a in add if a not in back]
    if missing:
        raise SystemExit(f'wrote {path}, re-read, and {len(missing)} rows are absent')
    return len(add)
