# Exit codes: one word, one meaning, one owner

Written because a code with no line gets guessed: rc=127 was read as a verdict twice while it had no line,
and `2` meant *timeout* in `rc.sh` and *bad usage* in three wrappers at the same time. The rule:

**A code's meaning lives in its owner, and the owner is a file. This table records ownership and the
measured meanings; it is not a second copy to be edited independently.** Change the owner first, then this
row, in the same commit — and when a wrapper learns a new code, the new code is a new word: add its line.

## The runtime's own vocabulary (`runtime/boot.c`, the comment above the outcome switch)

| code | meaning | measured by |
|---|---|---|
| 0 | the guest returned / exited normally | `case EXITED: return …exit_code` path |
| 1 | the guest faulted (signal) | `case FAULT: return 1` |
| 2 | **timeout** — the guest did not finish within `--timeout` | `case TIMEOUT: return 2` |
| 3 | **precondition** — a file, flag or plugin the run needs is absent or unusable; also `pbboot` usage and unknown arguments; also a `--nids` path supplied but unreadable | `boot.c` setup paths, `rt_elf_open` failure, `read_nid_db < 0` |
| 4 | **unimplemented import** — the guest reached a NID this runtime cannot serve | `case UNIMPLEMENTED: return 4` |

A guest that legitimately exits with status 3 is indistinguishable from a refused precondition *by code
alone*; the printed line distinguishes them, and that is a known cost of returning the guest's own status.

## Wrapper vocabulary (never produced by `pbboot`)

| code | meaning | owner |
|---|---|---|
| 3 | usage, missing input binary/plugin/ELF — the precondition word, not 2 | `tools/boot.sh`, `tools/test.sh`, `tools/draft.sh`, `tools/prepare_dump.sh`, `tools/test_hooks.sh`, `tools/rc.sh` (`run` with no argv or a refused argv) |
| 78 | **build failed; nothing ran.** Never mistakable for a guest outcome | `tools/boot.sh`, `tools/test.sh` |
| 124 | **cost exceeded** — a declared timeout was hit | `tools/restamp.py:76`; also GNU `timeout(1)`'s own convention |
| 126 / 127 | transport answers: not executable / not found. `tools/rc.sh` normalises both to **3**, because the instrument was absent, not the subject | `tools/rc.sh` |

`tools/rc.sh`'s `run` otherwise returns **the subject's own rc** (0–255) and prints `rc=N`; above 128 it says
which signal and keeps the code, because a signal is a fact about the subject.

## Tools that own their own vocabularies

Not restated here, deliberately — two copies of a table that are edited independently are one instrument
wearing two names:

- `tools/verify.py:22` — *Exit codes: 0 all cases match, 1 mismatch, 3 bad input.*
- `tools/check_retired.py` — 3 for a missing retirement/functions table; its verdict codes belong to its own main.
- `tools/capture_precheck.py`, `tools/promote.py`, `tools/join_import_pc.py` — each documents its own returns at
  its option parser; grep `SystemExit`/`return` there before quoting.

## Measured, at the commit that added this file

- `grep -rn "exit 2" tools/*.sh runtime/` → no matches; `runtime/boot.c` has exactly one `return 2`
  (`case TIMEOUT`). **2 means timeout and nothing else.**
- `pbboot` no args → rc=3 with `boot called=n/a`; `--nonsense` → rc=3; bad ELF → rc=3 with
  `boot called=n/a`; `--nids /nonexistent` → rc=3; `--nids /tmp` → rc=3; no `--nids` → unchanged boot.
