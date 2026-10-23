"""A mutation that cannot fail to mutate.

Three times in one stretch a falsification changed a value that was already at that value and then asserted
a refusal that was not owed: a partial-landing test that zeroed byte 7 of `0x5956678` (which is `0x00`), a
batch check whose "mutation" wrote `status='unknown'` (still landed -- `original` is the only non-landed
status), and, before them, an instrument whose 117 survivors were cases putting the only value at offset 0.
Each one looked like diligence and tested nothing, and each was found by noticing, which is not a mechanism.

`mutate` makes the mistake unrepresentable instead of observable: it refuses when the new value equals the
old one, in the same shape as `atomic_write` refusing to leave its bytes behind. The message names the
offset, the value that was already there, and the fact that nothing would be tested.
"""
import sys


def mutate(data, offset, new, what='buffer'):
    """`data` with one byte replaced -- refusing if it is already that byte."""
    if not 0 <= offset < len(data):
        raise AssertionError(f'mutant at {what}[{offset}] is outside a {len(data)}-byte subject -- '
                             f'a mutation out of range tests nothing and cannot be seen')
    old = data[offset]
    if old == new:
        raise AssertionError(f'mutant at {what}[{offset}] is already {new:#04x} -- nothing to test')
    out = bytearray(data)
    out[offset] = new & 0xff
    return bytes(out)


def mutate_hex(hexstr, offset, new, what='bytes'):
    """The same rule for a case file's `bytes` field, which is hex text and not a buffer."""
    raw = bytes.fromhex(hexstr)
    return mutate(raw, offset, new, what).hex()


def mutate_text(text, old, new, what='source'):
    """The fourth door: a mutant applied to SOURCE TEXT. Same two refusals as the others, plus the
    uniqueness an anchor needs -- a constant that appears twice is two mutants, and silently editing
    the first would be a mutation nobody described. Whole-line anchoring is the caller's job; this
    door refuses only what it can see."""
    assert old != new, f'mutant at {what} is already {new!r} -- nothing to test'
    count = text.count(old)
    assert count == 1, f'mutant at {what}: {old!r} occurs {count} times, not 1 -- ambiguous subject'
    return text.replace(old, new, 1)


def replace_field(row, field, value, what='row'):
    """The same rule for a structured fixture: a field already at `value` is not a mutation."""
    old = row[field]
    if old == value:
        raise AssertionError(f'mutant at {what}.{field} is already {value!r} -- nothing to test')
    row[field] = value
    return row


if __name__ == '__main__':
    # Bare start is part of the contract (gates run with PYTHONPATH deleted and cwd elsewhere): this module
    # is imported by tests and by fixture builders, and a tool with no entry point that exits 0 silently is
    # a tool whose absence looks like success.
    print('mutate: a library, not a command -- import it', file=sys.stderr)
    sys.exit(2)
