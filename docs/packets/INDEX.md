# Shape approval packets — 2026-10-20

| # | family | members | distinct bodies | status |
|---|--------|---------|-----------------|--------|
| 1 | `xor eax,eax; ret` → `return 0` | 4,721 (4,720 generated + 1 hand-built) | 1 | ready to approve |
| 2 | `mov eax,K; ret` → `return K` | 2,978 | 305 | ready to approve |
| 3 | `lea rax,[rip+K]; ret` → `return K` | 8,073 | 8,046 | ready to approve |
| 4 | static one-shot guard | 1,117 | 1,117 | ready to approve |
| — | bare `ret` | 7,761 | 1 | **decision page, not an approval** |

Member lists (`address,name,size,body_sha256`, sorted):

| family | file | sha256 |
|--------|------|--------|
| xor  | `members/xor.csv`   | `e71ad398f3d7cca6e771731f9776b8400e9ad6d4cd9fd91caecb5f563f68b780` |
| mov  | `members/mov.csv`   | `afb8cbcb7cd4d19c512c17c458ee1d82f3c82cd0886510ece526140150e09bd6` |
| lea  | `members/lea.csv`   | `1502ec95862ed03ff97da2e99578b81f35d1cfd34d5e6ef9fb866618443e4993` |
| guard| `members/guard.csv` | `197486ea89864388ce49a94bb9e100912772fd26d11eaf39b9c869f843e5d4d0` |

Those four hashes are the proposed `shape(<template_hash>)` identity: an approval names one,
and if the member set later changes the hash stops matching, so the approval goes stale on
its own rather than relying on a sentence in `notes`.

**What is not claimed anywhere in these packets:** no member of packets 1–3 has been
observed executing in game; the canary has nothing to perturb in a constant-returning
replacement; and none of these families bridges semantics — they reproduce a value, not a
behaviour.
