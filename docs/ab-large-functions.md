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

## Amendment 1 -- the adequacy criterion, replaced before the first decompile

The rule above measures the wrong thing, and the companion named it exactly: **three mutants chosen
by the author are caught by the first case that reaches the function**, so "minimum cases to catch
three mutants" cannot come back large, and a threshold it cannot fail is not a threshold. Mutants
settle whether the **comparator** is sensitive to a change. They say nothing about whether the
**behaviour** was ever exercised.

Primary criterion, as of this amendment (made before any pilot function has been decompiled,
translated or run):

1. **Cases until every basic block of the function executes at least once**, measured from the
   harness's execution trace, not asserted.
2. **Blocks that never run at any case count I can design** -- printed as a set, and carried into
   the approval packet as a **stated limit**, rather than discovered by a reviewer.
3. Mutants are retained, demoted to what they are good for: **comparator validity**, i.e. proof that
   a wrong translation would have been caught.

## The denominator, measured: `tools/blocks.py`

A block starts at the entry, at every branch target, and after every branch; it ends at a branch or
a return. Computed from the decoded bytes at `guest - 0x3fc000` with capstone, `detail=True`;
anything the decoder cannot place is **counted and refused, never approximated**.

Over the three pre-registered candidates plus a seeded 150-function sample of the tier (153
functions, `--sample 150 --seed 0`), on 2026-10-21:

| quantity | value |
| --- | --- |
| basic blocks, median | **67** |
| basic blocks, min / max | 1 / 1,434 |
| short decode (decoded bytes < declared size) | **70 of 153 (46%)** |
| functions with unplaceable branch targets | **54 of 153 (35%)** |

Three consequences, each of which changes the A/B rather than decorating it:

- **67 blocks at the median size means the answer to "how many cases" is not 2.** Whatever number
  the trace produces, the denominator is large and visible before a single case is written.
- **46% short decode** says the declared sizes in `symbols/ghidra_functions.csv` are upper bounds —
  the body ends before the size does -- so any cost derived from bytes is an over-estimate in exactly
  this tier. It also corroborates the `boundary_confidence` note (`ghidra-export-entry-size`) that had
  been carried as a curiosity: entry sizes are a Ghidra export property, not measured code extents.
- **35% have unplaceable branch targets**, i.e. indirect jumps whose targets cannot be enumerated
  statically. For those functions full block coverage **cannot be claimed by construction**; the
  honest report is coverage over the statically enumerable blocks plus the count of dynamic targets
  seen at run time.

## Cache trap, closed before the cache is written

Ghidra's output can embed the output path or a timestamp. A cached re-read compared against a fresh
decompile **in the same directory** would then match for the wrong reason -- and I would have
concluded the cache was sound when it was keyed to a directory. The cache's acceptance test is
therefore: decompile the same function twice into **two different output directories**, diff the two
fresh outputs to see what varies, and only then assert that a cached re-read matches its own fresh
control byte for byte.

## Amendment 2 -- what the declared sizes actually are, and what pilot 1 proves

The three pre-registered candidates, decoded:

| entry | declared | decoded | blocks | calls |
| --- | --- | --- | --- | --- |
| `0x00a78940` | 1,659 | **1,657** | 43 | 5 |
| `0x00b46d20` | 1,659 | **1,659** | 23 | 0 |
| `0x00fe0450` | 4,700 | **4,696** | 278 | 48 |

All three are still large by decoded extent, so the frame is sound -- but the census over the whole
tier says why that had to be checked rather than assumed, and corrects a sentence I wrote one
amendment ago: **3,299 of 7,791 entries (42%) decode short of their declared size, and the byte
consequence is 20,055,556 / 20,064,463 = 99.96%, delta median 0, max 14.** So the declared sizes are
upper bounds by **0.04%** -- trailing padding, not missing code -- and my "any cost derived from bytes
is an over-estimate in exactly this tier" was right in direction and **negligible in magnitude**.
Membership at the boundary is fuzzy in exactly **10 entries** of 7,791 that declare >1,024 and decode
<=1,024 (0.13%). The 47.2%-of-bytes figure stands.

