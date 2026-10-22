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

## Delta resolution: 8 of 8 land inside LOAD0, one code target per object, and the mechanism is now ours

Resolving each record's field2 pair as **`target = address_of_the_delta_word + value`**:

    0xbf060 record:  0xb8f90 -0x9694 -> 0xaf8fc (rodata)   0xb8f94 -0x5da78 -> 0x5b51c (code)
    0xbf160 record:  0xb8f98 -0x9654 -> 0xaf944 (rodata)   0xb8f9c -0x5d718 -> 0x5b884 (code)
    0xbf260 record:  0xb9160 -0x86b8 -> 0xb0aa8 (rodata)   0xb9164 -0x58f88 -> 0x601dc (code)

**8 for 8 land inside libc's own LOAD0**, the code targets disassemble as function prologues
(`AWAVAUATSH` = push r15/r14/r13/r12/rbx at `0x5b884`; `UH..H.=.V` at `0x601dc`), and the rodata
targets are not strings.

**So the objects' pointer fields are stored in the file as self-relative deltas, and the interesting
consequence is the one nobody predicted:** the `__sFILE` objects are in bss and read as zeros, while
**the wiring that must fill them is present and resolvable in the file.** A loader that maps the segment
and applies no relocation leaves them zero -- **which is exactly the null at `+0x28` we observe.**

**This is no longer a guest-side question.** The next instrument is our own code: does `boot.c`'s
relocation pass run for modules other than eboot, and does anything treat a zero word as "unset" and
skip it?

## The runtime already speaks SCE relocations -- and the 0x18 stride is the symbol entry size

`runtime/loader.c` defines the whole SCE tag set (`0x61000013` EXPORT_LIB, `0x61000015` IMPORT_LIB,
`0x61000029` JMPREL, `0x6100002d` PLTRELSZ, `0x6100002f` RELA, `0x61000031` RELASZ, `0x61000035` STRTAB,
`0x61000037` STRSZ, `0x61000039` SYMTAB, `0x6100003f` SYMTABSZ) plus `R_X86_64_RELATIVE 8`, and it
**applies** them: `loader.c:231 memcpy(&addend, r + 16, 8)` reads a 24-byte relocation entry, and
`:399 memcpy(image + r->target, &v, 8)` writes the result.

**So "our loader applies no relocations" is false, and the companion's mechanism 4 is refuted as stated**
-- the objects live in bss, so no loader wrote zeros over valid pointers; the deltas are a table that
must be *applied* to those fields.

**What the same file resolves as a side effect:** the two `0x18` values in libc's tag dump
(`0x61000033`, `0x61000035`) are consistent with a **24-byte symbol entry size**, which is the stride I
"refuted" twice and then found again in the 0x18-strided records at `0xd98c8`. The stride was never
wrong; only the object I attributed it to was.

**Open and now narrow:** does the loader run its rela pass for modules other than `eboot`, and does any
of its `R_X86_64_*` handlers skip a target whose current value is zero?

## Both greps answered: relocations run for every mapped object, and nothing skips a zero target

`boot.c:340` opens each object in a loop, `:405 rt_elf_map(o->elf, o->image, bind_import, o, ...)` is
called per object, and `loader.c:394-399` applies every relocation with **no test of the current value**:

    for (i < e->reloc_count)
        v = KIND_LOCAL     ? image + r->value
          : KIND_TLS_MODULE? e->tls_module_id
          :                  bound[r->value] + r->addend;
        memcpy(image + r->target, &v, 8);

**So the "handler skips a zero target" clause is excluded, and "the rela pass does not run for non-eboot
modules" is excluded too** -- **provided libc.elf is one of `objects[]`.** That is now the only remaining
premise, and it is one grep (`objects[...] = ` population), not a boot.

**`KIND_LOCAL` is `image + r->value`, which is exactly the self-relative scheme the descriptors encode**
-- so the descriptors and the loader agree, and if the objects were reachable by a relocation the
mechanism would work.

## The RELA decode is garbage: my vaddr->offset mapping is refuted, not the addend convention

    DT_SCE_RELA 0x162c8  size 0xbd60  entries 2020
    [0] off=0x3b841b04d8d48ff type=0      addend=-0x76befffff67d171e
    [1] off=0xdb0007871905d9c7 type=9276  addend=+0x35e800000003beff

`48 8d ...` is `lea` -- **these are code bytes, not relocation entries.** The `0x4000 + vaddr` mapping I
applied is wrong for this region, so **the addend-convention test the companion proposed has not run.**

**The missing predicate, stated as a rule:** a relocation record has `type < 40` and `r_offset` inside the
image. **Entry 0 has type 0 (plausible) and an r_offset 60 bits wide (impossible); entry 1's type is
9,276.** **A decode whose validity predicate fails on entry 1 must be discarded before entry 0 is quoted**
-- the same density check that caught 37.3 bytes per instruction, applied to a record stream instead of
an instruction stream.

**Next call is the program headers, printed, before anything is decoded from them** (`p_type, p_offset,
p_vaddr, p_filesz, p_memsz` for every header) -- **the mapping has now cost me four decode attempts and
has never once been printed beside the result that depends on it.**

## Program headers printed; the rela table is real, and it relocates nothing in the stdio range

    [0] type=0x00000001 off=0x4000  vaddr=0x0      filesz=0xb7924  memsz=0xb7924
    [1] type=0x00000001 off=0xbc000 vaddr=0xb8000  filesz=0x6cc0   memsz=0x1e620
    [2] type=0x61000002 off=0xbc000 vaddr=0xb8000  filesz=0x18     memsz=0x18
    [3] type=0x00000002 off=0xe7850 vaddr=0x0      filesz=0x280
    [6] type=0x61000000 off=0xc2cc0 vaddr=0x0      filesz=0x24e10
    
    file = vaddr + 0x4000   for BOTH LOADs (p_offset is NOT 0)

**The SCE tags are offsets into the `0x61000000` blob at file `0xc2cc0`, not vaddrs** -- which is why
`0x4000 + 0x162c8` and `0x162c8` both decoded as `lea` bytes. Decoded at `0xc2cc0 + 0x162c8`:

    entries 2020   pass type<40 and r_offset<0xd6620: 2020   fail: 0
    relocations whose target lies in 0xbf060..0xbf360: 0

**2020 of 2020 pass the validity predicate, so this is the relocation table; and not one entry names the
three stdio objects.** Combined with the loader loop (which writes every entry unconditionally), the
mechanism is settled: **the fields are unnamed, not named-with-a-wrong-address.**

