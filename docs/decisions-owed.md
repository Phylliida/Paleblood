# Decisions owed: five questions, five minutes

Everything below blocks work I am not allowed to do unilaterally. Each line: what it unblocks,
what I recommend, and what it costs if I am wrong. **The wall is 30 approvals against 21,086
clean rows**; four of these five questions are what stand between here and reviewing the families
that already have evidence.

**The five "unblocks" figures are not additive.** They sum to 28,797 against a clean-row
population of **21,086**: the `ret` members live inside the four families named in question 1, and
the SSE answer changes which of them can ship at all. **Union, not sum -- the ceiling is 21,086,
and each answer releases a subset of it.** A reader who adds them gets a number larger than
exists, which is the defect this campaign keeps paying for.

---

## 1. Approve the four family shape packets?

**Unblocks:** ~16,889 generated rows across four one-body families -- the compiler's static-guard
one-shot (1,117 members), `xor eax,eax; ret` (4,721), `mov eax,K; ret` (2,978),
`lea rax,[rip+K]; ret` (8,073). Each packet states its own limit in its own pages rather than
leaving it to the reviewer.

**Recommend: yes, all four.** Each family is one distinct body repeated, each carry a
machine-checked transcription (re-decode the member's own bytes, recompute the constant, compare
byte for byte -- two independent derivations), and each approval is pinned to a member-set hash,
so **an approval goes stale by itself** when a member changes.

**Cost if wrong:** a wrong rule is signed once and fans out over thousands of rows. Bounded by the
fact that the member-set hash re-opens the decision when the shape changes, and by the packets'
own stated limits (e.g. `lea` returns a guest address as a host integer: coverage, not a semantic
bridge; dereference untested).

---

## 2. `ret` (7,761 members, one body): naked `asm("ret")` plus a one-byte assertion, or a written exclusion?

**Unblocks:** 7,761 rows -- the largest single family in the tree. C has no pass-through
expression, so a body must either be naked asm or be excluded by policy.

**Recommend: naked asm, with a test asserting the compiled body is exactly one byte `c3`.**
Measured with clang: `-O2` emits exactly one `c3` for **both** candidates, so the assertion cannot
distinguish them -- **what naked buys is independence from the optimisation level**, because a
`void f(void){}` body is only a `ret` by an unstated gcc/clang habit. That is the entire argument,
and it is worth 7,761 rows.

**Cost if wrong:** nothing at runtime; the risk is that an explicit construct without an assertion
about its output has *moved* the trust rather than removed it. The assertion is what closes that.

---

## 3. `scope` in `reviews.csv`: one approval per function, or per shape?

**Unblocks:** 3,619 members of the `mov rax,[rdi+K]; ret` family, and every future family.

**Recommend: `shape`, written out as a column.** The economics are stark: **121 rules over 3,619
members, versus 3,619 signatures.** Both sentences must always be printed together, though --
**the fan-out gains 3,619 rows and the information gain is 121** -- or the number is a lie.

**Cost if wrong:** an approval that reads like per-member review approves less than the reader
believes. Mitigated because the per-member part is machine-checked transcription over every
member's own bytes, which is stronger than a human reading 3,619 numbers.

---

## 4. Where does `check_readable`'s SSE line sit?

**Unblocks:** ~300 tier entries (if strict) versus **most of 7,791** (if relaxed) -- measured
zero-SIMD density is **32.2%**, and ≤0.05 is **60.3%**.

**Recommend: allow low-density vector code (≤0.05)**, i.e. set the line at a threshold rather than
at zero. The tier's median SIMD density is **2.6%** and **47.4% of it carries ≤2% vector code**;
the binary filter collapsed a distribution whose mass sits near zero, and my fear (32.7% → 32.2%)
was larger than the fact.

**Cost if wrong:** bodies carrying incidental SSE get hand-translated with more room for error.
Bounded by the differential: a wrong body fails against the original, and the tier is destined for
generated bodies anyway.

---

## 5. A second approver for `zero_init`? (0 of 528 approved)

**Unblocks:** 528 rows, and the structural rule that the approving session must not be the
authoring one -- which makes `zero_init` **impossible for me to complete alone by construction.**

**Recommend:** either designate the companion session as second approver, or accept **machine-
checked evidence as the second signature** for `zero_init` specifically (the case set plus a
differential that distinguishes zero from nonzero), leaving human approval for families where a
shape claim is involved.

**Cost if wrong:** self-approval weakens the independence property the repo has been careful
about. That is why this one stays a question rather than a decision.

---

Recorded before the session boundary so the answer is a decision rather than a reading task.
Numbers here are the ones the tools print; where a figure is carried rather than measured, it is
labelled as carried in the packet it comes from.

## Delegation to host libc: the fork the 703-name table created

703 named imports is a strategy question, not a task list. One address space, and guest addresses
are already host-dereferenceable, so a large class of these could be delegated to host libc rather
than hand-written.

**The line, drawn once and applied per family:**

- **Delegate** -- stream, string and formatting calls: stateless, no cross-ABI structs, no ownership
  handed across the boundary (`memcpy`, `strlen`, `printf`, `vsnprintf`, and the `_Stdout` /
  `_Stderr` objects only if they are used as opaque handles).
- **Never delegate** -- the allocator and `FILE*` interop. libc.elf runs its own heap; two
  allocators over one region corrupt silently, and a `FILE*` from one libc passed to the other is
  the same failure with a different signature. `malloc`/`free`/`realloc` stay ours, and so does
  anything that hands a stream object across.

Status: **unanswered, and now hot** -- it gates a family rather than a function. The answer needed
is yes/no on the split above, not on delegation in general.

## Three import counts, three populations -- do not quote any of them alone

Measured in one call, none of the three agreeing:

| figure | population |
|---|---|
| 686 | eboot's imports, as the boot reports |
| 747 | NIDs in `docs/bind-order-eboot.txt`, which spans more than eboot |
| 673 / 76 / 80 | rows in `symbols/imports.csv` for eboot / libc.elf / libSceFios2.elf |

The residual `747 - 686 = 61` is **not** libc.elf's import count: `imports.csv` gives libc.elf 76.
So the span hypothesis is unconfirmed and the three figures must be reconciled to one partition
before any of them is quoted, exactly as `21,130` and the 652 were.
