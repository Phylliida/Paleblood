# The three axes, named before the first capture

A number that can be mistaken for the top line is a number that will be. So the axes are named here,
once, before any run can produce a value on one of them.

| axis | what it asserts | what it does not assert | where it lives |
|---|---|---|---|
| `edge-verified` | a replacement's output matched the original's on N authored edge cases | that the body is equivalent off those cases | `symbols/functions.csv` `status` |
| `verified` | a human read the body and approved it against its evidence | that it ran | the same column, one value further |
| `runtime-witnessed` | the replacement body was **observed executing in the game**, entered through the boundary stub, with its entry registers recorded | **anything about equivalence** | nowhere yet — deliberately |

**A hook firing is a witness, not a comparison.** It retires `unknown (no runtime witness)` and it moves
`edge-verified` by zero and `verified` by zero. One execution cannot distinguish a correct body from a
wrong one that happened not to matter; only a differential over authored cases can, and only a human
approval can promote.

`runtime-witnessed` is **not** a value of `status`, because `status` is exclusive and a fired hook does
not replace the evidence that got the row where it is. It will be a second column when a column is
worth its schema cost — one deliberate tree-wide change, never a piecemeal edit — and until then it is
a phrase in a run log with this file as its definition.

The vocabulary is enforced: `test/test_coverage_axes.py` fails if `runtime-witnessed` appears in
`validate_functions.STATUSES`, so the first capture cannot be quoted as having moved the top line
without a test going red first.

## Two requirements written down before the first capture

**The plugin's image base is compared with the boot's, printed, before anything is installed.**
`libbbgame` carries its own guest-memory globals and its own `rt_guest_read_ok` bounds. If any of them is
initialised by a call only the harness makes, the bodies read from address 0 while every counter says
installed — and both sides happening to map the image at `0x800000000` is exactly the coincidence that
hides it. So the first in-game run prints both bases and the resolved body address, and **refuses to
install if they disagree**. Fail closed, and print the disagreement rather than a count.

**The in-game recorder uses the harness's capture schema, not a new one** — the same fields `verify.py`
records: return value, register set, memory writes, case id. Then in-game evidence and harness evidence are
**one format with two oracles**, and the eventual in-game differential is an extension rather than a second
recorder. A bespoke first-capture format is a format nobody reconciles; that is the three-populations
problem with a schema attached.

**What runs at `dlopen`:** nothing of ours. `readelf -d libbbgame.so` reports `INIT_ARRAYSZ 8`, a single
entry, and that entry is `frame_dummy` (`nm -C` finds no `_GLOBAL__sub_I`), the CRT stub that only exists
to register the tm-clone table. There are no named or unnamed initialisers in the plugin, so a hook is
installed by an explicit call, never as a side effect of loading the library.
