# The three axes, named before the first capture

A number that can be mistaken for the top line is a number that will be. So the axes are named here,
once, before any run can produce a value on one of them.

| axis | what it asserts | what it does not assert | where it lives |
|---|---|---|---|
| `edge-verified` | a replacement's output matched the original's on N authored edge cases | that the body is equivalent off those cases | `symbols/functions.csv` `status` |
| `verified` | a human read the body and approved it against its evidence | that it ran | the same column, one value further |
| `runtime-witnessed` | the replacement body was **observed executing in the game**, entered through the boundary stub, with its entry registers recorded | **anything about equivalence** | nowhere yet — deliberately |

**A hook firing is a witness, not a comparison.** It retires `unknown (no runtime witness)` and it moves
`edge-verified` by zero and `verified` by zero. One execution cannot distinguish a correct body from a
wrong one that happened not to matter; only a differential over authored cases can, and only a human
approval can promote.

`runtime-witnessed` is **not** a value of `status`, because `status` is exclusive and a fired hook does
not replace the evidence that got the row where it is. It will be a second column when a column is
worth its schema cost — one deliberate tree-wide change, never a piecemeal edit — and until then it is
a phrase in a run log with this file as its definition.

The vocabulary is enforced: `test/test_coverage_axes.py` fails if `runtime-witnessed` appears in
`validate_functions.STATUSES`, so the first capture cannot be quoted as having moved the top line
without a test going red first.

## Two requirements written down before the first capture

**The plugin's image base is compared with the boot's, printed, before anything is installed.**
`libbbgame` carries its own guest-memory globals and its own `rt_guest_read_ok` bounds. If any of them is
initialised by a call only the harness makes, the bodies read from address 0 while every counter says
installed — and both sides happening to map the image at `0x800000000` is exactly the coincidence that
hides it. So the first in-game run prints both bases and the resolved body address, and **refuses to
install if they disagree**. Fail closed, and print the disagreement rather than a count.

**The in-game recorder uses the harness's capture schema, not a new one** — the same fields `verify.py`
records: return value, register set, memory writes, case id. Then in-game evidence and harness evidence are
**one format with two oracles**, and the eventual in-game differential is an extension rather than a second
recorder. A bespoke first-capture format is a format nobody reconciles; that is the three-populations
problem with a schema attached.

**What runs at `dlopen`:** nothing of ours. `readelf -d libbbgame.so` reports `INIT_ARRAYSZ 8`, a single
entry, and that entry is `frame_dummy` (`nm -C` finds no `_GLOBAL__sub_I`), the CRT stub that only exists
to register the tm-clone table. There are no named or unnamed initialisers in the plugin, so a hook is
installed by an explicit call, never as a side effect of loading the library.

## Symbol interposition: measured, not assumed

`nm -D --defined-only` over both binaries, intersected: **empty.** `pbboot` exports 59 dynamic symbols,
`libbbgame.so` 21,139, and **no name is defined in both** — so nothing is resolved by load order and
nothing is shadowed. The plugin references **no `rt_*` or `guest*` symbol at all** (`nm -D | awk '$1=="U"'
| grep -E ' rt_|guest'` is empty), and `pbboot` is a **PIE executable, not exported** (`FLAGS_1: PIE`, no
`-rdynamic`), so a plugin could not bind to its symbols even if it wanted to.

The consequence for this document is the opposite of the concern and just as load-bearing: **there is no
split state to shadow, and there is also no shared `rt_guest_read_ok`.** The bodies validate against
whatever bounds their own image of the mapping carries — the plugin's `rt_image` from `host->image` — so
the in-game capture's validity rests on `host->image` being the boot's mapped image, which is exactly what
the printed base comparison asserts before installing. **No interposition means no free agreement: the
assertion is the only thing that could make them agree, which is why it fails closed.**

