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

## What the case must satisfy — the gate, ahead of any body

1. **The slot is fixture-seeded, always.** 47/47 load targets are past `filesz`, so the shipped qword is zero
   and **no member of this family is testable from the shipped image.** Every expected value comes from the case.
2. **The slot byte must have bit 7 set (`>= 0x80`).** With a byte below `0x80`, zero-extension and
   sign-extension agree, and a body widened or sign-extended relative to `mov al` passes a differential that
   cannot see the difference.
3. **`rax[63:8]` must be nonzero before the load.** Rank 5 of the census is `mov rax,[rax+K]` -- 17 rows that
   differ from rank 1 **only** in whether `rax[63:8]` survives. A case with a small `rax` would make `al` and
   `rax` agree and the two shapes indistinguishable through the one channel this family has.
   **This is the `mov_al_imm` lesson pointed forward:** there, the case guaranteed `rsi == rax` and the alias form
   passed 793/793 while being wrong; here a small `rax` would guarantee `al == rax`.
4. **The witness is compared as the full 64-bit `rax`**, never `al` alone -- a comparison at the width of the
   write cannot see a write at a narrower width. The only channel this family has is `rax`, so the comparison
   width is the instrument's whole resolution.
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
