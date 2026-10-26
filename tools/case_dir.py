"""ONE definition of where a family's cases live, for every tool that reads or writes one.

Two tools disagreed about this by having two hardcoded strings: the emitter wrote
`data/cases/leaf/leaf_chain_deref_*` and `check_seeding` looked in `data/cases/chain`, so the gate
refused with "0 cases is not 0 refusals" while the case it was refusing existed one directory over.
A refusal that is really a path disagreement is the worst kind: it reads as a finding about the data.

Chain cases live in their own directory because 78 chain cases sharing `leaf/` with twelve thousand
legacy case directories makes every `cases_sha256` lookup ambiguous and a per-family diff impossible.
The family -> subdirectory table is a MIGRATION, not a design: every legacy family still resolves to
`leaf/`, and moving them would rewrite the ledger's existing `cases_sha256` paths for families already
recorded. When a family is migrated, it moves here, once, for both tools.

THE ROOT IS NOT A STRING. `case_dir()` returns a `CaseRoot`, which has no `__fspath__` and no
`__str__`, so `os.path.join(case_dir(f), ...)` raises TypeError. Readers ask it for a case by address
and get the one file the declared layouts name; a second directory layout for the same address is an
error, not a first match. Writers ask it for the directory of a declared layout; they cannot spell a
third root or a third filename.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_ROOT = os.path.join(ROOT, '..', 'data', 'cases')

# family -> subdirectory. A family absent from here resolves to leaf/ only if it is named below;
# otherwise case_dir() raises. A default is a decision nobody wrote down: the old `.get(family,
# 'leaf')` made every future family a leaf family silently, including a chain-shaped one.
CHAIN = {'chain_deref': 'chain'}
LEAF_FAMILIES = frozenset({
    'bytes', 'lea_disp_rdi', 'lea_rdi', 'lea_rip', 'mov_al_imm', 'mov_al_mem',
    'mov_eax_k', 'mov_eax_mem', 'mov_rax', 'movsx_deref', 'rax_rdi', 'ret',
    'ret_zero', 'rip_add_store', 'rip_load', 'rip_load_wide', 'rip_store', 'st_byte_imm',
    'st_dword_esi', 'st_imm32', 'st_qword_rsi', 'st_sil8', 'vmovss_load',
    'vmovss_store',
})

# (layout name, directory template, the file a reader opens by address)
LAYOUTS = (
    ('chain', '%08x', 'case.json'),
    ('table', '0x%08x', 'a.json'),
)


class CaseRoot:
    """A case root that cannot be turned into a path by string concatenation."""

    def __init__(self, path):
        self._path = path

    def _p(self, *parts):
        for p in parts:
            if not p or os.path.isabs(p):
                raise ValueError(f'case root path component is absolute or empty: {p!r}')
            if '..' in p.replace('\\', '/').split('/'):
                raise ValueError(f'case root path component climbs: {p!r}')
        return os.path.join(self._path, *parts)

    def find(self, address):
        """The case file for `address`, or None. More than one declared layout is an error."""
        found = [self.row_file(address, name) for name, _, _ in LAYOUTS
                 if os.path.isfile(self.row_file(address, name))]
        if len(found) > 1:
            raise SystemExit(f'case_dir: {address:#x} exists in {len(found)} declared layouts: '
                             f'{", ".join(found)} -- one row, one case; refusing the ambiguity')
        return found[0] if found else None

    def row_dir(self, address, layout):
        """The directory a writer uses for one address in a declared layout."""
        for name, dirfmt, _ in LAYOUTS:
            if name == layout:
                return self._p(dirfmt % address)
        raise ValueError(f'case_dir: unknown layout {layout!r}; declared: '
                         f'{", ".join(name for name, _, _ in LAYOUTS)}')

    def row_file(self, address, layout):
        """The exact file a reader opens for one address in a declared layout."""
        for name, dirfmt, fname in LAYOUTS:
            if name == layout:
                return self._p(dirfmt % address, fname)
        raise ValueError(f'case_dir: unknown layout {layout!r}; declared: '
                         f'{", ".join(name for name, _, _ in LAYOUTS)}')

    def key_dir(self, key):
        """A legacy matcher family's per-key directory (not an address-keyed layout)."""
        return self._p(key)

    def bare(self, name):
        """A legacy matcher family's file directly under the root (not address-keyed)."""
        return self._p(name)

    def ensure(self):
        os.makedirs(self._path, exist_ok=True)

    def is_dir(self):
        return os.path.isdir(self._path)

    def __repr__(self):
        return f'CaseRoot({self._path!r})'


def case_dir(family):
    """The CaseRoot a family's cases live under. Unknown families refuse; no silent leaf default."""
    if family in CHAIN:
        sub = CHAIN[family]
    elif family in LEAF_FAMILIES:
        sub = 'leaf'
    else:
        raise SystemExit(f'case_dir: {family!r} has no declared case layout; add it to CHAIN or '
                         'LEAF_FAMILIES in tools/case_dir.py -- a default here is a decision nobody wrote')
    return CaseRoot(os.path.join(CASES_ROOT, sub))