**Also corrected: the two "rodata" delta targets are not strings either** -- read through the correct bias
(`file = vaddr + 0x4000`), `0xaf8fc`/`0xaf944`/`0xb0aa8`/`0xb2c80` are 4-byte tables, not ASCII.

## The fail-closed refusal landed, and it never fired: the boot stops before the fault

Structural predicate (no literals): an export whose value is **past a load's `p_filesz` and inside its
`p_memsz`** names a `.bss` object; binding a data import to it now prints
`provider=data-unfilled` and refuses. `rt_elf_load_filesz` added so the test is computable from headers.

**Same command, one variable, both runs:**

    baseline (runtime/ stashed)  rc=3  imports 686: 219 bundled, 30 implemented, 4 unresolved, 433 unbound, called 24
                                 stop: unimplemented, eboot calls libkernel pO96TwzOm5E, returning to eboot+0x2081a85
    patched                      rc=3  identical on every number and on the same stop

**So the refusal is inert on this boot, and the pre-registered outcome did not occur** -- not `served 0`,
not `provider=data-unfilled`, but **a stop three layers earlier.** The guest never reaches
`0x20b56d2`: **the SIGSEGV I have been modelling for six slices is not reproducible at HEAD**, because
binding for `pO96TwzOm5E` regressed at some earlier commit and the run now halts at that call.

**The three stdio data imports were never bound to libc's exports in this configuration** (identical
unbound count with the check removed), so `bind_import`'s data-scratch path is still live and still a
zero object -- **the fault is behind an earlier wall, not behind my refusal.**

## The guest diagnosed itself: the heap allocation failed because my arena was 64 MiB and it asked for 116

Running `pbboot` directly (eboot + libc + libSceFios2, no `--nids`) reproduces the fault **and prints the
guest's own panic first**:

    [Dantelion2 Panic]
    ... Ps4RuntimeHeapImpl.cpp(324)
    _AllocateDirectMemory() failed for creating runtime heap. (size=121634816 bytes)
    DL_PANIC is firing core dump...
    pbboot: eboot: fault: signal 11 at eboot+0x20b56d2, address 0x0
    milestone entry; 213 bundled, 33 implemented, 4 unresolved, 436 unbound, 28 called

**121,634,816 B = 116 MiB against `k_arena_bytes = 0x4000000` (64 MiB).** So the fault's *cause* was
never the stdio objects; it was my own model refusing an allocation the guest treats as fatal, and the
panic screen is what dereferences the unpopulated `__sFILE` afterwards.

One variable changed -- arena `0x4000000` -> `0x8000000`:

    panic: gone
    stop:  unimplemented, eboot calls libkernel L-Q3LEjIbgA at eboot+0x2081ac6
    imports called 26 (was 28)

**Also refuted: the "33 implemented -> 30" regression.** The registry is intact -- `nm` shows both
`kernel_direct_memory.c` entries, and the NID model reproduces the known pair (`memset` ->
`8zTFvBIAIN8`) and `sceKernelGetDirectMemorySize` -> `pO96TwzOm5E`. The two invocation paths simply
report different populations (219/30/433 via `boot.py --nids`, 213/33/436 directly). **Why they differ
is measured and unexplained -- written down, not smoothed.**

## Arena reserves instead of rationing; the popup that survived says Map, and the 219/30/433 line was a build

Arena: `k_arena_bytes = 0x40000000` with `MAP_NORESERVE` -- untouched pages cost nothing, so the ceiling
is address space, not a number I invented -- and a refusal now prints the request beside the usage:

    pbboot: direct memory: allocation of N bytes refused, U of T used

Result: **panic gone, fault gone**, run `rc=0`, stop moves again:

    unimplemented: eboot calls libkernel L-Q3LEjIbgA, returning to eboot+0x2081ac6
    imports called 26

**`L-Q3LEjIbgA` was already named in the tree** -- `symbols/import_names.csv:249`, bind 125,
`sceKernelMapDirectMemory`. So the next wall is the one whose invariant I wrote into a file header and
never implemented: **Map is the identity over the arena**, because this runtime has one address space.

**Withdrawn: "two invocation paths disagree."** They do not. Same binary, same two modules
(`game/modules.csv` maps exactly `libc` and `libSceFios2`), with and without `--nids`:
**213 bundled / 33 implemented / 4 unresolved / 436 unbound, called 26** every time. The `219/30/433`
line came from an **earlier build**, so it was two builds, not two paths -- **and that means the
stash-baseline comparison I reported as "identical" compared a binary whose objects had not all
relinked. The baseline must be re-run clean before that claim is repeated.**

## Map landed as the identity, the run now names itself, and the pre-registration held

    pbboot sha256 b3c4f7fd5232
    unimplemented: eboot calls libkernel 6ULAa0fq4jA at eboot+0x207f2d8
    213 bundled, 34 implemented, 4 unresolved, 435 unbound, called 28

**Map: identity or refusal.** Returned `*addr == arena_base + directMemoryStart`, computed as the same
value Allocate handed out -- never "somewhere in the arena". A non-null hint that differs is refused with
both addresses printed; `prot`/`flags` are **logged, never obeyed**, and `mprotect` is never called,
because our pages are already RW and honouring a read-only request would break the identity at the next
writer.

**The identity line paid for itself on its first build:** `identity.c` sits at `runtime/`, where the only
`CONFIGURE_DEPENDS` glob in `runtime/CMakeLists.txt:9` does not reach (it covers `syslib/*.c`), so the
compiler never saw the file and the failure was an **undefined reference at link** -- not a stale build,
a missing source. `add_executable(pbboot ...)` now names it. **A glob is scoped to its directory; "new
files are globbed" is a claim about one directory, and I had been quoting it about a tree.**

**Pre-registration scored: new `unimplemented` NID, not the `_write` SIGSEGV** -- `6ULAa0fq4jA`, which
`symbols/import_names.csv:145` already names `scePthreadRwlockInit` (bind 58). **The stdio wall did not
reappear, so the panic path was its only caller so far.**

## The handle table landed, and the guard nobody had seen fire fired on the right thing

`runtime/syslib/pthread_rwlock.c`: guest storage keeps **8 opaque bytes** (index + magic `PTWH`), the host
`pthread_rwlock_t` lives in a 32-row side table under its own lock, and a stale or zeroed handle
**refuses and prints the handle** rather than locking freed memory. Built as a family so mutex/once/cond
land on the same table instead of four ad hoc globals. Attribute objects are not modelled and are not
read; that is written in the code, not implied.

