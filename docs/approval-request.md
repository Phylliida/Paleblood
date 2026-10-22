# Approval request — 2026-10-22 — one question, five minutes

**Question (the only one on this sheet): may one attestation cover a *shape* rather than a *function*?**

The standing rule this sheet is written under, restated: **every function is decompiled and verified, nothing is
called finished until you say so, and a function is only `verified` when a human has signed it.** This sheet does
not ask to change that. It asks how much work *one* signature may cover when the signer can re-derive the check
for every member of the shape themselves.

## The rule, in one line

> Every member of this family is the bytes `48 8b 47 K c3` or `48 8b 87 K(4 bytes) c3` — `mov rax,[rdi+K]; ret` —
> and the replacement we generated reads the same 4 or 8 bytes from the guest pointer it was handed and returns
> them in `rax`. The constant `K` is not typed by hand anywhere: it is recomputed from each member's own bytes.

## Falsify it yourself, without reading our code

From the repository root, with any `python3`:

```
python3 -c 'import sys
a=int(sys.argv[1],16); d=open("../data/bb/elf/eboot.elf","rb").read(); o=a-0x3fc000; b=d[o:o+8]
if b[2]==0x47: k,n=b[3],5
elif b[2]==0x87: k,n=int.from_bytes(b[3:7],"little"),8
else: print("NOT THIS SHAPE:",b.hex(" ")); raise SystemExit(1)
print(sys.argv[1], b[:n].hex(" "), "K =", hex(k))' 0x00410100
```

`file = guest − 0x3fc000` is this binary's layout; the command reads the ELF directly and prints the member's own
bytes. These three are members, decoded this way on 2026-10-22:

| guest address | bytes | K |
|---|---|---|
| `0x00410100` | `48 8b 47 10 c3` | `0x10` |
| `0x00418d80` | `48 8b 87 c0 01 00 00 c3` | `0x1c0` |
| `0x004261a0` | `48 8b 47 48 c3` | `0x48` |

Change the address to any of the **3,619** rows named `leaf_mov_rax_*` in `symbols/functions.csv` and the same
command re-derives that member's constant. **121 distinct values of `K` exist; `0x40` has 1,463 members and `0x48` has 1,450 — 2,913 of the 3,388
five-byte members (86%), not all of them.** The family's member set hashes to `bcc2bcb58f14c5ed…`; if the membership
changes, this request is stale by construction.

## The two answers, and what each costs you

**(a) `scope = function`** — every one of the 3,619 members needs its own signature line. At the rate signatures
have arrived so far that is not a delay, it is a different project.

**(b) `scope = shape`** — one signature covers the rule above, **applied by the machine to every member**, and the
per-member evidence stays in the ledger (each row already carries its own recorded differential run). One signature
here, then one signature for each of the other three shapes on the same terms.

**If you answer (b), you are still the only person who can sign a function off**, and any member whose bytes fail
the rule is refused by the tool rather than covered by your signature.

## What your signature would *not* claim

- It does not claim the dereference is safe at runtime — our cases use declared buffers, and the 25 unaligned
  members use `memcpy`; nothing here shows a real guest pointer is valid.
- It does not claim the replacements are integrated: **no replaced function has ever run inside the game.**
- It does not claim any of the 528 `zero_init` rows; those are a separate question with a different answer
  required (the approver may not be the author).
- It does not claim the other three shapes, and it expires if the membership hash above changes.

## Where to answer

Append one line to `docs/approval-answers.md` — `2026-10-22 scope=shape` or `scope=function`, plus anything you
want attached to it. Nothing else on this sheet needs a decision today.
