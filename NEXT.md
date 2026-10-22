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

## `idc/ps4libdoc` cloned: it is a name list, not a NID table

`git clone --depth 1` succeeded (rc=0). Its shape, measured with a control in the same call:

- `known_names.txt` -- 42,010 lines, a **bare names list** (`__absvdi2`, `sceKernelAllocateDirectMemory`),
  with only 284 NID-shaped lines in it. **Names, no NIDs beside them.**
- `unknown_nids.txt` -- 1,130,742 lines of **11-char NIDs with no names** (`AAAS3TTinKA`, ...).

So the repo cannot answer "what is this NID": it holds the two halves *apart* -- which names exist,
and which NIDs are unanswered -- not the mapping. `pO96TwzOm5E` (a name I already have) does not
appear in `unknown_nids.txt`, which is what a known NID looks like there. `FxVZqBAA7ks` appears
**nowhere in the repo at all**: neither among the 1.13M unknown NIDs nor in the names list, so it is
not "unknown to ps4libdoc" either -- it is simply not in the table's population.

**Therefore the clone does not convert decodes into lookups**, and the remaining 430 still need the
call-site oracle. Keep the clone for the complementary question it can answer -- "does this name
exist?" -- which is a cheap way to reject a guessed name before writing code.

## `FxVZqBAA7ks` decoded at libc's call site: three arguments, and not obviously the arena family

`0x27367` is the **return** address ("returning to libc.elf+0x27367"), so the call ends there. Bytes
`e8 39 90 fd ff` at `0x27362`, and the 32 bytes before it decode as

```
56 53 50            push rsi; push rbx; push rax
49 89 d6            mov  r14, rdx
49 89 f7            mov  r15, rsi
89 fb               mov  ebx, edi
8d 43 ff            lea  eax, [rbx - 1]
83 f8 01            cmp  eax, 1
77 0f               ja   0x27368          <- skips the call entirely
89 df               mov  edi, ebx
4c 89 fe            mov  rsi, r15
4c 89 f2            mov  rdx, r14
e8 39 90 fd ff      call (import)
```

So: **three arguments, all passed through unchanged, and the call is skipped unless arg1 is 1 or
2**; the result is returned as-is. That is a *status* call gated on an enum-like first argument, not
`Allocate` (six args, writable sixth), not `Map` (address first, pointer dereferenced), and not
`Release` (one address, no out-param) -- **so it is not the direct-memory family**, and the earlier
guess that the family follows in sequence is unsupported by this call site.

Recorded in `symbols/unresolved_imports.csv` with the evidence, **name left empty**: a 3-arg status
call gated on `arg1 in {1,2}` does not single out one name, and a plausible one would be
indistinguishable from a measured one. Next: eboot's own caller of `bind 47`, which has catalogued
boundaries -- two witnesses, and disagreement is a finding.

## `FxVZqBAA7ks` = `_write`, closed by two independent witnesses

The ps4libdoc clone paid after all, in the direction it can answer: hashing all **42,010** names in
`known_names.txt` through `harness.nid()` finds exactly one hit, **`_write`**, with three controls
in the same call (`sceKernelGetDirectMemorySize`, `sceKernelAllocateDirectMemory`, `scePthreadYield`
-> `pO96TwzOm5E`, `rTXw65xmLIA`, `T72hz6ffq08`, 3/3). The sweep's null-result ambiguity is what the
controls exist for, and this one was decisive.

**And it agrees with the decode, which is the point of having done the decode first:** three
arguments, unchanged, gated on `arg1 in {1,2}` -- `_write(fd, buf, n)` writes to stdout/stderr --
result returned as-is, since a write returns a count or an error. Neither witness alone named it;
together the signature and the name settle each other, and the row in
`symbols/unresolved_imports.csv` now carries both.

The general lesson: **hash sweep for the name, decode for the signature, and require agreement.**
Every future stop gets the sweep first (it is one call over 42,010 names) and the decode only when
the sweep is silent or the two disagree.

## The 430 are almost entirely nameable: sweep of all bind NIDs against 42,010 names

One call, hashing 42,010 names into a dict and matching every NID in `docs/bind-order-eboot.txt`:
**746 of 747 resolve.** Landed as `symbols/import_names.csv` (`nid, library, bind_index, name,
state`), with state = implemented / named / unresolved from the runtime's own `RT_SYSLIB` list.
The remaining import workload is therefore **a list of known functions**, not 430 foreign decodes --
`printf`, `vsnprintf`, `realloc`, `longjmp`, `__stack_chk_fail`, `__tls_get_addr`, libc++ symbols.

Caveat to settle before trusting the counts: the dump yields **747 NIDs** while the boot reports
**686** for eboot, so it spans more than eboot's import table; the states must be re-derived per
object before any "N unbound" figure is quoted off this file.

`_write` next, with the three details that bite: return the count from a real host `write()` and
loop on partial writes; write raw bytes, never `%s`, because guest output is octets and a
NUL-truncated line is indistinguishable from a correct one; refuse fds other than 1 and 2, and tag
guest output distinctly so the boot log stays parseable once it carries the guest's own printing.
