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

## _Getpctype: a wall converted into a named unknown (2026-10-25)

The wide-path dispatcher's next request after `wcsncmp` (which compared `/` against `s`: `n=6, stopped at
unit 0, 0x002f/0x0073 -> -1`) was `_Getpctype` (libc 65) -- the locale's character-classification table.

**Refused by name, deliberately.** The pointer is not the problem; the ENCODING of the flags the guest tests
against it is a target ABI this tree does not establish. Returning the host's table would classify characters
by another libc's bits: every test succeeds, every answer is plausible, nothing faults -- the most expensive
failure shape available.

The distinction this buys: an unbound import says "not done"; a named refusal says **which fact is missing and
how to measure it**. The measurement is the guest's own call sites -- the masks it tests are inlined
immediates beside its call, so a static read of those sites fixes the encoding from evidence, not from a
remembered header. That is a candidate, not a guess: `RT_SYSLIB_UNRESOLVED` prints the reason and aborts
(rc=134), so the wall cannot be walked past silently.

## The stream objects: an accepted GAP, and the guest's static use is proven (2026-10-25)

`ios_base::Init::Init` and `_Winit::_Winit` stay `RT_SYSLIB_NOOP` and the print now says **GAP, not model**.
Both are correct to leave: the real module bodies construct eight BSS objects (`cin`/`wcin` 104 bytes, six
output-side 96), all with relocations of no kind pointing at them -- the constructors write every pointer at
runtime, so **no loader fixup can create them**. Kimisupport's measurements (module-local to
`data/bb/elf/libc.elf`: Init `0x598c0` len 1049, guard `0xb89f0`, objects `0xd1480`/`0xd14e8`/`0xd1548`/
`0xd15a8`; `_Winit` `0x5c280`, guard `0xb8a70`, `0xd18a8`/`0xd1910`/`0xd1970`/`0xd19d0`) are for **this**
build and must not be transplanted to the retrobios `libSceLibcInternal.sprx`. Delegatehelper's ABI answer:
Dinkumware/Plauger V6.40, Sony-built, Itanium-mangled, FreeBSD libc underneath -- so address-only binding is
not ABI-defensible in general.

The use is static and proven: eboot reads `cin`'s GOT slot (`0x53e45f8`) at `eboot+0x1fa5437`, loads `[cin]`,
then `[vptr-0x18]`, then calls a virtual through the embedded streambuf at `cin+0x50`; all six slots are
referenced at `0x20e2681..0x20e26be`. **A zero page faults at `-0x18`, which is not attributable to the
import; `BB_DATA_GUARD` (default on) faults at the import's own page and names it.** Hence choice (1) of the
three: keep the printed gap, keep the guard fail-closed, and record that the first stream use is expected to
fault at the import's own guarded page. (2) refuse the constructor by name and (3) the real V6.40 object
graph remain priced, unbuilt.

Sentinels that must not become zeroes when they are served: `_ZSt7_BADOFF` (`0x53e4370`, must be **-1**;
a zero is a *valid* offset), `_ZSt7nothrow` (`0x53e4558`), `_ZTIi` (`0x53e4508`).

## The rt_syslib table has no duplicate detection, and one duplicate is a dead refusal (2026-10-25)

`boot.c:531` scans the `rt_syslib` linker section and keeps the **first** match for (library, symbol); the
loop binds and stops. There is no duplicate check anywhere, so two registrations for one key mean **link
order decides, silently**. Measured from `nm -n` on `pbboot`: 108 section entries. Two keys are registered
twice:

- `libc`/`memset` at section indices 13 (`kernel.c:97`, added by `d62ae07`) and 54 (`libc.c:225`, from
  `7ff79e6`). Same function, so no behaviour changed -- but **the `d62ae07` message overclaims**: memset was
  already served under `libc`; **only `memcpy` was the gap**. The duplicate (mine) is now removed.
- `libkernel`/`scePthreadCreate` at indices 36 (`RT_SYSLIB_MODELLED`, `kernel_thread.c:182`, returns
  0x80020023 EAGAIN) and 88 (`RT_SYSLIB_UNRESOLVED`, `pthread_sema.c:167`, refuses and names three
  blockers). **The MODELLED row wins**, which is consistent with the guest's own Dantelion2 panic quoting
  EAGAIN. The refusal row is therefore **dead code carrying a policy that cannot fire** -- a refusal that
  is not on the path is advice. The choice between the two policies is a behaviour change and is not taken
  here; card `055` carries it.

### Correction, same slice: the "duplicate" was a NAME collision, not one body twice

My duplicate detector collected `(library, symbol)` and never the function pointer, so "same function" was an
assertion about a key I had not read. Measured: **two `static` functions both named `libc_memset`**, one per
translation unit -- `kernel.c:90` (plain, registered under `libSceLibcInternal` and serving `libc`) and
`libc.c:226` (range-checked: resolves the pointer through guest/image space and refuses one it cannot
classify). Deleting the `kernel.c` row silently promoted the range-checked body, whose first refusal is
`memset: the pointer is above the mapping`, and the boot aborted **before** `_Getpctype`. The build was also
stale on the first retry (attribute after definition), and the stale binary reproduced the pre-fix failure
exactly. Restored: `rc=134` at `_Getpctype`, `above the mapping` hits **0**.

The open question, card `055`: should a guest heap pointer outside the loaded image be writable through
`memset`? Until it is decided, `libc`/`memset` resolves to the plain body and the range-checked one compiles
unused, with its proof kept because that is the design the guest memory model eventually wants.

**Scope of the alias sweep** (`026`): parsed **94** registrations from `runtime/syslib/*.c` against **95**
macro invocations in `runtime/` and **108** entries in the linked `rt_syslib` section. So "0 alias candidates"
is a statement about 87% of the table; the 13-entry difference is **unexplained and recorded as such**, not
rounded to zero (card `057`).

## The 13 are named: `PB_ATTR_NOOP` is a registration macro a `RT_SYSLIB*` grep cannot see (2026-10-25)

`pthread_sema.c` registers **14** attr handlers through `PB_ATTR_NOOP(lib, sym)` -- 15 textual matches,
`RT_SYSLIB_MODELLED` around a generated `attr_noop_<sym>`. Six of them duplicate keys that
`kernel_thread.c` registers with **real** bodies, and `kernel_thread.c` sits earlier in the section, so all
six have never run. They are removed; the eight unique ones stay (14 call sites - 6 removed).

That is the whole discrepancy, and it was never mysterious. One textual match is the `#define` line itself,
so the derivation is `94 - 1 + 14 = 107` registrations: the grep counts the macro **body** once and the
preprocessor expands it 14 times (kimisupport's derivation, confirmed per object: `pthread_sema.c.o` holds 22
entry symbols, 8 direct + 14 generated). The parser that reported 94 used one macro's spelling as the
definition of the table -- the same defect as `store_k`, one level up.

**Correction of my own count**: the "108" was an unanchored `grep -cE "rt_syslib_(unresolved_)?entry"` and
counted one extra symbol. Anchored to `entry_<digits>$`, the binary holds exactly 100 at this commit, which is
`107 - 7` (1 scePthreadCreate row, 6 dead attribute no-ops). An unanchored pattern is not a count of a set --
the same defect as `startswith` against `fullmatch`, now three times in this campaign.

**Entry count now closes by subtraction**: 108 at the start of the slice, **100** measured after it --
`-1` (`libc`/memset key collapsed to one body), `-1` (`libkernel`/scePthreadCreate collapsed), `-6` (the
dead no-ops). No unexplained remainder.

## Two registrations of one key now refuse at startup, with a control that fires (2026-10-25)

`rt_syslib_check_unique()` walks the section, compares `(library, symbol)` in the **binary's** strings rather
than in source text, prints both section indices and both function pointers for every pair, and `boot.c`
refuses when the count is nonzero -- a duplicate resolving by link order is a policy nobody chose, and the
second registration is the one that has never run. `test_syslib` calls it on a synthetic three-entry table
that reproduces the real pair and asserts exactly **1**; that control is the only reason to believe the
startup silence. `libkernel`/scePthreadCreate now resolves to the refusal in `pthread_sema.c`; EXPERIMENT A's
EAGAIN model is kept, compiled but unregistered, because **it is not pre-registered anywhere**: measured,
the only occurrences of "EXPERIMENT A" in the tree are its own comment and its print, and "EXPERIMENT B"
occurs nowhere at all.

## Carries and scanners: the two classes this campaign keeps rediscovering (2026-10-25)

Both arrived from outside (kimisupport, the companion) and both are worth more than the defects that
produced them.

**A carry that survives ten mentions has been verified zero times by the eleventh.** The companion carried
"A and B are pre-registered, B's expected result is a hang" across many summaries; measured, `EXPERIMENT A`
occurs only in its own comment and print, and **`EXPERIMENT B` occurs nowhere in the tree**. Repetition is not
corroboration -- it is the cheapest way to make a claim feel like an observation. The repair is mechanical and
already available: **every carry gets a file:line or it is deleted.** A carry is a pointer, never a fact.

**A scanner built from an example of the thing will always miss the second spelling of it.** Three defects
in one slice, one shape: `RT_SYSLIB*` could not see `PB_ATTR_NOOP`; `grep -cE` could not anchor and counted
108 for 107; `startswith` could not match a family name exactly. Each pattern was blind to a member of the
alphabet it scanned, **and each was blind in the direction that reports a smaller, tidier number** -- a
truncated match is indistinguishable from a short fact, a missed registration looks like a complete table, and
a prefix match looks like a family. The repair is never a better pattern to be added to that one: it is a
**second derivation by a different mechanism** (the preprocessor, `nm`, the linker section, the control that
fires) -- which is exactly why the `PB_ATTR_NOOP` rows were caught by `nm` counting object symbols rather
than by another grep.

## The ctype alphabet: what the guest's 73 call sites actually test (2026-10-25)

Measured after `_Getpctype` shipped (`510a1cf`), over every `e8` call to the import's only stub
(`0x2fbe6c8`; the slot `0x57e4798` is referenced by that `jmp [rip+d]` and nothing else -- the address
appears nowhere in the file as an 8-byte value, so there is no second copy to diverge).

- **73 call sites.** In the first 12 instructions after the call, **61** contain an immediate `test`/`and`
  (62 instructions); **12** contain none. The 12 are a *named* unclassified remainder, not a zero: they are
  call-and-do-something-else shapes and their tests, if any, are further out. A later pass may classify them;
  nothing here claims they do not test.
- **Distinct masks: `0x10, 0x80, 0xf, 0x144, 0x212, 0x232, 0x23e`.**
- **Constant-false masks: 0.** The table's alphabet is `0x1,0x2,0x4,0x8,0x10,0x20,0x40,0x80,0x400`, and no
  observed mask lacks every one of those bits. The concern that the guest tests bits the table never sets
  (`0x100`, `0x200`) is real but is *not* the failure it looks like: a mask carrying an unset bit **beside**
  set bits is a test **equivalent to its smaller subset**, not a test that is always false. Counted:
  `0x0100` appears with set bits in **21** sites (e.g. `test ax,0x144` == `test ax,0x44`) and `0x0200` in
  **14** (e.g. `0x232` == `0x32`). So the guest's classification is decided by bits this table can report,
  and the unset bits contribute nothing to any branch observed. The general form, worth having as its own
  sentence because the error it prevents is a set collapsed into a boolean: **`test ax, imm` is a
  disjunction -- an unset bit beside set bits contributes nothing, and only a mask whose tested bits are
  *all* unset is constant-false. "No bit is set that the guest tests alone" is a claim about bits; "the
  test is decided by nothing" is a claim about a mask, and conflating them is
  `a count cannot be subtracted from a set` in a new coat.**
- **Open, scoped:** whether some *other* code path (beyond 12 instructions) tests a mask made only of unset
  bits. Answering it is a search over the 61 classified windows plus the 12 remainders, not over the table.

**A completion with an expiry:** a refusal printed on the line *after* its own success line is worse than no
refusal at all — every reader takes the first line and stops, so the log records a success and buries the
refusal one line down. Measured twice in this tree (`__cxa_atexit` printing `handler registered` before
`table full ... refused`), and the repair is the general one: **print success only on success, and print the
count unconditionally** so a log cannot mean three different things. Companion class of the same defect:
**a capped table's count is a count of the cap, not of the demand** — `64 registered` stood in for `282`
until the capacity was raised, which is *a count cannot be subtracted from a set* with the cap as the
subtraction.

**A fourth mechanism for a tidy zero, and the worst of the four:** the comparison itself was sound and the
population was real, but one operand was a variable the previous statement never assigned, so the loop
compared an int against `None` and matched nothing. **An unset variable in a comparison is indistinguishable
from a measured zero, and no amount of re-running the same scanner will find it** -- only a number obtained
by a different derivation can. Hence the rule and its exact scope: **a second run of the same scanner is not
a control; an earlier, independently derived number is.**

**Scanner note, third instance of the same class:** the first pass over these 73 sites returned **0** because
the stub-search assigned nothing and compared an int against an unset variable -- a zero about the scanner,
printed as a zero about the population. `73` was already known from the previous pass, which is the only
reason the zero was caught: **a second run of the same scanner is not a control; the earlier number was.**

## Coordinate spaces and the tables that disagree about being "the catalogue"

- **`functions.csv` is the LANDED subset (38,101 rows); `ghidra_functions.csv` is the total (157,757).** A
  PC→owner join that reads the first reports "outside every extent" for bytes that are inside one. Checked
  across `tools/`: `join_import_pc.py` reads the total via `catalogue.load_extents("symbols/ghidra_functions.csv")`
  and is correct; the false zero this slice hit was a **hand** lookup in `functions.csv`, not a tool. The rule is
  the general one: **the join against extents must name the table that IS the extent set, and a landed table is
  a status view.**
- **`where()` prints vaddr space; the catalogue is PS4 space (+0x400000); file offset is vaddr + 0x4000.** All
  four are named in `runtime/address_spaces.h`, with the byte round-trip that proved them.
