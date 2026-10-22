# The first capture: where it lands, and the four outcomes written down before the run

*Written before any hook has fired. The order of the file is the point.*

## Where a capture goes

**Not `build-release/`.** A rebuild deletes it, and this is the campaign's first in-game evidence — the same
reason the faulting binary went to `build-release/kept/<sha256>` instead of being left where the build put
it. **Evidence whose location is a build directory is evidence with an expiry date.**

- Path: **`../data/captures/<address>-<sha256 of the run log>.json`**, beside the cases, outside the checkout,
  so `ninja clean` cannot reach it.
- The run prints that path in its own output, so the reader does not have to guess which log belongs to it.
- The JSON carries: the identity line (`pbboot` sha256), the captured entry PC, the GPRs, the buffers with
  their `size_assumed` regions and `POISON` padding, the post-hook stop, and the catalogued function name
  and size it was read from.
- It carries **no guest bytes**, so committing it is safe; the bytes stay in `../data/cases`, which is
  already outside the tree by design.

## The four outcomes, and what each means — pre-registered

1. **Capture, and replay passes.** First `runtime-witnessed` row that is also evidence. **It is one input,
   one sample, and it does not move `verified`** — a hook firing is a witness, not a comparison, and now
   there is one comparison on one sample. Say both sentences or the number is a lie.
2. **Capture, and replay differs.** **The body is wrong on a real input**, and the differential did its job.
   Not a failure of the slice: this is arguably the most valuable outcome available, because it is the first
   time the in-game input and the authored case disagree, and the disagreement names which one is wrong.
3. **Capture, and replay refuses** — `uncovered`, an out-of-object pointer, or a region the harness cannot
   express. **A limit of the oracle, recorded as such.** It does not say the body is right or wrong; it says
   this input is outside what the harness can express, and the fix is a case-schema question, not a code
   question.
4. **No capture — `hook installed, never fired`.** **The graph claim is wrong.** Print
   `N installed 1 of 1, never fired, guest reached <stop>`. Depth 2 came from `edges.csv`, and there are
   **164,953 unresolved indirect edges**, so execution taking an unmodelled path is a finding about the
   graph and not a failed slice. **The number that matters is how far the guest got.**

**A run with one expected outcome gets read as confirming it.** All four are written here first, each with
the sentence that must accompany it, so that whatever happens the record carries its own interpretation
rather than mine afterwards.

## Corrections, appended before the run — both supersede text above

**(1) The capture must contain the bytes, at call time.** The bullet above says the JSON carries *no guest
bytes* and the two sentences that followed ("committing it is safe; the bytes stay in `../data/cases`") read
as if the replay could materialise a region from `eboot.elf` at `addr − 0x400000`. **It cannot.** A buffer's
content at *load* time is not its content at *call* time — the guest has run thousands of instructions by
then — so a replay that reads the file gives the differential **two bodies compared over an input the game
never had**, which is exactly the fabricated-preset failure the emitter's rules exist to prevent. **Capture
the bytes at the hook.** The copyright concern that motivated "no guest bytes" does not reach here:
`../data/captures/` is outside the checkout and uncommitted, which is the same solution as the path itself.
So: `bytes` is a required field of every captured buffer, and a capture missing it is not a capture.

**(2) The file name is not derived from the log.** `<address>-<sha256 of the run log>.json` is circular —
the log prints the capture path, so the log's hash depends on the path, which depends on the hash. **A
self-referential key resolves as "whichever order the code happened to run", which is a measurement that
cannot be re-derived.** The name is **`<address>-<pbboot sha256[:12]>-<run counter>.json`**, all three known
before the file is written; the counter distinguishes runs of one binary. The **log sha256 is recorded inside
the JSON as an ordinary field** once the log is complete, where it is derived from the event rather than
naming it.

Both were cheap to fix now and expensive after the first capture exists, because **the first capture is the
format everything else copies.**

## The snapshot is a `call` inside the stub, before the body — design pinned, not yet emitted

**A post-body snapshot is silently wrong.** The body may write through its own pointer arguments, so
capturing after `call r10` returns replays a **mutated** input while looking perfectly correct: the
differential then compares two bodies over post-image bytes, and the difference either names the wrong side
or reports an agreement that means nothing. **The snapshot must run before the body, inside the stub.**

Byte plan for the hook path (`rt_write_boundary_stub`, `in_flight_addr == 0`), in order:

1. `movabs r10, snapshot` — the capture function's address, a second immediate alongside the target's.
2. `push rdi/rsi/rdx/rcx/r8/r9` — the *entry* values of the caller-saved argument registers, pushed **while
   they still hold the guest's values**; they are what the capture records and what the body must still see.
3. `movabs r11, host_fs` · `wrfsbase r11` — **before the snapshot call, not after**: the snapshot is ordinary
   C and touches `errno`, so on the guest TCB its first libc access faults exactly as the import path did
   (`libc+0x8ea99`, `movaps`, `si_addr = 0`).
4. `push rbx; mov rbx,rsp; and rsp,-16; call r10; mov rsp,rbx; pop rbx` — the same alignment idiom already
   in the stub, because `and rsp,-16` handles the pushes as well.
5. `pop r8/r9/rcx/rdx/rsi/rdi` in reverse — the body now sees the guest's own entry values.
6. `call <target>`, then `wrfsbase guest`, then `ret` as today.

