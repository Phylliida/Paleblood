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

## Amendment 5 -- the invocation shape was the cost, the axis is a distribution, and T_data measured

**Batch, not per function. 8.1 s was process start, not decompilation.** `Decompile.java OUT.c [LIMIT]
[TIMEOUT_MS] [STRIDE]` in one session, twice, with a 20 s per-function timeout:

    stride 700 --> 226 functions, ms=88,345, ms_per_function=390.9, wall 95.9 s
    stride 200 --> 789 functions, ms=363,853, ms_per_function=461.2, wall 371.7 s, failed=1

So the marginal cost is **~0.46 s per function** against **8.1 s per function** for one
`analyzeHeadless` call: a **17.6x** difference whose entire cause is JVM start and project load
(7.6 s of 95.9 s, i.e. 8% of the batch run and ~94% of the per-function run). The lesson is not
"cache the decompiler" -- it is that **I was paying 8 s of process start to buy 2 ms of analysis**,
and the cache I carried for eleven slices was answering a question nobody was asking. It is dropped
from the plan, not deferred again: `data/exports` already holds a full batch export.

**The two figures this replaces, both of which I had been quoting.** (1) "17.5 h for the tier" was
7,791 x 8.1 s -- an artefact of the wrong invocation; at the batch slope the tier is **~60 minutes**
and the whole 157,757-entry catalog is **~20 h**, not the 11.5 h I carried from a batching figure
whose population I never re-read. Both are now numbers with a command behind them. (2) The batch run
fails loudly on the pathological case (`failed=1` at a 20 s timeout), so the 35.8 s function is
caught by the timeout argument rather than by luck.

**Zero-SIMD is a filter on a continuous axis, and the census now reports the axis.**
`tools/simd_census.py` -- landed in the repo, because a tool that finds defects while living in /tmp
is not in the repo it protects -- scans the tier with a completed allow-list (VEX prefix, the legacy
SSE set, the `p*` integer set, the `ps/pd/ss/sd/dq/qu` suffix rule, with `insd/outsd` and friends
excluded) and **prints a known-positive control first**: `0x00b46d20` scores **351 instructions,
322 SIMD, density 0.917**, so the allow-list is shown to find a function known to be vector-dense
before any number below it is reported.

    7,791 tier entries scanned; density = SIMD instructions / total instructions
    p10 0.000   p25 0.000   p50 0.026   p75 0.191   p90 0.499   p99 0.910
    density = 0          2,512 (32.2%)
    0    < d <= 0.02     1,184 (15.2%)
    0.02 < d <= 0.05     1,004 (12.9%)
    0.05 < d <= 0.10       569 ( 7.3%)
    0.10 < d <= 0.25       873 (11.2%)
    d > 0.25             1,649 (21.2%)
    density <= 0.02  3,696 (47.4%)   with <=2 calls 270
    density <= 0.05  4,700 (60.3%)   with <=2 calls 287
    density <= 0.10  5,269 (67.6%)   with <=2 calls 297
    density <= 0.25  6,142 (78.8%)   with <=2 calls 341

**The honest statement, corrected from this morning's:** 32.2% is a **lower bound** on the reachable
tier and the ceiling is not 32.2% -- the median tier function carries **2.6%** SIMD, and 60.3% of the
tier sits at or below 5%, which is a body with a handful of vector ops that a helper can carry rather
than a different kind of program (`0x00b46d20` at 0.917 belongs to the 21.2% above 0.25 and needs
`game/engine/`, not a helper). The zero-SIMD count also moved **2,545 -> 2,512** between two runs of
my own instrument; the difference is the allow-list, and the earlier figure is withdrawn rather than
reconciled. **Where the line sits is a policy choice, not a measured limit** -- `check_readable.py`
forbidding SSE outside `game/engine/` is a decision the maintainer owns -- so it is raised as a
**fourth yes/no** rather than decided here.

