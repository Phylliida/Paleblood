# Decisions owed: five questions, five minutes

Everything below blocks work I am not allowed to do unilaterally. Each line: what it unblocks,
what I recommend, and what it costs if I am wrong. **The wall is 30 approvals against 21,086
clean rows**; four of these five questions are what stand between here and reviewing the families
that already have evidence.

**The five "unblocks" figures are not additive.** They sum to 28,797 against a clean-row
population of **21,086**: the `ret` members live inside the four families named in question 1, and
the SSE answer changes which of them can ship at all. **Union, not sum -- the ceiling is 21,086,
and each answer releases a subset of it.** A reader who adds them gets a number larger than
exists, which is the defect this campaign keeps paying for.

---

## 1. Approve the four family shape packets?

**Unblocks:** ~16,889 generated rows across four one-body families -- the compiler's static-guard
one-shot (1,117 members), `xor eax,eax; ret` (4,721), `mov eax,K; ret` (2,978),
`lea rax,[rip+K]; ret` (8,073). Each packet states its own limit in its own pages rather than
leaving it to the reviewer.

**Recommend: yes, all four.** Each family is one distinct body repeated, each carry a
machine-checked transcription (re-decode the member's own bytes, recompute the constant, compare
byte for byte -- two independent derivations), and each approval is pinned to a member-set hash,
so **an approval goes stale by itself** when a member changes.

**Cost if wrong:** a wrong rule is signed once and fans out over thousands of rows. Bounded by the
fact that the member-set hash re-opens the decision when the shape changes, and by the packets'
own stated limits (e.g. `lea` returns a guest address as a host integer: coverage, not a semantic
bridge; dereference untested).

---

## 2. `ret` (7,761 members, one body): naked `asm("ret")` plus a one-byte assertion, or a written exclusion?

**Unblocks:** 7,761 rows -- the largest single family in the tree. C has no pass-through
expression, so a body must either be naked asm or be excluded by policy.

**Recommend: naked asm, with a test asserting the compiled body is exactly one byte `c3`.**
Measured with clang: `-O2` emits exactly one `c3` for **both** candidates, so the assertion cannot
distinguish them -- **what naked buys is independence from the optimisation level**, because a
`void f(void){}` body is only a `ret` by an unstated gcc/clang habit. That is the entire argument,
and it is worth 7,761 rows.

**Cost if wrong:** nothing at runtime; the risk is that an explicit construct without an assertion
about its output has *moved* the trust rather than removed it. The assertion is what closes that.

---

## 3. `scope` in `reviews.csv`: one approval per function, or per shape?

**Unblocks:** 3,619 members of the `mov rax,[rdi+K]; ret` family, and every future family.

**Recommend: `shape`, written out as a column.** The economics are stark: **121 rules over 3,619
members, versus 3,619 signatures.** Both sentences must always be printed together, though --
**the fan-out gains 3,619 rows and the information gain is 121** -- or the number is a lie.

**Cost if wrong:** an approval that reads like per-member review approves less than the reader
believes. Mitigated because the per-member part is machine-checked transcription over every
member's own bytes, which is stronger than a human reading 3,619 numbers.

---

## 4. Where does `check_readable`'s SSE line sit?

**Unblocks:** ~300 tier entries (if strict) versus **most of 7,791** (if relaxed) -- measured
zero-SIMD density is **32.2%**, and ≤0.05 is **60.3%**.

**Recommend: allow low-density vector code (≤0.05)**, i.e. set the line at a threshold rather than
at zero. The tier's median SIMD density is **2.6%** and **47.4% of it carries ≤2% vector code**;
the binary filter collapsed a distribution whose mass sits near zero, and my fear (32.7% → 32.2%)
was larger than the fact.

**Cost if wrong:** bodies carrying incidental SSE get hand-translated with more room for error.
Bounded by the differential: a wrong body fails against the original, and the tier is destined for
generated bodies anyway.

---

## 5. A second approver for `zero_init`? (0 of 528 approved)

**Unblocks:** 528 rows, and the structural rule that the approving session must not be the
authoring one -- which makes `zero_init` **impossible for me to complete alone by construction.**

**Recommend:** either designate the companion session as second approver, or accept **machine-
checked evidence as the second signature** for `zero_init` specifically (the case set plus a
differential that distinguishes zero from nonzero), leaving human approval for families where a
shape claim is involved.

