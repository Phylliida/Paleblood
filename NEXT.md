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

## The null fault: reading (a), and a counter that measures trampolines

**No guest bytes reached stderr.** The rerun's stderr, filtered for lines not starting with
`pbboot:` / `runtime:` / `boot:` / `DL_PANIC`, is empty -- so `_write` produced no output, the
crash is not the guest reporting a failure it already had, and **reading (a) is live**: the return
path is the shape to check. No `unimplemented:` line for `FxVZqBAA7ks` either, so the loader took a
route that neither served the call nor stopped on it.

That route is visible in the loader and it also explains the nine-row gap:

    runtime/boot.c:403   write_trampoline(o->tramp + i * TRAMPOLINE_SIZE, &o->called[i], ...);
    runtime/boot.c:75    unsigned char *called;   /* per import: called at least once */

**The trampoline marks `called` itself, before it jumps to whatever the provider is.** So
`imports called 28` counts *trampolines entered*, not calls served by an implementation -- a
counter that measures intent, the same family as an approvals column that counts rows. That is why
`_write` raised "called" while `implemented` stayed 33: the two numbers are not two views of one
event.

Before any more implementations, split that counter: **called** (trampoline entered) versus
**served** (provider was RUNTIME and returned), printed as two figures. Until then no import
progress claim should quote "imports called".

## The null dereference: data imports get zeroed scratch, so stdio's FILE objects are all zeros

`runtime/boot.c:289-293`:

    if (kind == RT_ELF_IMPORT_DATA)
        return o->bound[index] ? (uintptr_t)o->bound[index] : (uintptr_t)(o->data + 4096 * index);

Each data import gets its **own 4 KiB block of zeroed anonymous memory** (`o->data` is one mapping
of `(imports + 1) * 4096`, PROT_READ|PROT_WRITE). `_Stdout`, `_Stderr`, `_Stdin` are in the named
list (`symbols/import_names.csv` rows 10, 12, 19; libc / libSceLibcInternal). So the guest receives
a pointer to 4 KiB of **zeros** in place of a `FILE *`, and the first stdio call that touches a
field of that struct reads a **null internal pointer** and faults at address 0x0.

That fits every observation at once: no guest bytes reached stderr, the fault address is 0x0, the
trampoline for `_write` was entered, and `_write`'s own body has no reason to have run. **So the
fault is a data-symbol problem, not an implementation problem, and `_write` is innocent.**

Not a "fix the loader" job in the same breath: a data import needs a *real* object behind it, and
for stdio that means the runtime owning host `FILE` objects and pointing `_Stdout`/`_Stderr`/
`_Stdin` at them -- which is the `FILE*` interop the delegation split says must stay ours. Recorded
as the shape; not implemented.

Rule for the dump, next run: print `provider` at bind time
(`bind <idx> <nid> <lib> provider=<runtime|bundled|unresolved|data-scratch> called=<0|1>`), because
the provider is decided there and inferring it from two counters is what cost this turn.

## Whose FILE layout: the reader is eboot, the provider is libc.elf, and libc.elf is on disk

`symbols/imports.csv:413-415` -- all three are **data** imports **of eboot** with provider
**`libc.elf`**:

    eboot,libc,_Stderr,data,libc.elf
    eboot,libc,_Stdin,data,libc.elf
    eboot,libc,_Stdout,data,libc.elf

(Separately `libSceFios2.elf` imports `_Stdout` from `libSceLibcInternal` with no provider, a second
reader to settle later.)

So the struct the guest reads is **libc.elf's**, libc.elf **is in the tree** (`../data/bb/elf/`), and
the layout is therefore **derivable rather than guessed** -- the honest branch, not the
delegate-everything fallback. Read libc.elf's own `fputs`/`fprintf`/`fwrite` to find the offsets it
uses on the object, and build the object to that layout. Only if that decode comes back ambiguous
does the stdio family get delegated wholesale, with the "guest must never touch a FILE field"
constraint stated as a limit.