**`T_data`, named last amendment, measured this one: it is a non-term.** `tools/rodata_table.py`
derives each table's extent from the binary rather than guessing it -- 256 level-1 words, ending 16
words past the largest level-1 value that names a level-2 block -- emits a `constexpr` array, pins the
**sha256 of the exact span**, and round-trips the emitted words against the bytes:

    sg_bracket_a: guest 0x02fc5120  words 384  span  768 B  max level-2 base 368  T_data 0.064 s
    sg_bracket_b: guest 0x02fc4a40  words 880  span 1760 B  max level-2 base 864  T_data 0.064 s

**And the two extents corroborate each other**: `0x02fc5120 + 768` is exactly `0x02fc4a40 + 1760`, so
the derived end of the second table lands flush on the start of the first. Two independent lookups
(derive-forward and neighbour-address) agreeing on a boundary is worth more than either alone, and a
guessed extent would rarely land flush.

**Still not measured, and this is the fourth amendment it has been true in: `T_translate`.** The
decompile term is populated, the cache question is closed as the wrong question, the population is
measured on the axis that matters, and the data tables are generated. What remains is one body, its
minutes, and the count of differential failures it takes to reach a pass -- with the three planted
translation errors still owed as the oracle's proof.

## Amendment 6 — "unplaced 3" was three exits, and 42.6% was two populations added together (dated: this slice)

**The number that blocked the pilot.** `tools/blocks.py --verbose` on `0x00414040` printed `unplaced 3`, and
amendment 5 recorded that the pilot therefore sits inside the 42.6% class where "every basic block ran" cannot
be claimed. Both sentences are wrong, and the mechanism is one line: `blocks()` counts **every static jump
target that is not an instruction boundary in the decode window**, and the decode window *is* the declared
extent. A tail jump out of the function therefore cannot be a boundary and is counted as a missing one.

**Measured.** The three targets of `0x00414040` are `0x41447d`, `0x414481`, `0x4144ad`; the entry is
`0x00414040+1072`, end `0x414470`. All three are **past the declared end**, by **+13, +17 and +61 bytes**,
inside a **179–227 byte gap** before the next entry at `0x414560`. The function has **66 blocks and zero
genuinely unplaceable leaders**; the pilot's coverage claim was never at risk from the population it was said
to belong to.

**Tier-wide, 7,791 entries (two independent implementations, `tools/blocks.py` and `tools/leaders.py`,
agreeing on the same definition; the 2,751 vs 2,750 difference is one duplicate address in the leaders run):**

| population | entries | share |
|---|---|---|
| internal unplaceable leader (target inside the declared extent, not an instruction boundary) | **742** | **9.5%** |
| exit (static target past the declared end) | **2,750** | **35.3%** |
| either | ≈3,320 | **≈42.6%** |

So the carried **42.6% was the union of two populations that demand opposite responses**, and the pilot sat in
the cheap one. `blocks.py` now prints both, and takes the declared end as an argument rather than
reconstructing it from the decoded tail — that reconstruction put `0x417e3a` of `0x00416e80` (exactly one byte
past the last decoded instruction, but inside the declared extent) on the wrong side of the boundary, and the
two tools disagreed 742 vs 0 until it was fixed. **A boundary reconstructed from a truncated decode is not the
declared boundary.**

**And the exits are mostly not tail calls to other functions.** Of **6,942** tier exit targets, only **316**
land inside another catalogued entry; the rest land where **no entry's `[start, start+size)` covers them** —
`symbols/ghidra_functions.csv` holds exactly **157,757** entries, so "unowned" is not a lookup artefact. Their
distance past the preceding entry's end: **p10 2, p50 17, p90 110 B**; **47.6% within 16 B, 81.9% within 64 B,
95.7% within 256 B, 99.9% within 4 KiB** (max 35,754 B). A median of 17 bytes is not a jump into distant code:
**the declared size of a Ghidra entry is systematically short**, ending at the last `ret`, with reachable
blocks — out-of-line epilogues, shared tails, stack-check paths — left outside every entry. 3,299 of 7,791
entries also have a short decode (declared minus decoded, max 14 B), which is a *different* truncation and was
already carried.

