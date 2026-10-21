# What is actually verifiable: two pools, not one

The catalog's 157,757 entries have been counted against two different questions, and the answers
are not interchangeable. Quote the pool, never a bare percentage.

## Pool A — in-game hookable (the factory's original target)

A hook is a 14-byte absolute jump written over the function's first bytes (`QUIRKS.md`), so an
entry shorter than 14 bytes cannot be installed, and neither can one that something branches
into within its first 14 bytes in the same module. Enumerated with exact decode plus a single
`ret`, no interior transfer: **12,739 entries (8.1%)**, **7,747 distinct templates**, of which
only **3 have ≥50 members** — the `static_guard` shape (1,117), a three-instruction RIP-relative
store (362), and a 49-byte `vmovaps` pair copy (263). Top-20 templates cover 2,255. The median
template has one member.

Inside Pool A the template engine is therefore exhausted after family #2: the remaining territory
is ~11,600 entries spread over ~7,740 mostly-singleton templates. This is the pool to plan in-game
deployment from.

## Pool B — verifiable by the differential, hook or no hook

`tools/harness.py:722 load_replacement` **never patches the guest image**. It dlopens the game
library, calls `bbgame_init` with a hook installer that installs nothing, and returns the
replacement's host address; the harness calls it directly. The original side runs unpatched guest
code at its own address. So the 14-byte floor is a property of *in-game installation*, and every
one of the 1,737 recorded members already carries host-call evidence — the hook rows they were
also required to have were never load-bearing for a ledger claim.

Entries ≤ 16 bytes, exact decode, terminating in `ret`: **38,125, with 6,206 refused** (declared
size does not decode cleanly, or ends in `jmp`), collapsing to **1,904 templates**. The six
largest:

| members | distinct bodies | size | body |
|--------:|----------------:|-----:|------|
| 8,071 | 8,044 | 8 | `lea rax,[rip+K]; ret` |
| 7,761 | 1 | 1 | `ret` |
| 4,721 | 1 | 3 | `xor eax,eax; ret` |
| 3,518 | 119 | 5,8 | `mov rax,[rdi+K]; ret` |
| 1,947 | 296 | 6 | `mov eax,K; ret` |
| 979 | 1 | 5 | `lea rax,[rdi+8]; ret` |

**27,197 of 38,125 (71.3%) sit in six templates, 17.2% of the catalog.** Pool A + pool B is the
addressable pool: **53,797 entries, 34.1%**.

## What a host-call run does and does not prove

It proves the body's behaviour given an ABI frame. It does not prove the body behaves correctly
when a *guest* calls it — a different caller, stack shape, and, in game, the jump itself. So a
host-only row is not a weaker evidence rung; it is the same evidence about a smaller claim, and
the difference is a work item with a name: **install and re-verify through the hook**.

An entry admitted on host evidence must say so where a reader can see it — a declared
`hook | host` field, fail-closed on absence, and a burndown that prints both counts. `replaced`
has silently meant both since the first generated body and must stop.

## Two limits on this census

- **"Verifiable body" is not "function."** Exact decode plus a return is strong evidence of a body
  and says nothing about entry points; 120,641 entries have no in-catalog caller to corroborate
  entry status. Say entries.
- The hookable enumeration parsed branch targets from `op_str` rather than the operand model, and
  has not yet been diffed against a hand-decoded member. Provisional until it is.
