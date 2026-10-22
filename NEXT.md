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
