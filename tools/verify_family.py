"""Verify every member of an emitted family, one differential per member, printing the rc VECTOR.

Phase 1 of the record protocol: --record must never be the first time these differentials run, because
source_hash is per defining file and one failing body after 77 recorded makes the family a re-record of 78.
1 is a mismatch, 2 a timeout, 3 a precondition refusal -- three different findings, so an rc per address.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from case_dir import case_dir
from catalogue import read_rows

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAMILY = "chain_deref"
PREFIX = "bb_leaf_chain_deref_"
ELF = os.path.join(ROOT, "..", "data", "bb", "elf", "eboot.elf")
LIB = os.path.join(ROOT, "build-release", "game", "libbbgame.so")


def one(addr):
    """(rc, shape, detail). `shape` names the channels the run actually carried: r=rax, m=mem."""
    case = os.path.join(case_dir(FAMILY), "%08x" % addr, "case.json")
    if not os.path.exists(case):
        return 3, "-", "no case file (a precondition refusal, not a mismatch)"
    # f"{addr:#010x}", never {addr:#x}: the case carries eight nibbles and the harness compares them.
    args = [sys.executable, "-P", os.path.join(HERE, "harness.py"), "--elf", ELF,
            "--case", case, "--address", "%#010x" % addr,
            "--replacement", PREFIX + "%08x" % addr, "--lib", LIB]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr.strip().splitlines() or ["(no output)"])[-1]
        return proc.returncode, "-", tail
    r = json.loads(proc.stdout)
    if "ret" not in r:
        # A fault is a key's absence, not an rc.
        return 0, "nokey", json.dumps({k: r[k] for k in r if k in ("errors", "bad_input", "exit")})[:120]
    shape = ("r" if "rax" in r["ret"] else "-") + ("m" if r.get("writes") is not None else "-")
    return 0, shape, "rax=%s writes=%s" % (r["ret"].get("rax"), len(r["writes"] or []))


def main(argv):
    # read_rows, never a raw csv.DictReader: the gates refuse a second reader of the catalogue, and
    # this file was refused for exactly that on its first green run.
    # read_rows yields TYPED rows and is a GENERATOR: `address` is already an int, so int(x, 0) is a
    # second reading of a value that has already been read.
    rows = list(read_rows(os.path.join(ROOT, "symbols", "chain_family.csv")))
    rcs, shapes, bad = [], {}, []
    for r in rows:
        addr = r["address"] if isinstance(r["address"], int) else int(r["address"], 0)
        rc, shape, detail = one(addr)
        rcs.append(rc)
        shapes[shape] = shapes.get(shape, 0) + 1
        if rc != 0 or shape == "nokey":
            bad.append((addr, rc, shape, detail))
    print("rc vector:", "".join(str(x) for x in rcs))
    print("members %d | zeros %d | rcs %s | shapes %s" % (len(rows), rcs.count(0), sorted(set(rcs)), shapes))
    for addr, rc, shape, detail in bad:
        print("  %#010x -> rc=%s shape=%s %s" % (addr, rc, shape, detail))
    if len(rcs) != len(rows) or rcs.count(0) != len(rows):
        print("family: %d member(s) did not return 0 -- the family is edited BEFORE the ledger hears "
              "about it" % (len(rows) - rcs.count(0)), file=sys.stderr)
        return 1
    print("family: %d/%d rc=0 -- phase 1 green, the record may be taken" % (len(rows), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
