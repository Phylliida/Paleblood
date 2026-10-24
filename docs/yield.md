# Yield per stretch, as a denominator rather than a phrase

The horizon figure (161 h at ~39 rows/h) predates the instrument phase. This records the measured alternative so a
forecast is a derivation instead of a phrase.

## Method (re-runnable, one command)

    git log origin/main..HEAD --numstat --format='@@%H%x09%s'

Classify each commit by its numstat: **row-bearing** if it adds lines to `symbols/functions.csv`, **gate-only** if
it touches `test/` or `tools/` and adds no row, **other** otherwise. Quote all three or none.

## Measured at `11e70c4`-era HEAD (68 commits, `origin/main = fa4acdf`)

| class | commits |
|---|---|
| row-bearing | **1** (`b6e4956`, **+1 row**) |
| gate-only (`test/`, `tools/`) | **39** |
| other (docs, symbols, artifacts) | **28** |

**Commit ratio: 39 gate-only commits per 1 row-bearing commit.** The only row added on this branch is
`0x0196f030`, 15 B, status `original`.

**THIS IS A COMMIT RATIO AND NOT A GATE RATIO, and the difference is not a rounding.** A refusal surface is
not a commit: several of the 39 are tests *of* a gate, docstrings, and a verification fix; `1ab` alone was
three commits before it was usable. So the surface ratio is smaller than 39 : 1 by an **unmeasured**
factor. Naming the unit here is the same discipline as `has_body` beside `landed` -- a rate that silently
changes its unit is the defect this doc exists to track, written into the doc that tracks it.

## What it means, and what would make it wrong

A stretch that produces **a body and no new refusal surface** is the evidence that the instrument phase was an
investment. A stretch that produces **a gate and no row** moves the ratio the other way. The ratio is only meaningful
quoted with its class counts beside it -- `39` alone is a numerator wearing a rate's clothes.

The honest horizon from this record is not a number of hours: it is that **no row has yet been added twice in one
stretch**, so any projection from one row per stretch is extrapolation from n = 1, and the pre-instrument figure is
not evidence about the post-instrument tree.

## PRE-REGISTERED: next stretch's target, published before it starts

**One row. Zero new refusal surfaces.** Written now, at `352f8ca`, so that the stretch is judged against a target
rather than read against the ratio afterwards. The direction that matters is falsifiable: a stretch that adds a
refusal surface and no row is **a miss against a written target**, not an interpretation of a number.

What **"row"** means here, so the numerator cannot be graded generously either -- and the unit matters because
`39 : 1` above was measured in COMMITS while this target is stated in ROWS:

> **a row is an address in `symbols/functions.csv` with a body AND its evidence trace** -- `1ab` terms 1-3
> satisfied: a first-run witness equal to the original's, at least two mutants dead at named disjoint magnitudes,
> and cases reconstructible from the row's own fields.

**A batch landing at `original` with no evidence trace does not count as a row for this target**, even though it
adds lines to the same file. It would satisfy the letter and produce exactly the transcription the campaign exists
to stop accumulating, and it would then read as the inflection. `0x0196f030` is the only row on this branch that
counts by this definition -- six pre-registered verdicts, three dead mutants, cases landed and the witnesses re-run
from them.

What "refusal surface" means here, so the target cannot be graded generously later: a new place where the tree says
no and did not before -- a new `SystemExit`/`refuse` path, a new required flag, a new guard with a failing input, or
a new column whose absence is refused. Tests *of* an existing surface are not a new surface; docstrings are not a
surface; a fix that makes a verification stop crashing is not a surface (it is a repair of an instrument with its
own defect).

If the stretch misses, the honest reading is the one this doc was written to permit: the tree is being made
unmakeable faster than it is being used, and that is worth knowing at the next boundary rather than at commit 140.

## PRE-REGISTERED (subject): which single row the next stretch takes, and why not the easy one

**One member of the 47-member `mov al,[rax+K] ; ret` family -- not the batch.** The batch would be 47 rows in one
commit with barely one row's evidence: a row-bearing commit by the old count, failing the definition above exactly
as the bare landing did.