**Lazy binding:** neither binary has `BIND_NOW` (`readelf -d` shows only `FLAGS_1: PIE` on both), so a
first call inside an installed body can resolve lazily. A hook that fires before its callee's PLT entry
has been resolved performs that resolution *inside the guest's thread* on the host `%fs` the boundary stub
restored — which would read as a body defect. `LD_BIND_NOW=1` on any run whose purpose is a capture, and
say so in the run's own log.

## Which bounds the bodies consult — the answer is "none, until now"

The empty intersection has a sharper consequence than shadowing. The one bounds function in the tree is
`rt_guest_write_ok` (`runtime/guest_mem.c`), and **its subject `rt_process.image` is assigned in exactly
one place, `boot.c:562–563`.** On the plugin path `boot.c` never runs, so `rt_process.image` and
`image_size` were **0**, and with `base == end == 0` the arithmetic `len > end - addr` **underflows to a
huge unsigned value and admits every address**: a bounds check whose subject was never initialised is a
licence, not a guard. It now refuses, and says which state it was in. That also means the plugin's
`rt_image` (from `host->image`) and the bounds check's `rt_process.image` are **two different globals, and
neither is the boot's mapping** — the printed base comparison compares `host->image` with what `boot.c`
mapped, and the disagreement it exists to catch is real rather than decorative.

**`rt_syslib_in_flight` reports the last import entered, not the faulting one.** The word is set by the
trampoline's prologue and cleared by the boundary stub's bookkeeping tail; a body that faults never runs
the tail, so the value at a fault is **the import that was in flight**, which is the intended reading —
but silence after a fault means *stale*, not *settled*, and must not be read as "nothing was in flight".

## What the bounds guard was doing on the harness path: nothing, and no row depended on it

`rt_guest_write_ok` has **eight callers, all of them system-library handlers** (`kernel.c`, `clock.c`,
`pthread_sema.c`, `appcontent.c`); `grep -rn 'rt_guest_write_ok\|rt_guest_ptr_ok'` over every replaced body
finds **none**. So no leaf family ever consulted it: `mov rax,[rdi+K];ret` and its siblings are compared on
their returned values and their buffers, and the guard's state cannot change a recorded verdict. **The
21,128 `edge-verified` rows stand.**

What the differential does guarantee is stated where `edge-verified` is defined: **output equality over
authored cases.** What it does **not** guarantee, and must not be implied anywhere: that every memory access
of a replacement body was range-validated. On the harness path the guard was **inert** — its subject
`rt_process.image` was NULL, so it admitted every address through an unsigned underflow — and on the boot
path it covered the image only. Two different states, one function, and neither is the guarantee a reader
would infer from the name.

The subject is now declared in the one function that is told what the image is, in both callers:
`bbgame_init` sets `rt_process.image`/`image_size` from `host->image`, as `boot.c` does on its own path.
**A guard whose subject is never initialised is a licence, not a guard,** and this one had been a licence
on exactly the path the campaign's evidence comes from.

## `runtime-witnessed` emits a case, or it is only an anecdote

A capture is written with `tools/case_emit.py` in **the schema `verify.py` reads**, so the first in-game
witness is immediately replayable through the original-vs-replacement differential. That upgrades the axis
from *the body ran once* to **a differential over an input the game produced** — the closest thing to
in-game evidence available without a full in-game differential.

* **The guest PC is the identifier** (`id == address == pc`), so a capture, a ledger row and a replay share
  one key; the emitter refuses anything that is not a ten-character address, because a short key would not
  join the ledger.
* **What could not be reconstructed is reported, not invented**: registers become the case's `args`,
  buffers become `buffers`, and every read past them is listed in `uncovered`. A fabricated preset would
  pass the differential on an input the game never produced.
* **The emit is proved by the reader, not by its own idea of the format**: `test/test_case_emit.py`
  re-emits forty real cases from `../data/cases` and requires the same `schema`, `address`, `args` and
  `buffers`, asserting the number actually compared so a filter that skips everything cannot read as green.