And the first grep for these returned nothing because `imports.csv` has **no NID column** -- it
holds names. Grep names there, NIDs in `import_names.csv`. That trap has now cost three slices.

## Pre-registration: what `struct __sFILE` should look like before I read it

Written **before** the decode, as a control rather than a discovery. FreeBSD 9's `struct __sFILE`,
which PS4's libc is derived from, in 64-bit:

| offset | field |
|---|---|
| 0x00 | `_flags` (int) |
| 0x08 | `_file` (int, the descriptor) -- low half of a word with `_cookie` adjacency |
| 0x10 | `_cookie` (void *) |
| 0x18 | `_read` (function pointer, guest code address) |
| 0x20 | `_seek` |
| 0x28 | `_write` |

**Falsification, stated so the read cannot be fitted afterwards:**
- If a word at 0x18/0x20/0x28 is a **guest code address** (inside `libc.elf`'s text), the guest's own
  stdio reads function pointers out of this object and **the host cannot construct it** -- `_Stdout`
  must resolve to **libc.elf's own initialised object**, whose address libc's init has already
  produced (the boot was inside libc.elf two stops ago). The arena is then the wrong tool.
- If those words are zero or host-looking, the object is constructible and the layout above is a
  candidate to match field by field.

**Two failed attempts to reach the object, both instrument failures, neither a finding:**
`libc.elf` has **no `SHT_DYNSYM` section** (`e_shoff` route returns nothing -- consistent with
`e_shoff = 0`), and my `PT_DYNAMIC` walk raised `KeyError: 6` on `DT_SYMTAB`, so the tag map did not
parse. Read the dynamic segment's tags and print them before indexing; an absent tag and a
mis-parsed segment look identical, which is the same lesson as `_line` in the pin checker.

## `libc.elf`'s program headers: SCE vendor types present, `PT_DYNAMIC` present, `DT_SYMTAB` absent

    ph0 0x00000001 LOAD   vaddr 0x0      filesz 0x0b7924
    ph1 0x00000001 LOAD   vaddr 0xb8000  filesz 0x006cc0
    ph2 0x61000002 SCE?   vaddr 0xb8000  filesz 0x18
    ph3 0x00000002 DYNAMIC off 0xe7850   filesz 0x280
    ph4 0x00000007 TLS    vaddr 0xb8018  filesz 0x220
    ph5 0x6474e550 GNU_EH_FRAME vaddr 0xb2548 filesz 0x53dc
    ph6 0x61000000 SCE_RELA off 0xc2cc0 filesz 0x24e10
    ph7 0x6fffff00
    ph8 0x6fffff01

**`KeyError: 6` is now explained structurally, not as my parse bug:** `PT_DYNAMIC` exists (ph3, 0x280
bytes) but carries **no `DT_SYMTAB`** -- PS4 modules use SCE dynamic tags, so the tag map legitimately
lacks tag 6. **An absent tag and a mis-parsed segment were not distinguishable until the segment was
printed**, which is why printing tags precedes indexing.

Note against the expectation: there is **no `0x61000020`**; the SCE types here are `0x61000000`
(`PT_SCE_RELA`, the relocations, 0x24e10) and `0x61000002` (0x18, next to the second LOAD's start).
So `_Stdout` is not in a `0x6100002x` table in this file -- the next read is `PT_DYNAMIC`'s tag list
itself (print tag/value pairs), since SCE names/providers live in those tags rather than in a symtab.

## `libc.elf`'s `PT_DYNAMIC`, printed: no `DT_STRTAB`/`DT_SYMTAB`/`DT_STRSZ`/`DT_SYMENT` at all

39 tag/value pairs, verbatim in the commit's file (see `docs/`-adjacent note below). The standard
tags that are present are all `DT_NEEDED`(1) x2, `DT_INIT`(12), `DT_FINI`(13), `DT_INIT_ARRAY`(25)/
`_SZ`(27), `DT_FINI_ARRAY`(26)/`_SZ`(28), `DT_PREINIT_ARRAY`(32)/`_SZ`(33)=8, `DT_PLTGOT`(3)=`0xbecb8`,
`DT_DEBUG`(21)=0, `DT_FLAGS`(30)=0.

**Absent: 5 (`DT_STRTAB`), 6 (`DT_SYMTAB`), 10 (`DT_STRSZ`), 11 (`DT_SYMENT`).** So the prediction
that standard tags would interleave with `DT_SCE_*` was **half right** -- `DT_SYMTAB` really is
missing, as predicted -- but there is no standard string/symbol table pair at all. Everything
name-bearing lives in the SCE tags: `0x61000007`, `0x61000009`(=`0x43`), `0x6100000d`, `0x61000011`,
plus the export-lib family `0x6100000f`/`0x61000013`/`0x61000015`/`0x61000017`/`0x61000019`.

**Values like `0x101010000001f` and `0x2010100000029` are packed (type|offset|size), not addresses**
-- the high bits repeat across entries while the low 32 vary, which is the signature of a packed
attribute word rather than a pointer. So **do not index into them as addresses**; `0x61000011`=0 and
`0x61000009`=0x43 are counts/sizes, not bases.

**No `DT_SCE_SYMENT` was identified by inspection, so the symbol stride is still unknown** -- and
indexing the SCE symbol table with 24 because `Elf64_Sym` is 24 is exactly the remembered-constant
error. The stride must be read from the tag that describes it (0x61000009=0x43=67 is a plausible
entry count for an 11-char-NID-shaped table: 0x6100000d=0x1010000003e pairs with it).

**Second route, now the primary one:** `eboot`'s `PT_SCE_RELA` names the exact slot for `_Stdout`
(the data analogue of the GOT-slot join). Two routes, one answer.

## eboot's `PT_SCE_RELA` is not 24-byte Rela entries -- and `_Stdout` is not in eboot by name

Two measurements, both fatal to the plan I was about to execute.

**1. `_Stdout\0` does not appear anywhere in `eboot.elf`** (`d.find` over the whole file: no hits).
So eboot's import table does **not** carry symbol names -- consistent with `module_functions.csv`
holding raw NIDs and with names having to come from a database or a hash sweep. **Any route keyed on
the string `_Stdout` in eboot is dead before it starts.** Key on the NID (`2sWzhYqFH4E`) instead.

**2. Decoding `PT_SCE_RELA` (off `0x53e9b40`, filesz `0x569d78`) at a 24-byte stride yields ASCII**:
`r_offset` fields read `6c62 6553 ...` = `"libSce...prx"`, and successive entries spell
`libSceVideoOut.prx`, `libSceNet.prx`, `libSceAudioOut.prx`, `libSceHttp.prx`, `libSceSysmodule...`.
**That region is a string table of library names, not relocations.** The 0x18 tags seen in
`libc.elf` describe its own tables; **assuming 0x18 here was the remembered-constant error, caught by
the decode rather than by the boot.** 236,517 "entries" is the tell: a count that large for a
157k-entry module was a stride that did not divide the data.

**So the SCE dynlib data is a mixed region** -- names, NID arrays and relocation words -- whose layout
must be found by content (ASCII runs, NID-shaped 11-char strings) rather than by a fixed stride.
That is the next instrument: print the region's printable-string runs with their offsets, and look
for the 686 import NIDs inside it.

## The NID table, located by content: `pO96TwzOm5E#p#J` in eboot; `FxVZqBAA7ks` is NOT there

Control hit, target missed -- and the miss is the finding:

    eboot.elf  pO96TwzOm5E -> 0x53ecaae   ctx: ...rTXw65xmLIA#p#J.IWIBBdTHit4#p#J.cQke9UuBQOk#p#J.
                                               pO96TwzOm5E#p#J.L-Q3LEjIbgA#p#J.rVjRvHJ0X6c#p#J...
    eboot.elf  FxVZqBAA7ks -> MISS
    libc.elf   FxVZqBAA7ks -> (see next)

So the NID table **is** findable by content, entries are **fixed 16-byte slots** (11 chars + `#p#J` /
`#q#q`-style 5-byte marker, then padding -- the neighbours are contiguous every 16 bytes), and the
markers are **in the file**, not manufactured only at bind time. Good: the table is 16-byte strided,
confirmed by adjacency rather than assumed.

**And `FxVZqBAA7ks` being absent from eboot retracts a conclusion I stated two sessions ago** that
`bind 47` proved eboot imports it. It does not: the bind dump spans **747 NIDs across more than one
object**, while eboot's own table is 686. The row was in the dump, not in eboot. That is the same
747-versus-686 gap, now with a concrete instance instead of a suspicion.

**Rule for the file, not just the log: divide first.** 236,517 entries for a 157k-entry module, and
747 NIDs for a 686-import object, were both arithmetic that contradicted the premise before any
decode; `1,072 -> 1,144` was the same class.

## libc.elf: which NIDs it holds, and who references its name table

Measured in one call (contexts trimmed):

- `_Stderr` = `H8AprKeZtNg` -- see commit body for the hit offsets and the bytes around them.
- `_Stdout` = `2sWzhYqFH4E`, `_Stdin` = `1TDo-ImpqJc` -- likewise.
- `pO96TwzOm5E` (`sceKernelGetDirectMemorySize`): **MISS in libc.elf**, while it HITS in eboot.
  So the companion's expectation that libc imports it is wrong; **libc does not call it**, eboot
  does. Presence in an object's name table is per-object and a miss is the informative outcome.

Referrer search for the name-table offset `0xc3094` as `u32` and `u64` is recorded in the body; a
table holding that value is the entry array that indexes the names, which is the structure the
relocation walk needs.

## libc.elf's SCE dynlib blob: address arrays located by content

Scan of `0xc2cc0..0xe7ad0` for fixed-stride runs of pointers landing inside libc's own LOAD ranges --
**80 runs of 16 or more**. The first and largest is at **`0xd9040`: 128 entries of 32 bytes**, each of
the shape

    0x0, 0xb8aa8, 0x8, 0x81e10      (flags?, name-or-attr, size 8, address)

with the fourth quad landing in libc's text (`0x81e10 < 0xb7924`). **That is an export/symbol entry
array found by content, with no reference format and no 24-byte assumption.**

Second run at `0xd9460` (98 entries) and a third at `0xd9880` (23) follow the same shape, so the blob
holds several such arrays rather than one.

Note `0xb8aa8` is *not* the name table (which lives at file offset 0xc3xxx, and this segment's
vaddr == offset): the second quad points into libc's data segment, so it is an attribute or a cookie,
not `st_name`. **Which quad names the symbol is the open question**, and the name table at 0xc3xxx
being contiguous with the stdio NIDs means the link is by ordinal or by a separate index array.

## Pre-registration (written before the scan): what `_Stdout` must look like in libc.elf's file image

Failure mode stated first, so a clean zero is not a refutation: FreeBSD initialises `stdout`/`stderr`
from `_initstdio`/`__sfp` at **runtime**, so a file image may legitimately hold zeros and a scan that
finds nothing would refute nothing.

Predicted values if the objects *are* static in this file (companion's, adopted because they are
checkable): `_flags` = `0x8` (`__SWR`) for `_Stdout`, `0x9` (`__SWR|__SUNB`) for `_Stderr`, `0x4`
(`__SRD`) for `_Stdin`; `_file` = `1`/`2`/`0` respectively; layout `_flags` 0x00, `_file` 0x08,
`_cookie` 0x10, `_read` 0x18, `_seek` 0x20, `_write` 0x28. **Any other reading is a finding.**

## `.bss` answered: 113 qwords point into it, and one array is 24-byte strided after all

`ph1` is `filesz 0x6cc0 / memsz 0x1e620`, so the bss tail is **`0xbecc0..0xd6620` (96,608 B)** --
printed before anything was scanned, per the rule that a range assumed empty is a range never checked.

**113 qwords in the file land in that tail.** So exported *data* objects with file-image zeros exist,
and `.bss` explains `_Stdout`'s zeros exactly as the companion predicted -- the object is knowable
without a dump after all.

The first hits after the blob are at **`0xcd140`, `0xcd158`, `0xcd170`, `0xcd188` -- stride `0x18`**,
i.e. a **24-byte-strided table holding bss addresses**. So the `0x18` tags in `libc.elf` were right
for libc all along; it was carrying that stride to **eboot** that was wrong. **Both facts are true at
once, in different objects.**

**Filter artifact worth the line:** the very first hit, file `0x198 -> 0xc2cc0`, is a program-header
field -- `0xc2cc0` is `PT_SCE_RELA`'s file offset -- not a symbol address. **Any scan for "pointer into
region X" also matches the tables that describe region X**, so candidate lists must exclude values
that are also segment offsets before they are read as addresses.

Next: walk the 24-byte table from `0xcd140` for entries whose address lands in the stdio neighbourhood,
and join by ordinal to the contiguous `_Stderr`/`_Stdout`/`_Stdin` names at `0xc3c34..0xc3c54`.

## The stride join, run over all 112: three bss addresses 0x100 apart

Excluding the phdr-field hit leaves 112 pointers into the bss tail. Scanning them in file order for
constant deltas (n >= 3) gives exactly two overlapping runs, both at file offset `0xd9928`/`0xd99d0`
and both **delta `0x100`**:

    0xbf060, 0xbf160, 0xbf260        (i.e. 0xbf060 + k*0x100, k = 0..2)

**That is the shape `__sF[0..2]` must have** -- three contiguous objects whose separation *measures*
`sizeof(__sFILE) = 256` rather than assuming it. Under FreeBSD's ordering `__sF[0]=stdin`,
`__sF[1]=stdout`, `__sF[2]=stderr`, so the candidate mapping is

    _Stdin  0xbf060   (__sF[0], _file 0)
    _Stdout 0xbf160   (__sF[1], _file 1)
    _Stderr 0xbf260   (__sF[2], _file 2)

**All three are inside the bss tail, so their file image is zero -- which is why the earlier `.data`
scan found nothing, and why `_flags`/`_file` cannot be read from the file at all.** The 0x100 stride is
the only evidence available without a dump, and it is exactly the evidence the companion asked for.

**Test that would falsify it cheaply:** the export table should carry these three addresses in three
consecutive entries (they are consecutive objects, and the names are consecutive NIDs). If the export
array at `0xd9040`/`0xd9928` shows them in the `_Stdin`/`_Stdout`/`_Stderr` order above, the mapping
is confirmed by an independent join; if it shows them in another order, the ordering assumption is
what is wrong, not the stride.

**Consequence for the fault either way:** if these are the objects, the runtime must **populate** them
(`_flags`, `_file`, and `_read`/`_seek`/`_write`), not find them -- the case-1 answer -- because a
bss object is zero at load and libc's `_initstdio` would have filled it, which means the fault is
either that init did not run or that eboot bound the slot before it did.

## Correction to my own tag table: `DT_INIT_ARRAYSZ` is 0, so libc has no init to run

Re-reading the dump I committed two sessions ago, with names attached this time:

    DT_INIT          = 0x0
    DT_INIT_ARRAY    = 0xbecc0   (a bss address)
    DT_INIT_ARRAYSZ  = 0x0       <-- this is the value I failed to read
    DT_FINI_ARRAY    = 0xbecc0
    DT_FINI_ARRAYSZ  = 0x0
    DT_PLTGOT        = 0xbecb8

I recorded "DT_INIT_ARRAY(25)/_SZ(27)" as *present* and never printed the pair's value, and **the size
is zero**. So the array at `0xbecc0` has **no entries**: there is nothing for a loader to call it with,
and the companion's check 2 ("does the runtime call each module's init array") is answered *structurally*
-- there is no array to run, whatever the runtime does.

That makes three readings collapse to one: libc has **no `DT_INIT`, and a zero-length init array**, so
`_initstdio` is not reachable through dynamic tags at all. Either it is called from eboot's init, or
stdio initialises lazily on first use inside the guest's own code path -- and in the latter case the
zeroed `__sFILE` at `0xbf160` is expected, and the fault is in whoever dereferences `_write` before
lazy init.

**A tag name recorded without its value is a claim, not a measurement** -- the same defect as the
`boundary_confidence` DISTINCT/`ghidra-export-entry-size` mismatches.

## `0x61000002` holds nothing text-shaped, and the three bss objects have 4-5 referrers each

    payload (0x18 B): 18 00 00 00 00 00 00 00 | bf f4 13 3c 01 00 00 00 | 71 00 00 02 00 00 00 00
    dwords:           0x18, 0x0,            0x3c13f4bf, 0x1,            0x2000071, 0x0

**No field is an address inside libc's text** (`0..0xb7924`): `0x13c13f4bf` is ~5.2 GB, not a code
address, and `0x2000071` is small and flag-shaped. So the companion's last place to look for a module
init entry **does not hold one**, and the surviving reading is **lazy, guest-side stdio init**.

**This does not license "no init exists"** -- the companion's distinction is right and stands: a real
`DT_FINI` at `0x81d80` with a zero-length `DT_INIT_ARRAY` is a placeholder pair, so the honest claim is
**"the init is not in the dynamic tags or in the 0x61000002 metadata"**, not "there is none."

**Export references, counted by raw qword search over the whole file:**

    0xbf060 (_Stdin?)  4 referrers at 0xd98c8 0xd98f8 0xd9910 0xd9928
    0xbf160 (_Stdout?) 5 referrers at 0xd98e0 0xd9970 0xd99a0 0xd99b8 0xd99d0
    0xbf260 (_Stderr?) 5 referrers at 0xd9988 0xd9a18 0xd9a48 0xd9a60 0xd9a78

So each bss object is referenced from **several parallel tables in the same 0xd98xx--0xd9axx
neighbourhood**, which is what an export entry array plus its lookups look like. **The addresses are
real exported data objects; the ordering question (`_Stdin`/`_Stdout`/`_Stderr`) is still unproven**,
because multiple tables carry them and adjacency in one is not the mapping.

## The RIP-relative scan for the three objects returned 0 -- and the zero is not evidence

    0x4000..0xb7924 (751,268 B) linear-swept from vaddr 0 -> 20,123 instructions
    751,268 / 20,123 = 37.3 bytes per instruction

**x86-64 averages three to four bytes per instruction.** 37.3 is an order of magnitude out, which means
the linear sweep desynchronised into data within the first few hundred bytes and **every instruction
after that was decoded from the wrong boundary.** So "0 references" is **not** a fact about libc's code
reaching the three stdio objects; it is a fact about my disassembly.

**Divide first, applied to my own instrument:** the same arithmetic that exposed 236,517 entries for a
157k-entry module and `1,072 -> 1,144` also flags a sweep whose bytes-per-instruction is impossible.
**A decode with an implausible density must be discarded before its result is read**, and this is the
second time in this campaign a matcher's zero was really the matcher.

To retry: disassemble **per entry point** (the `descent.py` path, from known function starts such as the
`DT_FINI` at `0x81d80` and the entries reachable from the 0xd98xx tables), not linearly over the whole
text; or find the references by searching the relocation blob for RIP-relative disp32s whose computed
target is one of the three, which needs no disassembly at all.

## Pattern scan (no decoder): 0 hits and a healthy density -- but the sweep is REX-only

Bounding the sweep by `DT_FINI + 0x2000` and matching `modrm & 0xC7 == 0x05` at `s+2` with lengths 7
and 11:

    540,032 bytes swept
    4,815 rip-relative candidates = 8.9 per 1000 B
    0 hits on 0xbf060 / 0xbf160 / 0xbf260

**The density is plausible** (one rip-relative form per ~112 bytes), so unlike the linear sweep this
instrument is not desynchronised -- **and its zero is therefore a real negative for the forms it covers.**

**But it covers only REX-prefixed forms** (`s` must be 0x48..0x4f). A 32-bit-operand rip-relative
reference -- `lea eax,[rip+d]` = `8d 05 dd dd dd dd`, `mov [rip+d],imm32` = `89 05 ... 11 bytes` --
**has no REX byte and is outside this sweep entirely.** So the honest statement is narrower than the
scan: **libc's 64-bit-operand code does not reach the three stdio objects directly**, and the 32-bit
forms remain unexamined.

That is consistent with the objects being reached **only through the pointer tables at 0xd98xx**, which
is what an export-table consumer (or a getter returning `&__sF[i]`) looks like -- and it would explain
why no direct reference exists to find.

## My `_Stdin`/`_Stdout`/`_Stderr` labels are WITHDRAWN -- and the records carry their own name pointers

Two things arrived together: the companion caught that the name table orders `H8AprKeZtNg`(_Stderr),
`1TDo-ImqkJc`(_Stdin), `2sWzhYqFH4E`(_Stdout) at `0xc3c34`/`0xc3c44`/`0xc3c54`, i.e. **stderr, stdin,
stdout** -- not the FreeBSD `stdin, stdout, stderr` I assigned. **My table came from a convention, not
from this file**, and it is withdrawn rather than patched.

Then the 24-byte records at `0xd98c8` turned out to be `(value, name_pointer, flags)`:

    k= 0  0xbf060  0xb8f90  0x8              A
    k= 1  0xbf160  0xb8f98  0x8              B
    k= 2  0xbf060  0xb8fa0  0x8              A
    k= 3  0xbf060  0xb8fa8  0x8              A
    k= 4  0xbf060  0xb8fb0  0xf000000001     A
    k= 7  0xbf160  0xb9158  0x8              B
    k= 8  0xbf260  0xb9160  0x8              C
    ...     and further aliases for B (k=9,10,11) and C (k=14,16,17,18)

**Three consequences.** (1) **Each object carries several exported *names*** -- aliases, which is why the
raw qword search found 4-5 referrers each and why no index arithmetic can map object to name.
(2) **The name pointers point at `0xb8f90`+ in the file-backed data segment, not at the `0xc3xxx` NID
table** -- so there are two independent name stores and I had been reading the other one.
(3) **The assignment is one read away and needs no convention at all**: read the C strings at
`0xb8f90`, `0xb8f98`, `0xb8fa0`, `0xb9158`, `0xb9160`, `0xb9320`.

**Rule that this earns:** a label inferred from a platform convention is a hypothesis; this file has now
contradicted FreeBSD ordering once, and the contradiction was in a dump I had already printed.

## Refuted: the second field is not a name pointer, and my own read produced 4 KB of binary

    field2 = 0xb8f90  ->  hex 4c 69 ff ff 88 25 fa ff  ...   printable 0/16

**Not a string.** The bytes are 8-byte displacement-shaped values, not names, so **`{value, name_pointer,
attrs}` was my hypothesis and the file says no.** The control I ran -- `nid(name)` for each row, searched
for in the `0xc3xxx` name table -- found **no matches**, which is consistent with the names never having
been names.

**Two instrument lessons, both mine.**
1. **A string read with no length bound and no printability test produced a 4 KB latin1 dump** -- the
   terminal filled with binary because I asked for `d[o:d.index(0,o)]` on a region that has no NUL for
   kilobytes. **Bound every string read (`o+64`) and require printable bytes before believing it.**
2. **My table walk's predicate was wrong**: `isrec` accepted two records then stopped, against a region
   where the earlier 0x18-stride scan found at least 19 address-bearing rows. **A predicate that
   classifies 2 of 19 as records is measuring itself.**

**What survives:** the three bss addresses, the measured `0x100` stride, the 0x18-strided records
existing, and the companion's name-order correction. **What does not:** my name-pointer reading, and with
it the "export table dump" idea in that form.
