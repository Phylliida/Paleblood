"""Does a decision id grant anything? LINE-ANCHORED, and only ever on the heading.

`authorised()` already paid for the substring version once: a search for the status word found it in the
PROPOSAL's own prose and authorised a tool on a document nobody approved. `1ab` repeated that hazard by
carrying the word in its body, so this module is written to the repair rather than to the convenience:

  * the id must be matched as a whole token at the start of a heading line
    (`^### <id>.`), so `1ab` can never match `1a` or `1abc`;
  * the status word is read from THAT LINE ONLY, never from the body, so prose that quotes the
    condition cannot grant it;
  * an unknown id, a missing file, or an unreadable heading returns False -- absence refuses.

WHO CALLS THIS, AND HOW: a caller names the authority for its invocation (`--under 1ab`) and consults that
one id. A caller that asks every id and proceeds if any returns True has built a union, and a union of
gated populations read as a sum is a defect this campaign has already paid for once (12,482 = 7,761 +
4,721, two gated sets quoted as one number). Naming the authority turns a wrong pairing into a refusal
instead of a silent grant, and prints `why()` on the failure path, where it is worth the most.

A door with no status set is a complete thing: it answers False for every id, including 1ab, and a
ratification is then a one-line edit whose effect is observable on the next run.
"""

import pathlib
import re

STATUS_WORD = "RATIFIED"
DEFAULT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "decisions.md"


def heading_line(decision_id, text=None):
    """The ONE line that speaks for this id, or None. Whole-token match against the heading only."""
    s = DEFAULT.read_text() if text is None else text
    pat = re.compile(r"^### " + re.escape(decision_id) + r"(?![0-9A-Za-z])")
    for line in s.splitlines():
        if pat.match(line):
            return line
    return None


def grants(decision_id, text=None):
    """True only if the id's own heading line carries the status word. Never a body, never a substring hunt."""
    line = heading_line(decision_id, text)
    if line is None:
        return False
    return STATUS_WORD in line.upper()


def why(decision_id, text=None):
    """The sentence a refusal prints, so a bare False is never mistaken for a missing row."""
    line = heading_line(decision_id, text)
    if line is None:
        return f"{decision_id}: no heading in decisions.md -- absence refuses"
    if grants(decision_id, text):
        return f"{decision_id}: granted by its heading"
    # Name the state the heading actually carries. The old sentence said "no status word"
    # beside a heading reading PROPOSED, NOT IN FORCE: a refusal whose reason contradicts
    # the text it prints teaches its reader to distrust the next one.
    head = line.strip()[:80]
    if "NOT IN FORCE" in line.upper():
        return f"{decision_id}: PROPOSED, NOT IN FORCE -- heading ({head})"
    return f"{decision_id}: heading carries no RATIFIED token -- NOT IN FORCE ({head})"
