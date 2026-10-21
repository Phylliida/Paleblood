# Approval packet 4 — the compiler's function-local-static one-shot guard (1,117 members)

**The member set.** `docs/packets/members/guard.csv`, 1,117 rows, every one width 41.
**1,117 distinct bodies** — the carried claim "one canonical body" was wrong: the three
parameter addresses differ per member, so the bytes differ. The unit of review is the
**rule plus the triple table**, not a byte string.

**The rule, nine instructions, uniform in all 1,117 members.**
```
lea rax,[rip+A]; cmp byte[rax],0; jne ret; lea rcx,[rip+B]; add rcx,0x10;
lea rdx,[rip+C]; mov [rdx],rcx; mov qword[rax],1; ret
```
displacements at bytes 3/15/26; the `jne` target is `address + SIZE - 1`, the `ret` at
offset 40 (not `address + SIZE` — my first matcher asserted the wrong one and refused all
1,117).

**Only three parameter triples exist**, at stride `0x30`: guards `0x05ac59d8/b8/c8` →
pointers `…d0/b0/c0` → storages `0x056b47f0/4840/4890`, sized 373/372/372. Uniform in all
1,117: compare 0, bias `0x10`, guard write 1, and **pointer == guard − 8 in 1,117 of 1,117**.
The guard is **read as one byte and written as eight** — that asymmetry is load-bearing.

**The trap.** `storage_bias = 0x10` is not visible in any register: the `lea` names the
storage base and the stored value is base + 0x10. A case that checks the pointer's *bytes*
is the only thing that sees it.

**Mutant.** `storage_bias 0x10 → 0x08`: rebuild rc=0, **6 of 6 cases fail across all three
triples**, diff naming `+0x5ac59b0: original 50 replacement 48`. Restore byte-identical by
`cmp`, rebuild rc=0, 6/6 pass. Mutation of one wrapper to point at another triple also
failed 5/5. (Measured before commit `53cbce7`; unaffected by it, since these cases compare
memory bytes and callee-saved registers, both of which kept their representation.)

**Review cost vs. gain, both sentences.** Three attestations cover 1,117 members — a review
ratio of 1/372 — and the fan-out gains **1,114 entries while the information gain over the
family is 3**. Saying only the first sentence would be a lie about what was learned.

```
0x0135bde0,frame_timing_static_guard_0135bde0,2026-10-20,<your name>,approved,<pin>,<cases sha>,shape approval: one-shot guard, nine instructions, three triples, stride 0x30; 1,117 members, 1,117 distinct bodies (docs/packets/members/guard.csv); storage_bias 0x10->0x08 fails 6/6; member-set hash 197486ea89864388
```