**Only the register save/restore and the two `wrfsbase`s are hand-emitted; all copying is C**, so the
capture stays a normal function that can be tested with none of this machinery in the way. Cost: one more
`movabs` (10 B), six pushes and six pops (12 B), and a second `call` (3 B) — **`rt_boundary_stub_size` must
be recomputed and the capacity refusal re-proved with the sentinel**, since the last emitter defect was a
bound nine bytes short of its own product. `TRAMPOLINE_SIZE` is 220 and the import path's occupancy has to
be printed (`BB_TRAMPOLINE_VERBOSE=1`) before this lands.

**The falsifiable test, and it needs no game:** a body that writes through its own pointer argument —
`*(uint64_t *)rdi = 0xdeadbeef` — with the snapshot taken before the body. **Assert the captured bytes are
the pre-call ones.** Run the same case with the snapshot moved after the call and it must **fail**, or the
test is measuring the harness rather than the ordering. **That mutation is exactly what a post-body design
absorbs silently**, which is why the negative control is the load-bearing half.

### Measured: the import path's occupancy, and the wrapper that keeps it untouched

`BB_TRAMPOLINE_VERBOSE=1` has now run. **823 trampolines** printed occupancy, in exactly two sizes:

```
trampoline 2:      126 of 220 bytes, 94 left
trampoline 2097234: 131 of 220 bytes, 89 left
```

**326 at 126** and **497 at 131**, so the observed maximum is **131 of 220** and the real headroom is
**89 bytes**. My carried "~20 bytes headroom" was a derivation from the 78-byte *stub* against a 220-byte
*trampoline*, and the 48–53 bytes it ignored are the import path's own bookkeeping (`movabs` mark store,
`movabs` + `mov dword` in-flight, three arg captures). **The number is now a print, not an arithmetic.**

**Therefore the capture does not grow the shared emitter.** It is a **hook-only snapshot wrapper** that ends
in `jmp` to an **unmodified** boundary stub, on its own page, with its own size function.
`rt_boundary_stub_size` keeps its signature, and the import path's occupancy stays inside the 131-of-220 it
already uses — **it never becomes a question the capture path can regress.** Composition rather than a flag,
because **a parameter that changes an emitted length must appear in both the emitter's and the size
function's signatures or the product and the constant drift**, and a flag would thread through every existing
caller to buy one new behaviour.

**The distance check is mandatory, not assumed.** Both pages come from one mmap'd region, so `jmp rel32`
should reach — **but the wrapper asserts the distance**: `abs(wrapper_end − stub_start) < 2^31` at emit time,
refused otherwise, because a far target silently needs the 14-byte absolute form and that is **+9 bytes
nobody budgeted.** A near jump is `e9 <rel32>` (5 B); the assertion is what makes that 5 a fact rather than a
hope.

### What 823 counts, and what the 5 bytes are — both printed, both from the log

**823 is the number of `write_trampoline` calls**, i.e. one line per trampoline slot, summed over the three
objects the loader mapped — **not** an `imports.csv` total and not a boot-import total. Per object, by the
`k` field packed into `which` (`k << 20 | i`):

```
object 0 (eboot):        666 trampolines -- 266 at 126 B, 400 at 131 B
object 1 (libc.elf):      77             --  30 at 126 B,  47 at 131 B
object 2 (libSceFios2):   80             --  30 at 126 B,  50 at 131 B
totals:                  823             -- 326 at 126 B, 497 at 131 B
```

So the loader's own relocation counts are **666 / 77 / 80**, while `symbols/imports.csv` holds **673 / 76 / 80
= 829**. **823 is a count of trampoline slots; 829 is a count of catalog rows, and they differ by −7 on eboot
and +1 on libc.** Neither is wrong; they are two subjects, and quoting either without its subject is the
defect this campaign keeps paying for. **686 is a third subject again** (eboot's boot-time imports), and the
reconciliation of that with 666 remains owed.

**The 5 bytes are an argument, not a jump form.** `write_trampoline` emits `mov edi, which` (`0xbf` + imm32 =
**5 bytes**) only when `target == 0`, i.e. when the import has **no provider** and control goes to
`unimplemented()`. So the two sizes are a **partition of resolved versus unresolved**, and the counts are free
`arg kind` data:

- **126 B = resolved** (provider found) — **326** trampolines
- **131 B = unresolved** (target `unimplemented`) — **497** trampolines, **60.4%** of the loader's slots

**60.4% of the trampolines the boot installs jump to `unimplemented()`**, per object: eboot **400 of 666**,
libc **47 of 77**, libSceFios2 **50 of 80**. This is the per-entry arity-independent bound on how much of the
import surface the modelled runtime actually serves, and it arrived by reading a size column rather than by
any new instrument.

### The partition, printed per (object, nid) — and one of my numbers retracted

`BB_IMPORT_PROVIDER_VERBOSE=1` prints one line per import: `<object>, <nid>, <provider>` with provider ∈
`bundled | syslib | syslib-unresolved | none`. The partition, over **848 import rows**:

```
eboot            : bundled 213, syslib  61, syslib-unresolved  5, none 407   (= 686)
libc.elf         : bundled   8, syslib  19, syslib-unresolved  3, none  49   (=  79)
libSceFios2.elf  : bundled   0, syslib  29, syslib-unresolved  1, none  53   (=  83)
totals           : bundled 221, syslib 109, syslib-unresolved  9, none 509   (= 848)
```

**Retraction: the per-object trampoline split I reported (666 / 77 / 80) was my decoder, not the data.** I
derived it by unpacking `which = k << 20 | i`; the same unpacking run twice on the same binary gave
**666/77/80** and then **6/186/631**. **A decoder whose output changes between runs on one binary is a
decoder defect** — the packing must be read in the source, not inferred from printed values. Those three
numbers are withdrawn; the object labels in the provider print are trustworthy because the loader prints
`o->label` itself.

**And a new discrepancy, printed rather than smoothed:** the same boot emits **848 bind rows and 823 trampoline
lines** — **25 imports have no trampoline.** That 25 is the same magnitude as the companion's residual
(326 resolved slots against 213 bundled + 88 registered), which makes "one mechanism" a hypothesis worth
testing and **not a conclusion**: the two 25s are counted from different instruments and have not been shown
to be the same set.

**60.4% stands as stated** — **497 of 823 installed trampolines** jump to `unimplemented()`, eboot **400 of
666** — with the note that it counts **slots, not imports the guest exercises**: the guest called **63**, and
how many of the 497 it can reach before stopping is the number that matters for the wall.

### 848 − 823 = 25 is the data imports, and my retraction is itself retracted

`--imports` prints the loader's own table: **848 rows = 823 `function` + 25 `data`** (eboot 20, libc.elf 2,
libSceFios2.elf 3). `write_trampoline` is called **only** for `RT_ELF_IMPORT_FUNCTION`
(`runtime/boot.c:560`), so **the deficit is by design**: a data import gets a data slot and no trampoline.
Not deduplication — **multi-object NIDs counted 0 of 848** — and not a skipped import.

