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

## The rodata extent: two different subjects, and only one of them is settled

Earlier versions of this file carried numbers that contradicted each other, because they answered different
questions without saying so. Separated:

* **Declared extent (settled, recomputable).** `game/large/rodata_pairs_02fc5120.h` holds **768 bytes = 384
  words**; `game/large/rodata_pairs_02fc4a40.h` holds **1,760 bytes = 880 words**. This is the data the
  repository owns, and `test/test_doc_numbers.py` recomputes both from the headers so the sentence cannot rot.
  Layout: 256 level-1 words then 16-word blocks, each class-2 entry naming a block through `bextr(r15, 0x404)`,
  so **`max(bases)+16 = 384` closes with no remainder** -- exact arithmetic, about the declared data.
* **Reachable indices (measured, and larger).** Sweeping all 65,536 units through the A-site chain asks for at
  most index **607** (`entry + ((unit >> 4) & 0xff)`), with **80 distinct indices past 384 actually requested**.
  So `max(bases)+16` is not a bound on what the original asks for, only on what the declaration contains.
* **Open, and why it matters:** whether the original reads past its own declared table. If what it asks for is
  <= the true end of the data the pin is real; if not, the original reads past it for some inputs. The
  "plausible upper bound" measure (longest run of values <= 3 from index 0) returned 5 for A and 0 for B, which
  is nonsense on its face and is withdrawn. **Honest state: declared 384, reachable >= 608, true end not
  established.**

**The gate this implies:** membership in the union of declared blocks, never `< extent` -- `< 384` admits an
index landing in a hole between blocks. And **table B (`0x02fc4a40`, 880 words, index source `0x41419d`) has
never had this closure run at all.**

