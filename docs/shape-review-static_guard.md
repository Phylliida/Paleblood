# Shape review: `static_guard` (1,117 entries, 3 behaviours)

This is a request for one decision, not 1,117. The family is the compiler's function-local
static one-shot guard: on first call, store `storage + 0x10` through a pointer slot and set a
byte flag; on every later call, return without touching memory. It is the first *generated*
family in the tree, so it is also the first test of whether the review format can attest a
shape rather than a function.

## What is being attested

One body. Every member is 41 bytes and decodes to the same nine instructions; the only
differences are four displacement/constant fields:

```
488d05 D1   lea  rax,[rip+D1]
8038 00     cmp  byte [rax],0
751c        jne  +0x1c            ; to the ret, at address + 40
488d0d D2   lea  rcx,[rip+D2]
4883c1 10   add  rcx,0x10         ; the value stored is base + 0x10, not base
488d15 D3   lea  rdx,[rip+D3]
48890a      mov  [rdx],rcx        ; pointer slot := storage + 0x10
48c700 01…  mov  qword [rax],1    ; guard flag, one byte read and eight written
c3          ret
```

| fact | value |
|---|---|
| members | **1,117** (all `size 41`) |
| raw bodies | **1,117 distinct** (each has its own displacements) |
| template, displacements zeroed | **1 distinct**, sha256 `2cdf3840547f7d4033ae610d83d5f98c…` |
| guard read | 1 byte; written 8 (the asymmetry is real, not a typo in this table) |
| pointer slot value | `storage + 0x10`; `pointer == guard − 8` in 1,117 of 1,117 |

Three behaviours, because three `(guard, pointer, storage)` triples account for 1,116 entries:

| guard | pointer | storage | copies |
|---|---|---|---|
| `0x05ac59b8` | `0x05ac59b0` | `0x056b4840` | 372 |
| `0x05ac59c8` | `0x05ac59c0` | `0x056b4890` | 372 |
| `0x05ac59d8` | `0x05ac59d0` | `0x056b47f0` | 373 |

One member of the family (`0x014405b0`) uses its own triple and is the pre-existing
hand-written one; it is not part of this request.

## Evidence

- **Cases:** 5 per member, `../data/cases/static_guard/<address>/` — guard set / guard clear /
  guard set with junk in the high bytes but low byte clear / guard clear with the pointer
  already bound / guard all ones. They preset the guard and the pointer slot, and read the
  pointer slot back by value, which is what makes `storage_bias` observable.
- **Recorded:** 1,117 of 1,117 members, `--record edge`, **0 failures**, 997–1,015 ms each.
  Every row carries its own `source_hash` and `cases_sha256`.
- **Mutant:** `storage_bias` `0x10` → `0x08` in `game/frame_timing/static_guard.cpp`, rebuilt,
  six members sampled across all three triples (2+2+2): **6 of 6 failed**, each naming the
  pointer slot and the wrong value, e.g. `memory +0x5ac59b0: original 50 replacement 48`.
  Reverted; source byte-identical by `cmp`; the same six **6 of 6 pass**.
- **Case mutation, earlier:** a wrapper pointed at another triple's addresses fails 5 of 5
  with the diff naming `+0x5ac59c0` / `+0x5ac59c8`.

## What approval would and would not mean

It would mean: this body, this case set and this mutant are the behaviour of these 1,117
entries, and the generated code is readable against STYLE.md. It would **not** mean 1,117
independent verifications, and no burndown may read it that way — the information gain over
the family is 3, which is why the review is per shape.

## The format question, which is the actual decision

`symbols/reviews.csv` is one row per function and its two pin columns (`source_hash`,
`cases_sha256`) are per member: all 1,117 share `source_hash` but every `cases_sha256` differs.
Two ways to express a shape approval:

**(A) One decision, 1,117 derived rows.** The reviewer approves this document; a tool then
writes the 1,117 rows, taking `source_hash`/`cases_sha256` from `validate_functions.py
--review-row NAME` so nobody types a hash, all sharing the same `date`, `reviewer`, `verdict`
and a `notes` naming this packet. The existing gate is unchanged, pins keep their per-member
meaning, and the approver's attention is spent once.
*Cost: 1,117 rows that are all one attestation wearing 1,117 bodies. The records would
overstate the review unless `notes` says "shape attestation, see docs/shape-review-static_guard.md".*

**(B) A shape-level record.** A new table (`symbols/shape_reviews.csv`: shape id, members,
template hash, evidence hash, reviewer, verdict) that `validate_functions.py` accepts in place
of a `reviews.csv` row for members covered by an approved shape.
*Cost: a second gate and a second meaning of "approved"; `promote.py` grows a branch.*

**Recommendation: (A), with the `notes` sentence mandatory.** It needs no new gate, keeps the
pins honest, and the per-shape cost is what the reviewer actually spends. If the illusion of
1,117 reviews is unacceptable, (B) is the honest schema and should be done deliberately, in one
commit, for all generated families — not invented halfway through this one.

## To execute in one sitting

1. `tools/validate_functions.py --review-row frame_timing_static_guard_0135bde0` (prints the two pins).
2. Re-run the six-member mutant check above (≈40 s) or accept the recorded result in this file.
3. Choose (A) or (B), and if (A), say the word and the 1,117 rows are generated and validated.