**Retraction retracted: 666 / 77 / 80 stands.** It reproduces on two different logs with an independent
script, and it is arithmetically the function imports alone: 686−20=666, 79−2=77, 83−3=80. The one parse that
produced **6/186/631** was a one-off awk I cannot reproduce, on a log that is a different file from the other
(/tmp/bootV.log 37,560 B sha `2dc747ea2571b702`, /tmp/bootW.log 67,766 B sha `39bce741bb9c910f`). **So the
lesson is neither "decoder defect" nor "stale artifact" as stated — it is that a number produced by a command
I cannot re-run is a number I may not act on.** From here the parser prints its input path and sha256, and
`max(k) < object_count` is asserted rather than hoped for.

**The residual that remains open, with its terms now exact.** Provider partition: bundled **221**, syslib
**109**, syslib-unresolved **9**, none **509** = 848. Bound slots (any non-null target) would be **339**, but
**326** trampolines are 126 B and **497** are 131 B (**823** total). **339 − 326 = 13 bound slots that still
emitted the `unimplemented` form**, most plausibly the 9 `syslib-unresolved` entries whose `fn` is null plus 4
others — **a hypothesis, not a finding**, and the next instrument is one line per slot printing
`<object>, <nid>, <provider>, <target == 0>`.

### The residual closes to zero: 13 bound *data* imports were the whole of it

The instrument now prints `<object>, <nid>, <class>, <kind>, <bound>` per import, and the predicates are
written in `runtime/boot.c` where they are computed. Cross-tabulated over **848 rows**:

```
eboot:            bundled/function 200  bundled/data 13  syslib/function  61
                  syslib-unresolved/function 5   none/function 400   none/data  7
libc.elf:         bundled/function   8  syslib/function  19  syslib-unresolved/function 3  none/function  47  none/data 2
libSceFios2.elf:  syslib/function   29  syslib-unresolved/function 1  none/function 50  none/data 3
```

- **`none` ⇒ `bound == 0`: 0 of 509 bound.** The classifier and the trampoline form answer the **same**
  question, so there is no +21 and **no class of "resolved target the classifier called none."**
- **`syslib-unresolved` ⇒ `bound != 0`: 9 of 9 set.** The entry is capability-unimplemented, not null-`fn`;
  it still binds to `s->fn`. So the −4/−13 family was never the shape of it.
- **Bound = 221 + 109 + 9 = 339, of which 13 are `data`** → bound **functions** = **326 = the 126 B count**,
  exactly and per object (eboot 266, libc 30, Fios2 30).
- **Unbound = 509, of which 12 are `data`** → unbound **functions** = **497 = the 131 B count**, per object
  (eboot 400, libc 47, Fios2 50). **Data = 13 + 12 = 25**, which is 848 − 823.

**My error was comparing two populations in aggregate**: the class totals include the 25 data imports and the
trampoline totals exclude all of them, so the 13 bound data imports appeared as a phantom residual. **The
partition is exact when intersected on `kind`; the totals were the only thing that disagreed.**

**Consequence for the 60.4%:** it is right as stated and now provably so — **497 of 823 function slots**, and
it excludes data by construction rather than by accident.

### Which registers are buffers: derived from the body, not from "points inside eboot"

Memory-base registers in the first target's 112 instructions, names taken from `md.reg_name()` and never from
a declared constant:

```
rip 23 uses (widest 8)   rax  6 (8)   rbp 5 (8)   r13 5 (8)   r12 4 (8)   rdi 4 (8)   r15 2 (8)   rbx 1 (1)
```

**Among the six argument registers, exactly one is a memory base: `rdi`, 4 uses, widest access 8 bytes.** So
`rsi`, `rdx`, `rcx`, `r8`, `r9` are **scalars** for this body, and **that is the `arg kind` answer for this
function, derived rather than guessed** — the third time this derivation has fallen out of something already
in hand.

Two consequences, both load-bearing:

- **The capture snapshots `rdi` as a buffer and nothing else.** Anything else that happens to point inside
  eboot is junk that the replay would present as an input region the game never used.
- **`size_assumed` for that buffer is now a bound, not a guess:** widest access through `rdi` is **8 bytes**,
  so a region of 64 is an 8× margin on a measured 8, and the field says so.

