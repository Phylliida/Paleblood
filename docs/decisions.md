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

## The fault was on the guest %fs: a host body ran with the guest TCB

`si_addr 0x0` with a **host** pc and image-space `rdi`/`rsi` is a null dereference. The candidate that
explains it: a host body running with `%fs` still on the guest TCB reads **zero** for every glibc TLS
slot -- `errno`, the stack protector's `fs:0x28` -- and the first dereference of what those zeros point at
faults at exactly `0x0`. Measured, not reasoned: `fault tls fs 0x64c06bf64040 guest 0x64c06bf64040 host
0x7b5c1f8a9740 -- GUEST TCB -- a host body ran with the guest %fs`. **The wall is the TLS base, not the
argument.**

It has to be read **before** `rt_tls_enter_host()`, which is the very act that would make every fault look
like it happened on the host. The signal frame does not carry it -- `REG_FSBASE` is not in `gregs`, whose
tail for x86-64 stops at the selector `ss` -- so a live `arch_prctl(ARCH_GET_FS)` at handler entry is the
only record. First attempt used `gregs[REG_FSBASE]` and did not compile; that is the measurement refusing
to be where I assumed it was.

**Withdrawn the same slice: "the last entered import names the body."** The `entered #N` lines are emitted
by the post-run summary loop in **import-index order** -- they are a set, not a sequence -- so `#669` being
last printed says nothing about being last called. The chronological trace does not exist; building it is
a separate instrument.

## The guard fixture is placed, and the sweep is on the runtime's own key

`add_test(NAME guard_selftest COMMAND pbboot …/eboot.elf --selftest-guard)` in the **top-level**
`CMakeLists.txt`, `SKIP_RETURN_CODE 3`: ctest `#5 guard_selftest … Passed`. A fixture outside the gate is
able, not placed.

`tools/check_implemented.py` now joins on **(NID, library)** -- the tuple `boot.c:474-479` binds on -- over
`docs/bind-order-eboot.txt`, the only population with a label per binding: **846 import rows + 2 module
rows** (the module rows are classified, never skipped: they have no NID and no library). Controls: both
labels of memset's NID must be served. **The first version of that control compared `("memset", lib)`
against a table holding `(lib, symbol)`, refused, and that refusal is the only reason the reversed key was
visible** -- a control that cannot be satisfied fails closed, which is why it is worth having.

## One byte: `49 8b 04 24` is `[r12]`, and it was carrying three anomalies at once

Every trampoline has been emitted with `mov rax, [r12]` where `mov rax, [rsp]` was meant. `REX.B` extends the
SIB base field, so `49 8b 04 24` reads r12 and only `48 8b 04 24` reads rsp. What that one bit explains:

- **The null fault.** `fault pc is inside trampoline slot 40 of 686 (offset 53 in the slot)`; offset 53 *is*
  that instruction; the earlier register dump had `r12 0`. It was never a body at fault and never the guest.
- **The pc column.** The stored "guest return address" was whatever r12 happened to point at -- which is why
  rows printed the resolver address, or nothing. After the fix: `#40 pc 0x8020b5c90 count 5`, and **zero rows
  at pc 0**.
- **The %fs reading.** A fault inside a slot happens *before* the crossing, so guest `%fs` there is the
  prologue's own state: the classifier's sentence ("a host body ran with the guest %fs") was a verdict printed
  by the code that produced the situation. It now prints the three bases and their relations, and says where
  the pc is, so the reader must join two lines instead of believing one.

Sequence that found it, each step cheaper than the last: in-flight import (reused the trampoline's own store,
cleared in a reachable epilogue), emit-time bases (correct: host base, guest base, process on host), the body's
own entry read (`entry fs 0x79ca... ` = host -- so the crossing worked), then pc-vs-image (outside), then
pc-vs-trampoline (**inside slot 40**), then the bytes.

With the fix the boot runs further and stops where a body is genuinely missing: `libc j4ViWNHEgww`, imports
called 18. A stub that has never been disassembled is not known to be right because its source reads right.

## Campaign frontier (a finding, not a decision -- this authorises nothing)

Measured at this tree. The branch-free, unlanded, independently-owned catalogue population is **6,888
rows** (`symbols/leaf_frontier.csv`): **6,288** pass every filter the leaf toolchain has and are simply
not done, and **600** are shorter than 14 bytes and need the floor and the byte tier's
position-dependence rule to move together (ask 7). **Zero are nested** inside a larger extent: this
catalogue's extents are disjoint, so the floor's "do not describe a tail as an entry" rationale has no
population here, while its cost is the whole 600. The census that counts every unlanded row at or
below 13 B independently gives **5,805 = 5,205 branch-bearing + 600 branch-free**, and the two counts
agree exactly once the branch selector is named beside them.

Correction, kept because it survived in prose for a slice: an earlier revision of this section
reported **139 / 117 / 22** and **6,749 nested**. Those came from `join_import_pc.load_extents`
parsing the size column as hex while `address` is hex and `size` is decimal -- every extent inflated,
every `owners()` window widened, independence destroyed. One decode of one row settles the radix
(`0x00400020`, size `102` decimal: 29 instructions ending in a `jmp`). Both consumers of `owners()`
were wrong by the same factor and agreed with each other, which is what a shared premise looks like.

When these close, **no selector in this tree can address another catalogue row**: the remaining
114,023 branch-containing rows belong to the function campaign, whose generated-C path carries no
single-block constraint. So PROGRESS reaches 100% of 43,734 -- 27.7% of the catalogue -- and SCOPE
stays 24.10% of Ghidra's reach.

`verified` does not move for any of them, and this is the reason the pivot is scheduled now rather
than discovered after the frontier lands: every leaf protocol lands at `edge-verified`, the byte tier lands
as `shape-approved, machine-verified` and never as "approved", and `verified` is gated on the user's
30 approvals against 21,086 all-rows-clean. The leaf campaign's completion and the goal's criterion
are different instruments. The same caveat stands on the other side: neither the function nor the
runtime track moves `verified` either until asks 1-7 are answered, while `in-game: unknown (no
runtime witness)` is the only entry the runtime track can change at all.

### 1n — One size parse, and a predicate is counted over the population before it gets a fixture

