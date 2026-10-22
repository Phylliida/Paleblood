"""The approval sheet is the artifact a stranger trusts to say yes, so its commands must run.

This test extracts the fenced `python3 -c` block from docs/approval-request.md, runs it against the real ELF for
every member the sheet tabulates, and asserts the decoded constant and bytes. It also recomputes the member-set
hash the sheet quotes, so a signature that should have expired fails the build at the same moment instead of
quietly staying valid in prose.

The opposite direction to test_install_mode.py: that one reads the real tree and has an expiry date; this one
reads the real tree and *fails* when the expiry arrives.
"""

import hashlib
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHEET = ROOT / "docs" / "approval-request.md"


def sheet_text():
    return SHEET.read_text()


def command_block(text):
    """The first fenced block that invokes python3 -- the one a stranger copies."""
    for block in re.findall(r"```\n(.*?)```", text, re.S):
        if "python3 -c" in block:
            return block.strip()
    raise AssertionError("no fenced python3 block in the approval sheet")


def tabulated_members(text):
    """| `0xADDR` | `bytes` | `K` | rows: the sheet's own examples, so the test cannot drift from the doc."""
    rows = re.findall(r"\| `(0x[0-9a-fA-F]+)` \| `([0-9a-f ]+)` \| `(0x[0-9a-fA-F]+)` \|", text)
    if not rows:
        raise AssertionError("the sheet tabulates no decoded member")
    return rows


class SheetCommandsRun(unittest.TestCase):
    def test_every_tabulated_member_re_derives_from_the_elf(self):
        text = sheet_text()
        block = command_block(text)
        members = tabulated_members(text)
        self.assertGreaterEqual(len(members), 3, "fewer examples than the sheet promises")
        tail = block.rsplit(None, 1)[-1]          # the address baked into the sheet's own command
        self.assertIn(tail, block, "the block must end with an address argument")
        for address, want_bytes, want_k in members:
            cmd = block[: block.rfind(tail)] + address
            run = subprocess.run(["bash", "-c", cmd], cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, "command failed for %s: %s" % (address, run.stderr[-400:]))
            self.assertIn(want_k, run.stdout, "constant drift for %s: %r" % (address, run.stdout))
            self.assertIn(want_bytes, run.stdout, "byte drift for %s: %r" % (address, run.stdout))

    def test_member_set_hash_matches_the_catalog(self):
        text = sheet_text()
        quoted = re.search(r"hashes to `([0-9a-f]{16})", text)
        self.assertIsNotNone(quoted, "the sheet must quote the member-set hash it expires against")
        rows = sorted(
            line.strip()
            for line in (ROOT / "symbols" / "functions.csv").read_text().splitlines()
            if ",leaf_mov_rax" in line
        )
        got = hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16]
        self.assertEqual(quoted.group(1), got,
                         "the member set changed: the sheet's signatures are stale and the sheet must be regenerated")


if __name__ == "__main__":
    unittest.main()
