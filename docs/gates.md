# Gates: a check is proved by its failure, never by its green

Three times in this campaign a gate has been certified by watching it pass, and each time the pass
was produced by the gate doing nothing:

* `check_agnostic.py` printed nothing on success, so **a pass and a hang were the same sixty seconds**
  -- and it had stopped finishing (44,001 patterns over 24,370 lines, ~1.07e9 searches).
* `ctest -R tools --timeout 1` reported **"Passed 57.01 sec", rc=0**, because the CLI flag is the
  default for tests with no `TIMEOUT` property, not an override of one. The timeout I was certifying
  never fired, and the run that "proved" it was indistinguishable from the run that proved nothing.
* `promote.py` exits 0 while unable to work; `verify.py run` on an empty directory prints
  `no case files` and exits 0. Both were read as agreement until the directories were filled.

So the convention, repo-wide:

> **A check is not accepted as working until it has produced its failure on demand, and the failure
> output is recorded beside it. Green alone is never evidence that a gate works.**

Attempt the failure first; record the command, the output line and the count. For a check whose
failure mode is "never finishes", the recorded case is a deliberately lowered budget (`TIMEOUT 1` ->
`***Timeout 1.01 sec`, rc=8), not a long wait.

## Gates and their recorded failing cases

| gate | recorded failing case | where |
| --- | --- | --- |
| `check_agnostic.py` | scratch root with one tracked function name and one tracked address -> rc=1, 2 findings labelled | commit `f4128fa`; rerun `--root /tmp/agn` |
| ctest `TIMEOUT` | property lowered to 1 s -> `***Timeout 1.01 sec`, ctest rc=8 | commit `1fa3650`; the restored value is 300 s |
| `install_mode.csv` | drop one `game/hooks.csv` row -> `violations()` returns exactly 1 | `test/test_install_mode.py` |
| `check_pins.py` | first run found **3,012** stale source pins across five recorded->now pairs | commit `df5c420` |
| `validate_functions.py` (`review_pin_errors`) | empty current hash with no `unavailable` declaration -> error; pre-patch it was 0 | `test/test_review_pins.py` (counterfactual from the diff, not yet measured by revert) |
| `check_readable.py` | refused 2,978 magic numbers and 25 literal `8` widths of otherwise correct generated bodies | commits `df06177`, `2e218b6` |
| static guard mutant | `storage_bias 0x10 -> 0x08` -> 6 of 6 cases fail, diff names `+0x5ac59b0` | `game/frame_timing/static_guard.cpp` history |
| leaf family mutant | constant-returning body -> 1 passed, 1 failed (`ret.rax` differs) | case set `00_marker_a` / `01_marker_b` |
| `verify.py --canary` | perturbs the replacement and requires failure | `tools/verify.py --self-test` |
| `progress.py --check` | fails whenever README/STATUS are stale, which is the normal state after an edit | observed before `progress.py --update-readme` |

Two rows carry an honest weakness and say so: the `review_pin_errors` counterfactual is argued from
the diff rather than measured by reverting the patched code, and the `readable` refusals are recorded
by their commit message rather than by a test that reproduces them.

## The other half of the same lesson

A gate whose cost grows with the population it reads becomes unable rather than red. Three instances,
all found only after the population grew: a resolver re-parsing ~15,773 rows once per ledger row
(8 m 27.411 -> 1.993 s), a defining-file walk at 44.6 ms per row, and the 1.07e9 searches above. The
mitigations now in the tree are a per-test `TIMEOUT` and `tools/stacks.py` armed at import, so the
next one prints its own frame instead of being discovered by a slice that noticed a silence.
