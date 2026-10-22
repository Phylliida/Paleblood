# Pre-registered prediction: the first `BB_IMPORT_PERMISSIVE` boot

Written **before** the flag exists, because the most expensive errors in this campaign have all
been expectations recorded after the result. Recorded here so the run is scored, not narrated.

## The three requirements the stub carries

1. **Per-NID outcome, not a call count.** Each row is
   `nid, ordinal, calls, outcome ∈ {continued, faulted_at <addr>}`, joined from the fault report
   to the last NID called. A stub returning 0 followed by clean continuation is "nothing needed
   yet"; one whose return value the guest dereferences is "needed now, masked". Conflating them
   makes the log useless as a worklist.
2. **The stub path must be distinguishable in the status JSON**, never folded into
   `imports_implemented` — a counter that moves without its evidence is the defect this repo has
   already paid for.
3. **The direct-memory constant is derived from what the runtime backs**, with an assertion
   `direct_memory_size <= region_bytes` in code, so "do not promise what you cannot back" is a
   line that survives the next editor rather than a principle in a document. No round numbers.

## The prediction

* **Distinct NIDs named: 4..12.** The boot is at library index ~30 of 467 and has already passed
  its earliest imports; a PS4 eboot's early path is heap sizing, a few libkernel queries, then
  thread creation. I expect a single-digit count, and I expect `sceKernelGetDirectMemorySize` to
  be the first, since that is where it has already stopped.
* **First non-import wall: thread creation** (`scePthreadCreate` / the `scePthreadYield` path) or
  **file/device open** — in that order. If the log names fewer than 4 NIDs and stops, that is a
  finding about the guest's boot path, not a stub failure.
* **If the log names 200 or more**, the next three days are a stub campaign and the plan changes:
  the tier generator waits, and the runtime becomes the critical path. That outcome would also
  mean the boot has been reporting "437 remaining" as a count of the *table*, not of what the
  guest actually touches.

## Scoring rule

Score the run against these three lines in the same message that reports it, including the miss.
An expectation that moves after the result is not a prediction, and twelve slices of this campaign
are already sunk in that habit.

## Stub safety: three conditions, or the log is what crashes

1. **The catch-all is explicit in `boot.c`, never "last in the section".** `boot.c:273` binds the
   *first* matching `rt_syslib` entry, so a stub that must come last would rely on linker file
   order within a gathered section: a convention, not a guarantee, and it fails *silently* -- real
   implementations shadowed, every import reporting `continued`. So: after the walk, if the import
   is still unbound and `BB_IMPORT_PERMISSIVE` is set, bind the catch-all there. Ordering then
   stops mattering, which is the point.
2. **Flush per row.** The rows that matter most are the last ones and the fault the stub invites
   may take the host process with it; a buffered log loses exactly the NID that faulted. `fflush`
   after each row, or unbuffered.
3. **Cap calls per NID** (`BB_IMPORT_PERMISSIVE_MAX`, default small). A stubbed yield or spin
   returns 0 forever: one row per call, millions of rows, and no crash to end the run. Over the
   cap -> abort **with the row flushed**, which turns a hang into a finding.
4. **A terminal-status line in the same log**: `end: exit=N` / `end: fault 0x<addr>` /
   `end: max-calls nid=<nid>`. A log that stops at row N with no terminator is the ambiguity this
   campaign has spent three slices removing everywhere else -- it cannot distinguish "the guest
   ended", "the guest faulted" and "the instrumentation died" without a join across two artifacts.
5. **Run it twice and diff the logs.** If the NID sequence differs between runs, the order is not
   the guest's boot path and the worklist is a *sample*, not an ordering -- which decides whether
   any implementation plan may be built on it. One command, before any implementation work.

## Owed before the batch: `kind` beside the count

`imports_implemented` went 30 -> 31 when `_init_env` landed as a *documented no-op*, so the field
now reports 31 "implemented" of which 30 are behaviours and 1 is a decision that no behaviour is
needed. That is the counter-without-evidence defect in a new coat. The status JSON and every
burndown must print `implementations: N, declared no-ops: M` -- the split, never the sum.

## Validate the ordinal table before trusting it past index 1

Two free ground-truth points already witnessed by boot output: **ordinal 0 -> `bzQExy189ZI`**
(`_init_env`) and **ordinal 1 -> `8G2LB+A3rzg`** (`atexit`). The PLT stubs carry `push N` before
`jmp 0x2fbe4a8`, and the GOT slots are `0x57e4690` (ordinal 0) and `0x57e4698` (ordinal 1). If
those two do not match the loader's table, `push N` is not the index -- **PLT ordinals are often
per-library, not global**, and then `push 2` means libkernel's ordinal 2 rather than libc's third
import. Two points are enough to tell those apart and the data is already in hand.

## Predicted next stop after the five-thunk batch

**`0x400020`** -- the startup body inside eboot, a frame prologue with its own callees, not an
import. That is a different kind of stop (missing capability, not missing import) and it is the
*next phase*, not a regression. `0x400020` is excluded from the no-op batch by measurement.