**Cost if wrong:** self-approval weakens the independence property the repo has been careful
about. That is why this one stays a question rather than a decision.

---

Recorded before the session boundary so the answer is a decision rather than a reading task.
Numbers here are the ones the tools print; where a figure is carried rather than measured, it is
labelled as carried in the packet it comes from.

## Delegation to host libc: the fork the 703-name table created

703 named imports is a strategy question, not a task list. One address space, and guest addresses
are already host-dereferenceable, so a large class of these could be delegated to host libc rather
than hand-written.

**The line, drawn once and applied per family:**

- **Delegate** -- stream, string and formatting calls: stateless, no cross-ABI structs, no ownership
  handed across the boundary (`memcpy`, `strlen`, `printf`, `vsnprintf`, and the `_Stdout` /
  `_Stderr` objects only if they are used as opaque handles).
- **Never delegate** -- the allocator and `FILE*` interop. libc.elf runs its own heap; two
  allocators over one region corrupt silently, and a `FILE*` from one libc passed to the other is
  the same failure with a different signature. `malloc`/`free`/`realloc` stay ours, and so does
  anything that hands a stream object across.

Status: **unanswered, and now hot** -- it gates a family rather than a function. The answer needed
is yes/no on the split above, not on delegation in general.

## Three import counts, three populations -- do not quote any of them alone

Measured in one call, none of the three agreeing:

| figure | population |
|---|---|
| 686 | eboot's imports, as the boot reports |
| 747 | NIDs in `docs/bind-order-eboot.txt`, which spans more than eboot |
| 673 / 76 / 80 | rows in `symbols/imports.csv` for eboot / libc.elf / libSceFios2.elf |

The residual `747 - 686 = 61` is **not** libc.elf's import count: `imports.csv` gives libc.elf 76.
So the span hypothesis is unconfirmed and the three figures must be reconciled to one partition
before any of them is quoted, exactly as `21,130` and the 652 were.

## Captures: the verifier works and there is no reachable subject (measured 2026-10-24)

Asked for a capture, I built the cheapest route and it returned a measured zero, not a
failed attempt. Counts are from one boot run (`pbboot sha256 49bed5b7…`, plugin
`735225e5…`) with `BB_PROBES` over **613 of 1,737** hook-mode sites that can carry a
5-byte jump (`1,120` refused for RIP-relative displacement, `4` for a branch in the
prologue), plus one hand-placed control at the guest entry `0x004000a0`:

* control fired **1** — bytes `554889e54157` read by vaddr from `e_entry`, so the
  address space is confirmed by a count and not by a row;
* every catalogued body counted **0**, including all **19** hook sites within 1 MB of a
  PC the guest is known to have executed;
* hook sites inside the boot/panic band `0x02080000–0x020c0000`: **zero**. The nearest
  is `0x02113c30`.

So `functions.csv` lists none of the code a boot run executes: the guest walls at
`scePthreadCreate` (its own `DL_PANIC`, EAGAIN on threads) before any catalogued body
runs. The ladder to a `verified` row therefore runs **through threads**, not through
the capture machinery — which, having been repaired this session, now records.

Two consequences, neither of which is a decision I can take:

1. `../data/catalog.sqlite3` already holds `verification_state` for exactly the **528**
   `zero_init` rows — `fixture loaded`, `original passed`, `differential passed`,
   `coverage available`, `mismatch none`, 8 cases each. That is differential evidence,
   and by the engine's own contract it moves no tier. Whether it may count as a witness
   is the user's call, and it is the only path to a row that does not require the
   threads wall to fall first.
2. The engine's own metadata says `functions_with_capture_provenance 0` and `edges 0`,
   so no capture provenance exists anywhere in this project yet — the first one will
   also be the first test of `promote.py`'s in-game path.

Suite state at `cf92f2d`, both binaries set and `BB_LOADER` = `build-release/runtime/libpbloader.so`:
`Ran 535 / 497.174 s / 8F 2E 1S`, and all ten are pre-existing — the same modules are red
at `60fd524` in a worktree. (`BB_LOADER` pointed at `pbboot`, a PIE the harness cannot
`dlopen`, manufactures 45 failures and 8 errors in the same suite.)