**Scored:** 34 -> **40 implemented**, 435 -> **429 unbound**, called 28 -> **36**, next stop
`188x57JYp0g` = **`sceKernelCreateSema`** (import_names.csv:148, bind 148) -- so the pthread cluster
prediction holds one more link.

**And the structural data refusal from two commits ago fired for the first time**, naming its own NIDs:

    eboot imports 2WVBaSdGIds#q#q from libc.elf: provider=data-unfilled
    eboot imports TVfbf1sXt0A#q#q from libc.elf: provider=data-unfilled

`2WVBaSdGIds` = `_ZSt3cin`, `TVfbf1sXt0A` = `_ZSt4cerr` -- **C++ stream objects, which live in .bss by
construction.** So the predicate (past `p_filesz`, inside `p_memsz`) selected exactly the class it was
written for, on the first boot that reached it, and it did so by naming a mechanism rather than an
address window. **A guard whose first firing is a known mechanism is evidence; a guard whose first firing
is a mystery is a bug report about the guard.**

## Single-threadedness as a checked variable, semaphores as a handle table, and the compiler caught the wish

`scePthreadCreate` **refuses by name** (it is now the 5th unresolved diagnostic), and because it is the
only call that could falsify the assertion, the semaphore family below it is correct *under* one guard
rather than each function assuming it privately. Every entry point calls `require_single_threaded()`.

**The no-ops record what they could not serve:** a `Wait` whose count is short prints the handle, the
request and the count, and says it would have blocked -- success here, a hang on a real kernel. `Poll`
returns a would-block error instead of lying, since a poll has an honest answer available.

Scored: 40 -> **45 implemented**, 429 -> **423 unbound**, 4 -> **5 unresolved** (the new one is
`scePthreadCreate`, refusing), called 36 -> **44**. Next stop `n88vx3C5nW8` from **libScePosix**, i.e. the
same primitive under the POSIX alias namespace.

**The compiler rejected my first version**: `static int guest_threads = 1;` was never read, so `-Werror`
failed the build. **A "single assertion" that nothing consults is a comment with a type**, and the tool I
had just described as making it checkable is what proved it wasn't.

## Time is reproducible and comes from one origin; the guest timeval is declared, not borrowed

**Epoch policy, decided before the code:** fixed `1700000000`, so a boot is reproducible and any
timing-dependent guest behaviour stays legible. **One origin function** (`origin_ns`, one
`CLOCK_MONOTONIC` reading at first use) serves every clock -- `gettimeofday` today, `clock_gettime` and
process time when they arrive -- so the guest cannot see time go backwards between two calls, which two
independent host reads would allow at microsecond resolution.

Guest `timeval` is **declared in our own terms with `_Static_assert(sizeof == 16 && offsetof(tv_usec) ==
8)`**, then written field by field; it happens to match x86-64 glibc, and "happens to match" is the
assumption that produced the `__sFILE` defect. `tv == NULL` returns success; `tz` is filled with two zero
int32s rather than left untouched (the true value is +00:00).

**One writer of guest memory means one place for the range check** -- `guest_write_ok()` refuses with the
address and the image bounds instead of taking a signal. **This is the first syscall in the tree that
writes guest memory, so it is the first place the check exists at all**; every later guest write should
route through the same helper rather than growing its own.

Scored: 45 -> **46 implemented**, 423 -> **422 unbound**, called 44 -> **46**. The same function is
registered under **`libkernel` and `libScePosix`**, which is the alias namespace arriving as predicted;
next stop `g8cM39EUZ6o` from **libSceSysmodule**.

## Sysmodule records ids instead of naming them, and the stop order became a file

**My first version carried an id->name table written from memory.** The guest asked for **id 180**, the
table lacked it, the refusal went back as a guest value, and the guest panicked
(`[Dantelion2 Panic]`, sha256 `d2a40f19a54f`). **That is the remembered-constant defect committed inside
the file written to avoid it, and it cost exactly one boot to prove.** The table is deleted, not extended:
ids are **printed and recorded**, with the honest note that they have no name here. Naming an id is an
evidence problem, and an invented name is indistinguishable from a measured one once it is in a table.

**Load and IsLoaded share one home**: a 64-entry accepted-id list, so nothing is ever "accepted and not
remembered" -- that pair would be worse than any stop. `is_loaded` consults the same list, `unload`
compacts it.

**`symbols/boot_history.csv` now exists**, and it is the artifact this track was missing: the sequence of
unimplemented NIDs **in the guest's own initialisation order** -- a dependency graph in execution order.
Rows 1-8 record what was measured, with the sha256 of the run where I have it and a blank where I do not.
The blank is the point: **a history row without its subject is the defect the sha256 line was added to
prevent, so the file records the absence rather than inventing a build.**

Scored: 46 -> **49 implemented**, 422 -> **419 unbound**, called 46 -> **47**. Next stop `R9lA82OraNs` from
**libSceAppContent**, return address `eboot+0x20261dd` -- twenty bytes after the sysmodule call returned.

## App content succeeds because the real machine succeeds; guest_write_ok has one home and two callers

`sceAppContentInitialize` returns **success**, prints its arguments, and says in the code and the log that
the success is **modelled**: the title's own content exists on a real machine, this runtime has none to
check, and **a fabricated failure is not more honest than a fabricated success -- both are models, and the
right one is the one the real system produces.** The add-on queries are the opposite case and are
truthfully empty: a base-game disc has no add-ons, so `GetNumAddcont`/`GetAddcontInfoList` write **0**
through the write check rather than inventing entries.

**`rt_guest_write_ok()` promoted out of `clock.c` into `runtime/guest_mem.c`** before this call existed, so
AppContent is its **first legitimate second caller rather than a copy**. Promoting it immediately found a
second target: `test_syslib` links `${PB_TEST_SYSLIB}` too, so the check had to be named there as well --
**a helper with one caller per target is how a "one home" claim quietly becomes two.**

**No panic on the success path** — the guest accepted it and moved on:

    appcontent: Initialize(args=0x8056a0200) -> success (modelled)
    unimplemented: eboot calls libSceAppContent 99b82IKXpH4 at eboot+0x20261eb

which is `+0x12` past the Initialize call site -- the guest's own next call in the same function.
Scored: 49 -> **51 implemented**, 419 -> **417 unbound**, called 47 -> **48**.

## Every registration declares what it is, and the boot line prints the decomposition

