"""One implementation of the two-directional list rule.

Three lists in this tree must fail in BOTH directions: entries that are live but unlisted, and entries
listed that no longer exist. The extern roster, the DictReader allowlist and derived.json's PENDING set
all want it, and it was being re-typed each time -- which is how a list enforced in one direction becomes
a place a future reader assumes a justification exists.

The shape enforces the property so the author cannot forget it: `compare()` returns both directions and
a caller that prints only one has to discard an argument on purpose.
"""
from __future__ import annotations


def compare(listed, live):
    """(unlisted, stale) as sorted lists. Both directions, always."""
    return sorted(set(live) - set(listed)), sorted(set(listed) - set(live))


def report(listed, live, *, fmt_unlisted, fmt_stale):
    """Problem lines for both directions; empty means the list is exactly the live set."""
    unlisted, stale = compare(listed, live)
    return [fmt_unlisted(x) for x in unlisted] + [fmt_stale(x) for x in stale]