## The boot's first walls, once the plugin stops refusing (measured 2026-10-24)

Before this slice, one 41-byte static guard on a full stub page made `install_hook` return -1,
which refused `bbgame_init`, which refused the boot — so the only evidence-capable configuration
never ran a guest byte. `runtime/plugin.c` now treats a site it cannot PLACE (RT_INSTALL_NO_ROOM)
as a printed gap and keeps installing; a site it cannot instrument HONESTLY still stops the
install.

Reached with `BB_PLUGIN=build-release/game/libbbgame.so`, rc=4:

1. `bbgame: installed 40 of 1737 selected, 1697 not instrumented for page room` — the stub
   allocator is ONE 4 KiB page and 40 hooks is its whole capacity (~101 B/site). This is the
   hook population's ceiling, printed, and it is the reason a capture can host at most 40 sites.
2. `eboot calls libc tsvEmnenz48` = `__cxa_atexit` (libc ordinal 41) — now MODELLED with a real
   64-entry table shared with `atexit`; a full table refuses with -1; the exit report prints
   `atexit: N handler(s) registered, 0 run` because the runtime does not re-enter guest code
   after the exit import. Serving it moved the wall.
3. `eboot calls libc sqWytnhYdEg` = `_ZNSt8ios_base4InitC1Ev` = `std::ios_base::Init::Init()`
   (libc ordinal 259). **This is where the boot stops now.**

   Measured afterwards, and it decides what "modelling" would even mean: of the target's 34
   mangled libc imports, **six are the standard stream OBJECTS** -- `_ZSt3cin` (26), `_ZSt4cerr`
   (27), `_ZSt5wcerr` (28), `_ZSt4wcin` (29), `_ZSt4cout` (30), `_ZSt5wcout` (31) -- plus both
   `Init` constructors (259 narrow, 260 wide), `ios_base::Init`'s destructor (10), `_Locinfo`,
   vtables and typeinfo. **There is not one stream operation among them**: no `operator<<`, no
   `__ostream_insert`, no `basic_ios` method.

   So `Init`'s entire observable effect IS the existence of those six objects, and a `modelled`
   entry that records the call and returns 0 while the objects stay unbound is `noop` wearing
   `modelled`'s name -- the collision class this campaign keeps paying for. **The unit of
   modelling is the six objects, not the constructor.** Modelling them requires SceLibc's exact
   `basic_ostream`/`basic_ios` layout and vtable ABI, which this repository does not have and has
   no note about; fabricating a layout to satisfy the gate is the default-0 defect one tier up.

   Options, now priced: (a) refuse by name and keep the wall (current) -- honest, blocks the boot;
   (b) host a real C++ stream object whose ABI matches SceLibc's -- needs the vintage/layout
   question answered first; (c) map six zero-filled objects and let a use fault with a nameable
   PC -- changes an unbound-import fault into a *constructed-looking* fault, which is worse than
   the current state because it prices a missing model as an addressing bug. **(c) is refused.**
   Not decided between (a) and (b).

The import census moved by exactly one and closes: 97 = 60 real + 26 modelled + 5 noop + 6 refused.

## The unbound-data pages are readable zeroes, and the first thing the guest reads is its canary (measured 2026-10-24)

`boot.c` gives every unbound DATA import its own page of private zeroed `data`
(`o->data + 4096*index`, `(imports + 1) * 4096` anonymous RW). That is enough to give an unbound object
import a unique address, and it is exactly what makes its use INVISIBLE: a read returns zeroes and the
boot proceeds. `BB_DATA_GUARD=1` now `mprotect`s those pages `PROT_NONE` and prints the whole slot table,
so a dereference faults at the object's own address and the address selects one printed row.

Two arms, same build, `BB_PLUGIN=build-release/game/libbbgame.so`:

  plain:              rc=4, next wall `libc WkkeywLJcgU` -- no fault, nothing to see
  BB_DATA_GUARD=1:    rc=1, signal 11 at `eboot+0x2083ff7`, address = a guarded slot

And the slot is named, by address, against the printed table:

  guard slot <addr>       libkernel f7uOxY9mM1U = `__stack_chk_guard`   <- faulted here
  guard slot <addr+4096>  libc      P330P3dFF68 = `Need_sceLibc`        <- its neighbour

