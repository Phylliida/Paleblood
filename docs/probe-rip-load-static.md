# Probe: `rip_load_static`, pre-registered before a single body exists

This file exists because a pre-registration that lives in a chat message is not one: the next
session cannot read it, and the numbers a commit is checked against must be readable by the person
the commit constrains. Nothing here is a measurement of the probe — no body, case, mutant or flip
exists. Everything below is derivable today from the catalogue and the image.

## Population

`census_rip_load.py` (committed as `a3e4c6a`, neighbour analysis added in `787a0d6`) finds, over the
catalogue with its four printed drop counters, **453 load-first-RIP-relative members**:

    containment: {'bss': 442, 'filesz': 11, 'filesz_indiscriminate': 6}   total 453

The 442 in BSS are **unemittable** — their targets lie past the RW segment's `filesz`, in zero-fill
the loader never writes, so a load returns a constant zero no case can perturb. That is why the
withdrawn family of 161 (`f511666`, receipt: library hash `7982090e5b0f94a1…` returning to its
pre-defect byte) was withdrawn rather than re-cased. **11 members remain, all inside `filesz`.**

## The five and the six

The body reads a dword at `pbl_image_base + (v - kGuestLoadBase)`; a `+4` mutant therefore reads the
next dword. If the two dwords are equal, the differential returns the same value whether the
constant is right or wrong by four, and a row would be evidence from a comparison that cannot
discriminate the number defining the family — **the withdrawn 161's defect at one member's width.**

| member | target | dword | dword+4 | verdict |
|---|---|---|---|---|
| `0x186ea70` | `0x5527acc` | `ffffffff` | `00000020` | discriminating |
| `0x1f98fa0` | `0x5528720` | `ffffffff` | `00000001` | discriminating |
| `0x23b7110` | `0x5528954` | `00000001` | `00000009` | discriminating |
| `0x24264d0` | `0x5528a00` | `0000000a` | `41200000` | discriminating |
| `0x2c6d570` | `0x56dc698` | `0000003c` | `00000000` | discriminating |
| `0xdfb9e0` | `0x5693c80` | `00000000` | `00000000` | neighbour-uniform (zero fill) |
| `0x1839d00` | `0x5527a90` | `00000001` | `00000001` | neighbour-uniform |
| `0x186ea40` | `0x5527ab4` | `ffffffff` | `ffffffff` | neighbour-uniform |
| `0x186ea50` | `0x5527abc` | `ffffffff` | `ffffffff` | neighbour-uniform |
| `0x186ea60` | `0x5527ac4` | `ffffffff` | `ffffffff` | neighbour-uniform |
| `0x23b7120` | `0x5528950` | `00000001` | `00000001` | neighbour-uniform |

**Only the five can flip.** The six stay `original` with a recorded reason in
`symbols/verification_unrecordable.csv` (`function,reason,date`), joined by name to
`functions.csv`'s `name` column — gated by `test/test_unrecordable_join.py` (`1cda8bf`), which refuses
a row naming a function the catalogue does not have. Their names must be **the ones the emitter
writes**; authoring `leaf_rip_load_static_<addr>` by hand before emission is the remembered-table
defect. Reason text: `neighbour-uniform within +4; the differential cannot discriminate v`.

## The run

1. **Step zero, done:** `game/leaf/load_base.h` + `load_base.cpp` (`aeabc54`) — one export,
   `nm -D` shows `B pbl_image_base`; asserted on the artifact in `test/test_image_base_set.py`.
2. Emit **11** bodies including `load_base.h`; every body's address arithmetic uses
   `kGuestLoadBase`, never a bare `0x400000` (the readability gate refuses the literal, correctly).
3. Assert `image_base_set` reaches the run JSON — still owed, five turns running. A body whose
   harness never set the base reads a harness-only mapping or faults; the fact must be recorded.
4. **11 `+4` mutants, one rebuild, expect 5 killed and the 6 named above surviving.** The mutant
   checks this table; it does not produce it. Restore by re-running the emitter, never patch-back.
5. Flip **only the five**; write the six unrecordable rows.
6. Gates: suite (365 + the new cases), `validate_functions`, ctest 18/18.

## Target numbers, and how to derive them

    edge-verified rows   33,974  ->  33,979        (+5)
    bytes (guest extent) 283,635 ->  283,697       (+62 = 7+7+7+34+7, sizes from ghidra_functions.csv)
    verified             21      ->  21           (differential tier is not `verified`)
    unrecordable rows    3       ->  9            (+6, with reasons and dates)

The byte column is **the sum of the replaced functions' guest extents**, not the size of any body
written for them; `progress.py` now prints the referent beside the number for exactly this reason
(`787a0d6`). Addresses are parsed with `tools/addrs.py` — five spellings of one address produced
three wrong totals and one silent `None`.

**If a number differs, the difference goes in the commit's first line**, not in a footnote.
