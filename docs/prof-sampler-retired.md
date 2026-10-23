# The SIGPROF sampler: retired by measurement, with the measurement kept

Built, instrumented, and refuted in one stretch. The code is deleted rather than left in the tree;
this file is what survives of it, because the finding is worth more than the sink.

## What it was

A `SIGPROF` sampling sink in `runtime/prof_sampler.c` — a histogram of PCs where the host executes,
independent of the guest's call shape, plus a `CPUTIME`/`Threads:` line from `/proc/self/status`. Three
files: the sink, one line in `runtime/boot.c` calling `rt_prof_sampler_init()` after `sigaltstack`,
and its source added to `runtime/CMakeLists.txt`.

## Why it is retired

    process_cpu_ms before rt_prof_sampler_init():  259.509
    process_cpu_ms after  rt_prof_sampler_init():    0.227

**259.509 ms of CPU had already been spent when the sampler was armed, and 0.227 ms remained.** A
sampler started after the work has finished measures the wire, not the machine. Its first three runs
reported `samples=0`, which I first chased as a plumbing bug:

* `alarm()` **is** `setitimer(ITIMER_REAL)` on glibc — one timer, two owners. `runtime/boot.c:215`
  and `:222` set the same `ITIMER_REAL` for the boot's own timeouts, so the sampler's period was
  taken from it and the counter never decremented. `samples=0` three times, with the timer quietly
  belonging to somebody else.
* The reframe outranked the fix: even with a correct timer, the window it could observe was 0.227 ms
  of a 259.7 ms boot. Fixing the plumbing would have produced a beautiful histogram of nothing.

## Resurrection condition

Arm it **before** the first instruction of the guest runs — i.e. before whatever consumes the 259.5 ms
— and use a timer that is not `ITIMER_REAL`, or take ownership of `ITIMER_REAL` in one place and let
the boot's timeouts ask it for a slot. Until then a profiler in this runtime measures its own tail.