Three facts, each with a witness:

1. **The guest reads `__stack_chk_guard` at `eboot+0x2083ff7` before it reaches the next import wall.**
   Today that read returns zero, so the canary loaded from the slot and the canary compared at function
   exit are both zero, and **every stack-protector check in this guest silently passes**. That is the
   permissive-zero class, measured rather than suspected, and it is `noop`-by-accident: the behaviour is
   the zeroing of anonymous memory, not a decision anyone made.
2. **It is not a wall.** The plain arm walks past it to `WkkeywLJcgU`, which is why it was never seen:
   the defect produces no output, no fault and no missing call until something depends on the value.
3. **`Need_sceLibc` (libc ordinal 0) is the literal next slot** and is still unbound — the same NID this
   campaign has carried for sessions as "no guessed implementation, ever". It is a data import, and the
   syslib table can only supply CODE (`bind_import` returns `s->fn`), so no current mechanism can serve it.

Pre-registered fix, not yet written: a **data-provider table** -- (library, nid, address, size) consulted
in the import loop for DATA imports -- with two entries that are not guesses:
`__stack_chk_guard` -> 8 bytes of runtime-owned storage holding a random nonzero value (low byte 0, as the
ABI's terminator convention requires), so a real smash is caught; and `Need_sceLibc` -> bound only once
its semantics are known, still refused until then. The canary's value must be ONE value per process and
printed once at startup, because two copies of a canary are two different claims.

## The canary is served, and the guard is the default (measured 2026-10-25)

The provider table exists: `boot.c`'s `data_providers[]`, consulted only for DATA imports, because a data
import needs an ADDRESS and the syslib table supplies function pointers. First row, and the only one:
`libkernel f7uOxY9mM1U` (`__stack_chk_guard`) -> 8 runtime-owned bytes holding a host-CSPRNG value with
the ABI's zero terminator byte, one value per process, **not printed** (a canary that appears in a log
protects nothing). Declared MODELLED in the comment, with the difference stated: the guest gets a canary
that FIRES, which is what the ground truth requires; it does not get the value the real kernel would have
chosen, and that is the whole of the difference.

What this settles, and what it does not:

1. **The stack protector is a DETECTOR, not a preventer.** With the canary served as zeroes, no smash was
   made possible -- smashes stopped being REPORTABLE. So every boot this campaign has run reached its wall
   under a disabled detector, and the reach measured in those runs is evidence about **control flow only,
   never about memory**. That does not retract any slice; it bounds what they were evidence of.
2. **The guard is now the DEFAULT.** `BB_DATA_PERMISSIVE=1` restores the zero pages and prints that it has
   done so. A permissive run is a run with a detector removed and must announce itself, because "safety off
   by default" is the shape this campaign refused once already (`--dry-run` opt-in; a default-0 image base).
3. **Measured after the provider: no other unbound data import is touched.** Guarded arm now reaches
   `libc WkkeywLJcgU` (rc=4) exactly as the permissive arm does, with `ios_base::Init` called once and zero
   faults -- so among eboot's 20 data imports, the canary is the only one read before that wall. The next
   unbound-data read will fault BY NAME, which is the point of the default.

Scope claim, on every percentage this tree prints: `157,757` is a CATALOGUE FLOOR, not a total. Executed
code now exists with a witness outside it -- `eboot+0x2083ff7` and `eboot+0x20b56d2`, both inside
`0x02080000-0x020c0000`, where the catalogue holds zero rows. SCOPE is `landed / 157,757` and therefore an
upper bound on coverage, stated as one.

## The wide-string path, and the width this target actually uses (measured 2026-10-25)

**The data-provider surface is closed for this reach, by measurement:** of eboot's 20 data imports, exactly
one is read before the current wall. `data_providers[]` stays one row until something reads a second one,
and the guard names it when that happens. Consequence worth stating: `Need_sceLibc` (`P330P3dFF68`) may
never need resolving on this path at all -- so "no guessed implementation, ever" stays a RULE rather than a
blocker, which is a different position from where it sat two slices ago.

`wcslen` (libc, WkkeywLJcgU) landed, and the assumption printed with it **refuted itself inside one run**:

  first version, 4-byte walk:  34,747 code units, first unit 0x00650074
  second version, 2-byte walk:     28 code units, first unit 0x0074

