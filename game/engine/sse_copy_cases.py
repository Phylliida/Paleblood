#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cases for the four 16-byte slot copiers at 0x00842ba0, 0x00842bd0, 0x02577f80 and 0x025aa050.

usage: sse_copy_cases.py OUT_DIR

One JSON per case in OUT_DIR/0x<address>/, the layout tools/preflight.py and tools/verify.py want.

Each case runs the original on one side and the replacement on the other, so what is checked is where
the 64 copied bytes land and which bytes of an overlapping region they carry. Two things the originals
do are deliberately NOT pinned, because nothing these cases can observe distinguishes them:

  * The order of the four stores. The two-stage members store slot 1 before slot 0 and slot 3 before
    slot 2 (0x02577f80's bytes are load 0,1,2,3 then store 1,0,3,2), and reversing a store pair is
    invisible: the four destination slots never overlap each other, and every one of them is already
    in a register by the first store.
  * The exact bytes of xmm0 and xmm1 at return. Comparing them would need `returns: vec`, and it does
    discriminate -- 0x02577f80 returns with xmm0 holding slot 0 and xmm1 slot 1, the interleaved
    members with different registers -- but xmm is caller-saved and no caller of a void function reads
    it, so pinning it would be pinning a compiler's register allocation rather than the function.

What the overlap cases DO pin is the load-before-store order, and that is the real difference between
the members: 0x02577f80 stages all four loads before any store, so with its destination overlapping
its source it reads pristine bytes, while the interleaved members read back bytes they have just
written. Both directions are generated as separate cases, because they are different situations: with
the destination above the source the interleaved form reads its own output, and with the destination
below the source it reads bytes it has not written yet.

Three shapes carry the rest of the weight:

  * `every_slot_wrong_byte` gives each 16-byte slot a byte that belongs to a different slot. A
    replacement that moved all 64 bytes as one blob in an order the original does not use still
    puts the right bytes at the right offsets, so what this pins is the offset of each move rather
    than the order the moves are issued in.
  * `overlap_*` as described above. Reversing the load order, dropping the staging, or moving a store
    across a load all show up here and nowhere else.
  * `last_slot_moved_only` changes the fourth slot only, with the destination preset to a
    different byte in every position, so a replacement that skipped the fourth move cannot pass by
    leaving bytes that already happened to match.

The register in the first argument carries the source for 0x00842ba0 and the destination for the
other three, so each case names its buffers by role and puts them in the arguments that member
reads. Getting that backwards is not a spelling difference: it copies in the wrong direction.

Every case writes 64 bytes at the destination base. The destination buffer also carries 15 bytes of
preset junk after the copy on the non-overlapping shapes, which is what pins the write extent: a
copy that overran the fourth slot would show up as bytes the original left alone.
"""
import json
import os
import sys

# The four members, in address order, each with the argument that holds its SOURCE.
MEMBERS = [(0x00842BA0, "rdi"), (0x00842BD0, "rsi"), (0x02577F80, "rsi"), (0x025AA050, "rsi")]

SLOT = 16
SLOTS = 4
COPY = SLOT * SLOTS

# The junk after the copied slots at the destination, and the size of the region each source
# buffer holds. The source is larger than the copy so that a run past the fourth slot reads
# defined filler rather than the end of a buffer.
JUNK = bytes(range(0xA0, 0xA0 + 15))
SOURCE_SIZE = 256
DEST_SIZE = COPY + 4096

# The bytes an overlap case starts from. Ascending but not uniform, so a smeared copy is a
# different pattern rather than a plausible-looking subset.
OVERLAP_REGION = bytes((i * 7 + 3) & 0xFF for i in range(COPY + SLOT))
OVERLAP_SHIFT = SLOT


def doc(address, case_id, args, buffers):
    return {
        "schema": 1,
        "address": f"0x{address:08x}",
        "id": case_id,
        "args": args,
        "buffers": buffers,
        "memory": [{"addr": f"buf:{name}", "bytes": buf["bytes"]}
                   for name, buf in sorted(buffers.items())],
        "returns": "void",
    }


def slots_case(address, case_id, source_register, source, destination):
    other = "rsi" if source_register == "rdi" else "rdi"
    args = {source_register: "buf:source", other: "buf:dest"}
    buffers = {
        "source": {"size": SOURCE_SIZE, "bytes": source.hex()},
        "dest": {"size": DEST_SIZE, "bytes": destination.hex()},
    }
    return [doc(address, case_id, args, buffers)]


def overlap_cases(address, source_register):
    """Both arguments point into one buffer, SHIFT bytes apart, once in each direction.

    For the three members whose source is rsi, `dest_below_source` is the case that discriminates:
    rdi is the higher address, so the interleaved form has to load a slot it has not stored into yet
    and reads back its own output, while the staging form has already read every slot. For
    0x00842ba0 the roles are swapped and `dest_above_source` is the discriminating one instead.
    """
    other = "rsi" if source_register == "rdi" else "rdi"
    buffers = {"region": {"size": len(OVERLAP_REGION), "bytes": OVERLAP_REGION.hex()}}
    return [
        doc(address, "overlap_dest_above_source",
            {source_register: "buf:region+0x0", other: f"buf:region+0x{OVERLAP_SHIFT:x}"},
            buffers),
        doc(address, "overlap_dest_below_source",
            {source_register: f"buf:region+0x{OVERLAP_SHIFT:x}", other: "buf:region+0x0"},
            buffers),
    ]


def shapes():
    """The non-overlapping cases: (id, source bytes, destination bytes)."""
    # Each slot's bytes are distinct within the slot, so a move that used the wrong eight-byte half
    # is visible as well as one that used the wrong slot.
    distinct = b"".join(bytes([0x10 + i * SLOT + k for k in range(SLOT)]) for i in range(SLOTS))

    # Each slot holds a byte that belongs to a different slot: the offsets are right, so the value
    # left at each destination offset is what a slot-order mistake breaks.
    rotated = b"".join(bytes([0x10 + ((i + 1) % SLOTS) * SLOT + k for k in range(SLOT)])
                       for i in range(SLOTS))

    uniform = bytes([0x33]) * COPY
    tail = bytes([0x44]) * SLOT

    return [
        ("distinct_slots", distinct, bytes([0x5A]) * DEST_SIZE),
        ("every_slot_wrong_byte", rotated, bytes(DEST_SIZE)),
        ("last_slot_moved_only", uniform[:3 * SLOT] + tail, uniform + JUNK),
        ("zero_source", bytes(COPY), bytes([0x01]) * DEST_SIZE),
        ("read_past_fourth_slot", distinct, bytes([0x77]) * DEST_SIZE),
    ]


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = argv[1]

    for address, source_register in MEMBERS:
        cases = []
        for case_id, source, destination in shapes():
            cases += slots_case(address, case_id, source_register, source, destination)
        cases += overlap_cases(address, source_register)

        directory = os.path.join(out_dir, f"0x{address:08x}")
        os.makedirs(directory, exist_ok=True)
        for i, document in enumerate(cases):
            path = os.path.join(directory, f"{i:02d}_{document['id']}.json")
            with open(path, "w") as f:
                json.dump(document, f, indent=1, sort_keys=True)
        print(f"{address:#010x}: {len(cases)} cases -> {directory}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
