"""The one shape a gate's line may take, and the rc it must come from.

Three times now a tool has printed a line whose SHAPE implied a verdict it never ran: `describe()`
formatting while the comparison was decided elsewhere, `extent_line()` rebuilding a relative `symbols/`
beside a compare that had used an absolute one, and `progress.py`'s `parses:` clause computing its own
count while the gate that enforces the count was never invoked. The last one let a raw `csv.DictReader`
through a green commit.

So: a caller passes the rc its check RETURNED, never a count it recomputed. `rc=None` means the check
could not run, and prints `not checked` in the same position -- **a line whose shape implies a verdict it
never ran is worse than silence, because silence at least reads as nothing.**
"""


def gate_line(name, rc, detail=''):
    """`name: ok (detail)` / `name: REFUSED (rc=N) -- detail` / `name: not checked`."""
    if rc is None:
        return f'{name}: not checked'
    if rc == 0:
        return f'{name}: ok ({detail})' if detail else f'{name}: ok'
    return f'{name}: REFUSED (rc={rc}) -- {detail}' if detail else f'{name}: REFUSED (rc={rc})'
