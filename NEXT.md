# Next targets

Two tracks. Sessions alternate between them (decompilation, then runtime, then decompilation,
...) unless the maintainer says otherwise; `Last session` below records which one ran last.
One line per target, in order; move a target to "Done" with its commit when it is finished.
Decisions and blockers go to STATUS.md instead of being worked around.

Last session: runtime

Needs the maintainer (cannot be done from the sandbox):
- `gh auth login`, so the local commits on `main` can be pushed and the branches opened as pull
  requests. Everything else here is unblocked without it; `../Paleblood-2026-10-19.bundle`
  (`git bundle --all`) holds the history.
- The affinity constant in target 2 below: `0x3F`, `0xFF`, or a decision to park it. No citable
  source in the tree pins it, and the game's libc bit-counts the mask to size worker threads
  (STATUS.md, "Open questions"), so a wrong guess changes thread topology silently.
- What `verified` means for a function whose captures are not in the checkout. 20 of the 21
  `verified` functions have no case directory here (their captures were recorded in a 2026-10-07
  checkout), so their `symbols/verification.csv` rows carry `cases_sha256` `unavailable` rather than
  a hash. `tools/verification.py::check` currently accepts that marker as sufficient; the argument
  for it is that it is a deliberate act by someone who looked, and that a blank is still an error.
  The argument against, and the reason this is here rather than settled in code: if those inputs
  cannot be re-run in this tree, "verified" claims more than the tree can show, and the honest
  status is `edge-verified` until the captures return. Flipping it is one predicate in `check`;
  what matters is that it is a decision, not a default.
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
  `../.venvs/paleblood/bin/python3 -P tools/make_review_packet.py --out ../data/review/engine_zero_init_review.md --caveat '<corpus fact>'`: anything naming a game function or case is
  passed as `--caveat`, because `tools/` is inside `check_agnostic.py`'s scope and a family name
  written into the tool turns that gate red.
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
   `RT_ORIGINAL(... kernel_usleep ...)` reach. What is missing is narrower: the write target is
   always `args[arg] + offset`, so a stub that takes no pointer argument cannot name the address it
   should change. `sceKernelUsleep` is exactly that case -- its argument is a microsecond count,
   and it is not among the eboot's 686 imports either, so the `imports` path cannot reach it. The
   fix is a `target` form (`{"target": "buf:state+0x10", "bytes": "..."}`) resolved through
   `self.value()`, about four lines per path; it is the same limitation items below already record
   against two verified functions ("the stub cannot set a global"). Cost of touching
   `tools/harness.py`: every catalog run's `harness_sha256` goes stale -- 528 addresses, ~3 min to
   refresh at 24 threads, then regenerate the packet. The dead `../data/cases/wait/*.json` were
   written for this and never executed: they name a pointer argument (`arg: 1, offset: 16`) that
   `sceKernelUsleep` does not have, which is why the format looked broken -- a spec by intent,
   never run, so never forced to be right. `kernel_wait_for_state_024bdd40` (`0x024bdd40`,
   replacement written and faithful) still shows `original` in `symbols/functions.csv` and no ledger
   row covers it.
2. `scePthreadAttrGetaffinity` (libkernel), called by the game's own libc while it starts: needs
   the main thread's CPU affinity mask on a PS4 (STATUS.md, "Open questions"). Then the next
   import `tools/boot.py` names.
3. Module loading at run time: when the game asks to load a module listed with action `stub` in
   `game/modules.csv`, report it loaded without mapping it.

Roadmap after the boot gets going: kernel, threads and memory; files; input; audio; video
out; GNM and shaders (the largest). Claimable work per system call group is in the issues
labelled `runtime`.

## Decompilation track

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

- `0x0138a370` frame_timing_task_dispatch_0138a370: verified (the task dispatcher; 51 recorded frames with 76 registered tasks each). With it the task manager's frame is done: `0x024512a0`, `0x01388c60`, `0x01388c70`, `0x0143e490`, `0x014400a0`, `0x0143f9f0`.
- `0x0143e490` frame_timing_task_flush_queue_0143e490 and `0x014400a0` frame_timing_task_workers_step_014400a0: verified (200 and 53 recorded calls; the list re-read after each task cannot be made observable with stubs).
- `0x024512a0` frame_timing_task_frame_024512a0 and `0x01388c70` frame_timing_task_run_01388c70: verified (51 recorded calls each; the singleton re-read after the fatal error cannot be told apart in the harness, whose stubs cannot set a global).
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
