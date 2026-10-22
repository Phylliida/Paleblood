# Case design: a case that cannot observe its own input asserts the harness

*Written after 117 of 118 mutants survived a family that was already "green". Every family after
this one inherits these rules.*

## The sentence

**A case that cannot observe its own input is a case that asserts the harness, not the body.**

The 765-member `mov eax,[rdi+K];ret` family passed **765 of 765** differential cases on the first
run. It was also wrong: the marker was written into `buffers[buf0].bytes`, which the harness copies
to **buffer offset 0**, while every body reads at **K**. Original and replacement both read the
zero-filled tail, both returned `0`, and the differential agreed — about nothing. The mutant pass
found it: **117 of 118 survivors.** After moving the marker to the displacement the body reads,
**118 of 118 mutants died and the restored control was 765 of 765 green.**

**A mutant pass is what makes a case set observable. It is not optional decoration, and a family
that has not survived one has not been tested.**

## Three rules this family paid for

1. **Put the input where the body reads it.** `memory` presets address `buf:<name>+<offset>`, so
   the marker goes at `K` and costs 8 hex bytes.
2. **Never pad `bytes` to reach an offset.** Doing so produced 2,295 case files totalling **503 MB**.
   `buffers[name].size` is first-class and `bytes` is optional (`harness.py:342`, `:345`, `:350`):
   allocate by size, then write the preset.
3. **Every case document needs `address`.** Without it the run refuses with a lone
   `verify:` line — `… is for None, not 0x0042b2b0` — which is a precondition refusal (rc=3),
   not a body defect.

## The buffer comparator compares raw bytes — proved by reading, before the family that needs it

Families whose correctness lives in a *store* (the value written through a pointer) run through
the buffer comparator rather than the return comparator, and the return comparator had a
display-format defect that cost 797 false failures. The buffer path does not share it:

- `snapshot()` (`harness.py:648`) captures raw bytes with `ctypes.string_at` for the writable
  segments and for every declared buffer — no reformatting.
- `byte_diffs()` (`harness.py:218`) compares at C level and returns the **raw new bytes**.
- `run()` records each diff as `{'addr': self.describe(start + offset), 'bytes': data.hex()}`
  (`harness.py:722`): the **value is raw bytes**, and only the *address label* goes through
  `describe()` — the same label on both sides of a comparison.

So a guest-space address stored into a buffer compares byte-for-byte, with no host→guest
remapping. **The first `lea add; mov [rdi],rax` case must still prove it by passing** — the read
licenses the family, the pass is its evidence.

## What each family's cases must carry

- an input at the displacement the body actually reads;
- a declared buffer for anything dereferenced, or `snapshot()` cannot see it;
- mutant coverage per **distinct constant**, one representative each, restored by regeneration;
- a mismatch assertion on the **value**, never merely a nonzero exit — a zero-filled tail makes a
  wrong constant look clean.
