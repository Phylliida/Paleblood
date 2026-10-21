# Decision page — bare `ret` (7,761 members). Not an approval request.

This is a different ask from packets 1–4 and is kept in a separate artifact on purpose: a
reviewer asked to sign this would be asked to approve a coincidence.

**The situation.** 7,761 functions are a bare `ret` (width 1, one distinct body). The
original is **rax-transparent**: it returns whatever the caller left in rax. The harness
boots rax as `0xdeadbeef` (`harness.py:58–59`), so the differential is well-defined, but a
C replacement cannot express pass-through.

**The trap.** `void f(void) {}` compiled at `-O2` emits a bare `ret` and **would pass every
case** — on an unstated compiler habit, not on a stated semantic. That is the `zero_init`
defect with the sign flipped: 7,761 rows certified on gcc's convenience.

**Option A — `naked` with explicit asm.**
```c
extern "C" __attribute__((naked)) void bb_leaf_ret_<addr>(void) { __asm__("ret"); }
```
States the semantic in the artifact; survives a compiler change; costs a compiler-specific
attribute and one more thing every generated family must be able to emit.

**Option B — written exclusion.** Record the 7,761 as deliberately unverifiable under a
host-installed model, with the reason, and stop counting them as reachable coverage. Cheaper,
and honest: pool B can never reach `verified` anyway, because no gameplay capture exists for
an uncalled host-installed function.

**What the decision changes.** Whether the ladder can cite 7,761 more entries, and whether
generated families should have a pass-through path at all. It changes nothing about packets
1–4.
