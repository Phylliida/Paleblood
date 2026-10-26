"""Typed catalogue rows -- the size STRING never leaves this module.

The radix bug appeared four times (family_scan, join_import_pc, thunk_census, progress) because four
call sites each did `int(r["size"], 16)` against a decimal column. A `parse_size()` helper would still
require every site to REMEMBER to call it, and the four failures were four failures to remember. So this
module yields rows whose `address` and `size` are already ints: after `read_rows` there is no radix left
to get wrong, and the gate (check_catalogue.py) only has to catch `csv.DictReader` outside this file --
one shape rather than three spellings of ["size"].

`parse_size` refuses a hex-looking size instead of guessing, because the whole class is one file header
saying `address,size` / `0x00400020,102`.
"""
import csv
import gzip
import os


def parse_size(text):
    """Decimal, and refuses rather than guessing: a hex-prefixed size is a caller reading the wrong column."""
    t = text.strip()
    digits = t[1:] if t[:1] in "+-" else t
    if not digits.isdigit():
        raise ValueError(f"size {text!r} is not decimal (addresses are hex, sizes are decimal)")
    return int(t)


def parse_address(text):
    """Hex, with or without 0x."""
    try:
        return int(text.strip(), 16)
    except ValueError:
        raise ValueError(f"address {text!r} is not hex") from None


def read_rows(path):
    """Yield dicts with int `address`/`size` (and every other column untouched).

    `.gz` is opened transparently: branch_band.csv.gz is a table like any other, and the alternative
    was a second reader outside this module -- which the catalogue gate refused, correctly, twice.
    """
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as f:
        for r in csv.DictReader(f):
            row = dict(r)
            row["address"] = parse_address(r["address"])
            if "size" in r:
                row["size"] = parse_size(r["size"])
            yield row


def load_extents(path):
    """[(address, size)] -- what the ownership join wants."""
    return [(r["address"], r["size"]) for r in read_rows(path)]


def require_absent(path, addresses):
    """Refuse if any address is already in `path`. The one presence test for an address-keyed table.

    `read_rows` types the address, so a caller that passes ints cannot acquire a radix here. The
    message names the table and the first collision; the emitter prefixes its own family and keeps
    the sentence.
    """
    wanted = {int(a, 16) if isinstance(a, str) else int(a) for a in addresses}
    present = wanted & {r['address'] for r in read_rows(path)}
    if present:
        first = min(present)
        raise SystemExit(f'{os.path.basename(str(path))}: {len(present)} address(es) already present '
                         f'(first 0x{first:08x})')