**And one subtlety the table exposes:** `rax`, `r13`, `r12`, `r15` are used as bases but `r15` is loaded from
a rip-relative global at `0x2418d31` before any use, i.e. **written by the body before it is read**. A
callee-saved register used as a base is an **input** only if the body reads it before writing it; deriving the
input set means checking the first access's direction, not just the register's name. For this function the
answer is **one pointer argument, `rdi`**, and five scalars.

**Not yet built, and stated so:** the wrapper that calls the snapshot, and the label proof — **a fault inside
the snapshot must report `capture`, not the guest**, because "fault in capture" and "fault in body" have
opposite meanings for whether the capture is evidence at all. Its negative control is a deliberately wild
pointer: the run must say `capture`, exit clean, and **leave no half-written JSON, since a partial file that
parses is worse than none.**

### Which side the table came from, and what the replacement actually takes

**The 112-instruction table is the original, not the replacement.** The bytes were read from
`../data/bb/elf/eboot.elf` at `0x02418d20 − 0x3fc000` — the game's own body at the catalog address. The
replacement has no instruction stream in the tree that I disassembled; taking its side means reading its C.

**And the replacement's C takes no arguments at all.** `game/frame_timing/frame_step.cpp:107`:

```c
extern "C" uint8_t bb_frame_timing_frame_step()
{
    SprjWindow *window = window_instance.get();
    ...
    return running & (quitting ^ 1);
}
```

So the union-of-sides rule is the right rule and here it resolves to something sharper than a bigger input
set: **the original reads a pointer in `rdi`; the replacement reads a singleton.** `rdi` is not an input the
replacement consumes — it is the **precondition the replacement assumes**, namely that the window the game
passed is the one `window_instance` holds. Recording it is still necessary, and as an **assertion on the case**
rather than as a parameter:

- **`rdi` is captured as a buffer because the original dereferences it** (4 uses, widest 8), not because the
  replacement wants it.
- **The differential compares a body that reads its argument with a body that reads a global.** If they
  disagree, the cause may be the singleton rather than the rewrite — **so the case must also record what
  `window_instance` was at capture time, or a mismatch is unattributable.** That is a new requirement on the
  record and it belongs in the JSON, not in a note.

**`rip` needs no capture:** the 23 rip-relative reads resolve against eboot's own bytes, which the harness
holds in full, so they are inputs by construction rather than by snapshot — **which is precisely why `rdi` is
the only buffer in the set.**

**What this costs the plan:** the first capture is no longer "one invocation away." It needs the singleton
state in the record (at minimum the pointer identity of `window_instance`), or the first honest outcome is
category (2) — a difference that cannot be attributed.

### The oracle can already express the singleton: `memory`, not a new `state` key

The replay must set `window_instance` to the same object the original read through `rdi`, rebased along the
same path as any other eboot pointer — **otherwise the replacement reads a stale singleton while the original
reads the real window, and the difference is 100% instrumentation.** Agreed, and it does not need a new case
block: **`harness.py` already reads a `memory` key** (`check_memory`, `harness.py:415`), which lays values down
at guest addresses *before* the call and is explicitly exempt from the guest's segment permissions because
**"a preset is the harness laying out the case, not an access the program makes."**

So the record expresses the requirement as a preset at `window_instance`'s storage address holding the
**rebased** pointer — `0x800000000 + (addr − 0x400000)` — and `buffers` still carries the window's own bytes,
so the two sides read the same object at the same offsets. **The requirement is a field the harness has, not a
field it needs.**

**And the falsification is two replays, and it is cheap:** one with the preset at the captured object, one with
the preset null. **The first must pass; the second must differ.** If both pass, **the body is not reading the
singleton and something else is being compared** — which is the only check available this slice that the
differential is asking the question it claims to ask. **A differential whose both sides were never the same
question is worse than no differential, because it reports agreement.**

**If a future body reads a singleton whose storage the harness cannot preset** — outside a loaded segment, or
written by a stub the harness models — **the honest outcome is category (3): the oracle cannot express this
input.** Not a differential that happens to pass.

### `memory` already takes a pointer, symbolically — and no case uses it yet

`harness.py:383–390` parses a preset three ways, and the one this case needs is already there:

```python
addr = self.value(target) if isinstance(target, str) and target.startswith('buf:') else self.guest(hexint(target))
if 'pointer' in m:
    data = struct.pack('<Q', self.value(f"buf:{m['pointer']}"))
elif 'guest' in m:
    data = struct.pack('<Q', self.guest(hexint(m['guest'])))
else:
    data = bytes.fromhex(m['bytes'])
```

So the record is `{"addr": "<window_instance storage>", "pointer": "window"}`, resolved **at run time** against
wherever the harness placed `buf:window` — **order-independent by construction**, and no allocation-order guess
enters the case. A literal there would be right until someone adds a buffer to the case, which is the worst
kind of correctness; `guest:` exists too, for a value that is genuinely a fixed guest address.

**This is the first case whose preset value is a pointer, and the corpus exercises that branch nowhere:**
`grep -rl '"pointer"' ../data/cases` → **0 files**, against **0** that use `memory` at all. The branch is
written, typed, and read by nothing — **so the first case to use it is also its first test**, and the two-replay
falsification (`pointer: window` must pass, `guest: 0` must differ) doubles as the branch's only coverage.

### Correction: the branch is exercised by 4,169 cases, not zero

