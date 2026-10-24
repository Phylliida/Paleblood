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

## The byte 101, RESOLVED FROM SOURCE: the predicate is `body_exists`, and the docstring was false by 101 bytes

Measured with the code's own helper (`landed.byte_totals`, `landed.body_exists`, `landed._body_index` over `game/`):

    rows 38,101 · bodied on disk 38,099 · bodiless 2
    byte_totals -> {'landed': 324066, 'transcribed': 325161}   <-- the board's two figures, from the code

The five `original` rows, checked individually: `0x00414040` 1072 Yes · `0x0111a600` 8 Yes · `0x0196f030` 15 Yes ·
**`0x004632d0` 67 No** · **`0x024264d0` 34 No**. So the excluded rows are the two bodiless ones, and `67 + 34 = 101`.

**Both board figures are therefore confirmed by the instrument that computes them** -- not by my arithmetic, and not
by a subset scan. The subset scan named the right rows; only reading the source named the right *reason*.

**And the docstring at `tools/landed.py:89` asserted the opposite:** *"`transcribed` counts every row that carries a
body, **which is every row in the file**"*. It is false: 38,099 of 38,101 carry a body. **The code was right, its
comment was wrong, and the comment is what a reader trusts** -- so the docstring now states the measured counts, the
two excluded rows, the 101 bytes, and the reason they are excluded.

**Fifth name collision, recorded: `has_body` vs `body_exists`.** The band column means "an address in
`functions.csv`" (38,101); the disk predicate means "a body was emitted" (38,099). **They differ by exactly the two
bodiless rows, so "the number of bodies" is wrong by two rows and 101 bytes depending on which one the speaker
meant.** That is the same repair owed for `store_k` and for `landed`, now on the word *body*.

## CORRECTED OPENING COMMAND: there is no census header to read, and `store_k` is named wrong by its own two lines

The next stretch's first command was recorded as "`head -1` on the census output, checked against the docstring that
names `store_k`". **That command has no subject.** `tools/leaf_shape_census.py` prints; it writes no artifact --
`ls symbols/*census*` returns nothing, and its only arguments are `--max-insns`, `--top`, `--elf`, `--targets-for`,
`--targets-json`, `--frontier`. **`store_k` is a dict key in a printed top-N table, never a file column**, so no header
can confirm or refute it. The finding was open against an artifact that does not exist: the second time this session
the *opening move* was the defect rather than the measurement.

**The two lines that compute it, read (`tools/leaf_shape_census.py:96-104`):**

    load_disp = ... ins[0].operands ...           # first instruction's memory displacement
    store     = ... ins[1].operands ... disp 0   # SECOND instruction's memory displacement, called `store`
    out.append({... 'store_k': store, 'src': ...})

**So `store_k` means "the memory displacement of the second instruction" -- whatever that instruction is.** In the
rank-1 chain family `mov rax,[rip+K] ; mov al,[rax+K2] ; ret`, instruction 1 is a **load**, so `store_k` carries a
**load displacement**. The name asserts a direction that two of the families it selects do not have: **a column name is
not a direction, now with a line number**, and this is the same defect the rank-1 record already carried as prose
without a source.

**What replaces the opening command:** read `:96-104`, not a header -- done, above -- and then **select the 47 by field
equality on `load_disp`/`load_target`, never on `store_k`**, because selecting on a misnamed column is selecting on a
quantity whose sign of direction is unknown. **Renaming `store_k` -> `disp_insn1` is owed and is a rename, not a
surface**; until it lands, every reader of that printed table must read the two lines first.

## The contradiction was MY ZERO-INDEX, and measuring both columns retracts a claim as well

I wrote that `store_k` is "instruction 1's displacement". In the source it is `ins[1]` -- **the SECOND instruction,
zero-indexed.** `load_disp` is `ins[0]`, the first. So **the two columns are different quantities**, not one quantity
under two names, and the "two counts over the same rows must be equal" contradiction was manufactured by my own
English, not found in the data.

**Measured over `symbols/chain_family.csv` (header: `address,size,load_disp,load_target,where,store_k2,store_width,imm`):**

    rows                                          78
    distinct load_disp                            78    <-- every row has its own K
    distinct store_k2                             47    <-- 47 values over 78 rows
    rows where load_disp == store_k2               0

**So the census's `store_k` is the quantity chain_family already calls `store_k2`** -- the second instruction's
displacement -- and the rename is **clarity, not a hidden distinction.** `store_k -> store_k2` in the census is the
repair, one table over.

**And a claim this campaign has carried since the chain pilot is refuted by the same measurement.** The `0x1590` pair
was recorded as *"shares both displacements, differs only by address."* **`load_disp` is 78-distinct across 78 rows, so
no two rows in this table can share a `load_disp`, and therefore none can share both.** Either that pair lives in a
different table -- the 47-member `mov al,[rax+K] ; ret` family, not this one -- or the claim was wrong when it was
written. **Either way it must name its table, and until it does, "the 0x1590 pair" is a sentence without an artifact**,
which is the second of those tonight.

