# Next targets

Two tracks. Sessions alternate between them (decompilation, then runtime, then decompilation,
...) unless the maintainer says otherwise; `Last session` below records which one ran last.
One line per target, in order; move a target to "Done" with its commit when it is finished.
Decisions and blockers go to STATUS.md instead of being worked around.

Last session: runtime

## The two-tier question, answered from the checker (2026-10-21)

Hand-written readable C++ is right for functions that carry meaning and cannot be the standard
for 157,757, but the readability gate does **not** force a second tier: `check_readable.py`
forbids calls by address, numeric offset accessors (`get<T>(p, N)`, `ptr_at(p, N)`, `p[0x..]`),
recording code, SSE outside `game/engine/`, and numeric literals other than 0/1 outside a
named-constant declaration (`constexpr`/`const`/`enum`/`static_assert`/`alignas`/`RT_ORIGINAL`/
`RT_GLOBAL`). Generated code satisfies all of that mechanically by emitting per-member `constexpr`
declarations and a named wrapper -- measured, not argued: the 27 added lines in
`game/frame_timing/static_guard.cpp` pass at rc=0 with no allowlist entry. So: **one tier, one
gate**, and the allowlist stays empty. The open risk is specific to the decompiler path, whose raw
Ghidra C carries hex literals inside expressions; if it is used at scale it needs a generated
constant-naming pass, and that decision is made at n=3 in the probe, not at 44,331.

Third argument for generation over storage, recorded: **generated cases cannot go missing**, so the
whole `cases_sha256 = unavailable` class (42 functions today) is impossible by construction under
the factory and permanent under the store.

## screen_easy's missing input (one command, not yet run)

`tools/screen_easy.py` consumes a `function_catalog.py export` JSON that `data/exports/` does not
have. The export wants local SQLite state, which exists (`../data/catalog.sqlite3`, the same one
`differential.py` uses):

    tools/function_catalog.py --state ../data/catalog.sqlite3 export ../data/exports/function_catalog.json

Then `screen_easy.py ../data/exports/function_catalog.json --min 14 --max 100 --self-contained`.
Run it after the probe: it turns the documented 35,986-row prescreened pool (19,076 at complexity
1) from a claim in a doc into a list the next fifty families can come from.

## Evidence that cannot be re-run (measured 2026-10-21)

142 of 727 ledger rows carry `cases_sha256 = unavailable` (82 edge, 7 option-recorded, 53
recorded): the row asserts a comparison whose inputs are not in the tree. They cannot be
re-recorded and cannot be re-checked, so their source pins are asymmetric in a way that matters:
a source edit stales them permanently. Three of them are stale today --
`frame_timing_mutex_lock`, `frame_timing_mutex_unlock`, `frame_timing_thread_self`, all recorded
2026-10-12 against `game/frame_timing/thread.cpp` -- because that file changed since (storage-base
correction), and there are no case directories for `0x0111acd0`, `0x0111acf0`, `0x0111a8a0` under
`../data/cases/`. Repairing them means authoring cases for the current implementation, not running
anything. Do not "fix" them by re-recording: `verify.py` would refuse with no cases, and a
hand-written ledger row would assert a comparison nobody made.

`verification.source_hash` hashes the defining file **plus every header it includes transitively**
from `game/` and `runtime/include/`, so every member of a family that shares one file carries the
identical pin (measured: all 1,117 static-guard members hash `game/frame_timing/static_guard.cpp` +
`runtime/include/runtime/guest.h`). The pin is therefore safe-but-over-broad: appending 3 wrappers
staled exactly 3 pins, each repaired by one `verify.py run --record edge` (~1 s of machine time, no
review event, since none of them is approved). At 1,117 members one edit to that file costs 1,117
re-records, about six minutes of machine time -- affordable, and the reason the shared file is the
right call for now. If the pin ever needs to be per-member identity, the honest substitute for
generated code is generator version + template + member parameters, with the file hash kept as a
check; that is a ledger scheme change and must be done as one deliberate migration, not piecemeal.

