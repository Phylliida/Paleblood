# Data this repository does not contain

The tree at this commit builds, tests, and gates without any of it. **It cannot reproduce one
differential.** Every row in the ledger whose evidence is a run against the retail image needs a tree
that lives outside the repository, deliberately: the images are copyrighted game data and the case
corpora are derived from them. A fresh clone therefore contains the instruments and none of the subjects,
and nothing about a green suite says otherwise — the suites that need this data are the ones that skip or
refuse without it.

Paths are relative to the repository root, i.e. `../data/` is a **sibling of the repository**, not a
subdirectory. Nothing here is in `.gitignore`; it is simply not in the repository at all.

## The trees

| path | what it is | who needs it |
|---|---|---|
| `../data/bb/elf/eboot.elf` | the retail executable, 93,667,640 B; its two `PT_LOAD` segments define every address this project quotes | `tools/harness.py`, `tools/load_segments`, the chain table, every differential, `tools/emit_leaf_family.py` |
| `../data/bb/elf/libc.elf`, `libSceFios2.elf` | the two bundled modules, for the TLS layout (`0x220/0x4a0`, `0x0/0x40`) and import origins | the runtime's TLS derivation; `tools/join_import_pc.py` |
| `../data/cases/` (`leaf/`, `zero_init/`, `static_guard/`, `canary/`, …) | the case corpora: one JSON per address, each with its fixture seeds and expected state | `tools/harness.py --cases`, `check_seeding.py`, and the ledger's `cases_sha256` column, which **cites bytes git does not track** |
| `../data/catalog.sqlite3` and `../data/exports/edges.csv` | Ghidra's exports: the static call graph and function extents | `tools/ghidra/`, the census tools. **A static graph: nothing in it is a PC that ran** |
| `../data/captures/` | runtime captures, for the rows whose evidence is a recording | `verify.py` on captured inputs |

## What refuses without each, measured at this commit

```
$ python3 tools/harness.py --elf /nonexistent/eboot.elf --case /nonexistent/c.json --address 0x400000
harness: /nonexistent/eboot.elf: cannot open                       rc=3

$ python3 tools/check_seeding.py --cases /nonexistent
seeding: refusing -- no case directory /nonexistent; 0 cases is not 0 refusals

$ python3 tools/progress.py --check --root /tmp/emptyroot
progress: refusing -- cannot read /tmp/emptyroot/symbols/ghidra_functions.csv; unread is not zero   rc=3
```

**Absence refuses; it does not pass.** That is the rule these three arms exist to uphold, and it is the
one property of this tree that a clone without the data can still check.

## What a clone CAN do

- build the runtime (`cmake --build build-release`) and run ctest over `runtime/`;
- run the whole Python suite that does not need the image;
- run every static gate: `check_catalogue.py`, `check_import_order.py`, `check_seeding.py` (it refuses on
  the seed *file*, not on the image), `check_pins.py`, `check_externs.py`, `check_retired.py`;
- read every number the ledger quotes, and re-derive every count from `symbols/`.

## What it cannot

- reproduce a differential, a byte-identical body, or a mutant kill;
- verify any `cases_sha256`, because the case files are outside the tree;
- re-emit a leaf family, because the emitter reads the image;
- confirm a single `verified` row. **The instruments are public; their subjects are not.**
