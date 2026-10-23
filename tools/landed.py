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


def landed_addresses(path="symbols/functions.csv"):
    """{address} for rows whose status is anything but `original`."""
    with open(path) as f:
        return {int(r["address"], 16) for r in csv.DictReader(f) if r["status"] != "original"}


def byte_totals(path="symbols/functions.csv"):
    """The same partition as `landed` vs `transcribed`, in BYTES.

    `landed` counts rows with status != 'original': evidence exists. `transcribed` counts every row
    that carries a body, which is every row in the file: transcription exists, evidence may not.
    Writing 78 bodies moves byte_totals['transcribed'] by 1,320 and byte_totals['landed'] by ZERO until
    the differentials record -- and one `live_bytes` would have to pick which it means, then be quoted
    as if it meant the other.
    """
    landed = transcribed = 0
    for r in csv.DictReader(open(path)):
        size = int(r['size'])
        transcribed += size
        if r.get('status', 'original') != 'original':
            landed += size
    return {'landed': landed, 'transcribed': transcribed}