`RT_SYSLIB` entries now carry **`kind ∈ {real, modelled, noop, refused}` declared at the registration
site** (`RT_SYSLIB_MODELLED` / `RT_SYSLIB_NOOP` wrappers; `RT_SYSLIB_UNRESOLVED` is `refused`), and the
boot prints the split: **`syslib registered 71 = 54 real + 6 modelled + 5 noop + 6 refused`**.

**Two different populations, and the line says which is which:** 71 is *table entries*, 51 is *imports of
this executable that matched one*. Confusing them would be the sum-without-decomposition defect in the
other direction, so the two numbers print with their subjects.

**The split makes "the boot advanced" falsifiable**: 6 of the 51 matched are modelled (fixed epoch, no
module file read, fabricated app-content success) and 5 are noop (blocking primitives that cannot block
because the guest is single-threaded). **The boot is walking fabricated state in at least 11 of 51 places,
and now the log says so instead of a summary nobody prints.**

## AppParamGetInt: modelled success, and the guest read two parameters and continued

`sceAppContentAppParamGetInt` (`99b82IKXpH4`, `import_names.csv:655`) zeroes its out-parameter through
`rt_guest_write_ok()` and returns **success**, declared `RT_SYSLIB_MODELLED` and printing the parameter id
each time. **The reason is the one that decides these: this tree has no app parameter store, and inventing
one of the real machine's parameter-not-found codes would be a wrong number the guest branches on -- worse
than a declared stand-in.**

**The guest read ids 0x0 and 0x1 and moved on, no panic**, so the return value does not gate the path
immediately: **that is a measurement, and it is more than a refusal would have told us.** Two calls, not
one: the second read is the guest asking twice, which is the behaviour a "not found" answer would have
changed.

Scored: 51 -> **52 implemented**, 417 -> **416 unbound**, called 48 -> **55** (seven calls into the
modelled path). Next stop is on the following line of the run.

### Correction, same slice: the guest did not continue -- it faulted

The first version of `boot_history.csv` row 9 said "guest continued" and that was **false**: the run ended
`signal 11 at host+0x615b94b659ab, address 0x0` after reading parameter ids 0x0 and 0x1, **five AppParamGetInt
lines in total, i.e. two ids read more than once each**. The milestone line still printed, because it is the
*entry* milestone and prints before the guest runs.

**So the modelled success did not gate the immediate path, and the next thing the guest did depends on a
pointer it does not have** -- which is the `__sFILE` absence family again (`address 0x0`, second occurrence),
not a pthread or sysmodule stop. Recorded as row 10 rather than folded into row 9, because **a history row
that is edited to look right stops being a history.**

## The fault moved and I can name its PC but not yet its cause -- and a rebuild nearly made me lie

`sema_wait` now documents that **zero is not a sentinel** (a handle is `(magic << 32) | (index + 1)`, so
index 0 is legal and `h == 0` means storage was never written) and that a refusal prints **how many table
rows are live**, which splits "never handed out" from "created elsewhere than this call reads".

**The fault persisted and moved**: `pbboot+0xaadb` (`sema_wait+0xb`, the load `mov (%rdi),%rcx`) in one
build, `pbboot+0xac8b` (`sema_wait+0x1bb`) in the next, **both with `si_addr == 0x0` and with no `sema:`
line printed at all** -- so the refusal path never ran. **`si_addr == 0x0` is inconsistent with `mov
(%rdi),%rcx` unless `rdi` is null, and the guard above it would have branched.** So one of my premises is
wrong, and the candidates are ordered: (a) the PC is inside an inlined block whose reported address is the
function's, (b) the fault is a call through a null function pointer that lands on this PC in the guest's
retargeted stub, (c) `si_addr` for this signal is not the faulting operand.

**The lesson worth keeping: I resolved `0xaadb` against the binary built *after* the fault.** The run that
faulted (`dcbd016910d0`) no longer existed on disk. **A symbol resolved against a rebuild is a name for a
different artifact** -- the sha256 discipline applied to the disassembler -- so the handler must print the
run's identity beside the PC, and the binary must be kept for the run that faulted.

## The register dump answered it in one run: the semaphore model's signature is wrong

Run `sha256 99e5f8a4d413`, binary kept at `build-release/kept/99e5f8a4d413`:

```
fault pc pbboot+0xadfb   (r11 = 0x63fa08c74df0, so RIP = r11 + 0xb, i.e. the trampoline target + 0xb)
regs rax 0  rbx 750e26c36668  rcx 1  rdx 0
regs rsi 1  rdi 53454d4100000012  rbp 750e67bfe3b0  rsp 750e67bfe3a0
regs r8 1  r9 0 r10 0 r11 63fa08c74df0 r12 8056a2748 r13 ... r14 ffffffff r15 ...
```

**`rdi = 0x53454d4100000012` is `HANDLE_MAGIC ("SEMA") | (index 18 + 1)` -- a semaphore handle, and the first
argument our `sema_wait` dereferenced as a pointer.** So the guest passes **`sceKernelWaitSema(semaId, need,
timeout)` with the handle by value**, and our model's signature `(int64_t storage, ...)` treats it as the
address of a handle word: **the fault is a signature mismatch, not a bad handle.** `rsi = 1` (the count asked
for) and `rdi` holding a live handle both agree.

**Second finding, about the instrument itself: `si_addr` printed `0x0` while the operand was
`0x53454d4100000012`.** So (c) was right -- the reported address is not the faulting operand here -- and a
fault report must print **both** `si_addr` and the register a load could have used, or the two will keep
being confused. That is the third time in this campaign that a report named one thing and meant another.

## The handle ABI class, corrected once and for all -- and the wrapper that retires the stale-binary class

`sema_wait/signal/poll/delete` take **the id by value**; `pthread_cond_init` takes **a pointer** to guest
storage; `AttrSetstacksize` takes **a pointer and a scalar**. Measured, not assumed: rdi held
`0x53454d4100000012` (`"SEMA" | 19`) while the old body dereferenced it. **Arity is knowable from the import
record; a first argument's kind is not, and that is why the per-entry argument-kind field is owed rather
than optional.**

`tools/bbrun.sh` builds, **exits non-zero on a failed build**, keeps the binary at
`build-release/kept/<sha256>`, and only then runs -- **`&&` between build and run, because a failed build
followed by a run produces a plausible result, and that class has now cost three incidents.** It earned its
keep on its first use: the build failed on a missing `guest_mem.h` include and **no run happened**, where the
previous pattern would have re-run the old binary and shown me the old fault as if it were an answer.

