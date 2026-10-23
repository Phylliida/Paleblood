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