`tools/catalogue.py` yields rows whose `address` and `size` are already ints. A helper would still need
every site to remember it; four sites each failed to remember. `tools/check_catalogue.py` refuses an
explicit size radix absolutely (zero today) and refuses a NEW `csv.DictReader` outside that module,
grandfathering the existing 55 files in `tools/catalogue_allowlist.txt` — which may only shrink, because
the gate also refuses an entry whose file no longer uses it. The detector walks the AST, not the text:
a regex version refused a docstring that quoted the defect it had just stopped making.

Two rules recorded here because both were learned by paying:

* **A predicate true of every input is not a predicate — count it over the population before writing a
  fixture.** A duplicate-start test was `bisect_left != bisect_right`, which means "at least one
  occurrence" and therefore returned 157,757 of 157,757. Two fixtures passed while it did. The negative
  fixture caught it; counting the predicate over the loaded catalogue would have caught it first, in one
  command, with no test authored.
* **A tool a hook runs has its import graph as part of its contract.** Importing `leaf_family_census`
  into `progress.py` pulled in capstone, which the pre-commit interpreter lacks, and the commit died.
  `tools/landed.py` exists in the capstone-free form that fix required.

## Blast radius of the open list, and the frontier batch it selects

The open list had thirteen items and twelve stretches of instrument work behind it, chosen by recency:
each fix revealed the next defect, so the exit condition was never written down. Here it is, chosen by
rows moved instead, computed once.

**No open item moves a row.** Of the thirteen, twelve move 0: the allowlist prune, the `parses.*` FROZEN
conflict, the two uncovered readers, `branch_census --out`, `family_scan`'s `116,475 / 1,919`, the pbboot
re-run, `__cxa_atexit`, ctest including `tools`, two generators' `--check`, the 290 s store test, the
`chdir` anchor. One — `source_hash` per file against 4,034 bodies in `bytes_family.cpp` — moves 0 and puts
**4,034 landed rows at risk of losing their evidence**, which is a different quantity from a gain. Two
more, ask 7 and the `--min-size 14` re-decision, gate **600 rows / 5,826 B** and belong to the user.
`verified` is behind the 30 approvals against 21,086 all-rows-clean and is not reachable from any of them.

**And the ladder's own generator has nothing left to land.** Measured, all sixteen templates:
fifteen report `0 unlanded members` (`ret` 7,761 landed · `lea_disp_rdi` 979 · `mov_al_imm` 793 ·
`mov_eax_mem` 765 · `rip_add_store` 362 · …), and the sixteenth, `rip_load`, offers 161 members that
`_refuse_zerofill` refuses **161 of 161** — every target outside `filesz`, a constant zero no case can
discriminate. So the 6,288 addressable frontier rows were never blocked by a repair; they are a
population that has no family, and the missing thing is *template coverage*, not correctness.

**The lever, from `tools/leaf_shape_census.py` (frontier CSV + ELF, no catalogue JSON):**

| instructions | rows | cumulative | what it is |
|---|---|---|---|
| 3 | 284 | 284 (4.5%) | expressible by a three-instruction template today |
| 4–6 | 1,714 | 1,998 (31.8%) | short chains |
| 7–12 | 1,905 | 3,903 (62.1%) | small functions, not leaves |
| >12 | 2,385 | 6,288 | functions; 1,654 instructions at the tail |

Top shape: `mov rax,[rip+K] ; mov [rax+K],K ; ret` — **78 rows / 1,320 B**, and seven of the fifteen
most common shapes are the same rip-load-then-dereference chain. That is the TCB census's "six chains,
six K globals unread" arriving as a population rather than a paragraph.

**Ceiling if the whole addressable frontier landed:** SCOPE 24.10% → 28.09% (44,306 / 157,757), PROGRESS
84.25% → 98.63% (43,134 / 43,734). **Zero of it is `verified`**, because a byte tier row is never
behaviour. The 600 "short" rows stay out with ask 7.

**Exit condition, in force from here.** No further instrument work until a frontier batch lands.
*A batch lands* when the rows are in `symbols/functions.csv` at `edge-verified`, the differential is green
against the shipped bytes, `--reemit <family>` reports the committed body unchanged, and the commit
message pre-registers rows and bytes. First batch: the 78-row shape, with the space rule applied at
emit time — **the load is image-via-supplied-base, the store target is an indirect through a pointer
loaded at runtime, so the gate must classify it as argument→obligation and the case must supply the
buffer**, and every case must discriminate (marker bytes, not zero-fill).

### Correction, same session: the 78-row batch is 78, and `_refuse_zerofill`'s reason was wrong

The companion's instruction was to run `_refuse_zerofill`'s check over the 78 rows' `rip+K` targets
**before** authoring any of them. Done, with a positive control on the segment parse (code address →
`filesz`; `0x090dc000`, in the gap between the two PT_LOADs → `unmapped`):

| shape `mov rax,[rip+K] ; mov [rax+K],K ; ret` | rows |
|---|---|
| load target inside `p_filesz` | **0** |
| inside `p_memsz`, past `p_filesz` (zero-fill tail) | **78** |
| in no segment at all | 0 |

So authoring first would have produced 78 bodies whose shipped-state load is a constant zero. That part
of the warning was exactly right. **But the reason the refusal states — "a constant 0 no case can
discriminate" — is false**, and three facts in `tools/harness.py` say so:

* `:458` admits a `fixture_setup` write anywhere inside any segment's **`memsz`**, not `filesz`.
* `snapshot()` at `:657` reads **`memsz`** bytes per segment, so BSS is part of the compared state.
* `boot['size']` is `0x50dc000 + 0x5f70f4 = 0x56d30f4` (the extent), so the slot is inside the mapped
  image.

Then measured rather than argued: mapped the image at `IMAGE` with that size, wrote a pointer into the
BSS slot `IMAGE + (0x5956678 − 0x400000)`, **read it back through the image**, stored `0x1234` at
`pointer + 0x1520`, and read `34120000` back with the marker at offset 0 intact. A case supplies the
discriminating value itself; the shipped zero is a state the body can never execute in (in-game the
global is initialised before the call, and calling it with 0 would fault).

**Corrected predicate: a target past `p_filesz` but inside `p_memsz` is admissible with a seeding case;
only a target in no segment at all refuses, because a write there faults.** Implemented in
`--targets-for`, which now prints the split as an identity and names how many rows need a seeded slot.