## The provenance decision (answered 2026-10-20, not yet implemented)

Asked and answered: `verified` keeps its meaning (recorded from the running game) and a third rung
is added for a traced differential. **Build one gate, not two pipelines**: `differential_runs`
already stamps `capture_provenance` (`synthetic_or_edge` today); extend that to a declared field
inside the capture content with values `game_recorded` / `traced_differential` /
`synthetic_or_edge`, and make `promote.py`'s requirement "two non-empty sets whose declared
provenances differ". That single rule serves both tracks and closes the two-copies-of-one-set hole
at the level of content rather than of path. In order, one slice at a time:

1. Provenance field + promote gate + `progress.py` counting the new rung separately + README and
   STATUS. Bounded; no harness identity change if `tools/harness.py` is untouched. **`promote.py`
   must stop exiting 0 when it can do nothing** (today: `no capture library at ...; nothing to do`
   returns 0, so CI sees green on a tool that ran nothing); "cannot act" is non-zero unless
   `--nothing-to-do-ok` is passed.
2. **The loop test — highest value on the board and available today.** Run the recorder under
   `capture_poc_replay`, dump a capture, feed it through `promote.py` in a throwaway worktree, and
   assert acceptance at the new rung. This proves the running-game path's endpoint before the game
   runs: if `recorder.hpp`'s output disagrees with what `promote.py` wants, that is found now and
   not after the boot clears.
3. **Recorder caller in `runtime/hooks.c`.** `rt_capture_begin` / `rt_capture_write` exist with no
   caller outside tests; the hook boundary is the caller. Before item 4: an affinity constant with
   no recorder yields no captures however far the boot gets.
4. `scePthreadAttrGetaffinity` = `0x3F`, with the citation and the which-cores residual in the
   comment, recorded as a decision in `symbols/boot_history.csv`.

Expectation to state rather than predict: `symbols/boot_history.csv` has four rows, `milestone`
`loaded`, `milestone_index` **0 of 8**, and the same `stops_at`
(`libc.elf->libkernel:scePthreadAttrGetaffinity`, `libc.elf+0x81ad5`) since 2026-10-07. Clearing
that site does not buy 21 -> 30 replacements; it buys one learned stop. **The deliverable is where
it stops next, not a promotion count.**

Needs the maintainer (cannot be done from the sandbox):
- Pushing. The sandbox has no credentials and `gh` stays unauthenticated, so nothing here can
  push; the maintainer pushes `main` periodically (as of `c25c9c3`, `origin/main` matches `main`).
  So: fetch at the top of a slice and end each one with `main` committable, and treat a slice as
  durable only when `git rev-list --count origin/main..main` reads 0. `../Paleblood-2026-10-19.bundle`
  (`git bundle --all`) is the fallback export and goes stale between pushes.
