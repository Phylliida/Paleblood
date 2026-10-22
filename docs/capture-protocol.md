# The first capture: where it lands, and the four outcomes written down before the run

*Written before any hook has fired. The order of the file is the point.*

## Where a capture goes

**Not `build-release/`.** A rebuild deletes it, and this is the campaign's first in-game evidence — the same
reason the faulting binary went to `build-release/kept/<sha256>` instead of being left where the build put
it. **Evidence whose location is a build directory is evidence with an expiry date.**

- Path: **`../data/captures/<address>-<sha256 of the run log>.json`**, beside the cases, outside the checkout,
  so `ninja clean` cannot reach it.
- The run prints that path in its own output, so the reader does not have to guess which log belongs to it.
- The JSON carries: the identity line (`pbboot` sha256), the captured entry PC, the GPRs, the buffers with
  their `size_assumed` regions and `POISON` padding, the post-hook stop, and the catalogued function name
  and size it was read from.
- It carries **no guest bytes**, so committing it is safe; the bytes stay in `../data/cases`, which is
  already outside the tree by design.

## The four outcomes, and what each means — pre-registered

1. **Capture, and replay passes.** First `runtime-witnessed` row that is also evidence. **It is one input,
   one sample, and it does not move `verified`** — a hook firing is a witness, not a comparison, and now
   there is one comparison on one sample. Say both sentences or the number is a lie.
2. **Capture, and replay differs.** **The body is wrong on a real input**, and the differential did its job.
   Not a failure of the slice: this is arguably the most valuable outcome available, because it is the first
   time the in-game input and the authored case disagree, and the disagreement names which one is wrong.
3. **Capture, and replay refuses** — `uncovered`, an out-of-object pointer, or a region the harness cannot
   express. **A limit of the oracle, recorded as such.** It does not say the body is right or wrong; it says
   this input is outside what the harness can express, and the fix is a case-schema question, not a code
   question.
4. **No capture — `hook installed, never fired`.** **The graph claim is wrong.** Print
   `N installed 1 of 1, never fired, guest reached <stop>`. Depth 2 came from `edges.csv`, and there are
   **164,953 unresolved indirect edges**, so execution taking an unmodelled path is a finding about the
   graph and not a failed slice. **The number that matters is how far the guest got.**

**A run with one expected outcome gets read as confirming it.** All four are written here first, each with
the sentence that must accompany it, so that whatever happens the record carries its own interpretation
rather than mine afterwards.

## Corrections, appended before the run — both supersede text above

**(1) The capture must contain the bytes, at call time.** The bullet above says the JSON carries *no guest
bytes* and the two sentences that followed ("committing it is safe; the bytes stay in `../data/cases`") read
as if the replay could materialise a region from `eboot.elf` at `addr − 0x400000`. **It cannot.** A buffer's
content at *load* time is not its content at *call* time — the guest has run thousands of instructions by
then — so a replay that reads the file gives the differential **two bodies compared over an input the game
never had**, which is exactly the fabricated-preset failure the emitter's rules exist to prevent. **Capture
the bytes at the hook.** The copyright concern that motivated "no guest bytes" does not reach here:
`../data/captures/` is outside the checkout and uncommitted, which is the same solution as the path itself.
So: `bytes` is a required field of every captured buffer, and a capture missing it is not a capture.

**(2) The file name is not derived from the log.** `<address>-<sha256 of the run log>.json` is circular —
the log prints the capture path, so the log's hash depends on the path, which depends on the hash. **A
self-referential key resolves as "whichever order the code happened to run", which is a measurement that
cannot be re-derived.** The name is **`<address>-<pbboot sha256[:12]>-<run counter>.json`**, all three known
before the file is written; the counter distinguishes runs of one binary. The **log sha256 is recorded inside
the JSON as an ordinary field** once the log is complete, where it is derived from the event rather than
naming it.

Both were cheap to fix now and expensive after the first capture exists, because **the first capture is the
format everything else copies.**