**What this retires.** "Coverage of the declared extent" is retired as a criterion — the declared extent is a
truncated body, so a function can be fully covered by that measure and still leave its own tail untested.

**What replaces it, in general form (the form that serves 7,791 members, not one pilot).** The coverage
denominator is the **reachable set from the entry by recursive descent, allowed to leave the declared extent**;
an internal unplaceable leader is a defect and is **named, never averaged** (742 tier-wide); an exit is
attributed to the entry that owns the target, and if none does it is recorded as a **partition gap** and is
never counted in the callee's denominator; after the cases run, executed addresses that fall inside the
reachable set are added as leaders and coverage is recomputed against the revised set, so a dynamic target that
lands mid-instruction becomes a **finding to report**, not an ambiguity to average away.

**Consequence for the denominator, recorded now rather than discovered at the end.** The campaign's burndown
counts **entries** (157,757). The 6,942 unowned exit targets per tier are reachable code that no entry owns, so
"all of Bloodborne decompiled" measured in entries will report complete while leaving that code unowned.
That is a stated limit of the measure, not a change of scope.

**Instrument.** `tools/leaders.py` (new) does the three-way split and the owner lookup; `tools/blocks.py` was
patched to print both populations (unplaced **742**, exits **2,750**) and keeps its old numbers otherwise
identical (blocks median 61, min 1, max 2,550; decoded 20,055,556 / 20,064,463 = 99.96%; 10 entries declaring
>1024 and decoding ≤1024).

## Amendment 7 — the 742 are not a defect class: zero mid-body unplaceable leaders exist in the tier (dated: same slice as amendment 6)

Amendment 6 called the 742 entries with "internal unplaceable leaders" a defect class and promised to name them.
Measured before anything was built on that sentence: **split all 742 by whether their unplaced targets lie in the
undecoded tail. All 742. Zero entries in the 7,791 have a static branch target landing inside a *decoded*
instruction.**

The mechanism, from four probes. `0x00416e80` targets `0x417e3a` with declared end `0x417e3e`; `0x00419d70`
targets `0x41a206` / end `0x41a209`; `0x0041c260` targets `0x41c89a` / end `0x41c89b`; `0x00448df0` targets
`0x449237` / end `0x44923b`. At every one of those addresses the bytes begin `e8` followed by a 4-byte
displacement — a 5-byte `call rel32` — and the declared end falls **1 to 4 bytes into that instruction**.
`0x00416e80`'s tail at the target is `e8 b9 66 ba 02`, a call to `0x02fc94f8`, one byte of which lies outside
the entry's declared extent. So the entry's own final instruction is truncated by its own declared size, and the
linear sweep "stopped early" because the remaining 4 bytes were less than one instruction needed.

**And a probe defect worth keeping, because it nearly produced the opposite conclusion.** My first attempt sliced
the tail as exactly `declared_end − target` bytes and decoded it: **0 instructions in all four cases.** A probe
that slices exactly the declared remainder cannot see an instruction that crosses it — the "0 instructions"
was my slice, not the bytes, and read the other way it would have "confirmed" that these targets point into data.