**Which member: the half of the `0x1590` pair.** That pair shares BOTH displacements with a sibling and differs only
by address, so its case must distinguish itself from a sibling that differs by a constant -- **the sharpest instance
of the family, which is what makes the standard reproducible rather than lucky.** An easy member would prove only
that an easy member can be landed.

**The address is read from `symbols/chain_family.csv` when the work starts, never from memory here.** A remembered
address is a numeral, and a numeral typed from notes is not the set it names (fourth sighting of that defect).

Its trail is `0x0196f030`'s shape: first-run witness equal to the original's, two mutants dead at named disjoint
magnitudes, cases reconstructible from the row's own fields. **The other 46 stay unlanded until this trail proves the
first one's shape was a shape and not a one-off.**

**Contingency, stated before the work so it is a finding and not an excuse:** if one member turns out to be
unlandable without the other 46 (shared TU, shared seed derivation, a family-level case directory), that is the
result -- and it is recorded here in advance as the expected shape of a legitimate miss, not discovered afterwards
as a reason the target moved.

## The selection rule above failed its first grep, and both predictions about why were wrong

Measured at `a128c2b`, one command: `5520` -> **0 matches**, `0x1590` -> **0 matches**, header
`address,size,load_disp,load_target,where,store_k2,store_width,imm`.

* **Prediction 1 (radix):** the file stores decimal `5520` and `0x1590` is a hex rendering. **Refuted.**
* **Prediction 2 (my rendering):** same hypothesis, different author. **Refuted by the same measurement.**
* **What the header shows:** `chain_family.csv` has **`store_k2`** and no `store_k` column. A scan of every CSV
  under `symbols/` found **none carrying `store_k`** (scope: `symbols/*.csv` and `*.csv.gz` only -- the artifact
  that does carry it is **carries it is identified only by a DOCSTRING, not by a header read** -- the census tool documents that its
  `store_k` column holds the second load's displacement. **That is a documentation claim, and a documentation claim
  is a hypothesis; a `head -1` is a measurement** (the `1y` distinction). So the opening move of the next stretch is
  **not a search but a confirmation**: read the census output's header and check it against the docstring that names
  it. If they agree, the column is **double-sourced** -- the same free cross-check that `has_body = 38,101` gave the
  catalogue counts. If they disagree, the docstring is wrong about its own artifact, which is **worse than an
  unlocated column and cheaper to learn now than mid-batch.**).

So the numeral failed on **provenance, not radix**: it named a column of a different artifact. **A prior about which
defect is common is not a measurement of which defect is present** -- and the radix hypothesis was ranked first
because it had five prior sightings, while the header was one command away the whole time.

### The class, now with three sightings in one stretch

`store_k` / `store_k2`  ·  `landed` / `has_body`  ·  `census_band.py` / `branch_census.py`

**Not a radix problem and not provenance in general: short names across artifacts that a reader can substitute
without noticing.** The shape that makes the substitution unwritable is **column constants qualified by their
artifact** -- `CHAIN.STORE_K2`, `CENSUS.STORE_K` -- so choosing wrong requires writing the wrong module name rather
than recalling the wrong string. **Owed, not built -- and deferred on BLAST RADIUS, not on the surface rule.** Checked against this doc's own four
clauses: a qualified-name rename adds **no** refuse path, no required flag, no guard and no column, so it is a
**refactor, not a refusal surface**, and citing the target against it was the same unit-upgrade this doc spent the
stretch fixing -- one level up, a label standing in for the reason. **A fix deferred on a wrong reason is a
preference wearing a ruling's clothes.** The reason that holds is the honest one: it touches **every reader of every
family table**, so its diff is large, is not reviewable in one window, and would sit astride the stretch meant to
produce a row -- consuming the budget it exists to protect.

**The selection rule is therefore unresolved and is restated as its own first task:** locate the artifact that
carries `store_k`, print the candidates by field equality, and only then choose a member. A target whose subject
cannot be found is the horizon-as-phrase one tier up -- and it was caught for the price of one grep, before the
stretch was spent.

