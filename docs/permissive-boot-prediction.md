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