**One fact, not three.** Zero mid-body unplaceable leaders · 742 entries whose declared size truncates the
instruction at a branch target · 2,750 entries with exits past the declared end (6,942 unowned targets, p50
17 B past the preceding entry's end) — all three are the same statement: **`size` in the Ghidra export is a
lower bound on the function body, not its extent.** Every per-entry decode, translation and verification in this
campaign operates on a truncated body.

**What this changes for the pilot and for the campaign.**
- The pilot's coverage denominator is unaffected in kind (0 internal unplaceable leaders, 66 enumerable blocks)
  but its body is **not** the 1,072 declared bytes: three `call`/jump targets land at `0x41447d`/`0x414481`/
  `0x4144ad`, so the translation must reach at least `0x4144ad + 61`.
- The tier's byte total (20,064,463) is a **lower bound** on the bytes the tier's functions occupy.
- The 742 and the 2,750 are **instrument boundaries reached from a short declaration**, not properties of the
  binary; the count of entries whose declaration is provably short is therefore **at least 3,320 (42.6%)**, and
  that is now a statement about the export, to be read as one.

## Amendment 8 — the body is sized by the descent set; the coverage expectation is pre-registered as zero (dated: this slice)

Amendment 7 ended by saying the pilot's body "must reach at least `0x4144ad + 61`". That was a direction,
not a size. The review that caught it is worth naming: sizing the work against the declared extent puts the
discovery of the extra blocks **inside `T_translate`**, where it looks like translation being slow rather than
the extent being short. Counted first, then translated.

**`tools/descent.py` (new, in the repo).** Recursive descent from the entry, allowed to leave the declared
extent; fall-through continues except after `ret`/`jmp`; a conditional jump adds its target and its
fall-through; a **call adds nothing** (its target is a callee, not this body) but keeps the fall-through;
indirect transfers are counted, never assumed away; an address that does not decode is reported and stops the
walk. Block leaders are entry + static targets + instructions after any transfer — the coverage denominator,
deliberately not the same set as the worklist.

| entry | declared | descent insns | blocks | span from entry | outside extent | owner of those |
|---|---|---|---|---|---|---|
| `0x00414040` | 1,072 B | **279** | **64** | **1,144 B** `[0x414040,0x4144b8)` | 22 insns `0x414471..0x4144b7` | unowned |
| `0x00416e80` | 4,030 B | **939** | **269** | **4,072 B** `[0x416e80,0x417e68)` | 9 insns `0x417e3f..0x417e63` | unowned |

So the pilot is **279 instructions over 64 blocks, 257 of them inside the declared extent** — not 264, and
not the 1,072 B the work was sized against. `0x00416e80` corroborates the shape at larger scale (939 vs 934 by
linear sweep, +38 B span, 18 indirect calls, 33 distinct call targets). Two block counts coexist for the pilot
and both are printed: `blocks.py`'s linear-sweep leaders **66**, the descent's reachable leaders **64** — the
descent number is the coverage denominator, because a leader that is not reachable from the entry can never
run.

**Pre-registration, written before any case for pilot 1 exists.** With **0 internal unplaceable leaders across
all 7,791 tier entries** (amendment 7), the expected number of **dynamic targets landing inside a decoded
instruction** on pilot 1's first case run is **zero**. If one appears it is a finding, with two candidate
causes to separate by re-deriving the descent from the observed address: **(i)** the descent set is wrong —
a successor was never followed; **(ii)** a decode defect on the case's own path. Zero is also what makes the
pilot's coverage claim cheap: no unplaceable leader means every block in the set can be enumerated as a
literal, so "every block ran" is checkable without a dynamic-leader revision at all.

**Supersession — stated so the older sentence is not cited later.** Amendment 6 said: "an exit is attributed
to the entry that owns the target, and if none does it is recorded as a partition gap." That rule used the
**decoded extent** as the boundary and is **superseded**. A target outside the declared extent that is
**reachable from the entry's descent is this entry's body**: the 22 instructions at `0x414471..0x4144b7` belong
to `0x00414040`, unowned by the partition but not a gap in *its* coverage. "Partition gap" now means only a
target reachable from **no** entry's descent — a fact about the partition, never about a function — and the
tier-wide set of those has not been computed.

**Queued, not claimed.** The union of descent sets is a third byte total, above the 20,064,463 declared and
above anything an entry count can express. One descent costs ~0.02 s, so the tier is ~3 min of work; it stays a
queue item until it is run and printed with its own control.
