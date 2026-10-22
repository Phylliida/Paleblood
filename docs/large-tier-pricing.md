# The >1024 B tier: what one measured body says about authoring it by hand

One body was translated and verified end to end (`0x00414040`, 1,072 B declared, 279
instructions, 64 blocks, 565 lines). This records what it cost, because one body is enough
to price the tier and the price decides the method.

## Machine clocks (measured, this tree)

| step | measured | note |
| --- | --- | --- |
| build, one body, incremental | **0.50 s** | clang 21.1.7, `-O3 -Werror` |
| differential, 3 cases, both sides | **0.93 s** | 0.31 s/case |
| one mutation cycle (edit+build+run+restore) | **0.97 s** | 2 plants, 2 caught, 0 survivors |

Whole tier at these rates: **7,791 x ~1.5 s = 3.2 h**. Machine verification is not the cost.

## T_translate: NOT measured

The 565 lines were authored across interactive work and no clock was ever started. That is a
gap in this pilot, not a zero. A defensible floor comes from the artifact itself: 279
instructions had to be read against the listing, and four of them contradicted the prose that
preceded them. At 2 s per instruction -- reading only, no reasoning -- that is 9 min per
function.

## The multiplication

| assumption | per function | tier (7,791) |
| --- | --- | --- |
| machine only (measured) | 1.5 s | **3.2 h** |
| reading floor (2 s/instruction) | 9 min | **1,169 h** |
| optimistic hand | 20 min | **2,597 h** |
| measured-feeling hand | 60 min | **7,791 h** |

Even the most generous hand estimate is **649 h at 5 min/function**, and the cheapest floor
above is **130x the machine cost of verifying the same function**.

## Conclusion: generate, do not hand-author

The tier is not hand-authorable. "Bulk first, hand later" was the right instinct with the
wrong mechanism: the bulk pass cannot be bodies typed by hand, because its floor alone is
hundreds of hours and its realistic cost is thousands. It must be a generator consuming the
decompiler's output (`T_decompile` marginal 0.39-0.46 s/function, tier ~60 min) under the two
gates this pilot proved:

* block coverage by address (`check_block_addresses.py`), which is cheap and blind to semantics;
* the differential with mutation (0.97 s per cycle), which is the only gate that sees a wrong body.

The hand path stays for the declared finish condition and for functions the generator refuses,
not for the tier's bulk.

## The rodata extent is short, not the original out of bounds

`rodata_table.py` derives the extent as `max(bases)+16`. Dumping bytes past that derived end
(`0x02fc5120 + 384*2`, 320 bytes) shows the words are still table-shaped: `2,0,0,0,2,0,0,0,
3,0,0,0...`, 26 nonzero of 160, values 2 and 3. So table A continues past the derived end and
**the derivation is short**. The earlier statement -- 1,280 of 65,536 units drive an index to
623 against a 384-word extent -- is therefore a fact about the derivation, not about the
binary, and the phrase "out-of-extent read" must be retired until the real end is found.

Beyond word 784 the values jump to 63,901, so the array ends inside that span. The next step is
to locate the end by the structure (where the 4-word pattern stops), re-emit both headers with
the corrected extent, and re-pin them. Until then the body carries the derived extent and says so.
