# Approval packet 2 — `mov eax, K; ret` → `return K;`

**The member set.** `docs/packets/members/mov.csv`, 2,978 rows, all width 6,
bytes `b8 imm32 c3`. **305 distinct bodies** (2,820 members share a body with at least one
other; the largest group is 402 members). Distinct bodies are the number that matters:
there are 305 distinct constants to be right about, not 2,978.

**The rule.** `bb_leaf_mov_eax_k_<addr>() { return k_leaf_mov_eax_k_<addr>; }`, with the
constant emitted above each body as a named `constexpr` — `K = <imm32>` read from the tail
of the `mov`, zero-extended into rax.

**Transcription check.** `K` is parsed from raw file bytes at `offset+1` as little-endian
`imm32`; the member list's `size` and `body_sha256` columns re-derive the same width from
the same file. Every K in the family lies below `0x10000000`, so no 32-bit truncation is
observable here.

**Mutant, measured this session, both directions.** Member `0x00463320` (`K = 0xf4240`):
`K+1` → `original 0xf4240 replacement 0xf4241`, rc=1; `K-1` → `0xf423f`, rc=1. Restored rc=0.

**What the canary covered.** Nothing applies — the replacement only returns a constant.
Same caveat as packet 1, stated rather than implied.

**Limits.** `mov eax, K` zero-extends; the family contains no `mov rax, K`, so the
distinction is unexercised and untested here.

```
0x00463320,leaf_mov_eax_k_00463320,2026-10-20,<your name>,approved,<pin>,<cases sha>,shape approval: mov eax,K; ret -> return K; 2,978 members over 305 distinct bodies (docs/packets/members/mov.csv); member-set hash afb8cbcb7cd4d19c
```
