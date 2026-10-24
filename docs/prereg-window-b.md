# Window B — pre-registration, written before any body exists

Measured at `7b8f903`, one read-only call, rc from the process:

    env -u PYTHONPATH $P -P tools/leaf_shape_census.py --targets-for 'mov rax,[rip+K] ; mov al,[rax+K] ; ret'

## The population

| field | value |
|---|---|
| shape | `mov rax,[rip+K] ; mov al,[rax+K] ; ret` |
| rows | **47** (rank 1 of the census's 15 shapes / 188 rows) |
| bytes | **658** |
| sizes | **{14: 47}** — MEASURED, not derived (below) |
| load target | inside `filesz` **0** · zero-fill tail **47** · unmapped **0** |
| distinct load K | **47** — every row its own constant, so no case can be shared |
| distinct second-operand K | **46** — the collision is offset `0x1590`, exactly twice |

**A total is consistent with a histogram and does not imply it.** My first version of the table above read
`47 × 14 = 658, so sizes {14: 47}` — arithmetic closure, which one 15-byte and one 13-byte row would also
satisfy. The census prints only `t[:5]`, so the histogram was obtained by calling the tool's own `targets_for`
(the mapper that produced the rows) and counting: **`rows 47 bytes 658 sizes {14: 47}`**, agreeing to the byte.
Recorded as measured because the version that inferred it was committed for one amend.

**The collision is a fact and not a defect.** 47 rows carry 46 distinct second-operand offsets: two members
touch `0x1590` and each has its own case. The chain family's `distinct_store_k2 == rows` held for those 78
members and is **not a law** -- it must not be inherited as a pre-registration wire for a different family. Cases
stay distinct because the load K is distinct (47/47), which is the field that decides case identity.

**Vocabulary caution.** The census calls the second instruction's memory operand a *store*; here the instruction
is `mov al,[rax+K]`, which **loads**. The column is the operand's displacement, and **the direction is not
carried by the name** -- a two-way label over a three-way fact. Read the shape, never the column name.

## The horizon this measurement reveals, and the correction it forces on the board

The census decodes **206** rows within three instructions and counts **6,004** as over the bound. The
emitter's vocabulary is single-shape templates; the census's 28 shapes are all two- and three-instruction
**compositions**, and the two sets share **no member** — measured, not assumed. So:

- the population any template library can reach is **206 rows**, of which the top five shapes are **132**
  and all 28 are **206** (`--top 28` summed: 28 shapes, 206 rows — counted, not read off the top-five line);
- **6,004 rows need an instrument that is not a template library** — a register machine over three-plus
  instructions — or they need nothing, and no tool in this tree addresses them.

`6,210 addressable` has been quoted as the campaign's remaining work for several slices. It is not. It is
**206 rows of template-expressible work plus 6,004 rows of a different technology**, and the second number
has never had a tool. The ladder's "nothing left to land" and the frontier's "6,210 remain" were both true
and about disjoint sets; this paragraph is what makes that a measurement rather than an observation.

### How each term of that equation is sourced — beside the number, not in a message

| term | derivation | second route | consequence |
|---|---|---|---|
| `6210` | `frontier()` over `symbols/leaf_frontier.csv`, `class == addressable` | **yes** — `test_the_population_is_the_committed_frontier` recounts it from the file by `r.split(',')[2]` | the left side of the `=` is double-sourced |
| `206` | the `shapes` counter in the decode loop | **no** — the `--top 28` table is the same counter rendered twice, so their agreement is a tautology of one derivation | one derivation, two formats |
| `6004` | the same loop's `over` counter | **no available route** — the only per-row artifact is `--targets-json`, which is **shape-filtered**: `over` rows produced no shape, so such a stream cannot contain them and would answer `0` by construction | single-sourced, no route recorded |
| `0` | the same loop's `undecoded` counter | **no**, same reason | single-sourced — **and an always-zero counter is indistinguishable from a bucket nothing can reach**; the detector is *what would have made this nonzero?* |

A second decoder written in the test is **not** the missing route: `test_host_hooks.c:160-167` is the
precedent, where a fixture that compiles its own copy of a property cannot notice it leaving the product,
and a recount by the same author over the same library agrees on the day it is written. **The honest
record is: the total is double-sourced, the terms are not, and why.** Closure catches omission, never
error — `206 + 6004 + 0 = 6210` was already closed while the 521 floated, because that 521 was a
difference between two named populations and not a missing term.

**First template, decided before it is written: rank 15, `mov rax,[rip+K] ; movsx eax,[rax+K] ; ret`, 1 row,
15 B.** Not rank 1's 47 rows. Its yield is 15 bytes; its product is **template #19 existing and being
falsifiable**, which rank 1 also needs and which rank 15 needs at a third of the width — and it is the only
member in the census where clause 2 (`>= 0x80` separating zero- from sign-extension) is **live rather than
vacuous**, so the retired clause is re-armed by a member that can exercise it. A retired clause re-armed by a
live member is the strongest form `retired, not deleted` can take.

## What the case must satisfy — the gate, ahead of any body

1. **The slot is fixture-seeded, always.** 47/47 load targets are past `filesz`, so the shipped qword is zero
   and **no member of this family is testable from the shipped image.** Every expected value comes from the case.
2. **RETIRED, with reason: the slot byte's bit 7 (`>= 0x80`) separates zero- from sign-extension, and
   this family has neither a sign-extending member nor a widened width to separate.** Ranks 1, 2 and 5 are
   `mov al`, `mov eax` and `mov rax` -- byte, dword, qword, and **none sign-extends**: `al` is the same under
   either convention and `rax`'s upper bytes come from the pointer, not from the loaded byte. Retained as a
   clause it would have been a `movsx` requirement carried by a batch containing no `movsx` -- the same object
   as `addr-only` on a family that dereferences: harmless until quoted as a reason. It is owed to the first
   `movsx`/`movsxd` family, where a byte below `0x80` genuinely lets a widened body pass.
2b. **Instead, the byte at `p_i + k2` must be NONZERO and per-member distinct, derived from that member's own
   `k2`.** In a zero-fill tail the register cannot see the second load's displacement at all: `byte(p_i+k2)`,
   `byte(p_i+k2+1)` and `byte(p_i)` are all `0`, so `rax`'s low byte is `0` whether the body added `k2`, `k2+1`
   or nothing. Without a marker at exactly that offset, `rax` proves only WHICH SLOT was read and says nothing
   about which displacement addressed it -- the clause-5 principle (a value derived per member, never inherited)
   applied to the buffer rather than to the slot.
3. **`rax[63:8]` must be nonzero before the load.** Rank 5 of the census is `mov rax,[rax+K]` -- 17 rows that
   differ from rank 1 **only** in whether `rax[63:8]` survives. A case with a small `rax` would make `al` and
   `rax` agree and the two shapes indistinguishable through the one channel this family has.
   **This is the `mov_al_imm` lesson pointed forward:** there, the case guaranteed `rsi == rax` and the alias form
   passed 793/793 while being wrong; here a small `rax` would guarantee `al == rax`. And it is measurable in
   advance: with an `al` witness all 47 members read the same `0`, because the byte at `p_i+k2` is zero-fill for
   every one of them -- a witness at the width of the write is constant across the whole population.
4. **The witness is compared as the full 64-bit `rax`**, never `al` alone -- a comparison at the width of the
   write cannot see a write at a narrower width, and here that is arithmetic rather than caution: `rax` before
   the second load is the planted pointer `p_i`, so the result is `(p_i & ~0xff) | byte_at(p_i+k2)`, and an `al`
   witness is `0` for all 47. There is ONE channel, and the correction is the census's own vocabulary trap: the
   column named `store_k` carries the SECOND LOAD's displacement -- this shape has no store, so `writes` watches
   nothing and an empty list compared against an empty list across 47 rows is the zero-versus-zero failure in its
   purest form. One channel, two byte-fields: a mistargeted SLOT moves `rax[63:8]`, a mistargeted OFFSET moves
   `rax[7:0]`. That is why the comparison width is 64 bits and why an `al` witness hides the slot mistarget while
   a `rax` witness exposes the offset mistarget.
2c. **`p_i` points at a fixture buffer, never into the zero-fill tail, and every 4-byte window of that buffer is
   distinct** (the marker repair of the 117/118 retraction, applied to the family it was invented for): a marker
   byte at offset `k2`, with neighbours that differ, so a body reading `k2+1` or `k2-1` reads a different byte
   and the low byte of `rax` names which offset it actually addressed. With no store in this shape, clause 2b is
   not a strengthening of the observable -- it is the only thing that makes the displacement observable at all.
2d. **The fixture asserts, before any case runs, that `{(p & ~0xff) | marker}` over the 47 pointers is 47-distinct**
   (clause 7 + 2b composed). The property the witness relies on is checked once in the fixture rather than
   trusted across 47 rows -- `derive_sentinel`'s move, one tier up.
7. **No two planted pointers may differ only in their low byte.** `rax` after the second load is `p_i` with one
   byte replaced, so pointers that agree above the low byte make the register witness collapse into the arithmetic
   one -- at which point it is no longer a witness to which slot was read.
5. **The slot's seeded value is PER MEMBER, derived from that member's `load_disp`** -- a pointer into that
   member's own buffer, distinct for all 47. The chain family's single derived sentinel (one `0x05` everywhere)
   was right THERE because its job was to prove **visibility**: that the store was observed at all. Here the
   decision the row encodes is the load's **identity** -- one byte, read at one offset, from a slot named by the
   row -- so a uniform sentinel would let a body that reads a fixed slot, or ignores `load_disp` entirely,
   return a plausible value from the wrong address and AGREE. **A uniform sentinel is a law about that family,
   and `46 != 47` in this one is the evidence that none of its constants may be inherited.**
6. **Pre-registered: a body that reads any other member's slot must FAIL**, and its failure is a fault, not a
   mismatch -- an unseeded slot in this case is zero, so a wrong-slot body dereferences 0 and the case refuses
   it by name. **The `0x1590` pair makes this provable rather than assumed:** the two members sharing that offset
   differ ONLY in `load_disp`, so under a uniform sentinel they would be exactly the two rows a wrong-slot body
   could pass. Swapping their slot constants is the first mutation owed, and both members must go red.

## Price, with its denominator

`~0.33 s/row` measured on the chain family ⇒ **~26 s** of differential for 47 rows, plus authoring, plus the
record protocol, which was the hour and not the coffee. The four widths (`47 / 27 / 20 / 17`, summing 111) are a
**second** pre-registration: each width has its own distinguishability requirement under clause 2 above, so a
width-parameterised emitter is an emitter question, never a licence to inherit 132 rows into one batch.

No `repair:` line accompanies this file: `1s.2`, it moves no rows.

### Amendment to template #19 (2026-10-23, before it runs): the base moved for a reason that is not the row

`2bbcff1` excluded the retired body `0x024264d0` from `symbols/leaf_frontier.csv`, against `retired.csv`.
Measured after the regeneration: **addressable `6,210 -> 6,209`**, total `6,810 -> 6,809`, and the census
absorbed it exactly -- **`6,209 = 206 decoded + 6,003 over + 0 undecoded`** -- so the row left `over`, which
is what a 34-byte body outside the three-instruction vocabulary should do.

Template #19 therefore runs against a base of **6,209**, not 6,210: its pre-registration is amended to
**`6,209 -> 6,208`** frontier addressable, with `+1 body, 15 B, verified 21 -> 21` unchanged. The band figure
is **unchanged at 7,956**: `0x024264d0` is 34 B and the band is `1 <= size <= 16`, so the retired row was never
in it. Two counts, one moved -- and the reason is the row, which is the distinction that matters.

**The ordering was the hazard, not the numbers.** Template #19 was pre-registered `6,210 -> 6,209`; the
frontier fix was also `6,210 -> 6,209`. Landed in one window, the two `-1`s would have been indistinguishable,
and the pre-registration's whole value is that **one commit moved two independent counts by exactly one**. The
fix went first and alone, and #19 now proves the same thing against 6,209.

The numbers above that this amendment supersedes stay as they were measured, with their provenance beside
them: a pre-registration that rewrites its own history cannot be checked against anything.

### Amendment: the witness width, decided per family before either runs

`pointer` buys legality at the cost of bits: with a runner-chosen buffer address the case cannot know `rax`
above bit 7, and the only directly assertable claim is `rax & 0xff == <byte at buf+K>`. That is exactly the
form that let `mov al,K` pass 793/793 while asserting nothing about `rax`'s upper bytes. The two families
carry this cost differently, so they are decided differently.

**Template #19 (`movsx eax,[rax+K]`) -- EXACT 64-BIT WITNESS, no pointer term.** `movsx eax` writes `eax`, so
the result is `rax = sext32(byte_at(p+K))` and **the upper 32 bits are zero by construction**, not by
assumption. The pointer term is *absent from the result*: the body replaces `rax` rather than merging into it.
So the assert is `rax == 0x00000000FFFFFF80`-style exact equality, 32 significant bits plus 32 provably zero,
and any wrong displacement reads a different planted byte and goes red. **Discriminating power: full.**

**The 47 (`mov al,[rax+K]`) -- 8-BIT WITNESS, DECLARED.** The result is `rax = (p & ~0xff) | byte`, so
`rax & ~0xff` is the runner's choice and the case cannot assert it. Pre-registered in these words: **the 47's
discriminating power is 8 bits; the upper 56 are unasserted and are named as unasserted, not as checked.** A
pass on any of the 47 certifies the byte, the displacement and the fault behaviour -- never the survivor half.

**Two recovery routes, both recorded with why they are not in force yet:**
* A declared fixed guest buffer address. **Unavailable:** `guest` in a `memory` entry asserts content at an
  address, it does not place a buffer, and rule 6 forbids deriving the expected value from what the runner
  chose. The buffer's address is the runner's, and that is the price of the buffer existing at all.
* Asserting the RELATION `rax & ~0xff == p & ~0xff` with `p` read at assert time. **Legitimate in principle
  and not yet expressible:** the case schema has no expectation expression that can reference the resolved
  address. `differential.py:767-776` already does combinatorial pointer-alias exploration, which is the place
  a relation-aware assertion would live. **Named as the follow-on, not silently dropped.**

**Consequence for ordering, and it is the reason #19 goes first:** #19's witness is strictly stronger than any
of the 47's. A pass there is worth more than a pass on a member whose upper 56 bits are unasserted, and it is
the only member where the retired clause (`slot byte >= 0x80`) is live -- sign extension is exactly the
mechanism that made it vacuous for `mov al/eax/rax`.

### Amendment: why #19's witness is exact -- one clause, and the cases it dictates

**The one clause:** `movsx eax` erases the pointer term **and** is the only census instruction whose result
depends on the top bit of the byte -- **both because the destination is 32 bits.** `mov al` merges into `rax`
(so `p & ~0xff` survives and the case cannot know it); `movsx eax` writes `eax` (so the pointer term is gone
and the upper 32 bits are zero by construction). The exactness of the witness and the liveness of the retired
`>= 0x80` clause are the same fact seen from two sides, **and neither is a coincidence of this row.** A reader
who asks "why is this witness exact when the 47's is not" gets that clause, not a paragraph of context.

**The cases, pre-registered as exact 64-bit equalities:**

| case | planted byte at `p+K` | pre-registered `rax` |
|---|---|---|
| A  | `0x7f` | `0x000000000000007f` |
| A' | `0x80` | `0x00000000ffffff80` |

**A and A' differ in exactly one planted value**, as the A/A' rule requires, and the pair **straddles the sign
boundary** -- `0x7f` and `0x80` are adjacent in the encoding and maximally apart in the result. That is the
tightest available test of the sign extension: a `movzx` body passes A and **must** fail A' by
`0xffffff00`, which is the smallest difference available at this width and is not a difference any rounding,
truncation or displacement error can produce accidentally. `0x80` is chosen as the boundary rather than
`0xff` for exactly this reason: `0xff` is also separated by a `movzx` body, but it sits 128 away from the
boundary, so it cannot distinguish "sign-extends the top bit" from "extends with a different constant for
large values" -- the boundary value can.

**Mutants, pre-registered with what each must move:**

1. `movsx` -> `movzx` at the same operands: **A green, A' red by exactly `0xffffff00`.** A red in both would
   mean the mutant changed more than the extension; a red in neither would mean the differential cannot see
   the sign bit at all.
2. `load_disp + 4` (reads the neighbouring planted byte): **A and A' both red**, because clause 2d makes every
   4-byte window distinct, and the red must name a *value* mismatch, not a fault.

### Amendment: the mutant table is three, and the deltas are disjoint by construction

The A/A' pair buys a third mutant for free, and it is the body this campaign would most plausibly ship:
**`movsx eax` mistyped as `movsx rax`.** A 64-bit destination sign-extends into all 64 bits, so **A stays green**
(`sext64(0x7f) = 0x7f`) and **A' fails in the upper half by exactly `0xffffffff00000000`.**

| mutant | A | A' | delta on A' |
|---|---|---|---|
| `movsx eax` -> `movzx eax` | green | red | `0xffffff00` |
| `movsx eax` -> `movsx rax` | green | red | `0xffffffff00000000` |
| `load_disp + 4` | red | red | by VALUE, not by fault |

The arithmetic is checked before the run, not after: `movzx(0x80) = 0x80`, so the gap to
`0x00000000ffffff80` is `0xffffff00`; `sext64(0x80) = 0xffffffffffffff80`, so the gap is
`0xffffffff00000000`. **The three deltas are disjoint, so a red on A' NAMES which body was emitted** -- which
is what a pre-registration buys at its best: not "it will fail" but "the failure will identify the mistake."

And the pair is doing double duty from one changed planted value: **the byte boundary and the destination
width.** `0x80` is the value that exposes a width error, not only a sign error -- which is the same argument,
one step further, for choosing the boundary rather than `0xff`.

### Correction to the mutant table, one commit after it: two opposite subtraction orders, both looking right

The table above states `movzx`'s delta as `0xffffff00` and `movsx rax`'s as `0xffffffff00000000`. **Those two
numbers were computed with opposite orders.** `0xffffff00` is `expected - actual`; `0xffffffff00000000` is
`actual - expected`. Computed consistently, `expected - actual (mod 2^64)` gives **`0x100000000`** for the
`movsx rax` row -- which is what my own check printed, disagreeing with the sentence I had already written --
and `actual - expected (mod 2^64)` gives **`0xffffffff00000100`** for the `movzx` row. **Neither row was a
magnitude; both were an unsigned wrap read in whichever direction produced a recognisable pattern.**

**The convention, fixed here: the table's third column is the MAGNITUDE of the difference, and the direction is
stated in words, because a 64-bit unsigned subtraction has no sign to carry it.**

| mutant | A | A' | magnitude | direction |
|---|---|---|---|---|
| `movsx eax` -> `movzx eax` | green | red | `0xffffff00` | observed is BELOW expected |
| `movsx eax` -> `movsx rax` | green | red | `0xffffffff00000000` | observed is ABOVE expected |
| `load_disp + 4` | red | red | by VALUE, not by fault | n/a |

The three magnitudes remain disjoint, so a red on A' still names the body. What changed is that the claim can
now be checked: **a delta quoted without its order is a number that agrees with whichever subtraction flatters
it**, which is the store/load direction defect one tier down.

### Amendment: the third mutant gets a computable magnitude, and the number in the proposal was not one

Plant `0x01` at `p+K+4` in both cases, so the wrong-displacement body reads a **known** byte instead of an
unknown one. The row then has a magnitude and a direction like the others:

| mutant | case | expected | observed | magnitude | direction |
|---|---|---|---|---|---|
| `load_disp + 4` | A  (`0x7f` at `p+K`) | `0x0000007f` | `0x00000001` | `0x7e` | BELOW |
| `load_disp + 4` | A' (`0x80` at `p+K`) | `0xffffff80` | `0x00000001` | `0xffffff7f` | BELOW |
| `movzx eax` | A' | `0xffffff80` | `0x00000080` | `0xffffff00` | BELOW |
| `movsx rax` | A' | `0xffffff80` | `0xffffffffffffff80` | `0xffffffff00000000` | ABOVE |

**The proposed figure `0xffffffff0000007f` reproduces under neither order:** `expected - actual (mod 2^64)` is
`0xffffff7f` and `actual - expected (mod 2^64)` is `0xffffffff00000081`; the magnitude is `0xffffff7f`. Recorded
rather than silently replaced, because a delta that reproduces under no stated subtraction is the exact object
the third column was rebuilt to prevent -- **and this is the second time in two amendments that a quoted delta
belonged to a subtraction nobody had named.**

**What the planted neighbour buys beyond a number:** the displacement mutant's red is now attributable with no
reasoning -- its magnitude differs from the extension mutants' and its direction is BELOW where the width
mutant's is ABOVE. **The weakest row became the strongest for one planted byte**, and the fixture already knows
`K`; clause 2d still holds because a planted `0x01` four bytes on keeps every 4-byte window distinct.
