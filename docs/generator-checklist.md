# Generator checklist, seeded from the one hand-built body

Written before the generator emits anything, because every item below was paid for by a defect
found while translating `0x00414040` by hand. An item here is a test, not an intention.

1. **A memory operand is not a memory access.** `tools/instruction_trace.py` classified both
   alike and was wrong for `nop DWORD PTR [rax+0x0]`, `lea` and `prefetch*`. Fixed at the class,
   with `test/test_instruction_trace_memory_operands.py` failing first. Do not re-add
   clflush/clwb/invlpg/xsave/fxsave to that class: they do touch memory.
2. **Three-way on a small enum, emitted as `switch`.** Never nested booleans
   (`if (klass) ... else ...`), which is the likeliest defect in every table-driven arm.
   `cmp si,1` after `movzx esi, word [...]` is a clean three-way; overflow is impossible, so
   16/32-bit compare equivalence may be assumed and stated.
3. **Fix the rodata extent derivation and re-pin before first output.** `rodata_table.py`'s
   `max(bases)+16` is SHORT: words past it are still table-shaped (`2,0,0,0,2,0,0,0,3,0,0,0`),
   and past word 784 the values jump to 63,901, so the end lies in that span. "Out-of-extent
   read" was a claim about the derivation, not the binary.
4. **Every literal a named `constexpr`.** `check_readable.py` refuses magic numbers, and it
   refused a hand-authored body with every number correct.
5. **Leaders emitted as `// 0x4140xx` labels, gated by `check_block_addresses.py`.** Addresses,
   not sizes: a body can carry every instruction and still omit a block.
6. **An EVIDENCE SCOPE block naming untested regions.** The pilot's mirror arms were unexercised
   by every ASCII case, and the body said so rather than leaving a reviewer to find out.
7. **Dead code preserved and commented, never deleted.** The unreachable arm at `0x4143f3` is
   argued unreachable, not removed; the unobservable `cmove` at `0x414483` is declared, not
   planted.
8. **Determinism: run twice, assert byte-identical output.** Without it `cases_sha256` pins
   nothing and every re-record looks like drift.
9. **Cases emitted from the leader set, one per static block first**, then mutations. A case set
   that never reaches a block cannot testify about it, and the ASCII cases drove 14 of 64 blocks
   while reading as a pass.

## Why generation is not only cheaper

Every divergence this pilot found is a **value-flow** error: which register holds which value at
a block boundary. That is the class a mechanical translation eliminates by construction, because
the decompiler's C names its locals and types them, so no human decides whether `eax` or `r9d`
carries the class at `0x414350`. Generation is 130x cheaper per function and structurally immune
to the defect the hand path spent two turns localising. The arithmetic says generate; the defect
taxonomy says the same thing for a different reason.

## The rodata extent: 384 words, closing exactly (my "608" was an instrument artifact)

The layout, read off the code rather than inferred: **256 level-1 words followed by 16-word
blocks**, each class-2 entry naming one block via `bextr(r15, 0x404)` = bits 4..7 of the unit, so
`base + 15` is the largest index a block can be asked for. `bt esi, edi` then tests a single bit
of a level-2 word, which is why those words hold large patterns like 63,901 and why any
"plausible class code" test past index 255 is measuring level-2 data against a level-1 criterion.

Measured on table A (`0x02fc5120`): level-1 values >= 2 are **8 distinct, min 256, max 368, all
multiples of 16**, occupying 256..383 = 8 blocks x 16 = 128 words, and **368 + 16 = 384** -- the
derived extent, closing with no remainder. Max requested index is therefore <= 383 < 384.

Two of my own numbers were artifacts and are withdrawn: a sweep printing "max requested 607" and
"80 indices past the derived 384" contradicts `e1 <= 368` by arithmetic, so the instrument was
wrong; and 608 (and "the derivation is short") came from that same bad input. A derivation
cannot confirm its own input.

**Gate: membership in the union of declared blocks, not `< extent`** -- `< 384` admits an index
landing in a hole between blocks, which a future non-contiguous table would hit. And **table B
(`0x02fc4a40`, 880 words, index source `0x41419d`) has never had this closure run at all**; the
same instrument must derive and gate both, per table, before either pin is called real.

## The rodata extent, measured as two bounds (reachability, not pattern)

Sweeping all 65,536 units through the A-site lookup chain against table `0x02fc5120`:

* **reachability lower bound: 608 words.** First lookup asks at most index 255; the second asks
  at most index **607** (`entry + ((unit >> 4) & 0xff)`), and **80 distinct indices past the
  derived 384 are actually asked for.** So `max(bases)+16` = 384 is short by at least 224 words,
  and the units that read past it are not hypothetical.
* **plausible upper bound: NOT ESTABLISHED.** The measure I used -- "longest run of values <= 3
  from index 0" -- returns 5 for table A and 0 for table B, which is nonsense on its face, so it
  is a broken measure rather than a bound. The earlier observation stands on its own: values past
  word 400 include 63,901, so the array ends somewhere in 544..783 by the earlier reading, and
  that reading is now the only one I have.

608 sits inside the 544..783 uncertainty band, so **the honest state is that I cannot yet say
whether the original stays inside its own table.** If required <= true end, the extent is settled
and the pin is real. If required > true end, the original reads past its table for some inputs
and the body must reproduce that read -- a finding about the binary, not a tool bug, and the
second time in this pilot that "the table is bigger" was the answer.

Class distribution over the unit domain: **63,232 class 0, 256 class 1, 2,048 class 2** -- so the
two-level arm is reached by 2,048 units, not the 600 I had been quoting for class 1 alone.

Next: locate the true end by structure (where the stride/class-code pattern breaks), then emit
both headers with the derived extent replaced by reachability + located end, and re-pin.