`0x00650074` is the bytes `74 00 65 00` -- UTF-16LE "te" -- so **this target's `wchar_t` is 2 bytes**, and
the first version did not return "half a length": it walked ~139 KB past a 28-unit string and terminated by
luck in adjacent mapped memory (a UTF-16 NUL is only half of a 4-byte unit, so the walk never sees a
terminator where the string ends). Nothing faulted. The guest used the number.

Then `wmemcpy` (libc, fL3O02ypZFE), the wall that wcslen left behind, and it corroborates the width from a
second direction: the guest passed **n = 28 units**, exactly the length `wcslen` returned. Two functions
agreeing on 28 is not two readings of one table -- it is the guest's own call convention confirming the
unit size.

Next wall, and it is a different shape from every wall so far: **`Q3VBxCXhUHs` = `memcpy` in
`libSceLibcInternal`, ordinal 9** -- not `libc`. The syslib table is keyed by (library, symbol) and every
missing wall until now happened to share the library. So the next decision is not an implementation but a
table question: whether another library's `memcpy` is an explicit alias row with a stated reason, or a
wildcard, and the answer is the explicit row -- a wildcard across libraries would bind every same-named
symbol in every library, which is a claim nobody measured.

## The wide-path cluster, and the two walls whose right answer is an implementation (measured 2026-10-25)

Landed this sitting, each with the print that makes its assumption falsifiable: `memcpy`/`memset` **aliased**
under `libc` (eboot imports them from `libc`; the bodies were registered only under `libSceLibcInternal` for
`libSceFios2` -- an alias row asserts a shared CONTRACT, ISO C 7.24.2.1/7.24.6.1, never a shared
implementation, and a wildcard over libraries would hide exactly that difference); `_FSin` (libc 38), the
**first wall whose right answer is an implementation's rounding rather than a standard's text** -- modelled on
the host's `sinf`, with the `_F`-prefix-is-a-fast-variant reading named as a HYPOTHESIS, and the first call
publishing `x=-1.5708 -> -1` so the float width is falsifiable from the log; `wmemcmp` (libc 245) and
`wcschr` (libc 243), both on the measured 2-byte unit.

The guest is now demonstrably parsing a **wide path**: `wcslen` 28 units (`'t'`), `wmemcpy` n=28 (the same
28, from the guest's own call), `wmemcmp` n=6 with the first difference at unit 0, then `wcschr` for `0x002f`
(`/`) which is **absent** from a 1-unit string.

Two operational facts that cost time: a host math call needs **`m` named in `target_link_libraries`**, and an
unlisted library fails at **link** time, which **deletes the artifact** rather than leaving a stale one --
`rc=127`, indistinguishable from a missing binary to anyone who does not read the build line. And my own grep
pattern `lib[a-z]*` **cannot match `libSceLibcInternal`** (uppercase `S`), so it silently reported the wall's
library as `libc`; a pattern that cannot express the field's alphabet cannot see the distinction under test.

## The three FILE objects: measured, located, and REFUSED (2026-10-25)

`NEXT.md:482-488` carries the measurement, in this tree and not in a companion's memory: `0xbf060`,
`0xbf160`, `0xbf260` -- `0xbf060 + k*0x100`, i.e. **three `__sFILE` objects of size 0x100 exactly**, with
`_Stdin 0xbf060 (__sF[0], _file 0)`. Ordinals, checked against `symbols/import_names.csv`: `_Stdout` is
**libSceLibcInternal 3**, while `_Stderr` is **libc 4** and `_Stdin` is **libc 9** -- three objects across two
libraries, so the data-provider table needs rows under both.

**They are still not provided, and that is a decision, not an omission.** A zeroed 0x100-byte object would be
a *plausible* FILE: `_flags=0`, `_p=NULL`, and the first libc routine to touch it would either allocate into
fields it believes exist or write through a null buffer. That is the "zero page gives an address and hides its
use" defect with the object's size added to make it more convincing. What the runtime can honestly do is what
it already does: leave the slot unbound, so the guard **faults at that object's own page and names it**. A
real model is a decision owed, and it needs the fields -- `_flags`, `_p`, `_r`, `_w`, `_cookie` -- not a size.