Boot now: **54 implemented, 414 unbound, called 62**, stop at `4+h9EzwKF4I` (`eboot+0x263b3ca`). **No
"sema:" line has printed, so the would-have-blocked prediction is still untested** -- and it is recorded: if
it fires, the guest is waiting on a thread that cannot exist, and the boot stops there instead of serving
success.

## The attr family landed in one declaration, and the wall it walked into is the one that was pre-registered

14 attr entries landed as one `PB_ATTR_NOOP` declaration (init/destroy/setdetachstate/setinheritsched/
setschedparam/setschedpolicy/setaffinity/get/getaffinity, plus the libScePosix spellings), all MODELLED and
printed. Run `f2ede9ccae55`: **61 implemented, 407 unbound, called 66, and the boot reached the `threads`
milestone -- then faulted at `eboot+0x20b56d2`, address `0x0`.**

**That is the guest's original fault address, which is the panic path, which means the guest took an error
path and panicked.** The pre-registered prediction's second branch: **the refusal did not get handled
single-threaded; the guest died on it.** So `scePthreadCreate` is no longer a diagnostic refusal -- **the
thread decision is now the wall, exactly as predicted, and it is not a surprise because it was written down
before the run.**

Note also: only **one** attr no-op line printed despite fourteen registrations -- so the guest configures
one attribute and immediately proceeds, which is consistent with it going straight at thread creation.

## (b) taken: the wall is named and the boot stops at it -- and the TLS question came back nonzero

`scePthreadCreate` now calls `rt_fatal` with the whole sentence (entry, arg, unmapped TLS, unlocked arena,
single-thread assumption). Run `34b3af572076`: **rc=134, the line above is the last thing the process says.**
The guest's panic path and the unpopulated `__sFILE` are no longer reachable from here, so **nothing after
this point is fabricated state.**

**The static measurement: `fs:` is used 16,854 times in the catalog, `gs:` zero.** `tools/seg_scan.py`, one
pass over all 157,757 catalog entries decoding per entry. The dominant form is `mov rax, qword ptr fs:[0]` --
**the TCB self-pointer** -- at `0x819414`, `0x819f34`, `0x81a00b`, `0x81a21e`, and 16,850 more.

**So the main thread has been reading glibc's TCB since the first guest instruction that touched it.** TLS is
not a threads-only concern and (a) is not "threads need TLS": it is **"the boot has read the wrong TLS all
along"**. That reframes the subsystem decision and it is why the measurement came before the scoping.

## The two TLS measurements, both decisive, and they close the design question

**(1) Displacement histogram: one distinct offset, `fs:[0x0]`, 16,854 times, 0 negative, 0 positive.**
Not "mostly zero" -- **the guest reads exactly one thing through %fs: its own TCB self-pointer.** So the
first guest TLS block needs to be valid, aligned, and have its self-pointer at offset 0, and nothing else
about the layout is load-bearing yet. `PT_TLS` (filesz 0x220 / memsz 0x4a0) sizes the eventual static image;
no offset in the code constrains where the pointer must sit, because there is only one offset and it is 0.

**(2) `wrfsbase` is available and works: CPUID leaf 7 EBX bit 0 set (`ebx = 0x219c91a9`), and a round-trip
test wrote a block and read it back (`fsbase 0x727a4184e740` -> to `0x6231ff781080` -> restored).** So (a) is
feasible with a two-instruction swap per guest<->host transition, **not** an `arch_prctl` per syslib call, and
the architecture does not have to batch guest code between host calls.

**Scope this fixes:** one guest TCB block per modelled thread, self-pointer at offset 0, `wrfsbase` on entry
to guest code, restore glibc's base on entry to any host function that may touch libc (which is all of them,
so the restore belongs in the same place as the trampoline's call, not sprinkled per call).

## Guest TLS is scoped, and the regression criterion is written before the swap is wired in

`runtime/tls.c` + `runtime/tls.h` exist: a 4 KiB aligned guest block whose first eight bytes point at
itself, `rt_tls_init()` probing CPUID leaf 7 EBX bit 0 **and** round-tripping `wrfsbase` (so the check is the
kernel's answer, not the CPU's advertisement), falling back to `arch_prctl` when absent, and
`rt_tls_enter_guest()` / `rt_tls_enter_host()`.

**It is deliberately not wired into the boot yet, and here is the reason in one sentence: the swap is only
correct if the host base is restored before any host code that touches libc, i.e. inside the trampoline at
the one site every syslib call passes through -- and wiring only the guest-entry half would run our own
`fprintf` on glibc's `%fs` while the guest block is installed, which is a fault that looks like a printf bug.**

**Pre-registered regression criterion, before the build: after the swap is wired at both ends, the boot must
reach `scePthreadCreate` with `called 66` and stop there.** Earlier is a TLS-layout error. Later is a finding.
Anything else -- a changed call count, a new fault, a silent success -- is a defect in the wiring, and the
criterion exists because the swap touches no syslib entry: **every number in the run would look unchanged by
construction, so only this criterion can say the swap is neutral.**

## The site audit: four boundaries, not one and not three -- so the wiring waits

Enumerated before wiring, as agreed:

1. **`rt_boot_call` (asm), the only instruction in the tree that calls guest code.** Reached from
   `run_guest`, which has **two** callers: `boot.c:483` (module entry, arguments NULL) and `:494` (main
   entry, `&params` and a callback). One function, two logical entries.
2. **`write_trampoline`: `jmp target` -- guest to host.** There is no return through the trampoline, so the
   restore cannot live there without changing the emitted code.
3. **`on_signal` / `rt_fault`: the failure path**, which runs with whatever `%fs` was installed when control
   was lost, and which itself calls `dladdr`, `printf`, `snprintf`, `addr2line`-style formatting.
4. **`guest_exit`, passed to the guest as argument `b` at `:494` -- a host function pointer handed to guest
   code, called by the guest, and its first statement is `exit_code = code; siglongjmp(...)`.** It touches no
   libc today, which is why nothing has broken; **the moment anyone adds a diagnostic to it, it runs on the
   guest `%fs`.** This is the site neither of us counted, and it is the one the "callbacks" warning was for.

**So the count is four, my expectation was three, and by the rule we agreed the wiring waits.** The finding is
that the boundary is not a place but a *property of who is executing*, and the emission of the trampoline is a
separate edit from the pair around `rt_boot_call`.

## Both one-line sites landed, criterion held, and the stub's register hazard is recorded