## ORDER, and one collision in the target that had to be resolved rather than graded around

**Term 4 of `1ab` first (canonical rendering of generated cases), then the chain member.** Term 4 is the only term
the worked example fails, it is a check over artifacts that already exist, and it converts **the moment a yes
arrives**: `0x0196f030` becomes eligible for `edge-verified` on the next run instead of on a promise about a future
one. The chain member is a trail from nothing and is a stretch, not an hour. **Not to be compressed into one.**

**The collision, stated before the work:** a canonical-rendering check makes the tree say no in a place it did not
before -- which is clause one of this doc's own definition of a refusal surface. So **term 4 is a NEW SURFACE**, and
the pre-registered target (`one row, zero new surfaces`) **forbids the very work that unblocks the row's promotion.**
Both readings cannot hold.

**Resolution, by amending the target now rather than grading it later:**

> **One row, and at most ONE new refusal surface -- and that surface must be the canon check, carrying its subject
> in the same commit** (the generated cases it refuses are the cases the row cites, not a fixture).

That keeps the target falsifiable in both directions: a second surface is a miss, a row without its cases cited is a
miss, and the surface arriving without its subject is a miss. **A target that forbids the work that makes the row
promotable was mis-specified, and the fix is to say so in advance rather than to discover it when the diff is open.**

## SPEC (not a surface): the canonical-rendering check, written before the diff exists

This is the document the check will be built to. It is prose in the same file that holds the target, and **a
specification is not a refusal surface** -- the surface is the diff, and the surface is bounded by the target above.

**Subject:** generated case files only -- the output of `case_docs` -- **never hand-authored cases.** Refusing an
unpadded hand-authored case gates the wrong population (the cases that already exist and already ran).

**Rule:** every address is rendered `0x` + **eight** digits (`#010x`). `0x5956a00` and `0x05956a00` are one address
and two hashes; only one of them is canonical.

**Planted negative, and it is the best kind available: `0x5956a00`.** That string came out of my own run -- it is the
**unpadded rendering of a real address in this tree**, produced by the defect this check exists to catch. A check that
renders `0x05956a00` **must reject it**. A synthetic fixture would prove the regex works; this one proves **the check
would have caught the defect that motivated it**, which is the property that makes `tier_authority`'s negative worth
more than its positive.

**Falsification, three directions -- one more than any prior pre-registration here:**

1. **a row** lands and is counted by the definition above (body + `1ab` terms 1-3);
2. **at most one new refusal surface**, and it is this check;
3. **the check arrives carrying its subject in the same commit** -- the generated cases it refuses are the cases the
   row cites, not a fixture. **A green check with nothing under it is a miss, not a pass** -- this is the direction
   that would otherwise be discovered as a green on an empty population.

**The honest sentence about where the count stands, recorded so the next stretch inherits it:** the count is **21**,
and it is 21 because **eight of the last nine things built were not rows.** Every one of them is a reason the next row
can be defended; **none of them is the row.** The next stretch's job is to make it the ninth.

## OPEN FINDING, measured: the board's two byte counts are NOT the five `original` rows, and the gap is 101

Prediction put to the tree: `bytes_transcribed - bytes_landed = 325,161 - 324,066 = 1,095` should equal the byte total
of the five `original` rows, since `has_body 38,101` exceeds `landed 38,096` by exactly those five.

**Measured (awk over `symbols/functions.csv`, `$5=="original"`): COUNT = 5 -- correct -- BYTES = 1,196.**

    0x00414040   1072
    0x004632d0     67
    0x0111a600      8
    0x0196f030     15
    0x024264d0     34
                  ----
                  1196

**1,196 != 1,095. The discrepancy is exactly 101.**

So the word (`landed` / `transcribed`) **does** differ from the row-count pair that agrees: the two byte counts are
**not** double-sourced, and one of them counts rows by a predicate that is not "status is not original". **This is a
byte-level instance of the class this session spent its length repairing, found by the cross-check the row counts
got free this morning.**