**Consequence that is not being quietly re-run.** The same reason retired **161 `rip_load` members**
("161 of 161 outside filesz") and removed them from the frontier. If the reason was wrong there too,
those rows are landable. That is a change to a rule that has already moved rows, so it is recorded here
as an open item with its predicate, to be decided deliberately — not re-derived in passing.

**Batch, pre-registered:** 78 rows / 1,320 B, one **family** emitter, not one shape — parameters
`(load K, store K2, immediate K3)` from the decode, because seven of the top fifteen shapes are this
same chain and a template per shape is how `parse_size` became four call sites.

### The rule's reason was a conclusion its check could not reach — and the population is now counted

`_refuse_zerofill` measured **addresses against program headers** and stated **a fact about cases**:
"a constant 0 no case can discriminate". The premise is true; the conclusion requires knowing what a
case writes, which the check has no access to. **A refusal whose stated reason is not the thing its
check measures is a comment, and a comment cannot be wrong loudly** — which is why it survived: I read
it as a finding rather than as a docstring.

Fixed at the source: the rule now splits into two conditions with **two strings that cannot be
confused**, each printing the question it answers —

* `address in NO PT_LOAD memsz` → the address is not backed by a segment; a read or write there faults.
* `past p_filesz, inside p_memsz` → **SEEDING REQUIRED**; the slot is not file-backed, and the refusal
  says explicitly what it is *not* answering.

The store arm's old message contradicted itself in one sentence (`memsz` in the first clause, `filesz`
in the second); both arms are now exercised — the load arm by `rip_load`'s real population, the store
arm by a probe address in no segment.

**Blast radius, counted rather than remembered.** The refusal history: `rip_load` **161 of 161** now
read `SEEDING REQUIRED` (from the code, not from my notes), and `symbols/thunks.csv`'s `excluded_by`
column — 16,815 rows, five distinct values (`family_scan:min-size=14` 5,805 · `family_scan:jump-free`
5,205 · `bytes:address dependent` 5,556 · `bytes:control flow` 184 · `bytes:trap (1j v)` 65) — contains
**no zerofill value at all**. A measured zero on a live column: the rule never gated any other table.
The 78-row chain is the second batch; both are the same condition, not two.

**Where the seeding lives:** in the case file. `evidence_hash()` already pins `cases_sha256` over every
fixture input, so a seeded slot is covered by the column that covers every other case — no new tier
value, no fourth status.

### Running the check found the check destroying the artifact it protects

`open(path, 'w').write(body_text(name, ms))` — Python evaluates the `open` first, so `body_text`'s
refusal (which is the *point* of the function) truncated `game/leaf/rip_load_family.cpp` to **0 bytes**
and left it on disk. A refusal that destroys the artifact it was protecting. And the `--dry-run` guard
sat *above* `body_text`, so a dry run printed `nothing written` and exited 0 for a family that refuses —
a dry run that never asks the question it exists to ask.

Both fixed by ordering: **build, then ask, then write.** Proven by artifact, not by message — after the
fix, `rip_load --dry-run` exits 1 with the refusal and `ls game/leaf/rip_load_family.cpp` says *No such
file*; and the positive control on the same path is `rip_store --reemit` → *reproduced byte-for-byte
(124 members)*, rc=0, so the emitting path still emits.

**Withdrawn attribution:** the 0-byte `rip_load_family.cpp` I saw earlier and attributed to "debris from
an older aborted emission" was this defect, reproduced by my own run. `ls -l` dated the new one 95
seconds before `date`; the old one was dated Oct 23 and I never checked whether a run of mine could have
made it. **A timestamp is evidence only about time; I used it as evidence about authorship.**

### Build-ask-write was a rule; `atomic_write` is a shape

Reordering one call site fixed one call site. The property is what matters: **`open(path,'w')`
truncates at the open**, so any failure in the producer — a refusal, a `KeyboardInterrupt`, a
`MemoryError` — destroys the artifact it was about to replace. `tools/atomicio.py` writes beside the
target, `fsync`s, then `os.replace`s, so the artifact is either the old bytes or the new ones. Four
tests, including the refutation: patch `os.replace` to raise and the old bytes must survive with no
`.tmp` left behind.

`leaf_family_census.write_table` — **the** writer of address-keyed tables — now goes through it, so
every family's three tables are covered by one call. `emit_leaf_family`'s body, case files and
re-emit write all go through it.

**`--dry-run` moved to the end of assembly**: the refusal, the case assembly, the table clash
assertions and the sort all run; only the write does not. Its old guard returned before `body_text`
and printed `nothing written`, which is a no-op with a reassuring message.

**Unreached arm, named:** the dry-run *success* branch has **no population** — every family is either
exhausted (`0 unlanded`) or refusing (`rip_load`, 161), so the sentence it prints has never been
executed. It needs a fixture family, not an argument.

**One of four generators wired.** `zero_init_gen:327/:397`, `slot_copy_gen:345/:394`,
`leaf_mov_rax_gen:166/:168/:193–197/:249`, `static_guard_gen:209/:365` still call `open(...,'w')`.
Each needs its own `--check` to be run before and after, which is not a change to make blind.

**And the bare rule caught this slice's own patch.** I inserted `from atomicio import atomic_write`
above the `sys.path.insert` that makes `tools/` importable; with `-P` (no cwd on `sys.path`) every bare
invocation died `ModuleNotFoundError`, while the tests passed because `PYTHONPATH=tools` was set — **an
entry point that starts only with environment help, introduced by the commit that was making mistakes
unrepresentable.** The import now sits below the path insert.

### One roster, two assertions; and the ordering rule became five lines of AST

`test_gates_bare` already derived its roster from `tools/*.py` carrying a `__main__` guard, and asserted
**one** property: it does not exit 0 silently. A traceback satisfies that assertion, so `ModuleNotFoundError`
passed it for as long as the suites ran with `PYTHONPATH=tools` — the harness supplying what the artifact
needs, which is the `2>&1` lesson in another costume. The same roster now asserts a second property, and the
assertion **names the missing module**: only a module that resolves to a file in `tools/` is a failure, so
`terminal_gif.py`'s Pillow stays a different finding instead of forcing a second exception list.

