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

## Bind dump: what it did and did not establish

`docs/bind-order-eboot.txt` (848 rows) exists and shows the loader's **index** order --
`P330P3dFF68#q#q` (libc), `f7uOxY9mM1U#p#J` (libkernel), ... -- which is **not** the PLT ordinal
order. Three consequences, in order of what they invalidate:

1. **The dump has no slot field.** `resolve()` knows the import index and the host trampoline
   (`o->tramp + TRAMPOLINE_SIZE * index`), not the guest GOT slot; the slot comes from the
   relocation that writes it. So the dump cannot be joined to `0x57e4690/698/6a0/6a8` yet --
   the slot must be added at the relocation apply site, not in `resolve()`.
2. **Those NIDs carry `#q#q` / `#p#J` suffixes** where the witnessed ones are bare 11-char base64.
   Asked where that comes from, and it is the *guest's own format*, not damage:
   `runtime/loader.c:346` splits an import name at the first `#` (`const char *p = strchr(name, '#');`)
   and `boot.c:235` compares **`RT_NID_SIZE - 1` bytes and then requires `'#'` on both sides** --
   the marker is expected, and the syslib match deliberately ignores what follows it. So the
   value join works if the suffix is stripped to the first 11 characters, exactly as the runtime
   does. The 223-row incident's markers were the same format, not a new corruption.
3. **The 652 reconciles: 219 bundled + 30 implemented + 4 unresolved + 433 unbound = 686.** So the
   in-game workload is **433 unbound**, not 652 -- 219 are bundled and already available. This
   closes the reconciliation item and improves the figure by a third.

And the stale-binary finding voids more than the progression: the two "witnessed stops" came
through the same `boot.py`, so **per-library ordinals stay alive**. `BB_PBBOOT` is now a literal
in `resume-kit.md`.

## Direct-memory family: names confirmed locally, arena not built

`harness.nid()` run with two controls in the same call (`_init_env` -> `bzQExy189ZI`,
`atexit` -> `8G2LB+A3rzg`, both matching the witnessed thunks):

| name | NID | stop? |
|---|---|---|
| `sceKernelGetDirectMemorySize` | `pO96TwzOm5E` | implemented (31) |
| `sceKernelAllocateDirectMemory` | `rTXw65xmLIA` | **current stop**, `eboot+0x2081aa3` |
| `sceKernelReleaseDirectMemory` | `MBuItvba6z8` | predicted next in family |
| `sceKernelMapDirectMemory` | `L-Q3LEjIbgA` | predicted next in family |

**This is the first stop that cannot be a no-op.** `AllocateDirectMemory(searchStart, searchEnd,
len, alignment, memoryType, off_t *physicalAddr)` returns 0 on success **and writes
`*physicalAddr`**; a stub returning 0 without writing hands the guest garbage it immediately uses
-- the `ret`-transparency problem again, in a pointer. Honest shape is a **model**, not a stub: a
bump arena, `alignment` honoured (0 = default), addresses monotonic and non-overlapping,
`*physicalAddr` always written, with the residual stated -- **no physical/virtual distinction, no
fragmentation, no reclaim beyond Release**. A model is testable by a differential; a no-op is not.

**Build it for the family, not the first caller.** `ReleaseDirectMemory`, `MapDirectMemory` and
`MapFlexibleMemory` are the same allocator seen three ways; if Release is written as "return 0"
the arena and the release path can disagree and nothing catches it. One arena, four entries,
allocations recorded in a table the differential can read back.

Also noted: bind-dump index 0 `P330P3dFF68` is marked UNRESOLVED in the external table, so it has
no known name and must not be given a guessed implementation.

## `FxVZqBAA7ks`: not in any table we hold, which is not the same as unnamed

A libc -> libkernel import. The public NID tables are game-facing eboot imports, so libc-internal
ones are mostly absent; two searches returned nothing. Stop looking up, start reading.

**The call site is the oracle** (`libc.elf+0x27367`, ~60 bytes before it, from section-addressed
bytes -- `harness` has no `elf_sections` helper, so find the section containing the vaddr first):
`Allocate` takes six arguments and writes through the sixth; `Map` takes a physical address first
and returns a pointer; `Release` takes one address and no out-param. **How many arguments are set,
and whether one points at writable guest memory, distinguishes the family with no name at all.**
Then read what libc does with the return: dereference means Map, compare-to-zero means status.

**And `Map` must be identity over the arena** -- written into the arena file's header rather than
here, because a later reader of the code is the one who needs it: one address space, so an arena
address is already guest-dereferenceable, and inventing a separate virtual range would make every
range `Allocate` had already handed out unreadable, failing as memory corruption in whichever
consumer ran second.
