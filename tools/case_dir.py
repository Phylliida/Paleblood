"""ONE definition of where a family's cases live, for every tool that reads or writes one.

Two tools disagreed about this by having two hardcoded strings: the emitter wrote
`data/cases/leaf/leaf_chain_deref_*` and `check_seeding` looked in `data/cases/chain`, so the gate
refused with "0 cases is not 0 refusals" while the case it was refusing existed one directory over.
A refusal that is really a path disagreement is the worst kind: it reads as a finding about the data.

Chain cases live in their own directory because 78 chain cases sharing `leaf/` with twelve thousand
legacy case directories makes every `cases_sha256` lookup ambiguous and a per-family diff impossible.
`DIRECTORY` is a MIGRATION, not a design: every legacy family still resolves to `leaf/`, and moving
them would rewrite the ledger's existing `cases_sha256` paths for families already recorded. When a
family is migrated, it moves here, once, for both tools.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_ROOT = os.path.join(ROOT, '..', 'data', 'cases')

DIRECTORY = {'chain_deref': 'chain'}


def case_dir(family):
    """The directory a family's cases live under. One function, both tools, no second string."""
    return os.path.join(CASES_ROOT, DIRECTORY.get(family, 'leaf'))
