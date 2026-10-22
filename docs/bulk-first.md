# Bulk first, hand later: the decision, its authority, and the one open term

## Authority

The user's own words: *"I don't mind doing them bulk first as long as we eventually go back and
do them by hand tbh, if that is faster."*

That is a decision, not an open question. It fixes the order (bulk-derived bodies now, hand pass
later) and leaves one condition to be measured: *if that is faster*. It has been measured:
**~3.2 h of machine verification for the whole 7,791-entry tier against a hand-authoring floor of
1,169 h** (2,597 h at 20 min/function; see docs/large-tier-pricing.md). The condition is met by a
factor of 360.

So the generator proceeds. It does not wait for a further ruling, and asking for one is stricter
than the standard the user set.

## What is still genuinely open, and is NOT covered by that answer

**A delegating trampoline.** A body that calls the original satisfies the differential trivially
and can never satisfy any reading of "decompiled". It is excluded here, in writing, before any
generator exists: no generated body may call, jump to, or otherwise delegate to the original
instruction stream at run time. The generator emits a reimplementation or it emits nothing.

## Why the order is safe under either eventual reading

Every generated row carries `replacement_origin: generated`, the burndown prints hand/generated
split, and the second-pass queue is ordered by reachability rather than address. If the eventual
hand pass never happens, nothing is misrepresented: 7,791 rows say `generated`. If it does, it
starts from a scaffold with per-block coverage and a differential already gating every member.
Not building is the only branch that loses work either way.

## Work that pays under either answer, carried in the same window

Interleaved with the generator, never queued behind it -- these move `verified`, which no
generator can:

1. the 490 computable NIDs bound, and the boot stop re-derived: the verified rung is gated by
   the boot, not by the tier;
2. the recorder caller in `runtime/hooks.c` (no capture can happen at all today);
3. `test_blocks.py` / `test_descent.py` -- three tools emit tier-level verdicts with no test;
4. pin identity (generator + template + parameters, one deliberate tree-wide change);
5. the ledger's O(N) `record()` over 21,229 rows -- same species as the 507 s resolver.