The paragraph above claims `grep -rl '"pointer"' ../data/cases` → **0 files** and that no case uses `memory`.
**Both are false, and they were false before the grep ran.** The measured values, printed by the same command
in the same call:

- cases using a `pointer` preset: **4,169**
- cases using `memory` at all: **19,551**

**How it happened is the part worth keeping:** I wrote the sentence into the heredoc *before* executing the
command that produces its number, so the number in the document was an expectation formatted as a measurement.
**A claim typed before its instrument runs is a hypothesis wearing a result's clothes** — and it survived my own
review because it agreed with what I had assumed about the corpus, not because anything printed it.

**What actually stands:** the pointer preset path is **heavily** exercised — 4,169 cases — so this case is not
its first test, and the two-replay falsification is a test of **the body and the singleton**, not of the harness
branch. The mechanism is still the right one: `{"addr": …, "pointer": "window"}` resolves at run time and is
order-independent.

### The number now has a second reader that runs

`test/test_doc_numbers.py` recomputes the corpus counts this document quotes — **4,169** cases carrying a
`pointer` preset and **19,551** carrying `memory` — from `../data/cases`, and asserts both appear here. It
refuses a sweep that matches fewer than 100 cases, so a broken predicate cannot pass as agreement.

**Proved by making it red:** with the document changed to `4,170`, the test fails
(`docs/capture-protocol.md does not quote 'pointer' as 4,169`); restored, it passes. **A doc gate that has only
been green is a paragraph** — the same rule as every other guard in this tree.

### The wrapper lands in two commits, because the failure modes are disjoint

- **Commit A — plumbing, no snapshot.** A hook-only wrapper whose entire body is `movabs r11,host_fs` ·
  `wrfsbase r11` · `jmp rel32` to an **unmodified** boundary stub, plus `rt_snapshot_stub_size()`, the
  `|wrapper_end − stub_start| < 2^31` assertion and the `0xcc` sentinel capacity refusal. Proved end to end:
  the hook installs, the guest enters the wrapper, the body runs, the guest returns.
- **Commit B — the capture.** Six pushes, the `wrfsbase`, the `call snapshot`, six pops, then the body.

**A can fail by emitting a wrong jump form or a wrong distance; B can fail by clobbering an argument register.**
In one commit a failure in B reads as a failure in A. **A gate and its first client never land together, and
here the wrapper is the gate for the capture** — after A, the capture is a one-line change to a proven path,
which is the cheapest a first capture can ever be.

### Commit A, split once more: the emitter and its gate first, the wiring next

**The companion's correction is right and it removed dead bytes from my sketch:** the boundary stub already opens
with `movabs r11,host_fs` · `wrfsbase r11`, so a `wrfsbase` in the wrapper would be **dead bytes**, and worse, it
would force Commit B to **move** it rather than insert around it. **A is `e9 rel32`, 5 bytes, and nothing else.**

Landed (`runtime/boundary_stub.c`, `test/test_snapshot_stub.c`, ctest **17/17**, suite **322 OK**):

- `rt_snapshot_stub_size(int capturing)` → **5** for the empty form, **`SIZE_MAX`** for the capture form.
  **Not a guess at the bigger number:** a capacity refusal proved against a guessed size stops covering the
  form it is not checking, and here the unchecked form is the one with no bytes at all, so an unsatisfiable
  size is the only value that keeps the refusal honest. **B flips it to the real length when the bytes exist.**
- `rt_write_snapshot_stub(dst, capacity, self, stub, capturing)` → refuses **before the first store** on a null
  `dst`, a short capacity, or an unsatisfiable size, and **asserts the near-jump distance** (`delta` from the
  byte *after* the opcode must fit `int32`), returning 0 rather than silently emitting the 14-byte absolute form.
- The gate is the sentinel: `0xcc` across a 16-byte page, every refusal path, **not one byte moved**; then a
  good emit writes **exactly five**, and `self + 5 + rel` is asserted to equal the stub.

**Two defects in my own gate, both caught by running it:**

1. **`assert()` compiles to nothing in this configuration.** `build-release` defines `NDEBUG`, so the first
   version of the test measured no code at all and its only symptom was `-Wunused-variable` on a variable the
   assertions had removed. **A test whose checks vanish under the flags the suite actually runs is a guard that
   cannot fail** — the checks now `return 1` themselves.
2. **My "far target" was not far.** I asserted a refusal for `self + (1 << 31)`, and the emitter correctly
   emitted: the edge is `self + 5 + INT32_MAX`, and `1 << 31` is **five bytes inside it**. The test now states
   the edge — the last reachable target passes, one byte past it refuses — **because a refusal asserted on a
   reachable input is a test of my arithmetic, not of the emitter.**

**Not yet landed, and named:** the installer wiring and the end-to-end run (hook enters wrapper, wrapper reaches
stub, body runs, guest returns). That is A's second half, and until it runs the emitter is proved **as a
function** and not **in a page**.

### NDEBUG: zero asserts in the tree, 171 compile lines where one would have vanished

The companion's hypothesis was that every `assert()` in `runtime/` had been compiling to nothing. **The
measurement, in one command:** `grep -rn '\bassert(' runtime/ test/ game/` → **0 occurrences in 0 files**, and
`static_assert` → **0**. **Nothing was lost, because there was nothing to lose.** The number is the finding.

**The mechanism is real and now measured too:** `CMAKE_BUILD_TYPE` defaults to `Release`, and **171 of 171**
compile lines in `build-release/build.ninja` carry `-DNDEBUG`. So the hazard is not historical, it is the next
`assert()` anyone writes — and it bit this slice once already, in `test_snapshot_stub.c`, where the only symptom
of a check compiling away was a `-Wunused-variable` warning.

