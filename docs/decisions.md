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
