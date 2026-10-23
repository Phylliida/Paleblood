"""Which rows have a BODY, in one place and with no dependencies beyond csv.

A row at status `original` is bookkeeping for a body nobody has written, so it is not landed. This
selector was duplicated: leaf_family_census.py had it (and drifted from an emitter by exactly one row
once), progress.py did not have it and counted every address in functions.csv, and the two disagreed by
one row -- 0x0111a600, 8 bytes, status `original`, the extent this campaign spent two stretches
overturning. One function, imported by both.

It lives here rather than in leaf_family_census.py because that module imports capstone, and progress.py
runs inside the pre-commit hook, whose interpreter does not have capstone. A dependency added to a tool a
hook runs is a new requirement on the hook's environment: the first attempt at this fix made every commit
fail with ModuleNotFoundError.
"""
import csv
import os
import re


def _body_index(root=None):
    """Every `bb_<name>` symbol the tree actually defines. One walk, cached by the caller.

    `transcribed` must mean "a body exists", and the ledger's `size` column is bookkeeping: 0x024264d0
    sat at 'original' with 34 B after its body was withdrawn with rip_load_family.cpp at f511666, and
    0x004632d0 sat at 'original' with 67 B and no body at all. Deriving from the tree makes the number
    right by construction instead of by everyone remembering to delete a row.
    """
    base = root or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'game')
    names = set()
    for dirpath, _, files in os.walk(base):
        for f in files:
            if f.endswith(('.cpp', '.c', '.cc', '.h')):
                try:
                    text = open(os.path.join(dirpath, f), errors='replace').read()
                except OSError:
                    continue
                names.update(re.findall(r'\bbb_[A-Za-z0-9_]+', text))
    return names


def body_exists(row, index=None):
    return ('bb_' + row['name']) in (index if index is not None else _body_index())


KNOWN_WRONG = {
    0x00414040: ("large_bracket_canon_00414040: body uses v_rcx|v_r9 where the original consumes "
                 "eax/ebx, and 0x29 where it wrote 0x28. A differential cannot distinguish this body "
                 "from a trampoline, so recording it would make every number after it retroactively "
                 "meaningless. Ordering is a plan; this is a refusal."),
}


def _refuse_known_wrong(rows):
    """Raise if any known-wrong address carries a status that would make it landed.

    Excluding it from the set is not enough: the failure mode is a future promotion, and a promotion
    that silently loses a row is indistinguishable from one that never ran. So the set refuses AND the
    call raises -- `progress.py` runs in the commit hook, so this is the choke point that cannot be
    skipped by a forgotten roster entry.
    """
    for r in rows:
        a = int(r['address'], 16)
        if a in KNOWN_WRONG and r.get('status', 'original') != 'original':
            raise ValueError(f'land: {r["address"]} carries known_wrong and a landed status; refusing. '
                             f'{KNOWN_WRONG[a]}')


def landed_addresses(path="symbols/functions.csv"):
    """{address} for rows whose status is anything but `original`."""
    with open(path) as f:
        rows = list(csv.DictReader(f))
    _refuse_known_wrong(rows)
    return {int(r["address"], 16) for r in rows
            if r["status"] != "original" and int(r["address"], 16) not in KNOWN_WRONG}


def byte_totals(path="symbols/functions.csv"):
    """The same partition as `landed` vs `transcribed`, in BYTES.

    `landed` counts rows with status != 'original': evidence exists. `transcribed` counts every row
    that carries a body, which is every row in the file: transcription exists, evidence may not.
    Writing 78 bodies moves byte_totals['transcribed'] by 1,320 and byte_totals['landed'] by ZERO until
    the differentials record -- and one `live_bytes` would have to pick which it means, then be quoted
    as if it meant the other.
    """
    landed = transcribed = 0
    rows = list(csv.DictReader(open(path)))
    _refuse_known_wrong(rows)
    index = _body_index()
    for r in rows:
        a = int(r['address'], 16)
        size = int(r['size'])
        if not body_exists(r, index):
            continue   # no body exists: neither landed nor transcribed. `continue` here is the whole
                       # row's absence -- the first version of this patch wrote `continue` for
                       # KNOWN_WRONG too, which dropped 1,072 B of a body that DOES exist from
                       # transcribed: a skip that means "not landed" must not mean "not a body".
        transcribed += size                     # a body exists, known-wrong or not
        if r.get('status', 'original') != 'original' and a not in KNOWN_WRONG:
            landed += size
    return {'landed': landed, 'transcribed': transcribed}