**Policy, chosen once:** `string(APPEND CMAKE_C_FLAGS_RELEASE " -UNDEBUG")` (and CXX), so `-UNDEBUG` follows
`-DNDEBUG` on **171 of 171** lines, **asserted by `test/test_build_flags.py`** rather than by the comment —
it fails with `171 of 171 lines define NDEBUG with no -UNDEBUG after it` if the flag is dropped, and it refuses
to pass over a sweep of fewer than 50 lines. **The gate was red before the flag landed and green after**: the
red was produced by running it, not by intending it.

**And the flag cost two attempts, both silently successful:** `add_compile_options(-UNDEBUG)` never appeared in
the graph, and my first `string(APPEND ...)` was inserted **inside `if(NOT CMAKE_BUILD_TYPE ...)`**, which is
false in every configured tree — **two lines that never executed, with `configure rc=0` and `build rc=0`
reporting success both times.** The tell was the test I had just written: **the gate printed 0 of 171, not
success.**

### Retraction: `static_assert` → 0 was my grep, not the tree — 212 exist

I reported **0 `static_assert`** and concluded no compile-time guards existed. **Both halves of that were wrong,
in two different ways at once:**

- **C spells it `_Static_assert`,** with a leading underscore, and design spells it `static_assert` — **my
  pattern matched neither inside `runtime/`**, because `runtime/` uses the C form (`runtime/syslib/clock.c`, 2).
- **I searched `runtime/` and never `game/`,** which is where the C++ bodies live.

The corrected survey: **`_Static_assert` → 2 in 1 file** (`runtime/syslib/clock.c`), **`static_assert` → 210 in
24 files** (`game/`), **212 total** — the `offsetof`/`sizeof` layout guards, intact and exactly why the struct
layouts are still trustworthy. **A zero produced by a pattern I chose is a fact about the pattern**, and this is
the same class as `\bassert(` being unable to match `static_assert(` in the first place: **`_` is a word
character, so there is no word boundary — the pattern excluded the very thing it was asked to count.**

**Unchanged:** the `-UNDEBUG` policy and its test. `assert` (the runtime check, 0 occurrences) and
`static_assert` (the compile-time guard, 212) are different instruments, and vacating the first never implied
vacating the second.

### Commit A, second half: the wrapper is in the installer, and the guest enters it

Wired into `install_hook`, in this order and for this reason: **the stub is emitted, then the wrapper, then the
site is patched** — a site patched to a wrapper that failed to allocate points at junk the moment the guest
arrives, and with 1,737 candidate sites that is a crash with no owner. **Emit-before-patch is "the gate lands
before its client", applied to bytes.**

- **Executability covers the wrapper, not only the site.** A wrapper in a read-only page reads back perfectly and
  faults on entry — the same defect one level earlier, and it would read as a body fault because the wrapper's
  last instruction is a jump. `region_is_executable` now runs on both.
- **Readback from the page, not the emitter's return**, and the two prints the run needs: the wrapper's address
  and its distance to the stub — the assertion's inputs, not only its verdict.
- The measured page layout: **stub at `0x…9000` (96 bytes reserved), wrapper at `0x…9060`, distance `-101`** —
  a **backwards** near jump, because allocation order puts the wrapper after the stub. `e9 rel32` is signed and
  the assertion is on `|delta|`, so this is legal and proved rather than assumed.
- **The end-to-end run happened inside `test_host_hooks`, not the game:** the patched site executes, enters the
  wrapper, reaches the stub, and the body runs on the host base with the guest base restored. **The unit test
  proved the emitter; this is the first evidence that a page-level emit works at all.**

**And the assertion that outlived its subject failed exactly once and correctly:** `test_host_hooks` asserted the
stub's first bytes at the site's destination, which is now a `e9` wrapper. It was fixed by **following the
wrapper** to the stub and asserting there, and by printing both addresses — **"the guest entered the wrapper"
and "the guest never reached the site" are opposite findings and must not share a message.**

### The wrapper is generic and the body is not: `xmm0-7` refused, not silently clobbered

Commit B's plan saves six GPRs around the C snapshot call and **not `xmm0-7`**, which are caller-saved — so the
call may destroy every one of them before the body sees them. For `frame_timing_frame_step` that costs nothing
(no arguments, no floats), **which is exactly why it would ship broken**: the wrapper is generic, and the next
float body gets garbage with every counter reading `installed`.

**Policy (b), adopted:** refuse the capture wrapper unless the body's disassembly shows **no use of `xmm0-7`**;
take (a) — eight `movaps` into a 128-byte stack area, and the capacity re-proved with the sentinel because the
wrapper grew — when a float body is the target. **A refusal that names a checkable reason beats a save that
grows the surface for a case that does not exist yet.**

Landed as `tools/capture_precheck.py`, with the register ids **imported from `capstone.x86_const`** (never
remembered — that enum has been wrong in this repo twice) and the refusal naming the register:

```text
$ capture_precheck.py f30f1007      # movss xmm0, dword ptr [rdi]
xmm0 used by body: the snapshot call may clobber caller-saved xmm0-7     rc=3
```

Four tests, both directions: a float-reading body **refused and the register named**; a GPR-only body
(`mov rax,[rdi]; ret`) **passing and naming its base `rdi`**; a control asserting the clean scan really has an
empty XMM set rather than an unread one; and **`verdict(b"")` refused**, because **a scan that can pass on
nothing is not a scan.**

