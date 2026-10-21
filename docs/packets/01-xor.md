# Approval packet 1 — `xor eax, eax; ret` → `return 0;`

**What you are being asked.** One rule, 4,721 members, one distinct body. You are not
auditing 4,721 programs; you are answering whether the rule below expresses this byte
sequence for every member, plus one machine-checkable assertion over the member list.

**The member set.** `docs/packets/members/xor.csv` — `address,name,size,body_sha256`,
4,720 rows, sorted. sha256 of that file: see `docs/packets/INDEX.md`.
4,721 total members = 4,720 generated + 1 hand-built smoke at `0x0040c4c0` (same bytes,
written before the generator existed and used to prove the pipeline end to end).

**The body, verbatim, and it is the only one.** Width 3, bytes `31 c0 c3`. sha256 of the
body: **1 distinct body hash across all 4,720 generated members** (measured this session
over raw file bytes at `file = guest - 0x3fc000`).

**The rule.** `bb_leaf_ret_zero_<addr>() { return 0; }` — the original zeroes eax and
returns, so the 64-bit return value is 0.

**Transcription check.** Single body, so there is no parameter transcription to check.
The rule and the bytes are the same object; the distinct-body count of 1 is the check.

**Mutant, measured this session.** One member (`0x0070ed60`) returns `1` instead of `0`:
`ret.rax: original 0x0 replacement 0x1`, rc=1. Restored: rc=0, byte-identical.

**What the canary covered.** Nothing, and that is the honest statement. A replacement that
returns a constant reads and writes no memory, so there is no perturbation for the canary
to apply — it reports "none applies" rather than a pass. These 4,721 rows rest on the
differential (both sides run every case) plus the mutant above, not on the canary.

**Limits.** rax only; no argument is read; no memory is touched. A member whose original
reads an argument (there are none in this family) would be out of scope.

**Paste-ready row** (`symbols/reviews.csv`), one row per shape, `address` naming a
representative member so the existing 8-column schema accepts it, with the member list and
its hash in `notes`:

```
0x0070ed60,leaf_ret_zero_0070ed60,2026-10-20,<your name>,approved,<pin>,<cases sha>,shape approval: xor eax,eax; ret -> return 0; 4,721 members (docs/packets/members/xor.csv, 4,720 generated + hand-built 0x0040c4c0); member-set hash e71ad398f3d7cca6
```

A `scope` column would make this structurally auditable rather than a sentence in `notes`;
that is a schema decision, and the request is separate from this approval.