**And 101 is already a carried number in this campaign: the ledger surplus, `38,197 - 38,096 = 101`.** Two appearances
of the same delta now require **one** explanation, not two -- and the candidate that would explain both is a row set
counted in the ledger and in `functions.csv` with different membership rules. **Stated as a hypothesis, not a
conclusion: this has not been measured.**

**Unresolved, and the next stretch's FIRST command rather than its canon check** -- a board quoting a byte gap whose
predicate is unknown is a number with a broken name, and the canon check would be built on top of it.

## The ROW 101 is explained: multiplicity, measured. The BYTE 101 is a different question and stays open.

Measured over `symbols/verification.csv` (header `function,cases,option,total,passed,failed,quarantined,source,cases_sha256,date`):

    records                              38,197
    distinct addresses                   38,096
    addresses with > 1 record                30
    surplus == sum(n_i - 1)                 101

So **`38,197 - 38,096 = 101` is multiplicity, not membership**: 30 addresses carry 131 records. The prediction was
right about the mechanism and **wrong about the number** -- 101 is not the count of duplicated addresses, it is the
*excess* they carry, and the two would have been confused by anyone who stopped at the predicted figure.

**Free cross-check nobody asked for: 30.** The number of addresses with more than one verification record is **exactly
the 30 approvals the board reports against 21,086 all-rows-clean.** The approval count was always a *record* count; it
now has a second derivation from the ledger itself.

### The byte 101 is NOT the same 101, and one cause for both is arithmetically impossible

A row is at least five bytes, so a row mechanism cannot produce a byte delta. **Tested separately, never in one
sentence** -- and there is a candidate that is NOT a coincidence: **34 + 67 = 101**, and those are two of the five
`original` rows' sizes (`0x024264d0` 34, `0x004632d0` 67). Hypothesis, **not measured**: `bytes_landed` includes those
two rows as well as `bytes_transcribed`, which would make the gap `1,196 - 101 = 1,095` exactly. A subset sum matching
to the byte is evidence to test, not a conclusion -- five sizes admit 31 subsets and one of them had to be small.

**First command of the next stretch:** test that membership directly -- read the predicate `bytes_landed` uses and
name the rows it counts. **Not this arithmetic again.**

## The byte 101 LOCALISED, measured: `bytes_landed` is exact, and `bytes_transcribed` omits two named rows

Two derivations from one artifact, compared (`awk` over `symbols/functions.csv`, `NR>1`):

    all rows        38,101 rows   325,262 bytes
    not original    38,096 rows   324,066 bytes   <-- equals the board's bytes_landed, to the byte
    original             5 rows     1,196 bytes
    closure: 324,066 + 1,196 = 325,262  (exact)

**`bytes_landed = 324,066` is confirmed exact** against `status != original`. **`bytes_transcribed = 325,161` is 101
short of the file total 325,262** -- so it is not "sum of all sizes", and the 101 is not arithmetic drift: it is
**101 bytes of rows that `bytes_transcribed` does not count.**

**The subset is unique, and it was checked rather than guessed:** of the 31 subsets of the five `original` sizes,
**exactly one sums to 1,095** -- `{1072, 8, 15}` = `0x00414040`, `0x0111a600`, `0x0196f030`. So the rows
`bytes_transcribed` omits are **`0x004632d0` (67) and `0x024264d0` (34)**, and `67 + 34 = 101`. The earlier
`34 + 67 = 101` hypothesis was right about the rows and **wrong about the mechanism**: they are **excluded, not
double-counted** -- the gap is `1,196 - 101`, not `1,196 - 101` by inclusion.

**`0x024264d0` is the retired row that was never landed**, so its exclusion from a *transcribed* count is correct by
the word. **The defect is therefore not in either number but in the label pair**: `bytes_transcribed` reads as "the
file's total" and means "rows carrying a transcribed body", which is the *fourth* time tonight a number was right and
its name wrong. **A count named after the artifact it is computed over would have made this unwritable** -- the same
repair owed for `store_k`, one axis over.