`rt_fault`'s first statement is `rt_tls_enter_host()`; `guest_exit` is one line, no pair, because its
`siglongjmp` lands in host code that must find the host base already restored. `tls.c` is now in the
`pbboot` target -- **it was not: `runtime/CMakeLists.txt:12` names files explicitly and I had never added
it, so the module from the previous commit was not compiled at all until now** (the same "a new directory is
not a new file" family, one layer over).

Run: **still stops at `scePthreadCreate` with `called 66`.** The criterion held -- and it proves nothing about
the swap being right, only that the two one-line sites changed nothing, which is what they should do while
`rt_tls_enter_guest()` is still unwired.

**The stub hazard, recorded before the emission changes: `jmp` -> stub -> `call hostfn` -> restore -> `ret`
makes the restore a call into our C, which clobbers `rax`, `rdx`, `rcx`, `r8-r11` and possibly `xmm0` --
exactly where the guest's return value lives, and a 128-bit return legally uses `rax:rdx`.** So the stub saves
`rax`, `rdx` and `xmm0` around the restore and restores them before `ret`; otherwise **the first 64-bit
syslib return comes back garbage only on the TLS-restored path, which reads as a wrong implementation rather
than a wrong stub.** Taking the stub over "call `rt_tls_enter_guest()` at the end of every syslib function":
the second is one site per entry, which is the shape this campaign has spent itself eliminating.

## The stub landed and the criterion fired -- earlier, which is the layout error it was written to catch

`write_trampoline` now emits: `movabs r11, mark; mov byte [r11],1; movabs r10, target; movabs r11, host >fs;
wrfsbase r11; call r10; movabs r11, guest >fs; wrfsbase r11; ret`, `TRAMPOLINE_SIZE` 48 -> 64, and
`rt_tls_init()` runs before any trampoline exists because the stub inlines both bases. **No C call sits between
the guest's jump and the target, so no caller-saved argument register is touched and `r11` is the only scratch
-- free by the ABI.** FSGSBASE absence is a startup refusal, not a second stub: **one stub, one ABI.**

**Run `2e1bef9d1536`: `imports called 1`, then `signal 4` at a host address in `libc.elf`'s mapping.**
Pre-registered criterion said **earlier is a TLS-layout error**, and it is earlier -- 1 call against 66. So the
swap is not neutral and the guest's own use of the TCB is what changes. `rdi 0`, `rsi 0`, `r12/r13` pointing
into the module image; the fault is `SIGILL`, which is an illegal *instruction*, not a bad load -- so the guest
likely took a pointer out of the block or from a path that previously returned glibc's TCB and reached code
that is not code. Next measurement: dump the guest block before the entry call and the first `fs:` access
after it, and read the guest instructions between the first `fs:[0]` read and the fault rather than guessing.

## The TCB-copy experiment: still `SIGILL` at `called 1` -- so the guest does arithmetic on the pointer

A copy of the process's own TCB (first `0x4a0`, self-pointer rewritten to the block) is byte-for-byte what the
guest saw before the swap, and it **still faults at `called 1`, `signal 4`.** So the guest is not reading TCB
fields and finding ours empty: **it takes `fs:[0]` and reaches *below* it**, which is variant II -- `[static
image][pad][TCB]` with `%fs` at the end -- and an aligned block with nothing before it is the wrong shape.

**The detail that argues for variant II over "a different field path": the fault pc ends in the same low bits
in both runs (`...d9a2`, `...89a2`, module bases different).** A fixed guest location reached twice, after a
pointer taken from `%fs`: **the same arithmetic landed on the same static-TLS slot, and what is there is not
code.** Not yet a conclusion -- the two runs used different binaries -- but it is the one number that should be
checked by resolving the pc against the kept artifact's module base before the layout is written.

## Variant II is in: image at `fs - memsz`, no pad, alignment at the end -- and the fault is unchanged

`rt_tls_layout()` builds `[PT_TLS image, memsz bytes][TCB]` in one region, `%fs` = the 64-byte-aligned end of
`memsz + TCB`, image at **exactly `fs - memsz`** (a pad between them would shift every `@tpoff` and move the
fault without fixing it), and the image is initialised from **eboot's own `PT_TLS`** (`rt_elf_tls_segment`,
`objects[0].image + (vaddr - RT_EBOOT_BASE)`). Bytes outside `filesz` are zero, **which is what a freshly
created thread sees on the real machine, so the uninitialised case is now faithful by construction rather than
a modelling decision.** The TCB copy stopgap is deleted.

Run: **still `called 1`, still `signal 4`.** So the layout is now the plausible variant-II arrangement and the
fault persists -- meaning the next question is not the layout but **what the guest does with the value**, and
the pc is the only thing that will say.

**Three runs, three different binaries and three different module bases, fault pc low bytes identical
(`...d9a2`, `...89a2`, `...c9a2`): the differing digits track the base, so the guest reached the same guest
address every time.** The `(no module resolved)` line prints a host address where an offset belongs, which is
the naming bug already logged -- **so the pc must be resolved by hand against each `kept/` artifact's module
base before anything is concluded from it.**

## Site 2 wired: the guest now starts on its own base, and the fault is at the same pc after the same one call

`rt_boot_call` sets the guest base before `call *%rax` and restores the host base after it, using `r11` only
(`rt_tls_guest_base_v` / `rt_tls_host_base_v`, read `(%rip)`), so no caller-saved argument is touched. The run
also now prints which imports were entered: **object 1 import #38 -- a `libc.elf` import, so the guest's first
import call is into the module that then faults.**

Outcome: **`called 1`, `signal 4`, pc low bytes `...79a2` -- the fourth run, fourth binary, same low bytes.**
So this is neither of the two pre-registered outcomes: not 66 (the mid-flight transition was not the cause), and
not 0 (the guest does start on its own block and still gets to its first import call). **What the two
configurations share is the failure point: the first import call is entered and the guest faults immediately
after.** That makes the block the suspect again rather than the transition -- **and it says the pre-swap 66-call
baseline ran entirely on glibc's TCB, so that baseline was never the guest's own state.**

## The fault was my own `wrfsbase` encoding: the F3 prefix was missing

Resolving the pc by arithmetic instead of by guessing: `0x9a2` in the low 12 bits, trampolines at
`tramp + 64 * index`, and the entered import was **#38** -> `0x980 + 0x22`. **Byte 0x22 of the stub is exactly
where `wrfsbase r11` begins** (10 mark + 4 store + 10 movabs r10 + 10 movabs r11). So the SIGILL was the
instruction I emitted, not anything the guest did.

