"""Which rows have a BODY, in one place and with no dependencies beyond csv.

A row at status `original` is bookkeeping for a body nobody has written, so it is not landed. This
selector was duplicated: leaf_family_census.py had it (and drifted from an emitter by exactly one row
once), progress.py did not have it and counted every address in functions.csv, and the two disagreed by
one row -- 8 bytes, status `original`, the extent this campaign spent two stretches
overturning. One function, imported by both.

It lives here rather than in leaf_family_census.py because that module imports capstone, and progress.py
runs inside the pre-commit hook, whose interpreter does not have capstone. A dependency added to a tool a
hook runs is a new requirement on the hook's environment: the first attempt at this fix made every commit
fail with ModuleNotFoundError.
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalogue   # the ONE typed reader: the commit hook refuses a second one, and the radix lives there


def _body_index(root=None):
    """Every `bb_<name>` symbol the tree actually defines. One walk, cached by the caller.

    `transcribed` must mean "a body exists", and the ledger's `size` column is bookkeeping: one row
    sat at 'original' with 34 B after its body was withdrawn with rip_load_family.cpp at f511666, and
    another sat at 'original' with 67 B and no body at all. Deriving from the tree makes the number
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


def _load_known_wrong(root=None):
    """The refusal table, as DATA: `symbols/known_wrong.csv`, columns `address,name,why`.

    It was a dict literal carrying a tracked address and a tracked function name -- both values the
    agnostic gate refuses in tools/, correctly -- and data is also the only shape in which the entry can
    be made to REFUSE in a test: a literal is reachable only by editing the file it guards. Absence of
    the file is not survivable and must not be: an import that quietly loaded an empty table would leave
    `_refuse_known_wrong` with nothing to refuse and every number looking fine.
    """
    base = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {r['address']: r['why']
            for r in catalogue.read_rows(os.path.join(base, 'symbols', 'known_wrong.csv'))}


KNOWN_WRONG = _load_known_wrong()


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
    that carries a BODY ON DISK -- which is 38,099 of the 38,101 rows, NOT every row in the file, as
    this docstring asserted until the measurement refuted it. Two rows carry no emitted body and are
    excluded from BOTH totals: the 67-byte and 34-byte rows (their identities are in docs/addressing.md,
    because tools/ may not carry a tracked address). That
    is why bytes_transcribed is 101 short of the file's size sum (325,262) -- and 67 + 34 = 101.

    Two predicates, one word: the band column `has_body` (symbols/branch_band.csv) means "an address in
    functions.csv" (38,101); `body_exists` here means "a body was emitted" (38,099). They differ by
    exactly those two rows, so quoting either as "the number of bodies" is wrong by two rows and 101 bytes.
    Writing 78 bodies moves byte_totals['transcribed'] by 1,320 and byte_totals['landed'] by ZERO until
    the differentials record -- and one `live_bytes` would have to pick which it means, then be quoted
    as if it meant the other.
    """
    landed = transcribed = 0
    rows = list(csv.DictReader(open(path)))
    _refuse_known_wrong(rows)
    # The walk belongs to the ROOT of the file being summed, not to this process's default: called bare, a
    # fixture's rows were checked against the repository's game/, so a fixture's byte totals were a function of
    # a directory it does not own. Same shape as image_base_set stored per process instead of per comparison.
    index = _body_index(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), 'game'))
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
