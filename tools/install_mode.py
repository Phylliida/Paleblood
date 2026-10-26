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
