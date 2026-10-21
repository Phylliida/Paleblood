# A/B: the >1,024 B tier, pre-registered before the first function is touched

## What the tier is, measured

`symbols/ghidra_functions.csv` is the whole partition: 157,757 entries, two columns, `address,size`.
Nothing else in this tree describes the population a decompiler pass would have to cover.

| quantity | value | how |
| --- | --- | --- |
| entries > 1,024 B | **7,791** | count of rows with `size > 1024` |
| bytes in them | **20,064,463** | sum of `size` |
| share of the 42,487,347-byte partition | **47.2%** | 20,064,463 / 42,487,347 |
| median size in the tier | **1,659 B** | sorted `size`, element `n // 2` |
| p90 size in the tier | **4,700 B** | sorted `size`, element `int(0.9 n)` |
| names available | **none** | the export carries no name column |

The last row is a cost this tier pays and pool B did not: every member needs a name before it can
have a case directory, and no name can be derived from an address.

## The question, and the mistake it nearly repeated

The standing question has been "is the decompiler pass faster than hand work". **Decompile time is
not the answer to it.** The catalog decompiles in about 11.5 h once, measured; against a campaign
whose remaining hand work is thousands of hours, that is a rounding error. The binding cost is
**authoring**, and inside authoring the binding term is **how many cases a large function needs
before its differential is worth anything**.

Pool B never taught us that number, because pool B did not need it: every landed family asserts a
**return value**, one case suffices to catch a constant-returning body, and the single memory read
was covered by two marker cases. A 1,024+ byte function returns something **and** writes something,
so one return-value differential is a weak witness -- a translation can be wrong in its side
effects and pass.

## Pre-registered deliverables, in priority order

1. **Cases needed for a non-trivial differential** (the primary number). Operational definition, so
   that it is not a feeling: for each pilot function, three mutants of the C translation are made --
   (a) return value changed, (b) one side-effect write changed or removed, (c) one branch direction
   flipped -- and the **minimum case count that catches all three** is recorded. That count, times
   7,791, is the quantity the tier's reachability turns on.
2. **Whether the side effect is observable at all** through `snapshot()` of a declared buffer, or
   whether it needs `scripted_write_targets`. A function whose effect lands outside every declared
   buffer cannot be witnessed without new harness surface, and that surface is a cost this A/B must
   price rather than discover later.
3. **Authoring cost, reported as two separate numbers**: minutes spent writing the C translation,
   and minutes spent authoring cases. Merging them into one figure is what would make this A/B
   unreadable -- the whole question is the ratio between them.
4. **Wall-clock from address to first clean differential**, per function, including the naming.

## Decision rule, fixed now

If a **median-tier** function (1,659 B) needs more than **5** cases to catch three mutants, the tier
is not reachable by this route at 7,791 members, and the honest options become (i) bulk decompile
with shape-level review at a coarser standard than `function`, or (ii) declining the tier in writing.
5 is chosen because 7,791 x 5 = 38,955 cases, and at the measured 115 ms per case run that is
1.24 h of machine time -- **the machine is not the constraint, so the threshold has to be set on
authoring, and 5 is where the case-authoring minutes stop being negligible beside the C minutes.**

## Candidates, chosen by rule rather than by eye

Selected from `symbols/ghidra_functions.csv` as the first unimplemented entry at the exact median
size, the second at the exact median size, and the entry closest to p90 -- in address order within
each class, so the choice cannot be tuned to a preferred function:

- median, 1,659 B: `0x00a78940`
- median, 1,659 B: `0x00b46d20`
- p90, 4,700 B: `0x00fe0450`

## The cache, tied to this

The decompiler cache has been promised ten times and shipped zero. It ships as this A/B's first
deliverable or it is deleted from the plan: one function decompiled, cached to disk, and re-read
from cache on a second invocation with the second run measurably shorter and byte-identical.
