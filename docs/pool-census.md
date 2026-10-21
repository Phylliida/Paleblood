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

### The two diagnostics that catch a fifth normaliser bug

Printed beside every future census, because a key that fails to zero a field does not announce
itself — it just makes every member its own family:

1. **Singleton count, plus whether singletons are real.** `templates=1,382, singleton-templates=746
   (54%)`, and the check that matters: **bodies appearing under more than one key = 0**. A high
   singleton fraction with zero split bodies means the singletons are genuinely distinct programs
   (`mov dword ptr [rdi + K], K; and byte ptr [rdi + K], K; ret` is one of them, not a mis-parse);
   a nonzero split count means the key is still eating something. Distinct bodies: **13,612**.
2. **The extreme keys printed verbatim**, so a decimal/hex residual is visible on sight rather than
   after a 35% discrepancy: largest `'lea rax, [rip + K]; ret'`, smallest `'ret'`.

## Review model: one rule, N transcriptions

`members / distinct bodies` alone reads as *8,672 review units*, which is unsellable and wrong. A
reviewer of `lea rax,[rip+K]; ret` is not asked to understand 8,045 programs; they are asked one
question — **does the generated rule correctly express this instruction sequence** — plus a
machine-checkable one — **was each member's constant transcribed correctly**. Split in the packet:

- **the rule**: one attestation per template.
- **the parameter table**: one assertion over every member — re-decode the member's own bytes,
  recompute the expected constant, compare against what the generator emitted. Two independent
  derivations of one value, the same discipline as `detail=True` against `op_str`, and stronger
  than any human reading 8,045 numbers. The domain is **13,612 distinct bodies, not 37,540
  members**: identical bytes must yield identical constants, so group by body hash and require a
  single constant per group — which also catches a generator that keys on address instead of on
  bytes.
- **the cases**: per template, since the constant is the only variance, plus two or three members
  run end-to-end so the assertion is not the only witness.

So distinct bodies becomes **the domain size of one assertion**, and the pool is *1,382 decisions,
27,151 of them transcription-checked*.

### `lea rax,[rip+K]; ret` must return a literal

A replacement running as a host function **cannot know the guest's RIP**, so the generated body
resolves the address at generation time and emits `return 0x…;`. That is also what makes the
transcription assertion exact and the replacement reviewable at a glance. Passing the site address
at runtime would add an argument the original ABI does not have, and the differential would stop
comparing like with like.

Which reorders the families: `lea` is cheaper than `mov rax,[rdi+K]` **not because of size but
because it needs no memory model at all** — and cheaper than `mov eax,K; ret`, which is 2,978
distinct constants over one six-byte rule with no shared structure, i.e. pure transcription.

## Three lines that must not be comments

- **`observed executing in game`** is not printed as `0`. A constant nothing can contradict is a
  comment wearing a number's clothes, the same species as `promote.py` exiting 0. It reads
  **`unknown (no runtime witness)`** until a hook-entry counter exists in the runtime to make it
  move on its own; then it is derived and printed. `hook-registered` and `host-only` are countable
  from the tree today and are the two lines that may carry numbers.
- **Determinism is not asserted on an empty table.** An empty file round-trips identically however
  broken the writer is; `--check` byte-identical twice proves nothing until a family lands in it.
  The property is asserted again when the file holds 4,721 rows, and the commit says which of the
  two it is claiming.
- **Zero members is a state, not a success.** `install_mode.csv` shipping empty means the schema
  exists and nothing uses it; the burndown says `hook-registered 1,737 / host-only 0` either way.

## What family #3 will and will not prove

`xor eax,eax; ret` has **one** distinct body, so its transcription assertion has a domain of one
and its packet is one page. Landing it proves **the gate** — that a non-`original` row can exist
with no hook row while both checker directions still bite. It proves **nothing about scale**, and
it must not be cited as evidence that the one-rule-plus-N-transcriptions model works. That claim
belongs to `lea rax,[rip+K]; ret` — 8,072 members over 8,045 distinct bodies — and until that lands
the review model is a design, not a result.

Predicted end state for family #3, to check against the burndown rather than reading whatever it
prints: count 1,737 → **6,458** (+4.09%); bytes 130,370 → **144,533** (+4,721 × 3 = 0.340% of
42,487,347); ledger rows 1,838 → **6,559**, multi-set surplus holding at exactly **101**;
exclusive edge-verified 1,716 → 6,437 with original 2 and verified 21 unchanged; and
`hook-registered 1,737 / host-only 4,721`. A miss on any of the six means a member silently failed.

## Pool B can never produce `verified`, and that is not a stall

`verified` means a differential against **recorded gameplay captures**. A function the game never
calls never has one. So every pool B family is **permanently `edge-verified`**: family #3 moves the
count line 1,737 → 6,458 and leaves the `verified` line at 21, and that is correct behaviour.

The consequence, written down before it looks like the campaign stopped: **translation work alone
reaches ~34.1% edge-verified and 0% verified growth.** The top rung is gated entirely by the boot
reaching game code — one recorder caller and one import wall — and by nothing in pool B. Any
twenty-turn stretch where the count climbs and `verified` and `observed executing in game` do not
is the campaign moving on the only rung it can reach without the game running.

## Two requirements for every checker and every large commit

- **Print the work, not just the verdict.** A baseline `rc=0` is consistent with "no violations"
  *and* with "the check never ran", exactly as an `rc=1` can come from a `NameError` instead of a
  rule — both happened while wiring this gate. `validate_functions.py` must print one line of its
  own arithmetic, e.g. `install_mode: 0 host rows · hook-resolved 1,737 · original 1,113`, so a
  wiring failure reads as `0 host rows` rather than as silence. Lands with the first family
  tranche, and applies to every `tools/` checker that reports only pass/fail.
- **A large insertion must not re-sort its file.** The 4,721-row `functions.csv` addition must
  append and rewrite in place, and the commit asserts its own diff shape — `git diff --stat`
  showing that file and additions only. A re-sorted 157,757-line diff buries 4,721 real changes
  where no reviewer will find them, and the assertion is what the reviewer actually relies on.