**Selection rule, corrected a second time:** the 47-member family is selected on **`store_k2` equality in its own
table**, never on `store_k` from a printed census, and never on `load_disp`, which is row-unique here and would select
exactly one member.

## INVENTORY: the class that is not gated -- prose claims about artifacts

Every instrument in this tree reads code or an artifact and compares it to something: `check_agnostic` over values,
`tier_authority` over a heading, the frontier guard over the ledger union, `has_body` over a catalogue. **Not one of
them can catch a sentence that names the wrong table, the wrong operand index, or an artifact that does not exist.**

**Three of tonight's last four findings were of exactly that kind**, and none of them was found by an instrument:

    "head -1 on the census output"        -- the census writes no artifact; no header exists
    "store_k is instruction 1's displacement" -- ins[1] is the SECOND instruction; zero-indexed
    "the 0x1590 pair shares both displacements" -- load_disp is 78-distinct, so it cannot, and the
                                                  sentence names no table in which it could

**The seven collisions tonight were not seven instrument failures. They were seven sentences**, and the instruments
caught only the ones that had already become numbers. **A claim that reads like a measurement and names no artifact
survives indefinitely** -- the `0x1590` pair did, for weeks, and was quoted in at least one pre-registration.

**But "no gate" overstates the inventory, and the distinction is the useful part:**

  * NOT gated, and probably not gatable: whether a sentence's *subject* is the artifact its parser reads. Deciding
    that "instruction 1" means `ins[0]` requires understanding the English.
  * GATED IF BUILT, and cheap: **artifact-existence and column-existence.** Every backticked `symbols/*.csv` in
    `docs/` and `tools/` docstrings can be checked for presence, and every `file:column` claim for membership in that
    file's header. That check would have caught **two of the three** above -- the census header that does not exist and
    the `store_k` column that is not a column -- **without understanding a word of the prose.**

**So the honest inventory is: prose claims are ungated on *meaning* and ungated on *reference*.** The reference half
is writable and is **owed, not built** -- and it is deliberately **not** the canon check's single surface, because
spending the stretch's one refusal on a doc linter would leave the row without its rendering rule.

## AMENDMENT to the surface definition, made before the next diff: tests of NEW invariants are surfaces

The four clauses -- a new refuse path, a new required flag, a new guard with a failing input, a new column whose
absence is refused -- exempt "tests of an existing one". **That exemption has a loophole: a NEW test asserting a NEW
invariant is a guard with a failing input, yet reading the exemption literally a stretch could add five new invariant
tests and truthfully report zero surfaces.** That is the target graded generously at the level where it is cheapest to
be generous, so it is closed now, while no diff exists.

**Fifth clause: a new test that asserts a property no test asserted before is a surface.** A test that re-asserts an
existing invariant over a wider population is not, and a test added to a surface already counted is not counted twice.

**Consequences stated, so the clause cannot be read two ways:**

  * the **canon check** is the target's single surface: it is a new refuse path AND a new invariant. It is one surface,
    not two -- the clause counts the check, not the artifacts of writing it.
  * the **doc reference check** (artifact exists, `file:column` in the header) is therefore **a second surface** and
    **cannot be built in the same stretch as the canon check.** It waits. Said now, not discovered in review.
  * re-asserting the frontier union, the `has_body` arithmetic or the tier authority over a new fixture is **not** a
    surface: those properties already have tests and the clause exempts wider populations of an existing assertion.

**And the doc linter's first real test is a PLANTED doc that names a table which does not exist** -- not a hypothesis
about one. A linter written and green in the same hour as its first run has been tested by nothing but itself, which is
the failure `1ab` exists to make unwritable for bodies and this clause exists to make unwritable for documents.

## LAST CLAUSE, so it is read on a night nobody remembers writing it: STUBBING is a surface, NARROWING is a scope claim

The fifth clause exempts re-asserting an existing property "over a wider population" and says nothing about the two
ways a green gets **manufactured** instead of widened. Both are now named, and they split:

  * **Substituting a stub for the artifact under test is a SURFACE.** The property being asserted may be old; the thing
    it is asserted against is new, so the test stops being evidence about the product. This is the
    `test_host_hooks.c:160-167` defect generalised: **a fixture that compiles its own library cannot notice the property
    leaving the product.** A stub is the same move at a smaller scale, and it arrives looking like a fixture.
  * **Narrowing a test's population is NOT a surface -- it is a SCOPE claim, and it must be printed with the test.** A
    test narrowed to the nineteen rows that pass is not a defect of the gate; it is a defect of the sentence that later
    quotes it as 47. **The rule is the one already in force for counts: never quote a number without its population**,
    now applied to tests, where the population is the fixture.

**Why the split is not cosmetic:** a stubbed test is a lie about the subject, and no population beside it can repair
that; a narrowed test is a true statement about a small subject, and a printed population repairs it completely. **One
is a surface and the other is a caption** -- and the campaign's own history says the caption is where the damage lands,
because `6,657` and `6,210` were both true and it was the sentence joining them that was false.

