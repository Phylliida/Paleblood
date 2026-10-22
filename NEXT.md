# Next session: execute in this order

1. **Print the loader's bind table.** In `boot.c`'s bind loop (`:273`), print
   `(slot, nid, library)` for all 686 bindings, before the guest executes. One run. This is
   *verified necessary*: a control run against `symbols/imports.csv` found **neither** witnessed
   NID in the file at all, so row order cannot be PLT order and no local artifact holds the map.
   **Also reconcile 822 vs 686 here** — `imports.csv` has 822 `eboot` rows, name-keyed and grouped
   alphabetically by library; the loader reports 686 total / 30 implemented / 4 unresolved / 652
   unbound. Two counts of "the import set" that cannot both be the guest's set. Until reconciled,
   **stop quoting 652 as "imports between the boot and game code"**; the loader's 686 is the only
   figure that means anything.
2. **Join by GOT slot, never by index.** Prologue thunks: ordinal 0 `0x2fbe4b8` -> slot
   `0x57e4690` (`_init_env`, `bzQExy189ZI`, witnessed at `eboot+0xb9`); ordinal 1 `0x2fbe4c8` ->
   `0x57e4698` (`atexit`, `8G2LB+A3rzg`, witnessed at `eboot+0xc1`); ordinal 2 `0x2fbe4d8` ->
   `0x57e46a0`; ordinal 3 `0x2fbe4e8` -> `0x57e46a8`. Slot arithmetic: `thunk + 6 + disp`.
   Loader iteration order equalling PLT order has never been shown.
3. **Intersect ordinals 2-3's NIDs against the 490 computable libc names.** Hits become documented
   no-ops; misses are sent to the companion as two NID strings.
4. **Batch `atexit` plus hits — `kind` per NID, never one flag for the batch.** An unnamed import
   may not receive a no-op: that claims its return value *and* every side effect are unnecessary.
5. **Add `kind in {noop, implementation}` to the status writer**; print the split on every
   burndown. Today `imports_implemented` reads 31 when the truth is **30 implementations + 1
   declared no-op**.
6. **Expect the wall after the batch at `0x400020`** — an in-eboot startup body with its own
   callees, not an import. That is the next phase, not a regression.

Not to be re-derived: `0x400020` and `0x224a6c0` are bodies, not thunks (prologue has **four**
import thunks, corrected down from six by looking). `_init_env` landed at `f191991`.

Board: 21,128 / 157,757 = 13.39% edge-verified incl. verified; 21 verified; 30 approvals against
21,086 clean rows; 0 of 528 `zero_init`. **`verified` has not moved in thirty slices.**

## Debt 0 (highest value, cheapest): make boot.py unable to clobber a table

`boot.py` has overwritten tracked tables with raw NIDs **twice** -- the 223-row `5f50aac` and
again today (`symbols/imports.csv`, `symbols/module_functions.csv`, both restored from HEAD).
Both were caught by `git status` after the fact and **never by a gate**, so vigilance is not the
fix: `boot.py` must **refuse to write when a raw NID would land and `--nids` was not given**, or
write to a temp path and rename only on a clean table -- the staging discipline
`static_guard_gen.apply()` already uses, because a writer that cannot undo trusts itself.
Cost: one guard. It has already cost two recoveries.

## Carried debts (restored — `cat >` truncated the previous NEXT.md)

The earlier NEXT.md was overwritten by a heredoc. Its content is not in this file, and the commit
that replaced it did not preserve it; the five debts below are re-added from the handover:

1. **Table B's extent closure has never been run.** `rodata_pairs_02fc4a40.h`, 880 words; only
   table A (`0x02fc5120`) closed at 384. Pre-registered: 880 = 256 + 39x16, so 39 distinct class-2
   bases, max base 864, no remainder. If it does not close, the layout does not generalise and
   **both** pins are suspect.
2. **`test_blocks.py` / `test_descent.py` / `test_check_block_addresses.py` do not exist** while
   three tools emit tier-level verdicts. `check_block_addresses.py` has five recorded failing
   fixtures but no registered test; registration without its failing case is the `check_agnostic`
   defect again.
3. **`record()` is O(N)** over 21,229 ledger rows — same species as the 507 s resolver and the
   1.07 billion searches: invisible at the current population, catastrophic at the target.
4. **One resolver, two callers** — `validate_functions.py`'s `_install_mode_hosts()` beside
   `verification.replacement_symbol()`: two answers to one question until one is deleted, or the
   agreement is a comment.
5. **Bundle owed at HEAD**, proved by **bare clone plus a commit count**, never by a size line.
   The bundle at `f9ad70c` is stale.