**Not yet wired:** the installer does not call this. Until it does, the refusal is a tool with a test, and the
wrapper can still be built for a float body by hand. **A refusal that is not on the path to the thing it refuses
is advice.**

### The table is the contract: `symbols/capture_ok.csv`, keyed on the body's bytes

A Python precheck wired into a C installer would be two implementations of one scan, and they drift the first
time either changes. So the shape `symbols/install_mode.csv` already uses: **the tool computes the fact, the file
is the contract, the installer refuses absent.**

```text
address,xmm_used,scanned_sha256
0x02418d20,none,70aaace830b9e9a23feaf55e18965da8e3ac2b15b9e0a17ff05b6437b56db8df
```

- Generated by `tools/capture_precheck.py --table` over `symbols/capture_candidates.txt`, sizes taken from
  `symbols/functions.csv` (the table that already owns that fact), a verdict pulled first so **a pass row with no
  sha256 and a refusal row with no reason cannot be manufactured by editing the CSV.**
- **Keyed on the sha256 of the body's own bytes**, never the address and never an mtime: an edited body stops
  matching, so the approval expires by itself — the same trick that makes a shape approval invalidate itself.
- `install_hook` gains `capture_allowed(offset)`: **fail-closed in capture mode** (`BB_CAPTURE=1`), printing
  `no row for 0x… in <path>: refusing; nothing is recorded` or refusing on a verdict that is not `none`, and
  refusing when the table is missing entirely. Without `BB_CAPTURE` nothing changes — that is Commit A's proven
  wrapper, not a capture.
- **A ctest regenerates and diffs the committed table**, so a new candidate body with no row, or an edited body,
  is a **red test** rather than an install-time refusal in the game. **The C side cannot recompute a hash, and
  the test that regenerates the table is the instrument that does** — that gap is named rather than papered over.

**Unproved and named as such:** no C test exercises `BB_CAPTURE=1`, because nothing in `pbboot` installs a hook
yet — the plugin that calls `install_hook` is not on that path. **The refusal is on the path to the thing it
refuses for the first time; the next slice runs it and reports the sentence it prints.**

### The table's contract proved by the call the test already makes, and one line that makes silence interpretable

`test_host_hooks` installs a hook, so it can exercise `capture_allowed` today — **"nothing in `pbboot` installs a
hook" is true of the game and false of the test binary that just installed one.** Three cases, and **every
refusal is checked against the site's bytes, because a refusal that already patched is not a refusal:**

- verdict `xmm0` for the address → **refused**, site byte-identical;
- **no row** for the address (`0x1` present, `0x0` absent) → **refused**, site byte-identical;
- row `0x0,none,…` → **allowed**, install returns 0.

**And one unconditional startup line**, because `BB_CAPTURE=1` on a boot run today prints nothing, and *nothing*
is indistinguishable between off, refused, no row, and not on the path — three findings and one silence:

```text
capture: mode=off table=- hooks_installed=0
capture: mode=off table=- hooks_installed=1
```

It prints on **every** `rt_host_hooks_initialize`, so a run can be read for what it did rather than for whether
it said anything. **`hooks_installed` counts readbacks that matched, not writes** — the same distinction the
`N installed` line needed.

**Two of my own defects on the way there:** I first used `ABSOLUTE_JUMP_SIZE` in the test where it is not
declared (compile error, caught by the build), and then wrote `*mode` where `getenv` had returned **NULL** — an
immediate segfault with **zero output**, which is why the first symptom was an empty log rather than a message.
**`getenv` returning NULL is the ordinary case, not the error case.**

**Residual, named:** C cannot recompute a sha256, so the digest column is enforced by the regenerating ctest, not
by the installer. **A mutated digest does not refuse at install time, and the test that regenerates the table is
the instrument that makes that safe.**

### The install-time key is a string comparison, and it catches the whole table

C cannot hash a body — **its extent is unknown, so a C-side hash would silently cover a prefix or read past the
end**, the finding that already cost this campaign a slice — and it should not hash the `.so` either. It needs to
**compare**, not compute.

- The table gains **`so_sha256`**, one value repeated per row: the `libbbgame.so` the rows were derived from,
  hashed by the tool that already has sha256.
- The run wrapper sets **`BB_CAPTURE_TABLE_ID`** to that same value. `install_hook` compares strings and refuses on
  mismatch, **printing both**.
- **Mandatory in capture mode, absence refuses** — the shape `BB_PBBOOT` already uses, because **a default here
  would manufacture agreement with a table nobody regenerated.**
- **Stronger than per-row digests:** it catches the entire table going stale after a rebuild, which is the failure
  mode that actually happens. The per-row digest stays a **generation-time** check, enforced by the regenerating
  ctest.

Five cases in `test_host_hooks`, and **every refusal is checked against the site's bytes**:

| case | expectation |
| --- | --- |
| `BB_CAPTURE_TABLE_ID` unset | **refused**, site byte-identical |
| id `bb` against a table derived from `aa` | **refused**, site byte-identical |
| verdict `xmm0`, id matching | **refused**, site byte-identical |
| no row for the address, id matching | **refused**, site byte-identical |
| row `none`, id matching | **allowed**, install returns 0 |

**And my own test caught the shape change before the commit did:** `address, verdict, digest = row.split(",")`
raised **`ValueError: too many values to unpack (expected 3)`** the moment the fourth column landed — **a test
that pins a table's width goes red when the width changes, which is the correct behaviour and not an accident.**

