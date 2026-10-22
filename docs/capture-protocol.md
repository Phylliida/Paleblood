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