The cheap check the companion asked for is the reason this landed before the hook path is trusted: **a
format nobody has loaded is wrong in exactly one field.**

## A capture's pointers are classified by owning object, and the table that classifies them does not exist yet

`pbboot` maps several objects; the harness maps one image. A pointer captured inside `libc.elf` replays as
**the same number over eboot's bytes** — differential passes, answer is about a buffer the game never had.
So `case_emit.emit_capture()` classifies every captured pointer against an object table and writes only
ownership-`eboot` pointers with bytes as `args`; **anything else goes into `uncovered` with its object named**
(`rsi: 0xe10040 in libc.elf`), and an eboot pointer with no captured bytes is `uncovered (no bytes captured)`
rather than a preset. Two tests pin both halves.

**The finding this produced: the object table has no artifact.** `symbols/boot.json` records module *names and
counts* (`libc.elf` 2,140 exports, `libSceFios2.elf` 165) and **no bases or sizes**, so the classification
currently has nothing to classify against. The loader is the only thing that knows, and it must print
`object <name> guest <start> size <n>` at boot — one line per object — before a capture can be classified
at all. Until then the emitter's contract is proved against a synthetic table, which is the same species of
proof as a check that has never fired on its subject.

`0x02418d20 frame_timing_frame_step` is in `symbols/functions.csv` at **467 bytes, status `verified`** — so
`id == address` joins the ledger row instead of 404-ing at replay time.

## The object table is a file, and the first capture is on a hand-authored row

`runtime/boot.c` now writes **`symbols/objects.csv`** (`name,guest_start,size,kind`) once per boot, and
`case_emit.load_objects()` reads it. **The print stays for the operator; the file is for the tool** — an
emitter parsing a log line breaks silently the first time the line is reworded: every pointer becomes
`uncovered` and the capture then looks clean. Same reasoning as `imports.csv`: a log line is a fact about one
run. `load_objects()` sorts by base, and `overlapping()` reports a table that is not a partition instead of
absorbing it, because first-match classification is correct behaviour over a defective table.

The writer lives where the bases are decided, and guest start is **the image delta from its own mapping base
plus `RT_EBOOT_BASE`** — the number the catalog uses, so a captured pointer joins it directly. The file does
not exist until a boot runs; until then the emitter's contract is proved against a synthetic table.

**The first capture target is `hand`, not generated.** `replacement_origins.csv` records the row's origin as
`hand`, so the first `runtime-witnessed` event is on hand-authored C and **says nothing about the generated
majority**. The capture's record carries `origin=hand` in `note`, because a count that does not carry that
will imply a claim the event cannot support. On the other hand, the row is one of the 21 `verified` rows, so
a surprise there is a surprise about **integration, not decompilation** — which is the axis the capture
exists to measure, and the two claims stay separable.

### The object table exists, and my "takes a boot" was an assumption in a limit's clothes

The boot was one command: `pbboot ../data/bb/elf/eboot.elf --module ../data/bb/elf/libc.elf
--module ../data/bb/elf/libSceFios2.elf`. The file now reads

```
name,guest_start,size,kind
eboot,0x00400000,91042036,eboot
libc.elf,0x80400000,878112,module
libSceFios2.elf,0x84400000,1525820,module
```

`overlapping()` → none: the three ranges are a partition. All four reachable hook addresses classify as
**eboot**; a module pointer at `0x80400010` classifies as **libc.elf**.

Two corrections, both needed before the file was right. **(1)** The writer sat in the block that runs after
`run_guest()` returns, so the wall (`rt_fatal`, rc=134) exited before it — **a table written where the run
ends is absent on exactly the runs that need it first**; it now writes at load time. **(2)** Guest start
subtracted each object's own mapping base, which printed `libc.elf` at `0x00400000` — **eboot's address**.
It now uses the single translation base `GUEST_BASE` that `guest.h` uses, and the module lands at
`0x80400000`. **That defect was found by `overlapping()`, which is why the helper exists.**

