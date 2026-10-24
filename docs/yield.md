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

What "refusal surface" means here, so the target cannot be graded generously later: a new place where the tree says
no and did not before -- a new `SystemExit`/`refuse` path, a new required flag, a new guard with a failing input, or
a new column whose absence is refused. Tests *of* an existing surface are not a new surface; docstrings are not a
surface; a fix that makes a verification stop crashing is not a surface (it is a repair of an instrument with its
own defect).

If the stretch misses, the honest reading is the one this doc was written to permit: the tree is being made
unmakeable faster than it is being used, and that is worth knowing at the next boundary rather than at commit 140.
