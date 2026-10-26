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

import csv
import io
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


def _header(path):
    with open(path, newline='') as f:
        return next(csv.reader(f), ['address', 'mode'])


def _fields(root):
    got = list(rows(root))
    path = _path(root)
    if got:
        return list(got[0].keys()), got
    if path.exists():
        return _header(path), got
    return ['address', 'mode'], got


def _write_rows(path, fields, got):
    """Every address-keyed write goes through here: canonical address spelling, sort, atomic replace.

    Extra columns are preserved. The old body emitted only `address,mode`, so a third column in
    the committed table was silently dropped by every append.
    """
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    for row in sorted(got, key=lambda r: int(r['address'])):
        out = dict(row)
        out['address'] = f'0x{int(out["address"]):08x}'
        w.writerow(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomicio.atomic_write(path, buf.getvalue())
    _cache.clear()


def append_host(root, addresses):
    """Add host-mode rows, refusing any address already recorded as something else.

    Writers used to append this table with their own csv.DictWriter, so each one carried its own
    duplicate/clash policy. The table's shape is this module's private fact: callers hand over
    addresses, never a path and never a row.
    """
    addrs = sorted({int(a, 16) if isinstance(a, str) else int(a) for a in addresses})
    path = _path(root)
    fields, base = _fields(root)
    if 'address' not in fields or 'mode' not in fields:
        raise SystemExit(f'refused: {path} has no address/mode columns: {fields!r}')
    have = {row['address']: row for row in base}
    clash = [a for a in addrs if a in have and have[a].get('mode') != 'host']
    if clash:
        raise SystemExit(f'refused: {path} already records 0x{clash[0]:08x} as '
                         f'{have[clash[0]].get("mode")!r}, refusing to write it as host')
    add = [a for a in addrs if a not in have]
    if not add:
        return 0
    for a in add:
        have[a] = {k: '' for k in fields}
        have[a]['address'], have[a]['mode'] = a, 'host'
    _write_rows(path, fields, list(have.values()))
    back = {row['address'] for row in rows(root)}
    missing = [a for a in add if a not in back]
    if missing:
        raise SystemExit(f'wrote {path}, re-read, and {len(missing)} rows are absent')
    return len(add)


def sort_host(root):
    """Sort an existing table without changing any row. Returns how many rows it held."""
    path = _path(root)
    if not path.exists():
        return 0
    fields, base = _fields(root)
    if not base:
        return 0
    _write_rows(path, fields, base)
    return len(base)