`tools/check_import_order.py` is the same rule as an AST check, because a rule about ordering loses to a
shape: for every `tools/*.py`, an import naming a module that resolves to `tools/<name>.py` must sit below
the `sys.path.insert` that makes `tools/` importable, and a sibling import with **no** insert is refused too.
Proven three ways — real tree, a planted violation (new), and a planted stale baseline line — each arm run
and each arm's rc read.

**The first run refused 41 sites in 20 files**, and the population is the finding: those tools start only
because a plain `python3 tools/x.py` puts the script's own directory on `sys.path`, which `-P` and any hook
running under an empty environment do not. `progress.py:478/495/498`, `record_bytes_family.py:26/27/38/39`,
`function_catalogue.py` thirteen deep, `join_import_pc.py:38`, `census_rip_load.py:32` (top level: dies at
import), `check_pins.py:35` (above its own insert at :40 — the exact defect, in the file that introduced the
pattern). Grandfathered by file+line in `tools/import_order_allowlist.txt`, shrink-only: a new violation
refuses and a stale line refuses, so the list cannot become a permission slip. `progress.py` is the sharpest
one: the pre-commit hook invokes it plainly, which is why nobody has seen it fail.

### The 40 grandfathered imports were fixed, and the allowlist deleted rather than emptied

Shrink-only is not small, it is slow. All 40 sites were one statement placed beside the imports, so they were
edited rather than tracked: 16 files, **+23 lines, −41** (the 41st is `check_pins.py`'s insert, moved above the
import it was supposed to precede — the file that introduced the pattern had it in the wrong order).
`tools/import_order_allowlist.txt` is **deleted**, not left empty: an empty allowlist is a tool waiting to be
re-populated, the same doctrine that says a `--apply` flag is deleted the day its authorisation is refused.
`test_gates_bare` loses its exemption set entirely — every tool with a `__main__` guard now starts bare, which
is one assertion over a derived roster with nothing to drift.

**Two of the 40 were load-bearing.** `census_rip_load.py:32` was a **top-level** sibling import, so that module
could not be imported under `-P` by anything, including the emitter that will want its scan.
`progress.py`'s three imports sat behind `--help`, unexecuted — the hook would have reached them the day
someone added a flag.

**And the repair's first attempt was caught by its own subject, not by me.** I computed the insertion point as
"after the prologue", which for a file with **no docstring** is line 0 — so `sys.path.insert` landed above
`import sys` in 16 files. `py_compile` passed, because the name is only needed at execution; my verification
loop grepped for sibling misses and `SyntaxError` and so reported sixteen clean rc=1s while every one of them
died `NameError: name 'sys' is not defined`. **A check that greps for the failure it expects will miss the one
it caused** — the insert point now comes from the AST's own import nodes, and the check greps `NameError` too.

**Measured defect, not fixed here.** `progress.py --root <abs> --check` run from `/tmp` exits **0** while printing
`cannot read the catalogue … unread is not zero` and `reach: unavailable …` (rc read directly, no pipe): either
`--root` is not threaded to the catalogue read or absence is read as clean in `--check` mode. Both are
violations of *absence refuses*; the hook is unaffected because it runs from the repo root, which is exactly
why it has never been seen.

### Two roots, one output: the gate read `--root` and the diagnostics beside it read the cwd

`progress.py --root <abs> --check` from `/tmp` exited **0** while printing `cannot read the catalogue …` and
`reach: unavailable …` (rc read directly, no pipe). The compare was honest — `compute(a.root)` reads what it
was told — and the **lines printed beside it** were about a different tree: `extent_line()` and `reach_line()`
took no root at all and rebuilt a relative `symbols/` themselves, while `_parses_clause()` beside them resolved
an absolute one through its own module, so **one output line carried one honest reader and one cwd-dependent
one**. Two instruments, two roots, one number.

Fixed three ways, each measured: `--root` is threaded into both lines through one `_symbols_dir(root)` (and
`landed.landed_addresses` already took a path, so the selector stays one implementation); **absence now
refuses** — a `--root` whose `symbols/ghidra_functions.csv` or `functions.csv` cannot be read returns **rc=3**
before anything is computed, instead of degrading every line to a sentence and exiting 0; and the three arms
are run apart: repo root rc=0, **`/tmp` with an absolute `--root` rc=0 printing the same 157,757**, `/tmp/nocat`
**rc=3** refusing.

**Class check done, not assumed:** `grep -n "add_argument('--root'" tools/*.py` finds it in 13 tools and every
one of them uses `args.root` afterwards; `progress.py` was the only file whose *helper* functions bypassed it.
A flag that parses and goes nowhere is the `--lib` class, and the way it hides is that the tool prints a
plausible number about the default.

**And the repair that preceded this one was caught by a test I already had.** `test_gates_bare` runs every
`__main__` tool bare and fails on a non-empty stderr with rc=1, so `sys.path.insert` above `import sys` — 16
files, `NameError` — would have failed it. What missed it was **a bespoke sixteen-file loop run beside the test
that already knew**: a hand verification next to a suite is how a suite's coverage gets spent on the thing you
were going to check by hand anyway. From here the suite is the check, and anything still hand-checked gets the
`NameError` arm added.

**Scope statement, because two greens certified different trees:** the `tools` ctest target is registered but
every "ctest 18/18" in this campaign was run as `ctest -E '^tools$'`, so **ctest has never covered
`tools/`, and no `atomic_write`, `check_import_order`, roster or 40-site result is in any ctest green.** Those
were covered by `test_gates_bare`, `test_atomicio`, `test_emit_leaf_family` and `test_progress_*`, run by name.
Until the target is unified, "ctest green" is a claim about `runtime/` only.

### The chain family's case schema: two independent fields, three links, and 62 cases for 78 bodies

**The schema already expresses the pair this family needs, and I read it rather than assuming it.**
`harness.py:391–399` resolves the write address and the value from **two independent fields**: `addr` is either
`buf:<name>` or a hex guest string routed through `guest()`; the value is `pointer` (`value("buf:…")`),
`guest` (`guest(hexint(…))`) or `bytes`. **`IMAGE` never appears in a case file** — `guest()` at `:402–407` owns
`IMAGE + ps4 − EBOOT_BASE` and its docstring says the `− EBOOT_BASE` belongs there and nowhere else. So the pair
is expressible without a literal: `{"addr": "0x5956678", "guest": "0x5400000"}`.

