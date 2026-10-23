"""One way to read an address out of a table.

There are five shapes of the same string in this tree: `0x00400020`, `00400020`, `400020`,
`0x400020` and `0x400020` in mixed case, and `ghidra_functions.csv` is zero-padded to eight hex
digits while ladder keys carry no padding at all. Joining two tables on the raw string therefore
works exactly for the tables whose spellings happen to match, and returns None — which reads as an
absent member, not as a failed join — everywhere else.

That has now produced a wrong total three times (the 483 family's 3,864 vs 2,982 B, the board's
+20 vs +62, and a five-member lookup that returned None five times and would have pre-registered
+0 bytes as complete). A count of arrivals is the argument for one helper; the zeros looking like
answers is the argument for importing it everywhere rather than where the author remembers.

Readers are migrated as they are touched; new code imports this. `int(s, 16)` is tolerant of the
`0x` prefix and upper case but not of a missing prefix on a decimal-looking string, so this is the
only place that decides.
"""
import re

_HEX = re.compile(r'^\s*(?:0[xX])?([0-9a-fA-F]+)\s*$')


def parse_address(value) -> int:
    """Decimal int, hex string with or without 0x, any padding, any case -> int."""
    if isinstance(value, int):
        return value
    m = _HEX.match(str(value))
    if m is None:
        raise ValueError(f'not an address: {value!r}')
    return int(m.group(1), 16)


def key(value) -> str:
    """The canonical join key: eight lowercase hex digits, no prefix."""
    return '%08x' % parse_address(value)