- The affinity constant in target 2 below: **answered -- `0x3F`.** The count has a source outside
  the tree (Digital Foundry, July 2013: "six of the eight AMD CPU cores are available to
  developers ... Both consoles allocate two Jaguar CPU cores to the operating system"), which
  sources *six*, not *which six*; `0x3F` assumes the OS takes the top two. Both sentences go in the
  comment, and the choice goes into `symbols/boot_history.csv` as a decision. This supersedes the
  earlier `RT_SYSLIB_UNRESOLVED` lean. Not urgent: without a recorder in the runtime, clearing this
  site yields no captures even if the boot advances.
- What `verified` means for a function whose captures are not in the checkout: **answered, both
  ways.** `verified` keeps meaning recorded from the running game, and a named third rung --
  `differential-verified`, counted separately in `progress.py` and the README -- holds a
  canary-backed traced differential with pinned cases. Widening the existing word would put 21
  recorded rows and 528 traced rows under one label with two evidentiary bases, which is the failure
  the ledger exists to expose. The work is queued in "The provenance decision" below.
- Independent review of the 528 `engine_zero_init_*` functions (`symbols/reviews.csv`). They carry
  no approved row, so `tools/promote.py` cannot move them; the nine reviewed `frame_timing_*`
  functions are the ones to prove that path on first. The packet to read is
  `../data/review/engine_zero_init_review.md`, written by `tools/make_review_packet.py`: the
  disassembly, the computed byte-identity of all 528 members, the traced differential verdicts, the
  case pin, the two weaknesses, and the freshness of every run against the tools in the tree
  (528 of 528 current). An approval now has to name what it approved: the row carries
  `source_hash` and `cases_sha256`, and `tools/validate_functions.py --review-row NAME` prints one
  ready to paste with both computed. Editing the replacement or the cases afterwards makes the
  approval stale rather than grandfathered, so a review of code that then changes is visible
  instead of absorbed. Regenerate the packet under the venv (`capstone` is imported) with
  `--caveat`, because `tools/` is inside `check_agnostic.py`'s scope and a family name written
  into the tool turns that gate red. The committed packet was produced by exactly this line, and
  the caveat text is literal for that reason -- without the flag its paragraph disappears at
  exit status 0 and nothing in the packet notices:

      ../.venvs/paleblood/bin/python3 -P tools/make_review_packet.py \
        --out ../data/review/engine_zero_init_review.md \
        --caveat 'One instance in this tree: `period_zero` of `engine_time_over_period` (unsigned divide by a period of zero, `signal 8` on both sides), declared in `game/engine/time_over_period_cases.py` so the case file says what it expects.'

  The caveat above is one line of shell (it is only wrapped here for fit); pasted as three lines
  with embedded newlines it would render differently and stop matching the committed packet.

  Refreshing the runs is the other half, one invocation per member, and it needs `--state` named
  explicitly: the default path lives under `$HOME`, which is read-only here, so an omitted flag
  refuses every worker before it opens the database (`catalog unavailable: ... Read-only file
  system`) rather than refreshing anything:

      tools/differential.py --state ../data/catalog.sqlite3 differential ADDRESS \
        --cases ../data/cases/zero_init/ADDRESS --function NAME \
        --elf ../data/bb/elf/eboot.elf --lib build/game/libbbgame.so --trace-instructions

  Run one member before fanning out. A batch of 528 successes and a batch of 528 refusals cost the
  same wall time, and the message is the only thing that tells them apart. `--resume` reuses
  completed sides under the same evidence key, so it does nothing in the slice that changed an
  identity file -- which is the only slice that needs a refresh. `differential_runs` appends (~3
  rows per address), so the evidence that a refresh happened is a `created_at` that advanced on
  528 distinct addresses, not a fan-out's exit status.
- Twelve cases among the already-verified families cannot fail against a dropped body, and the
  reason is in their inputs rather than in the comparison. Eight are `slot_copy` (`overlap_dest_
  below_source` in `0085c8e0`, `028cd370`, `02c1b760`, `02c1cd10`, `02f01ed0`; `overlap_dest_
  above_source` in `0085c8b0`, `02113c30`, `028cd340`): each copy is an identity map, `dest -
  source` equalling the intra-copy stride, so every store lands on the address it just read and a
  snapshot diff sees nothing. Four are `crc32` (`range_empty_from_zero`, `range_empty_from_
  garbage`, `range_all_zero_byte`, `byte_zero_byte_zero`): the first two contract to write nothing,
  so a body that writes nothing satisfies them, and the second two start from state 0 with zero
  data, which is a fixed point of the table at `0x04cdcf50` since its first entry is `0x00000000`
  -- the correct result equals the input and a same-value store is invisible to a before/after
  snapshot. Three of `crc32`'s four are now closed and the fourth is documented: `range_all_zero_
  byte` is kept as the identity property it is (it catches a body that writes the wrong value) and
  `range_zero_data_set_state` sits beside it with a seed that is not a fixed point, which the
  dropped-body mutant does catch; `byte_zero_byte_zero` cannot be made sensitive without ceasing to
  be the identity, so the reason is written into `game/engine/crc32_cases.py` instead of being
  silently omitted. Both `range_empty_*` stay correctly insensitive -- their contract is to write
  nothing. `test/capture_recorder_replay.py` now authors the edge half of a promotion the way such
  a case is actually written (a recorded input moved somewhere the recording never went), and
  mutation showed the guard that catches a perturbed-to-identical copy is the executed result, not
  `promote.duplicate_sets` -- which compares file contents and would accept a copy that also renamed
  its id. Remaining: the eight `slot_copy` identity maps, where the fix is poisoned destinations
  (nonzero payload, destination pre-filled with a value no copy would produce); no expectation is
  rewritten, because a case is input only. That is the same machinery a real edge set needs.

- Accepted, not fixed: `tools/harness.py:766` labels every unclassified exception `instruction
  tracing failed: {error}`, which is a false name for most of them -- the tracing branch is one
  `except` among many reasons a case can fail. The whole fix is the literal replacement

      result, code = {'bad_input': f'harness failed in the case: {type(error).__name__}: {error}'}, 3

  and it is deliberately not applied. `harness.py` is one of the five identity files, so a one-line
  message change stales all 528 catalog runs and needs the refresh plus a packet regeneration in the
  same commit; no test pins this string, so nothing currently reads the label and nothing is blocked
  by it. Recorded as a fix anyone may apply while they are already refreshing the catalog for another
  reason, not as work owed.

## Runtime track

How far the executable boots on our own runtime (`runtime/boot.c`, `tools/boot.py`): the boot
stops at the first system import we don't implement yet and names it. Each target implements
what the boot stops at, clean room (CONTRIBUTING.md), then re-runs `tools/boot.py`.

1. Generic input capture in the runtime: record a hooked function's inputs (arguments, the
   memory it reads, its calls' results) from the runtime side, with no code in the function
   (STYLE.md forbids recording code under `game/`). This replaces the per-function recorders that
   `tools/check_readable.py` found inline and the readability commits removed -- 21 commits, e.g.
   e5d65ea dropped `rt_capture_begin`/`rt_capture_write` from
   `game/frame_timing/monotonic_clock.cpp:55,64` (`git log -S rt_capture_begin -- game/`). In-game
   recordings resume once the runtime runs the game, and `tools/promote.py` can then move
   `edge-verified` functions to `verified`. That hook is the host interface's code-patch
   installer (`tools/harness.py:622-627`, a no-op because the harness has nothing to install); it
   is not, and was never, a way for a case to change state mid-run. Per-call writes already exist
   and are read on both scripted paths: `imports[].writes` at `:478` (raw bytes, with a `size`
   cross-check) and `stubs[].writes` at `:511` (`bytes`, `pointer` or `guest`), each applied after
   the call is served, resolved through `check_memory(write=True)` so it is traced, and recorded as
   `import_write` or `stub_write`. Stubs are installed by writing a jump at the guest address on
   both sides (`:313-327`, up to `STUB_SLOTS` 64), so a case can script any address, including the
   eboot's own thunk at `0x02fbfe68`, which both the original's call and the replacement's
   `RT_ORIGINAL(... kernel_usleep ...)` reach. That gap is closed (`3654028`): a write may carry
   a `target` (`{"target": "buf:state+0x10", "bytes": "..."}`) resolved through `self.value()`.
   Until then the write target was always `args[arg] + offset`, so a stub taking no pointer
   argument could not name the address it should change. A register is refused as a target on
   purpose: which register holds a pointer is the compiler's choice. The cost named here was paid
   in that commit (all 528 catalog runs refreshed, packet regenerated, `harness_sha256` 0 of 528
   stale).
2. `scePthreadAttrGetaffinity` (libkernel), called by the game's own libc while it starts: needs
   the main thread's CPU affinity mask on a PS4 (STATUS.md, "Open questions"). Then the next
   import `tools/boot.py` names.
3. Module loading at run time: when the game asks to load a module listed with action `stub` in
   `game/modules.csv`, report it loaded without mapping it.

Roadmap after the boot gets going: kernel, threads and memory; files; input; audio; video
out; GNM and shaders (the largest). Claimable work per system call group is in the issues
labelled `runtime`.

## Decompilation track

### The export turn: what the call graph can and cannot tell us (measured 2026-10-20)

`data/exports/metrics.csv` and `edges.csv` (81 MB, dated Oct 12) have never been joined to the
catalog. They describe the same bytes, and two of their columns carry no signal at all.

**Identity holds.** `metrics.csv` has exactly the catalog's 157,757 addresses, one row each, all
`Ghidra ExportFunctionAnalysis/1`, all `analysis_complete=true`. Sizes agree with Capstone on all
five controls (`0x00400020` 102, `0x024bdd40` 36, `0x02f714d0` 126, `0x004632d0` 67, `0x01652440` 126).
Of 500 randomly sampled `direct` edges, **489 decode to exactly the reported callee (97.8%)**; all
eleven misses are import-thunk resolution -- the encoded target sits in the `0x2fbe5xx`-`0x2fbfxxx`
PLT region and Ghidra reports the function it believes the stub stands for (e.g. call at
`0x024bdd55` encodes `0x2fbfe68` which `jmp`s through the GOT; Ghidra says `0x0248bac0`). So
`edges.csv` is a **thunk-resolved graph, not an encoding dump**: 2.2% of edges cannot be checked
against bytes by construction, and any join inherits that.

**`boundary_confidence` is a constant, and so is `fixture_difficulty`.** Every one of 157,757 rows
says `boundary_confidence = "ghidra-function-body"` and `fixture_difficulty = "unknown"`. The column
named confidence carries no confidence. So the boundary question was answered by decoding instead,
on every entry, with two independent tests -- does the body decode to exactly its declared size, and
does the last instruction transfer control:

| decodes | ending        | callers    | count  | %     |
|---------|---------------|------------|--------|-------|
| yes     | terminates    | callerless | 113790 | 72.13 |
| yes     | terminates    | called     |  27902 | 17.69 |
| no      | falls through | called     |   4889 |  3.10 |
| no      | falls through | callerless |   3329 |  2.11 |
| yes     | falls through | called     |   2599 |  1.65 |
| yes     | falls through | callerless |   1960 |  1.24 |
| no      | terminates    | called     |   1726 |  1.09 |
| no      | terminates    | callerless |   1562 |  0.99 |

**89.8% pass both tests; 10.2% (16,065) fail at least one; 5.2% (8,218) fail both** and are the
suspected non-function set. So 157,757 is not a number about the program: it is Ghidra's partition,
plausibly about 150,000 real functions plus a tail of fragments and data that could be five to ten
percent. Any report saying "157,757 functions" must carry that.

**Reachability is blocked, and the blocker is named.** 164,953 of 608,251 edges (27%) are
`unresolved_indirect`. Code pointers in the file's data are absent by design: of 398,183 eight-byte
values in the RW segment, 319,662 are zero, 27,021 are small integers, and **exactly one** points at
a catalogued function; the init array at guest `0x57e5b38` is zeros. This image is relocated at
load through the proprietary `PT_SCE_RELA` segment (`p_type 0x61000000`, `p_filesz 0x569d78` at
file offset `0x53e9b40`), which nothing in this tree parses. Three candidate numbers, none of them a
measurement of what executes: 842 reachable from the ELF entry (0.5%), 3,225 from the best single
node, and a 37.6% union over callerless nodes -- and a node with 1,051 out-edges reaches only 94
functions, so the graph is a shallow skeleton rather than an execution structure. Parsing
`PT_SCE_RELA` to recover code-pointer roots is a bounded piece of work and it is the prerequisite
for any reachability claim; until then the in-game track cannot be bounded from below or above.

**The number that does survive, and it inverts the reason to want it: 120,641 functions (76.5%) have
no in-catalog direct caller.** For three quarters of the catalog no static call-graph argument can
establish that a function executes -- only running the game, or a traced differential, can. So
capture is not a fallback for a minority; it is the only witness class for most of the tree. The
converse is equally true and equally invisible: a function that never runs produces no evidence, so
"not observed" is not "not executed". Both are unresolvable without the relocation roots.


### The decompiler runs headless, and it is not the bottleneck (measured 2026-10-20)

`tools/ghidra/Decompile.java` drives the analyzed project through the existing shim:

    ./data/bin/analyzeHeadless data/ghidra-proj bb -process eboot.elf -noanalysis -readOnly \
        -scriptPath Paleblood/tools/ghidra -postScript Decompile.java OUT.c [LIMIT] [TIMEOUT_MS] [STRIDE]

199 of 200 functions decompiled on the first bounded run, and the output corroborates the
Capstone reading of the same bytes: `FUN_00400020 size=102` is the `.init_array` walker over
`0x57e3bb8..0x57e5b38`, which the census had identified from disassembly alone. Cost, from a
stride-400 sample (395 functions spanning the whole address range, median per size class):

| size      | median ms | catalog n | bytes  |
|-----------|-----------|-----------|--------|
| <=16      | 2         | 44,331    | 0.7%   |
| 17-64     | 4         | 30,291    | 2.8%   |
| 65-256    | 11        | 46,179    | 15.8%  |
| 257-1024  | 33        | 29,165    | 33.5%  |
| >1024     | 233       | 7,791     | 47.2%  |

**The whole catalog is about 11.5 h of machine time, single-threaded, in the background** — 7 ms
median per function, with 3.3% of functions over 1 s consuming 80% of the total (`0x0112db00`,
56 bytes, took 35.8 s: a decompiler pathology on a small function, not a size effect). So
decompilation costs nothing against translation, case generation and verification, and it can be
run once over everything rather than per family. The output is raw Ghidra C -- `undefined8`
everywhere, arguments as `in_RDI` -- so it is the input to a translation pass, not a result.


Readability burn-down first (STYLE.md; CONTRIBUTING.md, "Definition of done"): refactor each
file in `tools/readable_allowlist.txt`, re-verify every recorded and edge case, get the
independent review, remove its line. Order: `game/ai/hk_ai_frame_update.cpp`, then the others
from the smallest up. New functions go to `main` only verified and readable.

1. The live functions the 60 FPS patches edit besides frame timing (47 live, 12 dead:
   `tools/patch_overlap.py ... --map`, `tools/reloc_refs.py`, `tools/refs_to.sh`). Done so far:
   the nine fixed-step state methods (Chalice Dungeon state machine; replaced, verified on edge
   cases stock and against "60 FPS++", waiting for a save that reaches the Chalice Dungeons).
   Still to do among those called in the clinic (probe run 2026-10-06, `continue.route`):
   `0x0183ac60` (20 KB; every frame-rate patch changes a jump and a flag) and `0x02713870`
   (11.6 KB; its only edit, Uncap FPS++'s, is broken in v1.09: QUIRKS.md). Each option part is
   checked against the patch that edits it (both sides patched, VERIFY.md).

## Done

- Runtime: libkernel `sceKernelGetProcParam`, `_sceKernelRtldSetApplicationHeapAPI`, the mutex and mutex attribute functions (SCE and POSIX names), `scePthreadSelf` and thread attributes (init, destroy, get).
- Runtime: the game's own libc and libSceFios2 modules are mapped as guest code (`game/modules.csv`) and the executable's imports they export are bound to them; their functions are tracked in `symbols/module_functions.csv`, replaceable later like game functions.
- Runtime: our own loader (`runtime/loader.c`) and boot harness (`runtime/boot.c`, `tools/boot.py`); the verification harness maps the executable with the loader.
- Review pins: the evidence hash is taken in the ledger's canonical order (`CASE_SETS` rank, then option) rather than in file order, so rewriting `symbols/verification.csv` cannot stale an approval that approved the same evidence. Measured before and after: all 30 stored pins still match, and the ledger has no function with two rows of the same set and option, so the order is total and the sort reorders nothing today. `test_the_evidence_hash_does_not_depend_on_how_the_ledger_was_written` writes the same three rows in a different order and asserts one hash, then changes one pin and asserts it moves. Also in this commit: the `differential.py` refresh invocation recorded in the target section (it existed only in commit messages, and omitting `--state` refuses all 528 workers), `docs/addressing.md` corrected to say the zero-fill is the anonymous mapping's guarantee with the loader storing only `filesz` rather than "data the loader writes as zero", and the `-P` / `PYTHONPATH` traps in `docs/ONBOARDING.md` -- which cost a red `validate_functions` in this very slice before the sentence existed (`ModuleNotFoundError: verification`, exit 1, which reads like a mismatch).
- Harness: a scripted write can name the memory it lands in (`target`, `3654028`), so a function that changes state it receives no pointer to is scriptable; the `size` cross-check now runs on stub writes as well as imports. Both are tested (`test_a_truncated_*_write_is_reported`); the stub test is red against `5ee1b4a` and the import test is green there, which is the asymmetry the shared helper closed.
- `0x024bdd40` kernel_wait_for_state_024bdd40: edge-verified, 13 cases, `game/hooks.csv` registration and a ledger row (`edge`, source `08865e57204289d9`, cases `774469f32dc3ad9b`). The cases are in `data/cases/wait_for_state`, generated by `game/kernel/wait_for_state_cases.py`. The state word lives in a case *buffer*: an earlier draft pointed the function at a spare spot in the image and wrote there through a register, which cannot work because a scripted write must land in memory the guest may write and the image's first segment is read+execute. `memory` presets reach that segment (a preset is the layout, not an access) but a write during a call does not, so the draft would have failed whatever the format. Checked red first: `ready_state = 3` fails 13/13, and `poll_interval_us = 999` fails 11/13 -- the two that pass are the zero-poll cases, which never call the sleep, so recording the delay argument (`argc: 1`) is load-bearing rather than decorative.
  `data/cases/wait/` is the superseded draft and is left on disk rather than deleted: every case in it writes into the read+execute segment, so it fails on the first poll and cannot be fixed without becoming the new set.

- `0x0138a370` frame_timing_task_dispatch_0138a370: verified (the task dispatcher; 51 recorded frames with 76 registered tasks each). With it the task manager's frame is done: `0x024512a0`, `0x01388c60`, `0x01388c70`, `0x0143e490`, `0x014400a0`, `0x0143f9f0`.
- `0x0143e490` frame_timing_task_flush_queue_0143e490 and `0x014400a0` frame_timing_task_workers_step_014400a0: verified (200 and 53 recorded calls; the list re-read after each task cannot be made observable with stubs).
- `0x024512a0` frame_timing_task_frame_024512a0 and `0x01388c70` frame_timing_task_run_01388c70: verified (51 recorded calls each; the singleton re-read after the fatal error is not scripted in the cases as recorded -- a `target` can now set that global (`3654028`), but adding it changes the case files, which moves `cases_sha256` and needs a new review).
- `0x01388c60` frame_timing_task_run_all_01388c60 and `0x0143f9f0` frame_timing_task_set_frame_value_0143f9f0: verified (task manager's frame; 51 recorded calls each).
- `0x0111a7f0` frame_timing_get_monotonic_ms: verified (1a7c39e).
- `0x02434770` frame_timing_pace_frame: faithful replacement verified; `BB_TARGET_FPS` and `BB_LIMITER_WAIT` options.
- `0x02418d20` frame_timing_frame_step: verified (first function with virtual calls).
- `0x02434520` frame_timing_flipper_init: verified.
- `0x013d3520` frame_timing_task_013d3520: verified (stock and against Uncap FPS++).
- `0x01c0c2b0` physics_instance_construct_01c0c2b0: verified (physics instance constructor; stock and 30/60/Uncap FPS++, 19 constructions recorded while the clinic loads; the motion rescale, listeners and root update run only outside the physics manager's special modes and are covered by edge cases).
- `0x0222bc10` ai_hk_frame_update_0222bc10: verified (Havok AI manager; stock and 30/60/Uncap FPS++, 51 recorded frames; the debug display, axis frames, boxes and the manager-wide draw do not run in the clinic and are covered by edge cases).
- `0x01cbdb20` character_frame_update_01cbdb20: verified (stock and 30/60/Uncap FPS++, 57 recorded calls; the name-string block does not run in the clinic and is covered by edge cases).
- `0x025b2fb0` render_swap_chain_present: verified (GXSwapChainCtrl; stock and 30/60/Uncap FPS++, 51 recorded frames; in the clinic it presents with interval 1 without waiting).
- `0x00fbc3e0` render_yebis_get_recursive_sample_parameters: verified (YEBIS middleware; stock and 30/60/Uncap FPS++, 54 recorded calls).
- `0x02377bd0` render_frame_update_02377bd0: verified (stock and 30/60/Uncap FPS++, 51 recorded frames).
- `0x01972900` input_pad_step_01972900: verified (stock and 30/60/Uncap FPS++; its advance branch was idle in the clinic, covered by edge cases).
- `0x016efd00` event_emk_add: verified (stock and 60 FPS++; 50 calls recorded in gameplay).
- `0x02483e80` kernel_condition_wait: verified; all waits in gameplay are untimed, so the FPS
  patches' `ret` on the timed path never runs.
- `BB_TARGET_FPS` in the limiter, frame step and flipper constructor checked against the
  community patches (`verify.py run --patch`).
- `0x004632d0` (was frame_timing_get_time_us): dead in the stock game, used by the FPS patches as a
  code cave; hook and replacement removed, back to `original` with a note.
- Retired a worry that cost several sessions: there is no checked-in generated hook table to go
  stale. `runtime/hooks.c` is the hand-written installer (`rt_hooks_install`), and the table is
  written to `build/game/hooks_table.c` by an `add_custom_command` whose `DEPENDS` are the
  generator, `hooks.csv` and `functions.csv`, so it is regenerated whenever any of them moves.
  Verified by reading the rule and the built table (623 rows, including the newest hook).
  `tools/gen_hooks.py` does not want a `diff` against a checked-in file; there is no such file.
- Harness: an `argf32` index that names no saved register is refused on both scripted paths
  (`saved_xmm`). Both prologues save xmm0 and xmm1 and nothing else, so index 2 read the next
  trampoline slot -- bytes no case sets, equal on both sides by construction, hence a comparison
  that passes on a value nothing loaded. At the last slot it read past the 6144-byte stub mapping.
  Tested by a fixture that loads the bit pattern of 1.0f into xmm0 and calls a stub; the frame is
  load-bearing, because the prologue ends `sub rsp, 8; call rax` and a leaf-style caller enters it
  with the stack misaligned and faults inside the dispatcher, which is how the first version of
  the fixture failed.
- Harness: exit status 3 has one shape on the wire. A refusal raised inside a ctypes callback is
  written to the result pipe (`report_failure`), and the parent prints it once; before, `guarded`
  printed to stderr and exited without writing, so the parent's parse of an empty pipe appended a
  second, misleading `Expecting value` line after the real diagnostic. A child killed between fork
  and write now reports that it exited without reporting why, instead of a parse error. The two
  refusal tests assert the message *and* that nothing follows it: status 3 plus a substring was
  satisfied by the bug itself. Refreshed everything the harness identity touches: 528 of 528
  catalog runs and the review packet, 0 stale.