**But the right kind here is `guest`, not `pointer`, and observability cannot tell the difference.** The body
stores through the loaded pointer, so in-game that pointer is a guest address. A `pointer` seed yields a
**SANDBOX host address**; `snapshot()` at `:657` includes `self.buffers` as well as writable segments, so a
sandbox store **is** observed, and a fixture writing into a space the game does not have would pass. **Link two
therefore reads against the RW segment's `memsz`** (`0x54dc000 .. 0x5AD30F4` — guest space; the
`0x50dc000/0x56D30F4` pair I first wrote was the ELF's *vaddr* space, one `EBOOT_BASE` short), not
against a buffer extent:
`base ≤ value`, `value + store_k2 + store_width ≤ base + memsz`, PF_W on that segment.

**A third link, forced by measurement, and it is the void-instrument class recurring.** Of the 78 rows,
**31 store an immediate of `0x0`** into a destination that is zero-fill — already zero. Slot seeded or not, that
store produces **no byte diff**, so the differential compares zero to zero and passes. The case must pre-set the
destination to a sentinel the immediate cannot equal (`0xA5 × width`), and the gate must assert
`imm != sentinel`. Uniformly, for all 78 — not just the 31 — because a rule that applies where it is needed and
not where it is not is a rule the next author has to re-derive. The immediates: `0x0 ×31, 0x1 ×36, 0x2 ×4,
0x3 ×1, 0x4 ×2, 0x8 ×1, 0xa ×1, 0xf ×1, 0xffffffff ×1`; widths `1 ×17, 4 ×61` (the `0xffffffff` at width 1
writes `0xff`, so the expected bytes are `imm & (2^(8·width) − 1)` little-endian — an encode the differential
would catch, and a place where an emitter can be quietly wrong).

**62 cases for 78 bodies.** Distinct `(load_target, store_k2, imm, width)` is **62**, not 78: sixteen rows share
a behavioural key with another row through all four fields, while distinct `(load_disp, …)` is 78. **The load
displacement is a coordinate; the resolved slot is the identity** — the `(module, ordinal)` lesson arriving in a
new place. So cases may be shared across those sixteen **and must be shown to be shared for the right reason**
(same address, same offset, same immediate, same width — asserted), while bodies stay 78 because their bytes
differ (sizes `{15: 28, 18: 50}`). One case file per *behaviour*, one body per *row*; a `--reemit` claim is
still per row.

### Retraction: the "one-character constant defect" at the RW segment was never a defect

I published two numbers for the writable segment and then "corrected" a docstring from one to the other:
`0x50dc000 .. 0x56D30F4` against a filesz end of `0x57e5b38`, which I called `0x400000` applied twice and
replaced with `0x53E5B38`. **Both of my numbers were in the ELF's vaddr space; guest space is +`EBOOT_BASE`.**
Reading the program headers (the only authority, and cheaper than the argument):

| | vaddr | off | filesz | memsz | flags |
|---|---|---|---|---|---|
| seg 0 | `0x0` | `0x4000` | `0x50d96dc` | `0x50d96dc` | 5 (R+X) |
| seg 1 | `0x50dc000` | `0x50e0000` | `0x309b38` | `0x5f70f4` | 6 (RW) |

Guest space: RW base **`0x54dc000`**, filesz end **`0x57e5b38`**, memsz end **`0x5AD30F4`**, tail
`memsz − filesz = 0x2ED5BC`; and `boot['size'] = 0x56d30f4` is that guest end **minus** `EBOOT_BASE`,
i.e. a size, not a bound. **`emit_leaf_family.py:284` always said `0x57e5b38` — the tree was right every
time, and the defect I claimed was a misreading of my own note.** The arithmetic that "closed" my
correction added a vaddr-space base to a vaddr-space filesz and called the result a guest end; the tail
matched by luck, because both ends shift by the same constant.

**Two laws, arriving together.** *A correction is a claim too — the file wins over the note that says the
file is wrong.* And: **a number that closes against a size has not thereby been shown to be a bound.**
This ELF speaks two coordinate systems one `EBOOT_BASE` apart and **both close**, against different facts —
vaddr-space end against `boot['size']`, guest-space end against `guest()`'s admissibility window. Closure
is consistency, never correctness, which is the radix lesson in a new place.

### The retraction is shared, and its smaller law is the one to keep

The `0x50dc000 / 0x309b38 / 0x5f70f4` triple reached me as **program-header bytes with no space named**, and
I published it as if it were addresses in the space the seeding gate checks. So the object that let both
readings "close" was **unlabelled units**, and the correction I then applied was a second reading of the same
unlabelled number. **A number without its space is the address-bias rule one tier up.** Beside the two laws
already written: **every number in these tables carries its space, or it is not a number yet.** vaddr space
and guest space are one `EBOOT_BASE` apart here; `boot['size']` is a size in the second while the same digits
are an end in the first, which is exactly how a wrong correction passes an arithmetic check.

### A gate that existed, enforced in both directions, and was never invoked

`tools/check_catalogue.py` had a shrink-only allowlist, a `rosters.compare` in both directions, and 55
grandfathered files — **and the pre-commit hook never ran it.** What the hook printed was
`progress.py:482`'s own DictReader count, in a line shaped like a verdict. So the new tool I committed last
slice used a raw `csv.DictReader` and **rc=0**. `a count is not a constraint`, arriving where I had just
written `a display is not a write`.

Repaired in three places, each proven to fail before it was trusted:

1. `check_seeding.py` reads the table through `catalogue.read_rows` — **the tool I write does not
   reintroduce the pattern its own gate refuses.**
2. `tools/hooks/pre-commit` invokes `check_catalogue.py` against `$tmp` (its `ROOT` derives from its own
   `__file__`, so the staged copy checks the staged tree with no flag), and the numbered list gains it.
3. `test/test_gates_wired.py` derives the roster **from the hook's own text, both directions**: every gate
   that owns a shrink-only allowlist must be *invoked* against `$tmp`, and no `tools/check_*.py` may be
   named in the header without being run.

Arms executed: wiring test red with the invocation deleted and green on restore; the gate refusing a new raw
reader (rc=1); accepting it once allowlisted (rc=0, so it enforces rather than counts); and refusing the
entry as **stale** after the file was deleted (rc=1). The migration that follows is the one this shape always
ends in: **move the 100 sites to `read_rows` and delete the file**, which is what the readable allowlist did
when it reached zero.