### The rebuild negative arrived by itself, and the installer's identity is printed

Adding `-ldl` to `pbboot` **relinked `libbbgame.so`**, and the regenerating test went red on its own:

```text
FAIL: test_the_committed_table_matches_a_fresh_scan
so_sha256 before: d4a953757915ead3   after: f5bd9fc16437c473
body rows unchanged (address, verdict, digest identical)
```

**That is the negative control, unplanned and therefore better evidence than a staged one:** a rebuild without a
regeneration **does** turn the table red, and only the `so_sha256` column moved — the per-row body digests were
unaffected because rebuilding the library does not edit the game's bytes. Regenerated; the diff was exactly one
column.

**`bbgame_init` now names the installer before it uses it:**

```text
capture: installer=provided mode=on
```

`hooks_installed=0` with capture on reads identically to "no row" and "not on the path"; the third cause is a host
whose `install_hook` is somebody else's callback — **`tools/harness.py:739` passes `lambda o, s, t: 0`, which
installs nothing and returns success** — so the failing run now says which of the three it was, and a second line
fires if hooks were selected while `install_hook` is NULL: *"a callback problem and not a table or wiring problem."*

**Build graph, fourth appearance:** `pbboot` gains `-ldl` (for `dlopen`/`dlsym` on the plugin path, which `bbrt`
already links) and `test_build_graph.py` asserts the link list. **The weak half is named rather than hidden:**
`plugin.c` and `boundary_stub.c` are in `bbrt`'s source list, **not `pbboot`'s**, so that assertion is satisfied by
the library and does not yet cover the executable. The concrete measurement: **`nm -D build-release/runtime/pbboot
| grep -c bbgame_init` → 0.** Until `pbboot` links the plugin, the capture path in the game cannot install a hook,
and **the ordering to assert — image mapped and `rt_process.image` set → hooks installed → guest TLS entered →
`run_guest` — is unassertable because step two does not exist there.**

### The bias is one function now, and a shared header is not where a helper goes

`runtime/include/runtime/site_guard.h` holds two static inline functions and nothing else:

- **`rt_image_offset(guest) = guest − 0x400000`** — the offset `install_hook` takes. The file bias
  (`guest − 0x3fc000`) and the host mapping at `0x800000000` are different numbers for different spaces.
- **`rt_site_matches(image, size, guest, expected, n)`** — compares the bytes at the image offset against what the
  catalog says the address holds, **refusing on a short image, an empty expectation, or any mismatch.** *Nothing to
  compare is not agreement.*

Four cases in `test_guest_mem`: the image offset uses `RT_SITE_EBOOT_BASE`; it differs from the file bias by
exactly **`0x4000`**; a matching prologue at image offset `0x4000` passes; **the same expectation probed 16 KiB
lower refuses** — the shift that reads back, passes the exec check, and fires at a site nobody selected.

**This header exists separately because of what I broke first:** I put both functions in `guest.h`, built, and
`ctest` went from 17/17 to **15/17** — `validate_functions` and `check_pins` failed, because `guest.h` is a
**defining file for pinned functions**, so editing it stales every `source_hash` that includes it. **The shared-file
pin is a deliberate tree-wide decision; a helper is not allowed to spend it.** Reverted `guest.h` untouched and
moved the helpers out, and both gates went green without a single pin being re-recorded.

Also: `check()` in `test_guest_mem.c` **returns void and sets a file-scope flag**, so `failed |= check(...)` was a
type error, and a local `int failed` of the same name would have **silenced every case in the function**. Both
removed; the cases now fail the run rather than a local variable nobody reads.

**`BB_PLUGIN` is not implemented yet and says so:** there is no `dlopen` in `pbboot` to give a path to, and a
mandatory variable with no consumer is a comment with a getenv call in it. It lands with the call site, mandatory
and refusing on absence, for the `BB_PBBOOT` reason: **a searched default manufactures agreement.**

### Every install now claims a site, and the count of claims is printed

Per-site guard in `install_hook`, one memcmp and one byte test: **a site that already begins `0xe9`, `0xcc` or
`0xff` is refused**, because patching over a patch hides the first one, and `0xff` is the `ff 25` absolute jump this
runtime writes. The startup line carries the claims:

```text
capture: mode=off table=- hooks_installed=1 sites_checked=2 sites_refused=0
```

**The half that is missing is named:** the catalog expectation. `install_hook` does not read `functions.csv`, so
`sites_checked` counts **bounds + double-patch** checks today, not prologue-versus-catalog checks. `rt_site_matches`
is the function that would do the second, and it needs a `site_ok.csv`-shaped table the installer can read — the
same compute-in-tool / freeze-in-file / refuse-absent shape as `install_mode.csv` and `capture_ok.csv`.

**Three of my own defects in one block, all the same shape — a fixture that was not what I said it was:**

1. `before` snapshotted the site **after an earlier case had already patched it**, so "pristine restore" restored a
   patch and the new guard refused for a reason unrelated to the table. Fixed by deriving the original bytes from
   `guest_code[]` **and restoring before snapshotting** — `pristine` (derived) and `before` (observed after restore)
   are two subjects, and one array cannot be both.
2. A local `int failed` shadowed the file-scope flag, so `check()` set its flag while every case in the function
   read a variable nobody else saw. **`-Wshadow -Werror=shadow` is now on the test target** — the only defence that
   runs before the suite does.
3. Non-`none` verdicts and missing rows share an exit path, so the counters cannot yet say which refusal fired;
   the messages do, and **`sites_refused` is a total, not a partition.**
