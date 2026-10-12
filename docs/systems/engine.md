<!-- Generated from the project documentation. Do not edit here: open an issue or a pull request. -->

# Engine

## Summary

`game/engine/` collects the engine-level helpers that sit under the game systems: small functions
that take an object owned by a caller, read a timing or configuration value out of it, and return
a derived number. They are not the frame limiter and not the task manager -- those are in
[frame_timing.md](frame_timing.md) -- and they do not own the clock they read.

The first tracked function divides the wall clock by a period carried in the caller's object. Its
ten callers all live in `0x0109....`-`0x010d....`, a region with no other replaced function, so
nothing yet ties this page to a named system. That region is the open question below.

## Key functions

### `engine_time_over_period` (`0x01088550`)

Reads the wall clock with `gettimeofday`, builds `seconds * 1000000 + microseconds` as one signed
64-bit count, and divides that count by the 64-bit period at offset `0x1d8` of the object passed
in. The quotient is the return value; the remainder is discarded.

The division is unsigned while the count it divides is built signed. A clock set before 1970
therefore produces an enormous quotient rather than a negative one, and that is original
behaviour, not a bug in the replacement. A zero period reaches the divide and takes `SIGFPE` on
both sides, before the original ever reads its stack canary; the canary is consequently
unobservable for this function and the replacement keeps none.

Offset `0x1d8` is what the instruction reads (`DIV qword ptr [RBX + 0x1d8]`). The decompiler
prints its own guess of `+0x1d0`, and nothing establishes what the field means, so the
replacement reads it by byte offset and does not name it. Ten call sites, all direct, none of them
replaced, so none of them appears in `game/hooks.csv`.

## Structs and globals

No structure is tracked yet. The object at offset `0x1d8` is known only by that offset: no size,
no other field, and no type has been established, and the caller region is unreplaced.

## Patch points

No patch point is established here. A patch belongs on this page only once an address is mapped
to a named engine function and its effect has been checked against the stock path.

## Open questions

- What object carries the period at offset `0x1d8`, and what the quotient means to its callers. Ten
  callers sit in `0x0109....`-`0x010d....`, which is unreplaced, so the unit and the consumer are
  both unobserved.
- Whether the quotient is a frame count, a period count, or a scaled time, and whether callers
  compare it against a constant.

### `engine_time_id` (`0x02e61280`)

Reads the same wall clock -- the executable's `gettimeofday` stub at `0x02fbe728`, on a 16-byte
`timeval` -- and folds a global counter into the result, returning 128 bits in `RAX:RDX`. Each
register packs two 32-bit fields, the *seconds* word low and the *microseconds* word high, so
neither half is a plain number and RAX is not simply the first field:

```text
RAX = uint32(seconds)             | uint64(uint32(microseconds)) << 32
RDX = uint32(seconds + counter)   | uint64(uint32(microseconds + counter + 1)) << 32
```

The counter is the 32-bit global at `0x0570d83c`. It is read once with a plain
`mov edx, [rip+...]` -- one access, no pointer -- bumped by two, and stored back. Both sums wrap
at 32 bits, and the counter store happens *before* the stack-canary comparison, so the counter
advances even on the failure path.

The stack canary is reached through a pointer: the original loads the slot at `0x057e3be0` with
`mov rbx, [rip+...]` and reads the cookie through it. The cookie is saved and compared but never
returned -- the microsecond half overwrites RAX long before the `ret` -- so no part of the result
depends on it.

The two guest accesses are why this function faults on a raw cast: `0x0570d83c` is a value read in
place while `0x057e3be0` holds an address, and neither PS4 address is where the image is mapped in
the host. Every guest access goes through `rt::ptr` so the address is translated first.
- Whether the period field is ever zero in the stock game. If it is not, the `SIGFPE` path is
  unreachable in practice, but it is still the behaviour the replacement must keep.