Also adopted: the catalogue baseline should be keyed on **`(file, enclosing function)`** rather than a site
count, because line numbers move on every edit and a count cannot express "new"; the shrink is then honest
and staleness stays expressible through the same `compare()`.

### `gate_line`: no tool prints a verdict it did not get from the gate

Three instances of display standing in for check, now one helper (`tools/gateline.py`):
`describe()` formatting while the comparison was decided elsewhere; `extent_line()` rebuilding a relative
`symbols/` beside a compare that had used an absolute one; and `progress.py`'s `parses:` clause computing
its own DictReader count **while `check_catalogue.py` — the tool that refuses a new raw reader — was never
invoked at all.** That is how a raw `csv.DictReader` rode a green commit.

The shape: `gate_line(name, rc, detail)` where **`rc` is what the check returned**. `rc=None` prints
`not checked` in the same position, because **a line whose shape implies a verdict it never ran is worse
than silence — silence at least reads as nothing.** `check_catalogue.audit(root)` is now the only verdict;
`main()` prints it and `progress._parses_clause(root)` prints it, and nobody recomputes a count to print.
Threading the root repaired a second two-roots defect in the same line: the clause called `scan()` with no
root, so `--root <tmp>` answered about this tree.

### Item for the emitter: the behavioural key goes in the row

The chain family's 78 rows reduce to **62 behavioural cases**, so sixteen pairs will carry an identical
`cases_sha256`, because `evidence_hash()` pins it. **That is correct and it is unreadable** — a reviewer
would see two rows with one case hash and read copy-paste. So each row carries `case_key` = resolved slot +
`store_k2` + `imm` + width, and the shared hash becomes **a fact checkable against a column instead of a
coincidence taken on trust.** Same move as `distinct bodies` in the pool-B families: one question the
reviewer can ask, and a re-derivation they can run.

### The seed is read back through the mapping, once per body, before the body runs

`check_seeding.py` is a static gate on a case FILE: it proves the file says to seed a slot. It cannot prove
the seed landed, because the image is mapped once and mutated by every run. The failure it cannot see is
quiet and expensive: **the body reads zero, the store goes to `0 + K2`, the differential compares two
zero-filled tails, and the row lands green.** So `apply_case`'s write path records every range it writes —
the seed and the destination sentinel alike — and after the loop calls
`read_back_mismatch(lambda a, n: ctypes.string_at(a, n), writes)`, refusing before the body runs with both
values printed.

`read_back_mismatch` takes its reader as a parameter so it can be falsified without an image: the tests show
a landed seed passing, a missed seed returning the zero the body would have read, a partial landing, and a
second written range — the sentinel — being checked rather than the first only. Same move that made the
`rt_guest_writable` fixture trustworthy: **the byte read back through the mapping, never the write's return
code.**

### An anchor is not a claim about execution order: the entry point belongs last

Wiring the read-back, I inserted `read_back_mismatch` above `def fixture_seeds`. The anchor was unique and
correct, the file parsed, and **44 of 64 harness tests failed with `name 'fixture_seeds' is not defined`.**
Mechanism: `if __name__ == '__main__': sys.exit(main())` sat at line 1092 and `fixture_seeds` at 1085, above
it; my insertion pushed it below, so when the module runs as a script `main()` reaches the call site before
the name exists. **A definition inserted between a call site and the entry point is a change to the
program's execution order, which is not a property of the anchor** — the same family as *a guard above its
own measurement shadows it*, one tier up: here the shadow fell on a whole function. The guard is now the
last statement of the file, with that history in a comment above it.

Also mine, and caught by its own run: the partial-landing test zeroed **byte 7 of `0x5956678`, which is
`0x00` already**, so the "mutation" changed nothing and the test demanded a refusal that was not owed. **A
falsification that alters a byte already at that value tests exactly as much as a differential that compares
two zero-filled tails.**

### Three structural invariants, because an anchor protects the write and nothing else

The patcher's checks, in the order they were learned, each one a defect that got past the one before:

1. `assert s.count(old) == 1` protects the **write** — one site, the intended one.
2. `ast.parse(s)` after the write protects the **file** — a two-phase write is atomic, not correct.
3. A **structural invariant** protects the **program**. My anchor was unique, the text was correct, the file
   parsed, and 44 tests died: inserting one definition above another moved `fixture_seeds` below
   `if __name__ == '__main__'`, so a script run reached the call site before the name existed.

**No amount of anchor discipline can protect execution order; only structure can.** The invariants now
enforced, one per artifact: **a module's is import-order** (a sibling import below the `sys.path.insert` that
resolves it) and **the harness's is guard-last** (the entry point is the last top-level statement) — both in
`check_import_order.py`, one AST walk, **one roster, two key shapes** (`file:line` for a site, `guard:file`
for a whole file, so neither can grandfather the other). **A table's is sortedness** — `write_table`'s
sort → adjacent-dup count → write → re-read, which is why that writer is shared rather than copied.

The first run found **one** violation in `tools/leaf_family_census.py`: guard at :78, definitions below it.
It was **latent, not live** — `main()` reaches nothing below the guard, proven by an exec of the module with
`__file__` supplied (my first proof of that omitted `__file__` and died of it, proving nothing). Repaired
anyway: **a violation is not an incident, and the invariant is what makes the next insertion safe.**

### A mutation must be verified to have mutated

Fourth member of one family, recorded by name rather than as a lesson: a partial-landing test zeroed **byte 7
of `0x5956678`, which is `0x00` already**, so the mutation changed nothing and the test demanded a refusal
that was not owed. Beside it: the differential that compared two zero-filled tails; the mutant that could
not be seen because both sides read zero; the census whose `{'0x0': 16508}` was a histogram of a fallback
literal. **A falsification that alters a value already at that value tests exactly as much as a differential
that compares zero to zero** — so a mutation carries an assertion that it mutated, the way a write carries a
read-back.

### The push is delivered, and the read that proves it is `ls-remote`, not a bare clone