The real limit is the other number: **3,321 of 7,791 (43%) have indirect branch targets**, so block
coverage for them can never be complete by construction, and the report for such a function is
static blocks covered plus the dynamic target set observed.

### Pilot 1 is a floor, not the tier

`0x00b46d20` makes **zero calls**. No landed replacement in this tree has ever made a call: pool B
read memory, the static guard wrote it, the leaf families returned constants. So pilot 1 proves the
smallest true positive -- *a zero-call 1,659-byte function can be translated, cased to block coverage,
and differentially verified* -- and nothing more. **A host replacement that invokes a guest callee is
a capability this tree does not yet have**; demonstrating it (how a host body calls a guest address,
and what the trace then attributes where) is a separate deliverable, and the tier is not reachable
until it exists. The verdict sentence for pilot 1 must say "zero-call", or it will be read as a
statement about 43%-of-bytes functions, 48 of whose blocks sit behind `0x00fe0450`'s 48 calls.

## Amendment 3 -- the tier is solid, the coverage rule is pre-registered, and pilot 1 measures a new thing

**The membership worry was 0.13% in magnitude and the census settles it in the tier's favour.** Ten
entries of 7,791 declare >1,024 B and decode <=1,024; decoded/declared is 99.96% with a median delta
of 0 and a maximum of 14 bytes. The tier is not fuzzy -- it is solid, and the only load-bearing limit
in it is the **3,321 entries (43%) with indirect branch targets**, whose block coverage cannot be
complete by construction and whose report is therefore static blocks plus the dynamic target set
observed at run time. Both sentences go in the packet: the tier is solid, and 43% of it cannot make
the claim this document's primary criterion asks for.

**Coverage is attributed by address range, not by the trace.** A block counts toward function F only
if its start lies inside F's own decoded extent `[entry, entry + decoded)`. Anything the trace reports
outside that range is attributed to its own function, or reported as **callee/unattributed** and never
counted. With a zero-call body this cannot bite; the moment a replacement invokes a guest callee the
callee's blocks would land in the caller's coverage and a caller could be **reported** fully covered
without being so. Pre-registered here, before the first case exists, because the fix is free today and
a retraction later.

**Pilot 1 measures hand translation of real logic -- the campaign's first such number.** Every member
landed so far was generated from a decode: `return 0`, a constant return, one `memcpy` at a fixed
offset. `0x00b46d20` is 23 blocks and 1,659 bytes of code that must be **read and rewritten**, and the
differential then verifies the rewrite. The deliverable is therefore not a verdict but a cost, stated
in advance:

| term | start | stop |
| --- | --- | --- |
| `T_decompile` | launching the decompile | Ghidra's C on disk (two runs, different output dirs, diffed) |
| `T_translate` | first read of that C | a hand body that compiles and links into the harness |
| `T_correct` | that build | the differential passing on the case set that reaches block coverage |
| `T_cases` | first case authored | coverage target met **or abandoned, with the reason** |

Reported separately, never summed into one "cost per function". `T_translate + T_correct` at median
size is the only per-function cost this campaign has never measured, and it decides the remaining 86%
of the bytes; a number produced by summing it with case authoring would decide nothing.

**Pilot 1 remains a floor.** Zero calls, so zero callees, so the callee-attribution rule above is
stated but untested by it. A host replacement invoking a guest callee -- the capability the 48-call
candidate and 43% of the tier need -- is a separate deliverable, and it must be demonstrated before
any tier verdict is written.

## Amendment 4 -- the decompile is measured, the cache question is settled, and the pre-registered class was wrong for a measured reason

