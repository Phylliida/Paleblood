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

Of the **44,331 entries ≤ 16 bytes**, **37,540 are leaf bodies** — exact decode to declared size,
terminating in `ret`, no interior `call`/`jmp` — collapsing to **1,382 templates**. Refused:
5,879 end in `jmp` (tail calls, a different semantics), **585 contain an interior transfer**
(they look like leaves until the call is read), 320 end in `call`, 7 in something else.

| members | distinct bodies | size | body |
|--------:|----------------:|-----:|------|
| 8,072 | 8,045 | 8 | `lea rax,[rip+K]; ret` |
| 7,761 | 1 | 1 | `ret` |
| 4,721 | 1 | 3 | `xor eax,eax; ret` |
| 3,619 | 121 | 5,8 | `mov rax,[rdi+K]; ret` |
| 2,978 | 305 | 6 | `mov eax,K; ret` |
| 1,462 | 115 | 5,8 | `lea rax,[rdi+K]; ret` |
| 793 | 1 | 3 | `mov al,K; ret` |

**The top five cover 27,151 of 37,540 leaves (72.3%) and 17.2% of the catalog**, at 8,672 distinct
bodies between them — 8,045 of those in the first template alone. Review and packet cost scale
with **distinct bodies, not members**: `static_guard` was 1,117 members over 1,117 bodies and cost
29 pages; family #3 is 4,721 members over **one** body.

### Two earlier counts disagreed with these, and why

`mov eax,K; ret` was first counted at 1,947 and `mov rax,[rdi+K]; ret` at 3,518 — 35% and 4% below
the figures above. The cause is the normaliser, not the binary: **Capstone renders an immediate
below 10 in decimal and one above in hex**, and the template key zeroed only `0x…`. Every body
whose constant happened to be small therefore fell out of its family into a singleton. Zeroing
both forms brings the counts to 2,978 and 3,619 (121 refused of the latter end in `jmp` or carry
an interior call). A template table whose key silently splits on render format is a count of one
printer's habits.

Two checks close the census's remaining hedges: parsing hex operands from `op_str` versus reading
`operands[0].imm` with `detail = True` **disagrees on 0 of 37,540** bodies, so the text-parse was
not distorting the branch classification; and the interior-transfer count of 585 is the reason
that test exists at all.

`k+AXqu2-eBc` — the one raw NID left in `symbols/imports.csv` — is imported by **two modules that
disagree about its library** (`eboot` as `libScePosix`, `libc.elf` as `libkernel`), so at most one
row is right and neither export table is in this tree. That is the closed form: *imports complete
except for NIDs from modules whose export tables are absent* — not an open hunt.

Pool A and pool B overlap only in the 14–16 byte band, so the addressable union is roughly 50,000
entries; a precise union is not quoted until it is measured.

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
- The pool B figures are measured twice by two instruments that agree exactly (`detail = True`
  operands versus `op_str`, 0 disagreements in 37,540). The pool A hookable enumeration is still
  single-instrument and remains provisional.