`origin/main` is **`ec67d60`**, and `git ls-remote origin refs/heads/main` returns that full sha from
GitHub. Push was never the missing instrument: **read** works from this shell and only push needs askpass
(rc=128). A bare clone of `.` was suggested as the proof and it is the weaker one — **it copies local refs,
so it shows the commit exists here, which I already knew.** The remote-side read is the one that carries
weight, and the local corroboration is the `refs/remotes/origin/main` reflog entry `update by push`.

**An item carried past its own resolution is a debt that reads as a risk**, so the caveat retires here.

### A delivered tree cites evidence it does not contain

`docs/data-requirements.md` states the external trees, what needs each, and **the three refusals measured
at this commit** (`harness: … cannot open` rc=3; `seeding: refusing -- no case directory`; `progress:
refusing -- cannot read …` rc=3). A pushed repository whose evidence lives only on one machine is **a
delivery defect, not a hygiene note**: the instruments are public and their subjects are not, and nothing
about a green suite says so.

### An anchor is unique as a substring without being unique as a line

`assert s.count(old) == 1` passed for `import harness` against a file whose line was `import harness as H`.
The write was unique and wrong: the alias migrated onto the new import line, `harness` lost it, and five
tests died with `'function' object has no attribute 'read_back_mismatch'` — a message that names the wrong
object because the name had been rebound to something else entirely.

**The anchor must be a whole line or a whole block: `assert ('\n' + old + '\n') in s`.** Uniqueness of a
substring is a property of the text; uniqueness of a line is the property the patch actually needs.

### Mutations that cannot fail to mutate

Three occurrences in one stretch — a partial-landing test that zeroed byte 7 of `0x5956678` (already
`0x00`), a batch check whose "mutation" wrote `status='unknown'` (still landed), and, before them, 117
survivors that were cases putting the only value at offset 0 — is the threshold where a rule has failed and
a shape is owed. `tools/mutate.py`: `mutate(data, offset, new)` and `replace_field(row, field, value)`
**refuse when the new value equals the old**, with a message that says the offset and that nothing would be
tested. The mistake is no longer observable; it is unrepresentable. Same shape as `atomic_write` refusing to
leave its temp file behind, and it costs one line at each call site instead of a paragraph in a log.

### 1o — IN FORCE (landed): a known-wrong body cannot be recorded, and a body-less row is not a body

`0x00414040` (`large_bracket_canon_00414040`, 1,072 B) carries a body that was written wrong: it uses
`v_rcx|v_r9` where the original consumes `eax`/`ebx`, and `0x29` where the original wrote `0x28`. A
differential cannot distinguish that body from a trampoline, so recording it would make every number
after it retroactively meaningless. It therefore sits in `landed.KNOWN_WRONG` with this reason, is
excluded from every `landed` set, and **raises** from `landed_addresses` / `byte_totals` if it ever
carries a status other than `original`. `progress.py` calls those and the commit hook runs
`progress.py`, so the refusal cannot be skipped by a forgotten roster entry. Ordering is a plan; a
refusal is a guarantee.

`0x024264d0` (`leaf_rip_load_wide_024264d0`, 34 B) has **no body**: `grep -rln` over `game/` returns
nothing, because it was withdrawn with `rip_load_family.cpp` at `f511666`. The original performs signed
magic division `eax % 10`, and `0xa % 10 = 0`, so the original returns `0` for the sample in the row:
retire, never widen. The row is retired by a marker in `notes` (this file has no `retired` *status* —
the vocabulary is `{edge-verified, original, verified}`), and `byte_totals` excludes it from both
`landed` and `transcribed`, because `transcribed` means *bodies that exist*.

Corollary, learned by writing it wrong first: a `continue` that means "not landed" must not also mean
"not a body". The first version of `byte_totals` skipped known-wrong rows entirely and reported
322,873 B transcribed instead of 323,911 — dropping 1,072 B of a body that exists.

### 1p — IN FORCE (landed): the `original` population is closed by decision, and the 77 are pre-registered both ways

All five rows at status `original` now carry their reason on record, so the gap between `bytes_transcribed`
and `bytes_landed` is a documented zero rather than a backlog:

| address | bytes | class | reason |
|---|---|---|---|
| `0x00414040` | 1,072 | known_wrong | body uses `v_rcx|v_r9` for `eax`/`ebx` and `0x29` for `0x28`; a differential cannot tell it from a trampoline, so `landed` refuses it and raises if it is ever promoted |
| `0x004632d0` | 67 | retired | calls `gettimeofday` and `stack_chk_fail`, and is the code cave the community patches overwrite — it needs a call model: deliberately not done |
| `0x024264d0` | 34 | retired | signed magic division `eax % 10`, `0xa % 10 = 0`; no body in the tree since `rip_load_family.cpp` was withdrawn |
| `0x0111a600` | 8 | retired | not an entry point: `movsxd rsi, esi`, no `install_mode` row, three instruments agree — nothing to verify as a function. Its old note, preserved here because the 200-character budget forced it out of the CSV: `MOVSXD RSI,ESI` then a tail call to `realloc` (import `0x02fbfe38`, NID `Y7aJ1uydPMo`), a 32-bit signed size sign-extended; 8 bytes, so the 14-byte hook does not fit (QUIRKS.md) |
| `0x01735230` | 18 | backlog | the pilot: body written, differential measured, three mutants fired, not yet recorded |

`transcribed` counts bodies that exist in the tree — one walk over `game/` — and does **not** consult the
notes column. So `0x0111a600` still contributes its 8 B while being retired: a retired row that has a body
is a body nobody will verify, and that is a follow-up (delete the body), not a number to adjust. A census
that reads the ledger's opinions is how 34 B survived a family withdrawal and 67 B survived never being
written.

**Pre-registered for the 77** (to be checked the moment `verify.py --record edge` runs, and a disagreement is
the finding):

* `bytes_landed` **322,746 → 324,066** (+1,320, the whole family: all 78 rows become evidence at once)
* `bytes_transcribed` **323,844 → 325,146** (+1,302, the 1,320 B of the batch minus the pilot's 18 B, which
  is already on disk as a body)

The two movements differ by exactly 1,302 B: the bytes that are *newly transcribed and also recorded*. The
pilot's 18 B is already transcribed, so it can only move `landed`.