**T_decompile = 8.081 s and 8.103 s** for `0x00b46d20`, **8.1 s** for `0x00414040`, on the existing
analyzed project (`data/bin/analyzeHeadless data/ghidra-proj bb -process eboot.elf -noanalysis
-readOnly`, i.e. `tools/draft.sh`). Ghidra's median for the catalog is 7 ms; process start dominates.
Against a per-function hand cost in hours, **decompile time is not a term in the budget** and the
resumable cache has been answering a question nobody was asking.

**The cache's acceptance test, run: two decompiles of the same function into two different output
directories are byte-identical.** `diff -r /tmp/draftA /tmp/draftB` returns 0 for `0x00b46d20` and
for `0x00414040`. The reason this matters is the failure it rules out: had Ghidra embedded the output
path or a timestamp, a cached re-read would have matched a fresh one **by accident** and I would have
certified an unsound cache on a diff that could not disagree. The mechanism is now known to be sound;
the cache is still **not built**, and this document does not ask for it -- see the pre-registration
below, which is the condition under which it would be worth building.

**The pre-registered candidate class was wrong, and by a measured margin rather than an argument.**
`0x00b46d20` decompiles to **1,090 lines containing 591 vector temporaries** (`undefined1 auVar[16]`,
i.e. live XMM registers): it is auto-vectorised float code. `0x00a78940` is the same shape (1,029
lines, 262 vector temporaries) and additionally leaks `extraout_RDX` ABI artifacts, meaning Ghidra
could not resolve its calling convention. Neither is translatable into `game/` bodies: `check_readable.py`
forbids SSE outside `game/engine/`, and a body placed in `engine/` to dodge that would be the gate
being circumvented rather than answered.

**So the class was re-measured rather than re-argued.** A Capstone census of the whole tier, counting
instructions whose mnemonic is SIMD (VEX or the classic SSE set):

    7,791 tier entries; 2,545 (32.7%) contain zero SIMD instructions; median SIMD per entry 9
    of the zero-SIMD entries, 257 have <= 2 calls

**New pre-registered rule, applied before any translation work exists:** among tier entries with zero
SIMD instructions and at most two calls, take the **first in address order** -- the tie-break that
cannot be tuned after the fact. That selects **`0x00414040`**: declared 1,072 bytes, decoded 1,070,
**264 instructions, 66 blocks, 0 calls, 3 unplaceable branch targets**. It is **below** the tier's
median size (1,659), so any cost measured on it is a **lower bound** for median-size translation, and
the report must say so in that direction.

**The subject, read rather than assumed:** it is a UTF-16 scanner over a bracket-pair table -- `(`/`)`,
`<`/`>`, `[`/`]`, `{`/`}` mirrored, with a lookahead that decides whether a pair closes -- writing a
normalised string, a position array and a flag array, and returning whether anything was seen. It reads
two **rodata bit-tables** (guest `0x02fc5120` and `0x02fc4a40`) through a two-level lookup: index by
the high byte, then, if the entry is neither 0 nor 1, by the high nibble into a second level whose
16-bit word is bit-tested with the low nibble. That idiom appears three times in the draft and
collapses to one helper in readable C++, which is the first concrete win of the readable rewrite --
and the site where a translation error would be invisible, because all three copies must collapse to
the *same* helper.

**A cost term no pool-B member had, pre-registered before it is measured: `T_data`.** Lifting the two
rodata tables into `constexpr` arrays is a step the leaf families never paid (they returned a
constant, or copied one word). Its size is unknown -- the tables' extents are not annotated -- so it is
named now, timed separately, and reported even if it turns out to be seconds.

**Status, stated instead of implied: `T_translate` is not yet measured.** The four clocks defined in
amendment 3 stand; the decompile term is now populated (8.1 s), the two-dir diff is green, and the
subject is selected and read. The translation attempt, its minute count and the number of differential
failures it takes to reach a passing body are the next entries in this document, and a pass on the
first attempt is to be reported as a suspicious result rather than a good one.