**`wrfsbase` is `F3`-prefixed: `F3 REX.W 0F AE /3`.** Without `F3`, `0F AE DB` is an invalid opcode. The inline
asm in `tls.c` was assembled correctly (the assembler supplies the prefix); **the hand-encoded bytes in the
trampoline were not, and nothing in the build or the run could have said so -- an unrecognised byte is not a
compile error in a buffer I write myself.**

**After the fix: `called 1` -> `called 3`, and the fault moved.** It is now `signal 11`, `address 0x0`, at
**`libc.so.6+0xa8564`** -- *host* glibc, not the guest image and not the stub. So the swap now executes, the
guest gets three import calls, and the next defect is on the host side: **host code is reaching a null TCB,
which is what happens when glibc runs while the guest base is installed.**

## The host-side null, read off the dump I already had

`signal 11`, `address 0x0`, `libc.so.6+0xa8564`, and the registers say what it is: **`rdi 0`, `rsi 0x20b58`,
`rdx 0x1000`, `rcx 0x22`.** That is a glibc string/memory routine called with **a null destination, a plausible
source and a page-sized length** -- `memcpy(NULL, 0x20b58, 0x1000)` in shape. The three entries entered were
**object 1 (libc.elf) imports #23, #38, #39**, so the culprit is one of those bodies copying into a guest pointer
that was null.

`rdi 0` also has an innocent-looking reading I must rule out before changing anything: **the guest itself may be
passing the null**, in which case the body is right to fail and the fault is the guest's own error path -- which
is exactly why the guard below prints the entry index rather than merely asserting.

**Structural fix (next, not yet written): assert `%fs` == host base at the first instruction of every host
handler, in the shared prologue, printing the entry index on mismatch.** Same move as `test_build_graph.py`:
one guard, at the place every path already passes through, permanently catching any future unwired site.

**Class rule adopted: no guest pointer reaches a libc formatter or a libc memory routine directly.** Every
`%s` on guest memory goes through the bounded copy, and every guest buffer is range-checked with
`rt_guest_read_ok`/`rt_guest_write_ok` before it is handed to anything that assumes validity -- **the guest
sending null where a real machine would send a valid pointer is precisely what `data-scratch` and unpopulated
modules produce, so this recurs.**

## The three entered imports, named -- and the null has an owner

`symbols/import_names.csv` names them: **#23 `scePthreadMutexInit`**, **#38 `sceKernelGetProcParam`**,
**#39 `_sceKernelRtldSetApplicationHeapAPI`** -- all `libkernel`, all `implemented`.

So the guest's first three calls are: create a mutex, **ask for the process-parameter block**, **hand the C
library its heap table**. Then it faults in a glibc memory routine with **`rdi 0`, `rsi 0x20b58`, `rdx 0x1000`**.
**`0x20b58` is below `RT_EBOOT_BASE` (`0x400000`), so it is not a mapped guest address** -- and it is exactly the
shape of `sceKernelGetProcParam`'s return being used as a source pointer.

Two candidate causes, and the next run's job is to separate them:
1. **`rt_process.proc_param` is a raw vaddr, not an image-mapped pointer** -- `kernel.c:12` returns it verbatim;
   if it was stored from the segment header without the `RT_EBOOT_BASE` bias, the guest receives `0x20b58` and
   every reader of the block faults on an unmapped address.
2. **The heap table the guest installs at #39 is used to allocate a destination, and it returns 0**, so the
   null is on the destination side and `0x20b58` is a legitimate source.

**The separator is one print**: `rt_process.proc_param` and its vaddr beside `rt_image`, at init and again in
the fault handler. **Not a guess about memcpy semantics -- a value printed before it is used.**

## Outbound pointers now checked like inbound; and the guard that did not fire

`rt_guest_ptr_ok(value, bytes, call)` landed as the outbound direction of the same check (it *is*
`rt_guest_write_ok`, named for the direction -- an address handed to the guest is the same hazard with the
failure deferred into a module we do not own). Callers: `sceKernelGetProcParam`, `memcpy`, `memset`.

**Result 1: `sceKernelGetProcParam` no longer refuses, so `rt_process.proc_param` IS inside the mapped image.
Candidate 1 (missing bias) is refuted, and it is refuted by the guard rather than by a print I had to read.**

**Result 2, the important negative: the `memcpy`/`memset` guards did NOT fire, so the faulting copy is not one of
our registered entries.** `rsp`/`rbp` are host-stack addresses, so the fault is inside a host body; `rdi 0`,
`rsi 0x20b58`, `rdx 0x1000`. **A guard placed where I assumed the copy happened proved the assumption wrong by
staying silent -- and a refusal that does not fire is evidence about reachability, not about correctness.**

**Next, and it is the one the companion asked for first: `rt_syslib_in_flight`, an index stored by the shared
trampoline prologue (`mov dword [rip+idx], imm32`) and printed by the fault handler.** Ten bytes in a stub with
sixteen spare. **Then the body is named instead of inferred from a register set, and no register can tell a
caller's NULL from my arithmetic after the fact.**

## In flight, named: #23 scePthreadMutexInit -- and the null is produced inside it

The instrument works and it is not the answer I expected: **`in flight: #1048599`** (packed `k << 20 | i` =
object 1, import 23), **args `0x8800bfcd0 0 0x774b3cffff20`**. So the fault is inside
**`scePthreadMutexInit`**, whose first argument is a valid libc-image pointer and whose **second is NULL**.
#38 and #39 completed and returned; the heap and proc-param hypotheses were never on the fault path.

**And the body is correct about the NULL attr** -- `mutex_init` does `attr ? *attr : NULL` and substitutes
`TYPE_ERRORCHECK` -- so the null that glibc receives is **not the guest's argument, and not an unguarded
dereference of `attr`**. It is produced downstream, inside what this body calls, or on its return path.

**What is left is a host stack walk**: `rbp` is a host address and the chain is intact in the dump, so four
return addresses resolved through `dladdr` name the frame that called the copy. **That is the next instrument,
and it is the only one that can distinguish "inside `mutex_create`" from "inside glibc's own init".**

## Frames: the fault is inside `malloc`, not inside `pthread_mutex_init`

**Pre-registered reading, then the output.** Frame 1 was expected to be a glibc memory routine and frame 2
either `pthread_mutex_init` ("glibc consumes a null we handed it") or `mutex_init` ("the copy is ours").

    frame 0 build-release/runtime/pbboot+0x7389 (?)          <- our signal handler
    frame 1 libc.so.6+0x419c0 (?)                            <- the restorer/trampoline
    frame 2 libc.so.6+0xa8564 (?)                            <- the faulting instruction
    frame 3 libc.so.6+0xa8b5d (?)
    frame 4 libc.so.6+0xab53c (?)
    frame 5 libc.so.6+0xabd86 (malloc)
    in flight: #1048599 args 0x8800bfcd0 0 0x756ff2ffff20

