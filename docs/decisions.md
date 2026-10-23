# Decision log

Decisions are final unless their stated revisit condition triggers. Each entry names what
implements it, so "decided" and "in force" cannot drift apart.

## 1. Bare-`ret` bodies (7,761): inline asm, not an empty C body

**Decided: asm form.** The byte-exactness guarantee comes from the byte assertion (a `c3` check in
CI), not from the source form; the source form's job is to state intent. Under an unverified
compiler, `void f(void){}` predicts clang's behaviour (`-O0` prologue, `-fcf-protection` prepending
`endbr64`), while `__asm__("ret")` is flag-independent and immune to both drift classes.

- These carry an origin marker distinguishing **asm-by-design** from **asm-as-placeholder** ("not
  yet decompiled"), or a future contributor spends effort "finishing" them.
- Every one carries the same byte assertion as any other function.

**Owed:** the byte-assertion tool itself. As of this entry `ls tools | grep -i byte` is empty — the
guarantee the decision rests on does not exist yet, and no asm family may land before it does.

## 2. General rule for single-instruction asm bodies

**Decided: a rule, not an enumerated list**, with three teeth:

1. **Uniform verification** — every asm body carries the same byte assertion as `ret`, no
   exceptions.
2. **Strict single-instruction definition** — one instruction only; operands may come from C
   values; **no sequencing of multiple asm statements** (sequencing is where the policy rots).
3. **Monotonic-count governance** — the asm-body count is a tracked metric and may only grow by
   explicit approval.

**Binding applies to:** `mov al,K;ret` (793) and `mov al,[rdi+K];ret` (245) — a body that must name
entry `rax`, which C cannot — and `ret` itself (7,761). A body of one instruction plus the
terminator is within 1 + 2, since the terminator is decision 1's subject.

## 3. Hash-based approval of large sets (8,073)

**Decided: yes, with four conditions.** (a) The hash covers the **shape predicate**, not only the
member list — otherwise redefining the predicate silently invalidates the approval. (b) CI checks
the recorded hash against the current set. (c) Member extraction is deterministic **and tested**;
trust in a hash approval reduces entirely to trust in the extractor. (d) **A delta-review path is
required**: when a set changes and the approval decays, the re-review shows what entered and left.
Without delta tooling, hash decay becomes approval churn and someone rubber-stamps to make it stop —
that is the failure mode to design against.

## 4. Approval `scope`: absent vs garbage

**Decided: absent defaults to the narrow scope (`function`); garbage errors loudly.** A typo like
`shap` must not silently narrow to `function`, leaving someone believing they hold a shape approval.

**In force:** `validate_functions.py:353-357` — empty becomes `function`; anything not in
`REVIEW_SCOPES` is refused by name.

## 5. The 528 `zero_init` functions: self-approved, machine-verified

**Decided: approve, but labelled exactly what they are — "self-approved, machine-verified", never
"approved".** Mutation testing applies to the set. If a second human appears they upgrade the label
**by sampling**, not by re-reviewing all 528. `approver != author` is reserved for shapes complex
enough that self-review is the weak link; `zero_init` is near the floor of that risk curve.

## 6. Cross-runtime delegation boundary: four prohibitions

**Never cross: the allocator, `FILE*`, and load-bearing `errno`. Pin the locale.**
Allocator — each runtime frees its own; mismatch is silent corruption. `FILE*` — handle semantics
differ. `errno` — delegated formatting sets it in one runtime while the host reads the other's, so
errors cross as **return values only**. Locale — formatting is locale-sensitive; pin it in the
delegation contract or expect a miserable bug.

## 7. SSE density 0.05

**Decided: accept 0.05, but fix the metric before fixing the threshold.** (a) Validate the
threshold against **known** SSE users before trusting it on unknowns. (b) **Tiny-function
instability**: 4 instructions with one SSE op scores 0.25 — add an absolute-count floor or a minimum
size. (c) **Weight by instruction class**: `xorps`/`movaps` for zeroing and copies are benign and
C-expressible; arithmetic SSE is the signal. At minimum, measure how much of the near-zero mass is
benign-SSE noise before locking the number.

## 8. The decompiler-batch follow-up: withdrawn

**Withdrawn 2026-10-22. Revisit only if re-decompile frequency exceeds N per month.** The premise
died when batching measured ~60 minutes for the whole >1,024 B tier (17.6x cheaper than the
per-function run), not 17.5 h. This entry exists because the item was promised nine times and
shipped zero: an unrecorded death is a tenth promise waiting.

## 9. Depth over breadth — timeboxed, evidence standard first

**Decided: one function executed end to end, ~40 turns, explicit kill criteria.** The value is not
the count (21 to 22 is nothing); it is that depth is the only path that validates the full pipeline
and the only one that needs no external human. **Define what observation proves the function ran
before writing the body** — breakpoint, coverage, log line — and if that path does not exist,
building it is the deliverable and possibly the real blocker. Target: **the smallest executed
function with no unshaped dependencies.** Expiry on tooling gaps returns to breadth **with a price
measured**; that is a success of the timebox, not a failure.

## 10. Push cadence

The human pushes (askpass blocks the agent). **Per-landed-packet cadence** thereafter, and the agent
writes a **bundle file as a build artifact** so the human's manual step is one command, never a
decision.

### 1a. Measured, after the byte tool existed

`tools/check_asm_bytes.py` compares the bytes the CPU executes (read at the function pointer
in-process) against the original extent in `eboot.elf`. Three results, one of which corrects a
sentence I wrote from reasoning rather than measurement:

- `bb_asm_pilot_004034f0` — naked `asm("movb $1, %al; ret")` vs `0x004034f0`: **3 of 3 bytes
  identical** (`b0 01 c3`).
- `bb_c_pilot_004034f0` — a C body of the same shape: **differs at offset 0**, `b001c3` vs
  `554889`. The control fires, so the assertion can fail.
- `bb_c_pilot_ret` — empty C `void` body vs a `ret`-only extent (`0x00406600`, byte `c3`):
  **differs at offset 0**, `c3` vs `55`.

That last one is the correction. I wrote that for the 1-byte family "byte equality is necessary and
not sufficient, because an empty C body at `-O2` emits one `c3`" — **and in this tree's actual
configuration the empty C body emits `push rbp` first**, so the assertion *does* distinguish. The
statement was true about clang at `-O2` and false about the artifact in front of me, which is the
distinction that matters: **the byte assertion is exactly the instrument that catches a future
flags change, and its green means "these bytes are the original's", not "this source form is the
reason".** Decision 1's stability argument stands on its own; it just cannot be *rescue* for a
check that turns out to work.

### 1b. The byte-identity evidence tier: a case-set value, never a fourth status

Byte identity makes the differential redundant for the asm families — equal executed bytes to the
original extent is equivalence, not a proxy for it — so **8,799 members would cost zero cases.**
What that must not become is a row pretending a differential ran.

**`original | edge-verified | verified` is a partition**; a fourth status would make `edge-verified`
mean "a differential ran" for some rows and "the bytes were compared" for others, and no reader
could tell which. So the tier is a value of the **`cases`** field — `bytes`, meaning *no case set;
the evidence is byte identity* — and `evidence_hash()` already hashes `cases|option|cases_sha256`,
so **the kind is inside every approval and moving a row from `edge` to `bytes` decays it.**
`test/test_evidence_bytes.py` holds both halves: accepted, and the hash moves.

**Owed:** `progress.py --join` must print the split, or the headline silently merges 8,799
byte-backed members with 22,376 differentially-backed ones, and the first question anyone asks of
14.20% is "which of these actually ran?" **Owed:** the byte-assertion corpus digest for
`cases_sha256` (a hash over `(address, executed bytes)` pairs), and one `record_many` call proving
the path accepts `cases='bytes'` — the test above proves the vocabulary, not the writer.

### 1c. The digest decays in one direction and holds in the other — measured, not argued

Four builds of the same member set, `bb_asm_pilot_004034f0` against `0x004034f0`:

| build | digest | so_sha256 | outcome |
|---|---|---|---|
| baseline | `15f7205eb6957de7` | `4f485606570ce154` | matched 1 of 1 |
| comment-only edit | `15f7205eb6957de7` | `4f485606570ce154` | **identical — the control** |
| `movb $2` | — | `609b0f848c2e2e81` | **refused, 0 of 1 identical** |
| restored | `15f7205eb6957de7` | `4f485606570ce154` | back to baseline exactly |

**The second row is the one that makes the first four worth anything:** without it, a digest that
moved on every build would look exactly like a correct one. And the fourth proves the build is
reproducible for this purpose — same sources, same bytes, same digest. ±1, the mutant discipline,
applied to a build rather than to an instruction.

### 1d. The writer is proved; the family's numbers are pre-registered before it runs

`record_many` refuses a root with no HEAD ("cannot read HEAD … the pre-record snapshot is diffed
against a commit"), so the writer proof ran against the real tree and was reverted with
`git checkout`, not with a patch:

    record_many({cases:'bytes', total:1, passed:1, cases_sha256:'15f7205eb6957de7'})  -> wrote 1
    evidence_hash('leaf_asm_pilot_004034f0')                                        -> d6c8b9a36ec19632
    ledger split  rows 22478 / functions 22377 / byte_backed 1 / differential 22376
    after `git checkout -- symbols/verification.csv`  rows 22477 / functions 22376 / byte_backed 0

So the tier is end-to-end: vocabulary, writer, hash, progress split. **The digest is family-wide by
design** — all 793 rows carry the same `cases_sha256` — because one bad member then decays all 793
instead of leaving 792 approvals standing over a broken family, and per-member digests would let a
cherry-picked subset look clean. Each row's `source` says `check_asm_bytes.py` and the note says
the claim is family-wide; a reviewer reading one row must know the scope of what backs it.

**Pre-registered, from the size column, before the run:** 22,376 → **23,169** edge-verified · rows
**+793** · bytes **252,274 → 254,653 (+2,379)** from `{3: 793}` · evidence line
**`22376 differential / 793 byte-identical`**. **If any of the four disagrees, stop and read —
never adjust the expectation to meet the output.**

### 1e. Byte-tier families need no case schema, and big families need per-batch digests

`mov al,[rdi+K]` landed with **no buffer, no snapshot, no marker**: under `cases='bytes'` nothing
declares anything, and the claim is "these bytes are the original's". **The byte tier is what makes
the 245 and the 624 cheap — reintroducing the case schema out of habit would cost it back.**

For `ret` (7,761) one family digest is the wrong blast radius: a single bad member would decay all
7,761 and say nothing about *where*, and bisecting across a dozen tool runs is not a diagnosis.
**Batch by ~500, one digest per batch:** a failure localises to its batch and names it, and rows
still cannot be cherry-picked inside a batch. `record_bytes_family.py --batch N` is the mechanism.

### 1f. `ret` (7,761): no mutant exists, and byte identity does not prove the source form

Every previous family had a constant to move ±1; `ret` has **no parameter, so no mutation is
possible**. The correct entry in the record is **mutants n/a, with that reason** — a family
reporting a mutant count it could not have measured is the `assert applied == 4` shape.

Byte identity proves the executed bytes equal the original extent. It does **not** prove the body
is asm: an empty C `void` body is what this tree compiles to `push rbp` today, which is a fact about
the current flags, not a proof about `c3`. **Every one of the 7,761 rows therefore reads:
byte-identical to the original extent; the source form is decision 1 and is not evidenced by these
bytes.** At 7,761 rows, that is where scope honesty has to be explicit rather than implied.

Digests are **per batch of 500** (16 batches), not one family digest: a bad member decays its
batch and names it, and rows still cannot be cherry-picked inside a batch.

### 1g. The 624 stores, and what the census says is left

Three shapes, not "the store families": `mov dword ptr [rdi+K], esi; ret` (225), `mov qword ptr
[rdi+K], rsi; ret` (200), `mov byte ptr [rdi+K], K; ret` (199). All byte-tier, **no `returns`, no
`void`, no snapshot** -- that question belonged to the differential tier and is not reopened here.

With these the byte-backed pool is **9,423** (7,761 + 793 + 245 + 624) and the leaf supply is thin:
the remaining unlanded leaves are spread over hundreds of shapes at single-digit depth, where
per-family amortisation is gone. The next mass is the **>16 B tier**, and that is a different
mechanism (a body, not a leaf), so it is a planning question, not another template row.

### 1h. Where the byte tier stops: one basic block, no branch, no loop, no call

Byte-identical transcription is honest when the whole body *is* the instruction: `mov [rdi+K],esi;
ret` has no C expression more faithful than the instruction. **It is not honest for a body with
control flow.** Applied to a 1,072-byte function it means "ship the original bytes": behaviour
preserved, nothing decompiled, 113,426 rows rising while the goal moves zero — **the
`void f(){}`-for-`ret` failure at scale, a number rising on a technicality.**

So the rule, enforced in `record_bytes_family.py::assert_no_control_flow`:

- legal: **exactly one basic block, zero calls, and the extent decodes to exactly its size**;
- illegal: any branch, loop, call, or an unplaced branch target — then the body must be a
  reimplementation and the evidence must be **differential**, never bytes.

Decided from the bytes by `tools/blocks.py` (`blocks.census`), so it is mechanical, not a
judgement. **Both directions were fired before this was relied on:** 175 `mov rax,rdi; ret` members
pass; a 64-byte extent at `0x00414a40` is refused as *3 block(s) with 1 call(s)*.

### 1i. The 2 MB size cap, and which tables are exempt

`tools/check_no_game_data.py` refuses any staged file above 2 MB. That cap stops large **artifacts**,
not the working tables that grow with the work. Exempt, each a text table the tools read and
`validate_functions.py` checks row by row: `ghidra_functions.csv` (catalogue), `verification.csv`
(evidence ledger), and **`functions.csv` (the ladder — the first table whose growth crossed the cap
on its own merits, 2.21 MB at 34,135 rows = 21.6% of the reach)**. Every further exception is a
decision recorded here, never an edit made at the moment a commit is refused.

### 1j. shape-agnostic `.byte` bodies for the remaining leaf tier — RATIFIED 2026-10-22

**Ratified by the user on 2026-10-22; the answers and their conditions are recorded in
§1l, and the conditions are obligations of the tool, not of the ratifier.**

This section satisfies `emit_byte_leaves.py::authorised()` as of 2026-10-22, which requires a line
beginning `### 1j.` containing no `PROPOSED`. The guard is line-anchored and word-checked because
the first version was a substring search, and a substring search was satisfied by the very prose of
the proposal quoting the string it looked for. **A guard that a document can satisfy by describing
the guard is not a guard.**

The census: **4,776 transcribable leaves remain over 1,168 shapes (~4 members each), 47,655 B.**
Per-shape `TEMPLATES` rows would be **1,168 rows for 4,776 members** — the per-family amortisation
trap this project already named, and a larger one.

The proposal: **one naked function per member, body = the original extent copied through `.byte`,
with one generated comment line per instruction from the same decode the §1h guard runs.** The
emitter is then shape-agnostic, §1h stays the only legality gate, and the comments cannot drift
from the bytes because they are produced from them.

**What it costs, stated against decision 1 and not around it.** Decision 1 authorised
*single-instruction* asm with a uniform byte assertion, "strictly one instruction, no sequencing",
and a monotonic asm-body count. A `.byte` body can encode several instructions and **removes the
assembler — the third instrument that named a hand-emitted mnemonic — from the loop.** The byte
assertion then proves **a transcription, not a reconstruction**: it still catches the defect class
this project actually keeps paying for (bias/offset, length, indexing — and the offset arithmetic is
already exercised for all 4,776 by `blocks.census`, which decodes every extent to exactly its
declared size), and it cannot catch "the source form is right", because there is no source form.
Under 1h that is admissible only because the extent has no branch, no loop and no call: there is no
behaviour to get wrong, only bytes to copy.

Approving this makes the asm-body count jump **11,759 → 16,535** — the monotonic-counter tooth of
decision 1 exists exactly to make that a decision rather than a drift. **This is that decision,
asked for once.**

### 1j (iv) — added before the ask goes out: position independence

`.byte` fixes the *encoding*; it does not fix the *meaning* of any instruction whose value depends
on where it sits. `lea rax,[rip+K]` executed from `libbbgame.so` computes `.so_addr + K`; the
original computed `guest_addr + K` — different by the load offset — and the byte assertion passes
because the bytes are identical. Same failure as `void f(){}` for `ret`, one tier up: **a green
certifying the wrong claim.**

So transcription is legal only when **no instruction has a RIP-relative operand, a relative branch,
or an address-valued immediate**, checked in the same capstone walk the guard already runs
(`record_bytes_family.assert_position_independent`, refusing by member name). This is not a
proposal: it is a **defect that had already landed** — `rip_add_store` 362 + `rip_load` 161 +
`rip_store` 124 = **647 byte-tier rows retracted at `git rm` of their bodies**, board
34,135 → **33,488** (21.64% → **21.23%**), bytes 285,245 → **276,841**, byte-identical
11,759 → **11,112**.

Measured with the new tooth, over the unlanded leaf set: **5,423 transcribable · 4,097 position
independent (the honest size of ask 7) · 1,326 address-dependent** — those 1,326 need C bodies
computing `image_base + K`, which is exactly how the 8,072 `lea rax,[rip+K]` members were done.

### 1j (v) — pre-registration for ask 7, written before the run exists

If 1j is ratified, the landing run is expected, to the unit:

| quantity | now | after 4,097 | source |
|---|---|---|---|
| edge-verified incl. verified | 33,488 | **37,585** | functions.csv status tally |
| ledger rows | 33,589 | **37,686** | verification.csv (**surplus stays 101**) |
| bytes | 276,841 | **316,323** | sum of the members' own sizes (39,482 B) |
| byte-identical | 11,112 | **15,209** | verification.csv `cases='bytes'` |

Batches: **9** (8 × 500 + 97), one digest each, so one bad member decays ~500 rows and names them.

Two enumerators, named rather than averaged: the **leaf census** (`C.members`) gives **4,097 / 39,482 B**;
the **size-band census** over the whole catalogue gives **4,099 / 39,488 B** for 1..16 B. They differ by
**two members**, by construction: one enumerates *leaves*, the other every unlanded catalogue row in the
band. Ask 7 covers the leaf population, 4,097.

### 1j (vi) — the >16 B tier, measured before anything is written

`tools/census_band.py` applies the §1h + 1j(iv) filter to unlanded catalogue rows by size band:

| band | unlanded | transcribable + position independent | yield | bytes |
|---|---|---|---|---|
| 1..16 | 12,578 | 4,099 | 32.6% | 39,488 |
| 17..24 | 4,846 | 977 | 20.2% | 19,484 |
| 25..32 | 6,760 | 433 | 6.4% | 12,426 |
| 33..48 | 8,696 | 490 | 5.6% | 19,412 |
| 49..64 | 8,819 | 237 | 2.7% | 13,219 |
| 65..96 | 11,523 | 245 | 2.1% | 19,355 |
| 97..128 | 8,982 | 111 | 1.2% | 12,188 |

**2,493 rows above 16 B** (2,137 of them in 17..64), not the ~5,600 a flat 5% projected: the 5% holds
as an *average* of a distribution that decays from 20.2% to 1.2% inside the first 128 bytes. **The
cheap part of the >16 B tier is the part immediately above the boundary** — and above ~128 B, single-
block, no-call, position-independent bodies are rare enough that the leaf tier is still the cheapest
supply in the catalogue.

### 1k. An address STORED INTO MEMORY has no channel — measured, both directions

The 647 rows retracted in `ee1ac58` were rebuilt as C bodies that resolve the rip-relative address at
emission time (`end of the lea + disp`, a constant) and store it through `rdi` — the convention the
8,072 `leaf_lea_rip` bodies use for *returns*. The bodies build; the cases exist; **the differential
refuses them, and the refusal is the finding.**

Measured on `leaf_rip_store_01631c60` (guest `0x1631c60`, `lea rax,[rip+0x4173bb9]` → `0x57a5820`):

| body's stored value | differential |
|---|---|
| `0x57a5820` — the guest address, correct in-game | **0/3**, `memory buf:out+0x2: original 3a replacement 7a`, `buf:out+0x4: original 08 replacement unwritten` |
| `0x8053a5820` — `IMAGE + (0x57a5820 − EBOOT_BASE)` | **3/3, clean** |

The original reports `0x8053a5820` because the harness executes it **inside the host mapping**. The
project already knows this and says so at `tools/harness.py:464–467`: *"This is a value conversion,
not a display one: the original runs in the host mapping and a computed pointer lands at
IMAGE + (guest − EBOOT_BASE), while a replacement…"* — and `Machine.normalised()` applies that
conversion **to return values only**. There is no equivalent on the memory channel, so a store of an
address is compared in whatever space the relocated original happens to use, and a correct
replacement fails.

**Storing the image-space value in the body is refused**, though it passes 3/3: it bakes the
harness's mapping into a shipping body and would put a host-mapping address into a guest buffer in
the game. A body tuned to the instrument is the `void f(){}`-for-`ret` defect with a green
differential.

**Proposed: a declared slot channel.** A case may name slots — `"guest_address_writes":
["buf:out+0x0"]` — and the harness translates the **original's** bytes in those slots from image
space to guest space, exactly as `normalised()` does for returns. **Original side only**: a
replacement that stores an image-space address must still fail, which is the only way the channel
avoids becoming an alibi. Not implemented yet, and it must not be implemented as a patch to the
`writes` diff: those are **diff runs**, and a slot whose stored bytes partly coincide with the seed
yields a run shorter than eight, which cannot be decoded back into a value. The slot must carry its
own full before/after bytes, declared, refused if the address is not inside a declared buffer.

**Pre-registered for the run after the channel exists**, per family:

| family | members | bytes | rows | cases |
|---|---|---|---|---|
| `rip_store` | 124 | 1,364 | +124 | 372 in 124 dirs, 101 distinct resolved addresses |
| `rip_add_store` | 362 | 5,430 | +362 | 1,086 in 362 dirs |

Board after both: functions **33,488 → 33,974**, ledger **33,589 → 34,075** (surplus stays 101),
bytes **276,841 → 283,635**, differential **22,376 → 22,862**. `rip_load` (161) is **not** in this
queue: it dereferences the resolved address, and nothing maps guest space for a replacement to read.

### 1k, continued — the channel landed, and its first version compared nothing

**Implemented as `guest_address_slots`**, a case key naming `{"addr", "width"}` with width 4 or 8
(anything else refuses). The harness resolves the address, refuses one outside a declared buffer,
captures the bytes before and after execution, and — critically — **translates them on the original
side only**: `harness.SIDE` is set in `_run_isolated` **before the fork**, so the replacement's bytes
are never rewritten. The `writes` diff skips any run falling entirely inside a slot, so a slot's bytes
are not compared twice in two spaces, and the slot carries its own full before/after record, which is
what makes it independent of the run-splitting problem.

**Measured, both directions, on `0x1631c60`:** original reports `buf:out+0x0 after
20587a0500000000` (= `0x57a5820`, guest) and a replacement storing image space reports
`20583a0508000000` (= `0x8053a5820`) → **`rc=1`, failed 3**, naming the slot and both hex strings.
With the guest-space body: 3/3, then **124/124** over the family. The channel refuses the body that
passes without it, which is the only property that made it admissible.

**The first version of the comparison compared nothing, and a body tuned to the instrument passed
3/3.** It read the declaration out of `case`, the parameter `compare_case` takes as an optional third
argument — and on the `run` path that map comes from `case_expectations()`, which keys on
`case['id']` while **the emitted cases have no `id` field at all**, so the map was empty and `case` was
`None`. `writes` were empty on both sides because the run fell inside the slot; the return was
translated identically on both sides; **everything compared clean.** Fixed by keying the comparison off
**what the two sides report** — the union of the slot names, with one-side-only recorded as a diff — so
no caller can switch the check off by omitting an argument, and no key convention can disaggregate it.
Named with the rest: `capture_ok.csv`'s guest-vs-image key, and now this — **a declaration looked up by
a key the two readers spell differently is a declaration half of them ignore.** Worth stating plainly:
`tools/differential.py:1184` still calls `compare_case` with no case at all; the slot check no longer
cares, and `expected_fault` fails closed there, but a future declaration read through `case` would go
inert in exactly this way.

**Family `rip_store` landed on that basis:** 124 members, `{11: 124}` → **+1,364 B**, 372 cases in 124
directories, `nm -D` 124. Board to the unit against the pre-registration: functions **33,488 →
33,612**, ledger **33,589 → 33,713** (**surplus 101 unmoved**), bytes **276,841 → 278,205**,
differential **22,376 → 22,500**, byte-identical **11,112 unmoved**, **`verified` 21 unmoved**.
Measured, not carried: `verification.csv` holds 22,541 `edge` **rows** over **22,500 functions** (the
ledger has 41 second rows), so a count quoted from rows where the metric is functions inflates the
board by 41 — the same shape as the surplus, one layer down.

`rip_add_store` (362 members, +5,430 B) is **not** in this commit: its body stores `resolved + K2`, so
it needs the same channel and its own both-directions control before it prices anything.

### 1k, third — `rip_add_store` lands, and two instruments had to be read rather than invoked

`rip_add_store` (362 members, `{15: 362}` → **+5,430 B**) landed on the same channel with the same
both-directions control: a body storing `0x80513f7f0` instead of `0x553f7f0` fails **rc=1, failed 3**,
`slot buf:out+0x0 after: original f0f7530500000000 replacement f0f7130508000000` — the two spaces
visible in one hex string pair. Board to the unit: functions **33,974**, ledger **34,075** (surplus
**101**), bytes **283,635**, differential **22,862**, byte-identical **11,112**, **`verified` 21**.

**`normalised()` is range-gated**, so the slot channel is only correct for values that land inside the
mapped image: `if IMAGE <= v < IMAGE + boot_size`. Before applying, all 362 stored values were checked
and land in `0x553f7d0..0x57623e0`, inside the guest image — measured, because a value outside the
range would be compared untranslated on both sides and fail for a reason that has nothing to do with
the body.

**The emitter's `members()` returns nothing for a landed family**, by design (`members()` skips
landed addresses, which is the single-selector repair from the `12482 flipped` defect). Consequence
found the hard way: the control could not be built from `members()` and had to be built from the
**artifact** — parse the body file for name/constant pairs. That is the `--reemit` debt arriving as a
concrete cost rather than a predicted one: **once a family is landed, the generator is not able to tell
you what it emitted.**

**Two stale numbers per family, both forced, both caught by their guards:** `symbols/capture_ok.csv`
(`so_sha256` moves on every relink) and the `memory` corpus count in `docs/capture-protocol.md`
(22,218 → 23,304 with this family's 1,086 cases). The second is a doc quoting a **corpus count**, so
every landing expires it — a fixture of the present with a dated label. Recorded as a cost, not a
surprise; the predicate (`grep -rl '"memory"'`) is the stable thing and the number is not.

### 1k, fourth — `--reemit`, and the third arrival of "a prefix is not a population"

**The generator can now answer "what did I emit" without reading the artifact.** `members(name,
landed=True)` selects exactly the addresses carrying a `leaf_<name>_*` row; `reemit()` re-derives the
body from the census, **refuses if any landed member cannot be reproduced** (naming the addresses and
the counts), and otherwise compares the regenerated text with the committed file **byte for byte**,
with `--write` opt-in and `git status` as the witness. Landed: 14 families reproduce exactly, `ret`
included at **7,761** members, and `rip_load` correctly reports that no rows exist for it.

**Writing it reproduced the defect it was meant to prevent, in its third costume.** The first
`landed_rows()` used `startswith(f'leaf_{name}_')`, so `ret` matched **12,482** rows — its own 7,761
plus the 4,721 `leaf_ret_zero_*` members owned by a different emitter — and the refusal printed
`7,761 of 12,482 landed members reproduce; missing 4,721 ['0x40c4c0', …]`. **The instrument caught the
instrument**: a re-emit that emitted from that population would have written 4,721 bodies under the
wrong family, exactly the 647/362 shape. Fixed by parsing the key (`rpartition('_')`, head equal to
`leaf_<name>`, tail 8 hex digits) — never a prefix, never a segment count. Same rule as the retraction
parse: **`rsplit('_', 1)`, always.**

**Empty membership is now a refusal that names the door**, not `ValueError: min() iterable argument is
empty`: a landed family prints `0 unlanded members (N already landed) … --reemit <name>`, and a family
with nothing at all prints `0 members … nothing to land and nothing to re-emit`, both `rc=1`. Proved by
`test/test_emit_leaf_family.py`, which asserts the property over **whichever families are landed**
(so landing or retracting changes its coverage instead of reddening it), plus the partial-population
refusal, the two empty messages, the named difference, and the key parse.

### 1j (v) — traps, and the fifth tooth: `fs:`/`gs:`, `rip`-relative one register over

**Traps: 65 rows, measured before the clause was written.** In the ≤16 B band, of the **4,099** rows
that passed every existing tooth, **64 execute `int 0x41` and one executes `ud2`**. A trap is not a
returning body: the differential would time out or die and the failure would be reported against the
harness rather than the body. `record_bytes_family.TRAPS` (one list, used by both the writer and
`census_band.py`, so counter and gate cannot disagree about the class) refuses `int`/`int1`/`int3`/
`into`/`ud0-2`/`syscall`/`sysenter`/`sysret`/`sysexit`/`iret*`/`hlt`/`in`/`out`/`invd`/`wbinvd`/`cli`/
`sti`/`clts`/`swapgs`/`wrfsbase`/`wrgsbase`/`rdmsr`/`wrmsr`/`lgdt`/`lidt`/`lldt`/`ltr`/`vmcall`/`vmrun`.

**`fs:`/`gs:`: the tooth costs nothing here and is still the right refusal.** Counted with control
first (capstone `op.mem.segment` reads `0x20` for `fs:` and `0x21` for `gs:`; a zero from a guessed
field is this campaign's most repeated defect): across the catalogue **7,914 rows / 16,854
instructions** — the 16,854 is an *instruction* count, not a row count, so the two numbers are two
scopes and never an average — and in the ≤16 B unlanded band **zero**, measured on the **superset**
(12,092 unlanded rows), so zero in the 4,034 as well. Segment-relative leaves in this catalogue are
longer than 16 B.

**The call-path answer, read rather than assumed.** `tools/harness.py:176` is `ctypes.CDLL(path)` and
the body is reached with `getattr(lib, name)` from CPython, and **`grep -rn wrfsbase tools/` finds only
`instruction_trace.py`'s mnemonic list — no code on the differential path can install the guest FS
base**, so `%fs` there is the host TCB. The hook path (`install_hook`'s 14-byte jump inside the guest)
runs the same bytes under the **guest** base. **One body, two meanings, decided by how it was called**
— which is why the tooth is right even though it moves no row today.

**Re-registered on the new population, not adjusted.** refusal counted by reason, zero silent:
`{'address dependent': 6,694, 'control flow': 1,298, 'decode': 1, 'trap (1j v)': 65}` →
**4,034 members over 2,598 shapes, 39,040 B** (was 4,099 / 2,602 / 39,488). Landing all of it:
functions **33,974 → 38,008** · ledger **34,075 → 38,109** (surplus 101) · bytes **283,635 → 322,675**
· byte-identical **11,112 → 15,146** (`differential 22,862 + 15,146 = 38,008`, so nothing is
double-counted) · **9 batches, 8 × 500 + 34**.

### 1h-b — the differential tier's TLS blind spot: TLS-touching bodies need capture, not a better assertion

**Both sides of a differential run in the harness process, so `%fs` is the host TCB on both sides.**
`tools/harness.py:167–187` maps the guest image itself (`rt_elf_map`, `LOADER_BIND`, `IMAGE =
0x800000000`) and installs the replacement with `ctypes.CDLL(path)` + `getattr(lib, name)` (`:176`);
`grep -rn wrfsbase tools/` finds only `instruction_trace.py`'s mnemonic list. Nothing on that path can
set the guest FS base.

**Consequence: a TLS-touching body is compared host-TLS-to-host-TLS.** The differential is green by
construction and green *about the wrong subject* — it cannot detect the difference, because both sides
carry the same error. Third member of one family: the comparator whose input was empty, the `.byte`
body admitted by a range check over a guessed bound, now the base identity on both sides. **A
measurement whose subject is outside the instrument is not repaired by a stronger assertion.**

**In-game the same bytes run under the guest base** (`install_hook`'s 14-byte jump executes inside the
guest), and the guest TLS block is modelled as **one** of three PT_TLS carriers with `tls.c:33`
hardcoding `0x4a0` — so the in-game value comes from a block the runtime only partially models.

**The rule, stated once so the deep tier inherits it:**
- A **TLS-touching** body can be honestly `edge-verified` only as *"defined relative to whatever base
  the caller supplies"* — which excludes the in-game value. That is not the claim a ledger row makes.
  Its route to a claim is **capture** (an in-game witness), the same route pool B needs.
- **Pool B can never produce `verified`** (a synthesized body has no in-game witness). Sharpen it:
  **a TLS-touching body cannot honestly produce `edge-verified` either.** Two different reasons, one
  destination.
- Within the byte tier the shape is already refused (`fs:`/`gs:` tooth, §1j (iv)); the tier mechanism
  for the differential tier is a case-level **TLS slot** — the `guest_address_slots` shape one tier
  over, declared with before/after — **not built**, named here as the route.

**Where it bites, measured (not estimated):** 7,914 rows / 16,854 instructions catalogue-wide, and
**zero of them sit at or below 16 B** — the whole ≤16 B population is 44,331 rows (32,239 landed +
12,092 unlanded) with **0** TLS-touching members. So **every one of the 7,914 lives in the deep tier**
(113,426 rows above 16 B = **7.0%**), i.e. exactly the 2,277-body and 113,426-row work that inherits
this rule rather than rediscovering it.

**Measurement note:** the first attempt at a size histogram swept all 157,757 rows with `detail=True`
and was killed by the 600 s tool cap. **A killed sweep is a censored measurement, not a zero, and not
a sample** — so the question was narrowed to the population that can answer it (rows ≤16 B) instead of
re-running the same sweep and hoping.

### 1h-c — the TLS-slot mechanism is `fork`, not a slot; and the byte tier's population is the partition's

**Not buildable in-process.** Setting the guest FS base from inside the harness means `arch_prctl(
ARCH_SET_FS)` or `wrfsbase` against the **harness's own thread**, and CPython's TCB lives there: `errno`,
the exception state and the GIL would all break. A case-level slot the shape of `guest_address_slots`
would be cheap and wrong, and it would present as a harness crash rather than as a TLS diagnosis. The
mechanism is **`fork()` a child, set FS there, run both sides in it, report the verdict through a
pipe** — the `differential.py` `_run_isolated` fork extended by one `wrfsbase`, and it is **not built**,
because the deep tier is the only consumer and 0 of the ≤16 B rows touch TLS. Recorded so the next
session does not start with the slot.

**The byte tier's population is the catalogue's 1..16 B unlanded rows, not the leaf-shape census.**
The shape census recognises **5,888** of the **12,092**; emitting from it gave **4,033 / 39,036 B**
where the pre-registration says **4,034 / 39,040 B** — a near-match, which is the "two instruments, one
number" trap and not agreement. Byte transcription is shape-agnostic, so the emitter now iterates the
partition.

**One tooth set, proved by two implementations counting to the same digit.** `refusal()` in
`record_bytes_family` is now the only place the 1j (iv)/(v) predicates live — and it was **missing the
relative branch/call tooth**, which the emitter's dry run exposed as a 5,076-row disagreement with
`census_band.py`. After adding it, the two instruments print, independently:

```
emit_byte_leaves.py   4,034 leaves, 39,040 B   {control flow 1,298, decode 1, address dependent 6,694, trap 65}
census_band.py        4,034 over 2,598 shapes   {address dependent 6,694, control flow 1,298, decode 1, trap 65}
```

**A tooth in the counter and not in the emitter is the 647 retraction waiting to happen**, and the
emitter shipped with §1h alone — it would have emitted bodies for all 6,694 address-dependent rows.

**The band is priced, written once, and ungated on ask 7.** `tools/land_bytes_band.py` writes the
band's rows at `original` in a single pass (no cases: byte evidence is the digest, and a case file here
would be differential-tier cost for byte-tier evidence). It **refuses before pricing anything** while
`docs/decisions.md:243` still reads `### 1j — PROPOSED, NOT IN FORCE`: the rows presuppose an answer
the ratifier has not given, so bookkeeping them would be a claim made on the ratifier's behalf. I wrote
the 4,034 rows once, saw them land, and reverted them — **the gate fired on a real population and not
on a fixture**, which is the only way to know it is placed rather than able.

**And a selector, not a second copy of one.** `leaf_family_census.landed_addresses()` is now the single
answer to *does a body exist for this address?* — **rows past `original`, never rows that merely
exist**. Writing the band exposed the difference: the counter said 12,092 unlanded while the emitter
said 4,034 + 8,059 = 12,093, both "right" about different populations. With one selector both print
`unlanded 12093 · 4,034 over 2,598 shapes · 39,040 B · {address dependent 6,695, control flow 1,298,
decode 1, trap 65}`. **The deliverable did not move — 4,034 and 39,040 B are unchanged — only the
denominator did**, and a corrected denominator that leaves the paid quantity alone is the cheap kind.

### 1l. Answers of record — six asks and ask 7, 2026-10-22

Recorded here because **an answer that lives in a chat message cannot be read by the person it
constrains**, and every one of these carries obligations that outlive the conversation. Each is
quoted as given, with the condition it attached; the conditions are the tool's work, and none of it
is done yet.

1. **Rule-level approval — YES.** One approval per *rule*, with a machine-checked transcription over
   **every** member and **2–3 executed spot checks per template**. Condition: **the approval hash
   must cover the rule predicate itself, not only the membership list**, and a membership-set change
   triggers **delta review (what entered, what left), not a full re-review.** *Obligation: the hash
   today (`member_set_hash`) covers membership only; a rule-predicate field must enter the same hash
   or the approval renews itself silently when the predicate changes.*
2. **Delegation — YES for stream/string/formatting; REFUSED for the allocator and `FILE*` interop.**
   Two boundary conditions added: **`errno` never crosses — errors as return values only**, and
   **locale is pinned in the delegation contract**, because formatting is locale-sensitive.
   *Obligation: both conditions in the contract before any delegated family lands.*
3. **SSE residual — YES, ≤0.05 as a stated bound, not a claim of exactness.** Conditions: **validate
   the threshold against known SSE users before trusting it**, add a **minimum function size or
   absolute-count floor**, and **weight by instruction class** (benign `xorps`/`movaps` versus
   arithmetic SSE). *Obligation: an unweighted residual over a population that is mostly register
   moves is a number about the population; the floor is what stops it being an average.*
4. **The 528 `zero_init` — YES, by the user, for this class**, conditional on **machine-checked
   transcription and mutation testing of the set**. The signature attests **the rule and the
   checker, not 528 individually read rows**, and the tier must be labelled honestly —
   **`shape-approved, machine-verified`**, never `approved`. *Obligation: a distinct status token,
   and the existing `approved` column must not be reused for it.*
5. **`ret` 7,761 — YES, naked asm**, one-byte `c3` assertion on each. Explicitly acknowledged: the
   purchase is **flag-independence under an unverified compiler, not a different byte stream**, and
   these must be **marked `asm-by-design`** so no one spends effort "finishing" them.
6. **`scope` — YES, shape-scoped claims alongside function-scoped, the shape named in the row.**
   Parser contract: **accept exactly `function`, `shape`, or absent (absent defaults to
   `function`); reject anything else loudly.** *A typo must error, never silently narrow.*
   *Obligation: the current `shape_answer` predicate matches `scope=shape` anywhere in a
   non-comment line, which is a satisfied-by-description guard of the same family as 1j's; it must
   become a field parse.*
7. **`### 1j` — ratified 2026-10-22** by the user's own edit to this file. The byte tier is
   authorised from this commit; the pre-registration in §1j (v) is unchanged, and
   **it is re-run, never adjusted.**

8. **DEBT, recorded 2026-10-23 — `source_hash` is per defining FILE, not per function.**
   Measured, not suspected: one comment line inside one of ten `rip_load_wide` bodies made all ten
   ledger rows stale at once (`08d6e34a3ffc7eca` -> `a7410dce547c013a`), so the staleness guard is
   conservative in the right direction and **cannot localise** -- it refuses a family, never a
   member. Population beside the debt, because a debt without one reads as a nit:
   `game/leaf/bytes_family.cpp` holds **4,034 bodies in one file**, so a one-member edit invalidates
   4,034 evidence rows and re-runs the file -- the 7,051-second finish-condition calculation with a
   different multiplier. Today the population is **10**, which is when this is a function and not a
   cliff. The fix is the content-hash principle `symbols/capture_ok.csv` already uses: hash the
   body's own bytes (the `bb_<name>` definition as emitted), not the file that happens to hold it.
   Until then, `promote.py --to edge-verified` over-reports staleness at family granularity and
   never under-reports it -- the direction that refuses work rather than crediting it.

### 1m — TCB fields are measured, and a zeroed TCB is a permissive zero

`tools/census_tcb_arith.py` over `symbols/ghidra_functions.csv`: **16,508 `%fs` sites, one distinct
displacement, `0x0`** — every one of them `mov rax, qword ptr fs:[0]`, the `tcb_self` slot. But the
displacement histogram measures where the door is, not the room behind it: **8,992 of those reads take
the pointer out of `fs:0` and dereference it within sixteen instructions, reaching 71 distinct offsets in
8,933 accesses.** Rank: `+0x58` 3,870 · `+0x20` 3,787 · `+0x10` 815 · `+0x8` 83 · `+0x18` 41 · `+0x50` 30 ·
`+0x60` 26 · `+0x30` 24 · `+0x90` 20 · `-0x8` 18 · `+0x80` 15 · `+0x28` 14. Negatives total 18, so module
TLS at negative offsets is *nearly absent* from eboot and cannot be what the TCB is for.

The first run of that tool printed `0` for the second number. That zero was **the instrument**: Intel
syntax puts the load's destination at operand 0, so a filter reading `operands[0].mem` cannot match a
load, and `0 reads` looked exactly like an absence. Printed shapes are now part of its output.

So the runtime installs a **zeroed 0x100-byte TCB** and the guest reads `[rax+0x58]`, `[rax+0x20]`,
`[rax+0x10]` from it **8,933 times**. A zero there is not a missing feature, it is a permissive zero in
the one structure the whole thread model is built on: `mov rdi, [rax+0x58]` yields null and the next
dereference of `rdi` is the `address 0x0` fault this campaign has already spent slices diagnosing.

In force: **`scePthreadCreate` is not implemented before these offsets have meanings.** The refusal it
emits today is the correct behaviour for a runtime whose TCB has no declared layout. Implementing a
thread on a zeroed TCB would manufacture the next fault in a fresh population and pay for it there.
Revisit condition: name the field behind `+0x20`, `+0x58` and `+0x10` from evidence (a write site, a
provider's write, or a catalogue function that both writes and reads the same offset), and only then
emit a layout.

**Correction, same day — the ranking above mixed two depths.** The chain is
`mov rax, fs:[0]` · `add rax, qword ptr [rip + G]` · `mov rax, qword ptr [rax]` · `mov rdi, [rax + 0x58]`,
so `+0x58` is a field of an object obtained *through* the TCB, not a TCB field. Two versions of the scan
printed 0 for this reason and both were the predicate: `operands[0].mem` cannot match a load, and
`add rax, [rip+G]` both writes and reads the holder, so a clobber rule named carelessly truncated the
chain at instruction one. The walk is now depth-tracked and the pure-write mnemonics are listed
explicitly. Re-measured:

* **depth 0 — TCB fields: 31 distinct, 1,390 accesses**; `+0x10` 1,284 · `+0x30` 19 · `+0x20` 10 ·
  `+0x120` 8 · `+0x210` 8 · `+0x8` 8. **Written by eboot: `+0x10` 611 times, `+0x30` 1, `+0x20` 1,
  `+0x8` 5.**
* **depth 1 — fields of the object the TCB points at: 21 distinct, 4,021 accesses**; `+0x58` 3,733,
  then `+0x8` 72 · `+0x18` 69 · `+0x10` 56. Written by eboot: `+0x8` 31, `+0x18` 15, `+0x10` 17.
* depth 2: 5 distinct, 41 accesses.

So the layout **is** declared — in the guest's own code, not in the runtime — and 618 depth-0 writes are
the guest building its own thread structure. The runtime's correct behaviour is therefore what it already
does: a correctly sized zeroed block (now `0x750`, derived) with `tcb_self` pointing at itself. **Zeroing
was never the defect; the defect is that the code which fills these fields has not run**, because the boot
stops before it. `scePthreadCreate` stays refused for a narrower reason than 1m first stated: not because
no layout exists, but because no thread has ever reached the eboot init path that writes it.

Revised revisit condition: a thread implementation is admissible once the boot reaches the guest code that
performs the depth-0 writes (`+0x10`, 611 of them) — that is the population that proves a TCB gets built,
and it is measurable by running rather than by naming fields from their rank.

**Second correction — the spill discriminator ran, and it does not support a spill.** `--spill K` reports,
per function, whether `[tcb+K]` is written and read inside one window and how far apart. For `+0x10`:
**457 functions have both, 71 read-only, 7 write-only; median write→read distance 27 instructions, zero
pairs within 4, zero within 16, 12 over 64.** A save-before-call/restore-after slot is symmetric and a
handful of instructions wide, so the numbers refuse that explanation; `+0x10` is used like a field, with
readers that never write it. What it *is* remains unnamed — 611 writes over 457 functions is more traffic
than a per-thread slot needs, and naming it from this rank is exactly what 1m forbids.

Three zeros came out of `--spill` before this number did, all three the break rule: `add rax, [rip+G]`
writes the holder and reads it, so a `not hop` test — and before that, any write to the holder — truncated
every window at instruction one. And the first distances printed empty because the write/read lists
accumulate across every `fs:0` site in a function, so `j - i` measured from whichever site came last;
pairing distances are only meaningful in absolute instruction positions. **A pairing test whose anchors
differ per element is not a pairing test**, and the tool now prints the windows it accepted before its
counts.

**The three-way split was the real output, and the risk population is measured at zero.** Of the functions
touching `[tcb+0x10]`: 457 write and read it (a zeroed TCB cannot victimise them), 7 write only, and
**71 read it and never write it** -- the only population a zeroed TCB could fault. Intersecting those 71
against the walk from `0x004000a0`: **770 direct-edge reachable addresses, 0 hits.** On the paths the boot
can walk, the zeroed TCB cannot fault before the guest writes the field itself, so the thread question
separates from the TCB question.

**The bound is part of the result:** `guest_reach.py` follows direct edges only and **1,523 unresolved
indirect call sites** leave the visited set, so this says "no read-only `[tcb+0x10]` reader is a
direct-edge descendant of entry", not "none can run". `guest_reach.py --visited` exists for this -- its
summary reports counts, and an intersection computed against a summary is a coincidence test dressed as a
query. The first intersection I attempted read that summary and would have printed zero for the wrong
reason.

## The stub frame, computed from the emitted bytes rather than remembered

`boundary_stub.c` emits `push rdi, rsi, rdx, rcx, r8, r9` (capture form only) then `push rbx;
mov rbx,rsp; and rsp,-16; call r10`. With the guest `rsp0` pointing at its return address at stub entry:

* capture wrapper -- `rbx = rsp0-56`: `[rbx+0]` saved rbx, `+8` r9, `+16` r8, `+24` rcx, `+32` rdx,
  `+40` rsi, `+48` rdi, **`+56` the guest return address**.
* syslib boundary stub -- `rbx = rsp0-8`: `[rbx+0]` saved rbx, **`[rbx+8]` the guest return address**.

**No fixed offset from `rsp` is valid in either stub**, because `and rsp,-16` runs after `mov rbx,rsp`:
with a 16-aligned `rsp0` the handler's `rsp` is `rsp0-72`, so `[rsp+48]` reads the pushed `rdx` -- a guest
argument, which is an address-shaped value and would print as a plausible return PC. That is the
BSS-word-read-as-a-return-PC defect in its third costume. Read the frame through `rbx`, and note the offset
differs per stub: a single constant would be wrong for whichever path was not being looked at.


## The import stub table, measured (replaces three carried figures)

Scanning the whole RX segment for `jmp rel32` whose target is the resolver `0x2fbe4a8` gives **661 sites,
16 bytes apart**, first at `0x2fbe4c3`. Each stub is a fixed 16-byte record starting 11 bytes before its
resolver jump, so the table is **`0x2fbe4b8` .. `0x2fc0e08`, 661 stubs**:

    ff 25 <disp32>   jmp qword ptr [rip + disp]   ; the GOT slot, 6 bytes
    68 <imm32>       push <index>                 ; 5 bytes, always imm32
    e9 <rel32>       jmp 0x2fbe4a8                ; 5 bytes

`push` values run contiguously `0 .. 0x294`, so **index = stack position = stub number = GOT slot number**
(confirmed twice: stub 0 -> `0x2fbe4be + 0x28261d2 = 0x57e4690`; stub 660 -> `0x2fc0dfe + 0x2824d32 =
0x57e5b30 = 0x57e4690 + 8*660`). Calling a stub is `call <0x2fbe4b8 + 16*index>`.

Three carried figures corrected on the way here: the header is **not** variable-length (`push 0x2a1` and
`push 0xfc` are both imm32); the table base is `0x2fbe4b8`, and reading from `0x2fbe4b3` -- five bytes
early -- decodes as garbage, which is what my first dump did; and `docs/bind-order-eboot.txt` holds **848
bind lines**, not the 747 I have been quoting. 661 stubs against 848 binds is another pair that must not
be reconciled before both scopes are printed.

The script's first pass printed "jmp-to-resolver sites: 1" because it only counted sites whose preceding
bytes it could decode as a `push` -- **a filter printing its own acceptance count under the label "sites."**
The 661 came from counting the jumps themselves.

## Who calls scePthreadCreate, and what it does with the result (measured)

**The three-population claim was mine and it is wrong.** `docs/bind-order-eboot.txt` is a concatenation of
per-module bind tables, each renumbering from zero: line 252 is `bind 252 6UgtwV+0zb4 libkernel`, but lines
701 and 838 read `bind 14` and `bind 72` -- **other modules' ordinal 14 and 72**, whose NIDs are
`-L+-8F0+gBc` and `xeYO4u7uyJ0`, not aliases of `scePthreadCreate`. The assertion that caught it is the one
worth copying: read the NID at the ordinal you are about to use, beside the stub you are about to scan.
Scanning the union of 252/14/72 produced 546 sites, **528 of which are callers of different imports**; the
real population is **18**.

**The 18 callers, and none of them is in Ghidra's partition** -- every site falls in an uncatalogued gap
(of the 157,757 catalogued functions, none contains any of the 18). Five of them sit in one consecutive
cluster, `0x1087339 .. 0x108739e`, spaced 0x15 apart, and every one of the five has the same shape:

    call <stub 252>          ; scePthreadCreate
    cmp  eax, 0x805a1001     ; one specific code is expected
    je   <continue>          ; tolerate it and carry on
    test eax, eax
    jne  <error path>        ; any other nonzero -> error
    mov  edi, 0xb5           ; zero -> success, proceed

**So the guest branches on `rax`, and it distinguishes a specific constant from generic failure.** The
`rax == 0`-only case -- the one that would have made a returned error invisible -- **does not occur here**:
returning a nonzero code lands on a real error handler, and returning `0x805a1001` is treated as an
expected, tolerated condition rather than a failure. A modelled return code is therefore *visible* to this
caller, which is the precondition (a) needed and the opposite of what I predicted.

## The scePthreadCreate caller is a bool, and its error path only returns false

`0x1087330` is `push rbp; mov rbp,rsp` followed by five `mov edi,<id>; call <stub 252>` in a row
(`0x1c, 0xb5, 0x19, 0xb2, 0x1a`), each followed by the same three-instruction test:

    cmp eax, 0x805a1001 ; je <next thread>      ; tolerated, carry on
    test eax, eax       ; jne <its own error stub>  ; any other nonzero
    <next thread>                               ; eax == 0, carry on

and **five separate error stubs, each exactly `xor eax,eax; jmp <epilogue>`**, against a success epilogue
of `mov al,1`. So the function returns **1 if every creation succeeded or was tolerated, 0 if any did not**,
and the failure path **logs nothing, aborts nothing, and does not jump to a main-loop handler** -- it
returns false. Experiment A ("return a generic failure") therefore **cannot kill the boot at this level**:
it makes one `bool` false and the consequence moves up to whoever consumes it, which is the next thing to
read rather than the next thing to assume.

Labelling, per the two-experiment split: A measures *the consequence of a failed creation*, B (returning
`0x805a1001`) measures *the guest's tolerance of a code it is coded to accept*. B is a **modelled tolerance**
and any printout from it must say so -- a boot that reaches the init path through B has no thread in it.

## Pre-registration: the two scePthreadCreate experiments

Linear walk of `0x1087330..0x10873c6`, 50 instructions, exact: **5 creates** (`0x1c, 0xb5, 0x19, 0xb2,
0x1a`) each followed by `cmp eax,0x805a1001 / je <next call's argument> / test eax,eax / jne <xor eax,eax;
jmp epilogue>`, plus **2 internal calls** between #4 and #5 (`0x1088610`, then `0x1088360` against `test
al,al`). The boolean returned is therefore a conjunction of five creations **and** an internal predicate.
Every one of the five `je`s lands on a following instruction that is an argument, not a handler -- the
"error argument" reading was adjacency, not control flow, and a linear walk is what retires it.

**Experiment A** -- the refusal returns a generic nonzero code (not `0x805a1001`).
Pre-registered expectation: `0x1087330` returns **0** at the first `jne`, no logging, no abort, and the
measurement is what **its caller** does with that false. Outcomes, named in advance:
  * boot continues past the false  -> the five threads are not load-bearing at init; record as such.
  * boot stops with a printed reason -> the false is load-bearing one frame up; name the handler.
  * boot stops without printing    -> the false reached a path with no message; that absence is a finding.
A cannot be confused with success, because no code path through it produces a live thread.

**Experiment B** -- the refusal returns exactly `0x805a1001`. This is **modelled tolerance, not thread
creation**: `je` carries the guest past all five checks and the function returns **1** with zero threads in
existence. Pre-registered expectation: **a hang, not progress** -- the guest waits on something the five
threads would have signalled. **A timeout here must be reported as "the tolerated code did not unblock the
boot,"** never as a slow boot, never as a pass; B gets its own explicit timeout because a hang and a
deadlock share an rc in this harness. **If B hangs, that is a positive result**: it proves the five threads
are load-bearing, which no return code can tell me.

Order: A first. B only after A's consequence is read, because A is the experiment whose result cannot be
mistaken for the other.

## Correction: the fifth term is inverted, and `0x1088360` is a getter

`0x1088360` is `mov al, byte ptr [rdi + 0x192]; ret` -- **not a predicate over the creations**, a field read
on the object returned by `0x1088610`. Combined with `test al,al; je 0x10873ae`, where the target is
`mov al,1` (**success**), the function is **`creations_ok && field == 0`**, not a plain conjunction: **the
field being zero is the healthy path**, and create #5 (`0x1a`) runs only when the field is nonzero. The
earlier "conjunction of five creations and an internal predicate" inverted that term; corrected here.

**Why that does not need site instrumentation for A:** the five creations are straight-line, each
`jne <xor eax,eax; jmp epilogue>`, so **the first failure short-circuits and `0x1088360` is never reached**
-- its call site is four calls later. A fails create #1, so the false it produces cannot have come from the
field read. The ambiguity exists only when creations succeed, which is B, and B produces no false at all.
**One print still required: the refusal must say it was reached**, or a silent stop is unattributable.

**Prediction registered for A:** the boot stops **at the refusal with one create attempted and four never
reached**. If the output instead shows two or more creations attempted, the short-circuit reading is wrong
and the `je`s go somewhere other than the next call's argument -- which would contradict a linear walk
already printed, and would mean the walk and the runtime disagree about the same bytes.

## Experiment A: blocked before create #1, by a chain of unbound libc imports

Run with A's body in force (`sce_pthread_create_a`, returning `0x80020023` EAGAIN, declared MODELLED).
**The guest never reached thread creation.** The boot stopped at **libc import #33, `atexit`**
(`8G2LB+A3rzg`), with `imports called: 2`. So the pre-registered prediction -- *stops at the refusal with
one create attempted* -- is **untested, not refuted**: no create was attempted, because the init path
calls two libc imports before it gets anywhere near the threads.

**`atexit` answered as MODELLED** (registration accepted, handler never runs, because the runtime does not
exit through libc): registered 89 -> **90 = 54 real + 25 modelled + 5 noop + 6 refused**, imports
implemented 63 -> **64**, imports called 2 -> **3**, and `#33` itself called **twice**. The boot then
moved one import and stopped at **libc #40, `__cxa_guard_acquire`** (`3GPpjQdAMTw`) -- the C++ static
initialisation guard, which is a real body (read the guard byte; 1 = you must run the initialiser and call
release, 0 = already done) and the next rung, not a stub.

**A defect found by the run and unrelated to it:** `pbboot` exits **rc=0** while printing
`unimplemented` and stopping. **A stopped boot and a finished boot have the same rc**, so any harness
keying on the return code reads "the guest stopped at an unbound import" as success. `rc` is not a pass
here; the stdout line is the only signal, and a caller that does not read stdout is told the boot
succeeded.

**Confirmed, having been carried as a prediction for two slices:** the default build fails to link
`test_plugin` -- `hooks.c` references `rt_capture_begin/run_id/write` and that target does not link
`capture.c`. `runtime/pbboot` links fine, so `--target pbboot` is the honest build until the test target
is fixed; building the default target and reading rc=1 as "my change broke it" would have been wrong.

## The cxa_guard triple, guest memory behind the segment table, and a stopped boot that says so

`__cxa_guard_acquire` / `release` / `abort` are registered (imports implemented 64 -> 66, registered
89 -> 93 = **57 real** + 25 modelled + 5 noop + 6 refused). **Three registered, two counted:** `abort`
appears nowhere in `symbols/import_names.csv`, so it is a body no eboot import reaches -- registration
counts bodies, implemented counts imports, and the two numbers differ by exactly that.

The run: two acquires at **byte 0 -- initialiser must run**, two releases setting the byte, two distinct
guards (`0x8056a5740`, `0x8056a2558`). **The property that makes the triple load-bearing is
implemented and NOT yet observed**: a third acquire of either guard would print `byte 1 -- already
initialised`, and no call in this boot makes one. Until one does, `release`'s write is a body I wrote
and the read-back is a claim.

**The guard arrives in image space, not guest space.** Raw value `0x8056a5740` = `IMAGE + 0x16a5740`,
because the guest executes at the image mapping, so a `lea rip`-computed address is what the CPU
addresses. **An instruction to convert it with `rt_guest()` would have double-mapped it** -- `rt_image +
(0x8056a5740 - 0x400000)` -- and written a plausible address that is not the guard. The space is now
measured and printed on every call; the normalisation accepts both spaces and stops the boot when
neither applies.

**And `rt_image` is defined in `plugin.c`, which `pbboot` does not link** -- my first version of this
body did not link, and the linker named it. That is the shared-emitter defect in my own code, caught by
the build rather than by review. The mapping now comes from `rt_map_note(elf, image)` in the loader,
which is in `pbboot`; a body that needs the mapping asks the loader rather than reaching for a global
owned by another target.

**The return code now distinguishes stopping from finishing**: `unimplemented` -> **4**, fault -> 1,
timeout -> 2, and the guest's own exit code passed through (so a guest exiting 4 is indistinguishable
from an unbound import; the stdout line is the discriminator).

The boot then moved ten imports and stopped at **`memset`** (`8zTFvBIAIN8`, libSceLibcInternal 11 /
libc bind 61). `symbols/import_names.csv:24` already labels that row **`implemented`**, and the runtime
has no body for it: **the file's status column is a claim about intent, and the run is the measurement**
-- the same class as an approvals column that counts rows.

## memset: the wall was a library label, and the sweep built for it cannot see that class

`memset` was **registered all along** -- `runtime/syslib/kernel.c:88` under `libSceLibcInternal`. The
guest imported it through the **libc** binding of the same NID (`bind 61 8zTFvBIAIN8#q#q libc`,
`bind 11 8zTFvBIAIN8#D#E libSceLibcInternal`), and the bind loop at `boot.c:474-479` matches
`!strncmp(name, nid, 12) && !strcmp(library, s->library)` -- **read, not inferred**. So the refusal
"eboot calls libc 8zTFvBIAIN8" was a lookup that found no body under that label, not a runtime without
one. Registering it again under `libc` served it: **58 registrations, 57 distinct bodies** -- one symbol
under two labels, legitimately, and **the "real" count in the coverage line counts registrations**, so it
now overstates distinct bodies by one.

`memset`'s body returns its destination (a void body breaks every chained caller) and proves the range
writable **before the first byte**; the conversion is one helper now, bounded **both ways**
(`image <= v < image + extent`), because a threshold accepts infinity and a value past the mapping is not
in the mapping.

The guard fixture (`--selftest-guard`) asserts **the byte**, not the return codes: a body that remembers
which guards it has seen on the host and never writes the word passes a return-value fixture and fails
the moment a guest reads its own guard byte. Measured: `acquire=1 byte-after-acquire=0 release->byte=1
second-acquire=0 byte=1 -- PASS`, the byte read back through the guest mapping.

**The fixture's first placement was dead code and read exactly like a flag never passed.** It landed in
`for (size_t k = 1; ...)` -- the MODULES loop -- while eboot's entry is called after that loop, so
`selftest_guard && k == 0` could never hold, the guest ran, and the old fault came back as if nothing had
changed. An index-by-constant into a loop whose bounds are the population, third arrival.

**And the sweep is coarser than the lookup it checks.** Joining `import_names.csv`'s `implemented` rows to
the registration table by symbol name gives 43 matched / 0 missing -- and would have matched memset
through kernel.c's libSceLibcInternal entry **before the fix**, reporting zero missing about the row the
run was refusing. A join key coarser than the lookup blesses the row that is broken. The population that
can see labels is `bind-order-eboot.txt` (one row per module-table binding), not the csv (one row per
NID) -- the same 848-vs-748 gap carried since the stub table.

New wall: **signal 11 at address 0x0, pc in host space**, `rdi`/`rsi` image-space -- the guest reached 17
imports and the fault is inside host code, not in the guest mapping.
