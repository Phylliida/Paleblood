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
