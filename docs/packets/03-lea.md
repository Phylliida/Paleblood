# Approval packet 3 — `lea rax, [rip+K]; ret` → `return K;`

**The member set.** `docs/packets/members/lea.csv`, 8,073 rows, all width 8,
bytes `48 8d 05 disp32 c3`, disp32 at offset 3. **8,046 distinct bodies**; 54 members share
a body with exactly one other (27 pairs, max duplicate 2). The carried figure "8,045" was
wrong by one and is corrected here from a fresh measurement.

**The rule.** `bb_leaf_lea_rip_<addr>() { return k_leaf_lea_rip_<addr>; }`, with
`K = a + 8 + disp32` resolved at emission time (RIP after the instruction is `a + 8`) and
emitted as a named `constexpr` because a host-side replacement cannot know the guest's RIP.

**Transcription check — the only independent one in this campaign.** Two routes that never
touch the same object: capstone's `i.address + i.size + disp32` over a 7-byte `lea`
(declared size 8 including the `ret`) versus `struct.unpack('<i', raw[off+3:off+7])[0] + a + 8`
over raw file bytes. **0 disagreements across 8,073.** Every constant is seven digits and
inside the guest image band `[0x017e8bb0, 0x05ad30e6]`.

**Mutant, measured this session, both directions.** Member `0x005a0170` (`K = 0x4b464ef`):
`K+1` → `original 0x4b464ef replacement 0x4b464f0`, rc=1; `K-1` → `0x4b464ee`, rc=1;
`K+0` → rc=0. Both sides render at the same width, so this is a real one-unit detection.

**The comparator defect these rows found, and its fix.** Until commit `53cbce7` every one
of these 8,073 rows was rc=1 on a leading zero: the original runs in the host mapping and
returns `IMAGE + guest - EBOOT_BASE`, and that one width (`returns: i64`, the default for
all 15,772 leaf `abi.json`) was routed through a display formatter that mapped it back and
padded it. Values were right; verdicts were unusable. The fix makes the space conversion a
value operation returning ints and demotes formatting to display only. All 8,073 rows are
now recorded clean: `passed == total`, `failed 0`.

**Measured about the stored values, and what is not.** The re-record could not be
diffed against a pre-record snapshot because none was taken, so *that the verdict
changed and nothing else did is unmeasured.* What is measured, over all 8,073:
**every stored value equals the independently derived constant, 0 disagreements
by two routes that share no object.** The recorder now snapshots
`symbols/verification.csv.pre` once, stamped with its HEAD, so the next re-record
is diffable rather than merely assertable.

**What the canary covered.** Nothing applies — the replacement returns a constant.

**Limits, stated rather than discovered later.** All 8,073 members return a **guest address
as a host integer**; both sides compute the same number, so this is **coverage, not a
semantic bridge** — nothing here dereferences the address, and no member has been observed
executing in game. 8,046 distinct bodies (the 305 was `mov eax,K`'s count, carried
here by mistake and removed).

```
0x005a0170,leaf_lea_rip_005a0170,2026-10-20,<your name>,approved,<pin>,<cases sha>,shape approval: lea rax,[rip+K]; ret -> return K; 8,073 members over 8,046 bodies (docs/packets/members/lea.csv); 0/8,073 transcription disagreements by two routes; K+/-1 fail, K+0 passes; member-set hash 1502ec95862ed03f
```