**Neither branch fired: frame 5 is `malloc`.** The interrupted chain is `mutex_create`'s `malloc` and four frames
of glibc's own allocator internals. **So `pthread_mutex_init` was never reached, our body has not yet written to
the guest pointer, and the null destination is inside the allocator, not in an argument we passed.**

**And the attr question is settled by the recorded arguments, not by reading the body: `rsi` is exactly 0, so
`attr` is NULL and the `TYPE_ERRORCHECK` substitution is the path taken.** The indirect shape (a non-null attr
whose struct holds nulls) needs `rsi != 0` and cannot occur in this call.

**What that leaves, and it is a smaller question: glibc's allocator is being entered with a broken state**, which
is what a C library whose `%fs` was a *different* TCB for part of its life would look like -- tcache and the
arena list live off `%fs`. **The test that separates "allocator broken by the earlier pre-swap entries" from
"this call specifically": allocate and free 48 bytes at the top of the `#38` body, before anything else touches
the heap, and see whether it faults there instead.**

## Measured: inside a syslib body, `%fs` is the GUEST block, not the host base

    in-body fs 0x63e9d158dc40                      <- equal to the guest block
    fs host 0x72972f4a1740 guest 0x63e9d158dc40    <- and the host base is a different address

**So the swap does not hold at the body's first instruction**, while the `in flight` index written by the same
stub *does* hold -- same emitted bytes, one effect visible and one not. Two explanations remain:
(i) the write executes and something restores the guest base before our body's first statement; (ii) the stub
executed is not the stub `write_trampoline` emits, and the index is set by another path (the "two emission
shapes" note). **The readback guard settles (i) versus (ii) in one build: `rdfsbase` immediately after each
`wrfsbase` in the stub, stored to a global and printed in the report.**

**This also re-reads the allocator crash: `malloc` works at init (`malloc(48) = 0x611845587490`) and the same
call inside a body faults -- because glibc's tcache and arena pointers live off `%fs`, and `%fs` there is our
guest block, which holds a self-pointer and zeros.** The heap probe moved the fault to the *first* heap use in
guest-triggered code and named it `in flight: #38`, which is what a wrong `%fs` predicts and what "corrupted
heap" does not.

## The stub's own readback: the host imm64 is correct, the `wrfsbase` executes, and `%fs` is unchanged

    stub obj 1 #38: ... 49 bb 40 17 80 3e a8 77 00 00  f3 49 0f ae db  50 49 bb ...
                             ^ movabs r11, 0x77a83e801740   ^ wrfsbase r11  ^ push rax
    stub readback 0x651e4ea01c80 (host base 0x77a83e801740)      <- NOT host
    in-body fs 0x651e4ea01c80                                    <- the guest block
    fs host 0x77a83e801740 guest 0x651e4ea01c80 live 0x77a83e801740   <- host, in the handler

**So: the baked value is right (case 3 of the three, not a stale emitter), the `wrfsbase` is emitted with its
mandatory F3 and the right ModRM, and the base is unchanged five bytes later.** And the *handler's* `wrfsbase`
does take, since the report reads the host base while the body left `%fs` on the guest block.

**And `probe_fsgsbase()` cannot fail.** It reads `%fs`, writes that same value back, reads again, and sets
`have_wrfsbase = 1` when the two are equal -- true for a working write and for a silently ignored one.
It is the `promote.py` shape: a check whose failure mode is unreachable, gating a startup refusal that has
therefore never fired.

## Stride refuted, slot proved, and the write still does not take: it is a code-location fact

All four uses of `TRAMPOLINE_SIZE` read the same macro (`:53`, `:390` binding, `:510` mmap, `:519` emitter), so a
guest jumping into the middle of a stub is ruled out statically. The `which` token then closed the other half:

    probe says wrfsbase WORKS          <- discriminating probe (writes a DIFFERENT value, restores)
    stub readback 0x636645ce0c80 which #1048614 (host base 0x743f7f001740)

`#1048614` = object 1, import 38 -- **the stub that ran is the stub I dumped.** Its host-base imm64 is correct,
its `wrfsbase` carries F3 and /3-r11, the instruction is reached (the `which` store after it executes), and five
bytes later `%fs` is still the guest block -- while the same instruction works at init and in the handler.

**Next discriminator, and it separates the two remaining causes: emit the same six bytes into an ordinary
malloc'd RWX buffer in `main` and call it.** If it no-ops there too, the cause is the hand-emitted form or the
mapping; if it works, the cause is something about the stub region or the caller. **The instruction is the same
in both places, so whichever variable moves between them is the one that matters.**

## The address-0 fault was `movaps`, not a format mismatch: the guest's stack was misaligned at our call

    8ea99:  0f 29 85 40 ff ff ff   movaps %xmm0,-0xc0(%rbp)

An x86 #GP reports `si_addr = 0` because it is not a page fault, and `movaps` requires 16-byte alignment --
so "fault at address 0 inside glibc" was a misaligned `rsp` at the body's entry, which is exactly what a guest
call site supplies. The fix is in the stub (`push rbx; mov rbx,rsp; and rsp,-16; call; mov rsp,rbx; pop rbx`),
with **rbx** carrying the guest's rsp because it is callee-saved and because a global would be wrong the moment
a body re-enters another import -- the global version was tried first and hung at libc.elf+0x59ca1.

Result: the `scePthreadCreate` wall now prints its full sentence and stops the run on purpose.

## memsz verified against the headers, not against the strings

    libc.elf     PT_TLS file 0xbc018 vaddr 0xb8018 filesz 0x220 memsz 0x4a0   <- what tls.c and the wall use
    eboot.elf    PT_TLS file 0x50e0040 vaddr 0x50dc040 filesz 0x0 memsz 0x750 <- never read by any code
    libSceFios2  PT_TLS file 0x50018  vaddr 0x4c018  filesz 0x0 memsz 0x40   <- never read by any code

The `0xa4a` in my last report was a transposition **I** typed; the source, the wall and the ELF agree on `0x4a0`.
But the check surfaced the real fact: **three modules carry PT_TLS and the runtime models one of them**, and the
layout's `guest_memsz` starts as a hardcoded `0x4a0` default rather than a value read from the object it is
laying out -- the same shape as every other constant in this runtime that turned out to be a memory.