**Pre-registered sharing, `tools/case_sharing.py`** (after the 77 land): **78 case directories must hold 62
distinct contents.** Three outcomes and only three — 62 is the design; **78** means sharing did not happen
and every address got its own copy, which is harmless on disk but leaves `case_key` carrying no information;
**fewer than 62** means two behavioural keys collided in one case file, which is a **wrong-body hazard** and
stops the record. The gate refuses only that last one, because it is the only one that can produce a body
compared against a case authored for a different slot. Corollary, stated beside `evidence_hash`: **a hash
pinned by two directories is not an identifier — query the ledger by `address`, never by hash.**

### 1q — A family's access declaration is a set, and its value source may be `seeded`

`ACCESS` maps a family to ONE `(kind, source)` pair. `chain_deref` has two obligations with different bounds:
it dereferences a rip-relative slot (78 rows, a static address) and writes through the pointer it loaded
(argument-derived). Declaring either half alone prints a green that is true about half the family —
`addr-only` would be vacuity with a new name, and `store/argument` prints "nothing to check" over 78 static
loads. Three changes, in this order because each one makes the next safe:

1. **The extractor must read the names the emitter emits.** `re.findall(r'constexpr std::uint64_t (?:v|at) = ...')`
   matches ZERO of `chain_deref_family.cpp`'s 78 declarations (it emits `kImm`/`kSlot`/`kStoreDisp`), against
   124 in `rip_store` and 10 in `rip_load_wide`. A scanner keyed on a naming convention the emitter does not
   share reports a correct family as unparseable and the zero reads as clean — the `647` shape, third arrival.
   Convergence on one name beats `ACCESS` carrying per-family names, because two names means every future
   scanner picks one and half the families go unchecked. **And empty `targets` for a kind that needs them
   must REFUSE, not print nothing-to-check.**
2. **`ACCESS` becomes a uniform tuple of pairs** — `(('addr-only','static'),)` — never a union of a pair and a
   tuple-of-pairs. Six migrations now beat one polymorphic branch forever; a union is how the next reader
   writes `decl[0]` and gets a `str`.
3. **`source` gains `seeded`**: a static address whose VALUE the case supplies. Its bound is `memsz`, not
   `filesz`, because all 78 slots sit in the zero-fill tail (`inside p_filesz 0 | inside p_memsz past filesz
   78 | in no segment 0`) and are safe precisely because the case presets them. Bound at `filesz`, a
   `load/static` declaration would refuse 78 of 78 — a gate refusing a family whose load is satisfied by
   seeding. This is the `rip_load` retraction in reverse: there zero-fill meant the differential compared
   zeros; here it means the case supplies the value and the differential is real because of it.

**`seeded` must be earned, not declared**: the gate checks that the family's rows declare a seeding for each
`seeded` target, the same conjunction `check_seeding` already proves for these 78. The two instruments read
different artifacts and must agree — two instruments that agree because they read the same table is the
failure to avoid.

So `chain_deref` is `(('load','seeded'), ('store','argument'))`: both rows true, and "who supplies this
value" is answerable in the table instead of in a comment.

**Correction to (1), made before any code exists to inherit it — the names are DATA, not a convention.**
Converging `kImm`/`kSlot`/`kStoreDisp` with `v`/`at` is not a refactor: it re-emits `chain_deref_family.cpp`,
changes `source_hash` for that family's one defining translation unit, and **staleness-refuses all 78 recorded
rows** — a full re-record plus differential re-run, i.e. the two-hour family cost paid for six reds and zero
new rows. Rejected on price, not on principle.

So the declaration carries its own constants: `ACCESS[fam]` grows from `(kind, source)` to
`(kind, source, *names)` — `('load','seeded','kSlot')`, `('store','argument','kStoreDisp')` — and the extractor
reads the names out of the declaration instead of matching a spelling it assumed. **A name in a table is not an
assumption, it is an input**; the `647` lesson is that a scanner must not ASSUME a spelling, not that every
emitter must spell alike. The table becomes the convention, no future scanner picks a name, and **no recorded
byte moves**.

Empty `targets` still REFUSES — now printing the declaration's names beside what the file actually declared, so
the next reader sees `kSlot` next to `kStoreDisp` rather than a zero. Convergence becomes an optional tidy-up
taken whenever a family is re-emitted for other reasons: **never a tax paid today for zero rows.**

**How the uniform shape arrives without a migration table (recorded so the next author does not reintroduce the
branch):** `kind, source, *names = decl` unpacks a 2-tuple and a 3-tuple through **one statement**, with no
`isinstance`, no `decl[0]`-is-a-string test, and no legacy path. A `seeded` family that forgets its constant
name gets `names == ()`, finds no targets, and **hits the empty-`targets` refusal** — the forgetting is caught
by the mechanism that exists for it rather than by a check written for forgetting. Two consequences worth
stating: the migration is a **data edit** (every entry becomes a decl it already is), and **an entry may not
silently carry neither names nor a case obligation** — that is the shape `check_seeding` covers from the case
side, and the two instruments must keep reading different artifacts.

**A family with two obligations is two decls**, and the loop iterates decls: `chain_deref` is
`(('load','seeded','kSlot'), ('store','argument','kStoreDisp'))`. One family, two rows, two bounds, one table —
the set, not the pair, which is the whole of (1) through (3) in one line of data.

**How (1) was proven, and the standard it sets for every refactor that touches a gate:** the gate's full output
before and after the two edits is **byte-identical — 71 lines, `rc=1` on both sides**. The `rc=1` is the
stronger half: identity **including the failure path** means the refactor covered the branch that actually runs
on this tree, not only a happy path no family here takes. **A refactor is proven by invariance on the real
tree at its real rc; an invariance proof taken only on a passing gate has not been taken**, because a gate that
exits 0 exercises a branch the refusal path never reaches.

**`seeded` is TWO conditions, and the second is not arithmetic.** The bound is arithmetic on the ELF —
`msz` end, not `fsz` end, because the slot lives in the zero-fill tail (78 of 78). The **supply** is a claim
about a *different artifact*: the case must write the value the body will read. **A branch that implements only
`memsz` passes every family whose slot happens to sit in zero-fill while saying nothing about whether anything
ever wrote it** — which is the whole history of the `rip_load` family, where zero-fill meant the differential
compared zero to zero and the mutant was invisible. Both conditions, or the word `seeded` is a synonym for
`static` that reads as if it were safer.
