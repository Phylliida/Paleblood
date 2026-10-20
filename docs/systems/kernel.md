<!-- Generated from the project documentation. Do not edit here: open an issue or a pull request. -->

# Kernel

## Summary

The engine's core library (Dantelion2, "ClassLibrary/Core/Kernel" in its source paths): thin
wrappers around the PS4 kernel for threads, mutexes and condition variables, which report every
unexpected result through the engine's fatal error function (`0x024b55b0`, file, line, message).

The executable and bundled `libc` import POSIX-like calls such as `getpagesize`, `getpid`,
`clock_gettime`, and `gettimeofday`; an import does not mean Paleblood implements it. In the
current runtime, both `getpagesize` entries are registered as fail-loud unresolved diagnostics
because the PS4 page-size value is not established, as recorded in merged Paleblood [PR #66](https://github.com/Yharnam-Hunters/Paleblood/pull/66).
See the runtime system-call notes for implementation status and evidence limits. In the game
evidence reviewed so far, the frame limiter passes null as `gettimeofday`'s timezone argument;
numeric clock ID `4` is confirmed for `sceKernelClockGettime`, not for the imported
`clock_gettime` wrapper.

`kernel_condition_wait` (`0x02483e80`) waits on a condition variable: forever when the timeout
is -1, else with a timed wait that returns -3 on timeout. It is called about 40 times a frame in
gameplay. The community frame-rate patches replace its timed-wait call with a return that would
jump to a garbage address if it ran; every wait recorded in gameplay is untimed, so it never
does.

`kernel_wait_for_release_024bd150` (`0x024bd150`) is the engine's wait-for-release step. It takes
the lock at the global `0x05aa4578` — whose own word *is* the vtable, slots `+0x18` and `+0x28` —
and reads bit 0 of the node's `+0x31`. Modes 1 and 2 move on when the node is released; mode 1
otherwise waits for the node's word at `+0x10` to read `2`, and mode 0 answers null unless the
node is released. Every mode that moves on bumps the byte at `+0x30` and walks to `+0x18`, or
twice through `+0x80` when the guard at `+0x88` is set. The wait body (the `usleep` at
`0x02fbfe68` and the re-read of `+0x10`) is not covered by the differential cases: the loop leaves
only when `+0x10` reads exactly `2`, which makes the number of calls before it leaves depend on
when the write lands, so no case file can state a call sequence that holds on both sides.

`kernel_pending_code` (`0x004663f0`) folds two adjacent words of a caller-owned object into one
code. The word at `+0x34` is a count of work in flight, tested with `jg`, so it is signed: only a
strictly positive value returns `2`, and a word with the top bit set is not "greater than zero" to
this function. Otherwise the result is bit 0 of the word at `+0x30`. It calls nothing and writes
nothing.

`kernel_index_code` (`0x004664e0`) maps an index to a code word out of seven 32-bit entries in the
executable's read-only data at `0x02fc5480`: `0x100, 0x100, 0x28a, 0x2bc, 0x2ee, 0x2ff, 0x2ff`.
The bound is unsigned, so an index above 6 — including every negative index, whose bit pattern is
above 6 when read unsigned — returns `0x2bc` instead of indexing backwards out of the table, and
the index is sign-extended only after it has passed the test. The load is a 32-bit `mov eax`,
which zero-extends into RAX. Two of the seven values appear twice, so indices 6 and 7 are the only
pair that separates the bound from the table's own contents.

### Runtime thread-call implementations

These are Paleblood runtime services, not newly decompiled game functions. Merged [PR #62](https://github.com/Yharnam-Hunters/Paleblood/pull/62)
implements `scePthreadEqual` by comparing the object pointers used as guest thread handles. Its
synthetic registry tests cover one handle compared with itself, distinct handles in both argument
orders, and null; the public FreeBSD `pthread_equal(3)` contract supports zero for unequal and
nonzero for equal, but the PS4's exact nonzero value is unknown. Merged [PR #72](https://github.com/Yharnam-Hunters/Paleblood/pull/72)
implements imported `sched_yield` by yielding the host thread and returning zero, following POSIX
and FreeBSD's documented contract. Unit tests check the result but cannot show that another host
thread actually ran.

The similarly named `scePthreadYield` remains registered as an unresolved, fail-loud diagnostic.
FreeBSD's `pthread_yield` returns `void`, Linux's analogue returns `int`, and no PS4 declaration or
inspected guest call site settles the guest-visible signature. Do not infer that it is implemented
from its registry entry. None of these changes has been verified by a new Bloodborne boot.

## Key functions

| Address | Size | Name | Status | Notes |
|---|---:|---|---|---|
| `0x004663f0` | 18 | `kernel_pending_code` | edge-verified | `2` while the signed count at `+0x34` is above zero, else bit 0 of the word at `+0x30` |
| `0x004664e0` | 25 | `kernel_index_code` | edge-verified | bounds-checked lookup in the seven-entry table at `0x02fc5480`; an index above 6 returns `0x2bc` |
| `0x02483e80` | 204 | `kernel_condition_wait` | verified | Dantelion2 PthreadCondition wait (untimed when timeout is -1); the FPS patches put a ret on the timed path |
| `0x024bd150` | 216 | `kernel_wait_for_release_024bd150` | edge-verified | waits for a node's `+0x10` state word to read `2` under the engine lock, then bumps `+0x30` and walks to `+0x18`, or twice through `+0x80` when `+0x88` is set |
## Structs and globals

Not documented yet.

## Patch points

- `30 FPS++`, `60 FPS++`, `90 FPS++` and `Uncap FPS++` write a return over the timed-wait call
  in `0x02483e80` (see above); our replacement keeps the original behaviour.

## Open questions

- Which objects the ~40 condition waits per frame belong to (job queues, the render thread?).