**The writer is env-gated, fail-closed: `BB_OBJECTS_CSV=symbols/objects.csv pbboot … <eboot> --module …`.**
The unconditional write let the **test suite** overwrite this artifact within the same slice that created it —
the suite boots a mock eboot of 8192 bytes, so the tracked table briefly read `eboot,0x00400000,8192` and
`m.elf,0x80400000,4096`. **An artifact written by every run of anything is an artifact nobody can cite**;
a guard on the output protects the state.

**(3)** The gate's first version wrote `if (!t) … else fclose(t)` and **segfaulted every boot in the suite**
(four failures, rc −11, against `pbboot sha256 ac188cdab9f9`): with the variable unset `t` is `NULL` and the
`else` branch ran `fclose(NULL)`. Unset is now silent, set-but-unwritable is an error — **a request that
failed is not the same thing as a request not made.** Suite 317 OK, ctest 16/16, and `symbols/objects.csv`
unchanged after both.

## A case carries no address at all, so the emit is a copy and the conversion never exists

Settled from data, not from the schema I remembered: **35,344 cases** in `../data/cases` carry `args`;
every buffer reference is `buf:<name>` or **`buf:<name>+0x<offset>`**, and **0 of 16 buffer names are
address-shaped**. A pointer is expressed as *an offset into a declared region*, so the document never holds a
guest address and never holds a host one. **The emit is therefore a copy**, and the "does it need
`0x800000000 + (ptr − 0x400000)`" question has no referent: there is nothing in the case to convert.

`emit_capture()` was rewritten to speak that convention: `buffers` is keyed by name and may carry `address`
and `size`, a captured pointer inside a declared region becomes `buf:<name>` (or `buf:<name>+0x<offset>` when
it is not at the base), a pointer outside every declared region but inside an object is `uncovered` with its
object named, and a pointer in no object at all is emitted as a scalar. Two tests pin it, and the
population test refuses the whole file set if any `buf:` reference names an undeclared buffer — **a
filter that skips everything must not pass as a green.**

**eboot's size, checked against the ELF's own segments.** `readelf -lW` gives LOAD1 `vaddr 0 memsz
0x50d96dc` and LOAD2 `vaddr 0x50dc000 memsz 0x5f70f4`, so the image ends at `0x56d30f4` = **91,074,804 B**
from the base. The table says **91,042,036**, which is **32,768 B (0x8000) short** — so a pointer in that
last 32 KiB would classify as outside eboot and be reported `uncovered`. That is the safe direction (a false
negative, not an in-range false positive), and it is a defect: `o->size` is not the ELF's extent end. The
catalog's highest address `0x02fbe370` is far inside (offset 45,842,288 of 91,042,036), which the size test
asserts.

### The assumed region size is a field, and the padding is poison

A capture knows **where** a pointer points and **what bytes are there**; it cannot know **how many bytes the
body reads**. So `emit_capture(..., size_assumed=N)` writes `size_assumed` into the buffer spec alongside
`size` and `bytes` — **the limitation lives in the artifact, not in a message** — and pads the region past
what was captured with `POISON = 0xA5`, not with mapped zero.

Why poison rather than zero: **a body that reads past the captured region gets a distinguishable value
instead of a plausible one, and the original cannot be fooled into the same wrong answer.** The failure this
prevents is the one a differential cannot see — **if both sides read past the region and fault identically,
the comparison reports agreement.** The replay path inherits the rule explicitly: **a fault on either side is
a failed capture, not a match.**

**The size is proved, not chosen.** Capstone over the first target's 112 catalogued instructions gives a
widest memory access of **8 bytes** and no SIMD in its shape, so `WIDEST_ACCESS_BYTES = 8` and an assumed
region is a multiple of it (16 / 64 / 128 all are). **64 bytes picked by feel would be a remembered constant
wearing a field name.** The harness has no poison convention of its own — `verify.py`'s "canary" is a
falsification check on the comparison, not a fill value — so this field and its constant are new here.
