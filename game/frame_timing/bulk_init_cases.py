#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cases for the bulk initializer and object constructor at 0x01440640 and 0x01440680.

usage: bulk_init_cases.py OUT_DIR

One JSON per case in OUT_DIR/0x<address>/, the layout tools/preflight.py and tools/verify.py want.

0x01440640 copies three 16-byte constants from the image (0x04ccbb20/30/40) to the data block
(0x058b7e60/70/80). Two things about those cases carry the weight:

  * the source constants are PRESET to values that differ from both the file's bytes and the
    destinations. A replacement that bakes the shipped constants in as literals passes a case where
    the source still holds them, so the discriminating cases are the ones where it does not.
  * each destination is written with one 16-byte store, which is what a 16-byte preset of adjacent
    junk plus a 16-byte readback pins. Writing the same values as four separate dwords would leave
    each 4-byte group's bytes identical and still produce a different write record.

0x01440680 stores `0x056fe140 + 0x10` into the object's first qword, the handle rsi into the second
and the dword edx into the third -- 24 bytes of it. The case that matters is the vtable pointer: the
LEA's own target is 0x056fe140 and the value stored is 0x056fe150, so the pointer is checked byte by
byte rather than by "did it change". The handle and the mode are chosen with all four bytes of the
dword distinct, so a replacement that widened or narrowed either store is visible.
"""
import json
import os
import sys

# The three source constants and their destinations, in address order.
CONSTANTS = [
    (0x04CCBB20, 0x058B7E60),
    (0x04CCBB30, 0x058B7E70),
    (0x04CCBB40, 0x058B7E80),
]

# The constructor's object and the value it must store at +0: the LEA target plus its bias.
VECTOR_BASE = 0x056FE140
VECTOR_BIAS = 0x10

# Values that share no byte with the file's own constants or with each other, so a case where the
# function does nothing at all is distinguishable from one that copied.
DISTINCT_SOURCES = [
    bytes.fromhex("112233445566778899aabbccddeeff00"),
    bytes.fromhex("0f1e2d3c4b5a69788796a5b4c3d2e1f0"),
    bytes.fromhex("8000000040400000000000800000803f"),
]

# The junk already sitting in each destination before the call.
PREVIOUS_DESTINATIONS = [
    bytes.fromhex("deadbeefdeadbeefdeadbeefdeadbeef"),
    bytes.fromhex("cafebabecafebabecafebabecafebabe"),
    bytes.fromhex("0123456789abcdeffedcba9876543210"),
]


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = argv[1]

    # 0x01440640: all three copies at once, discriminating sources.
    room = os.path.join(out_dir, "0x01440640")
    os.makedirs(room, exist_ok=True)
    memory = []
    for (source, destination), data, previous in zip(CONSTANTS, DISTINCT_SOURCES, PREVIOUS_DESTINATIONS):
        memory.append({"addr": f"0x{source:08x}", "bytes": data.hex()})
        memory.append({"addr": f"0x{destination:08x}", "bytes": previous.hex()})
    cases = [
        {
            "schema": 1,
            "address": "0x01440640",
            "id": "copies_all_three_constants",
            "args": {},
            "memory": memory,
            "returns": "void",
        },
        # Every source and every destination preset to a value no other one holds, and no source
        # equal to its destination: all three copies have to move bytes, so a replacement that
        # drops one of the three cannot hide behind a destination that already matched.
        {
            "schema": 1,
            "address": "0x01440640",
            "id": "all_six_locations_distinct",
            "args": {},
            "memory": [
                entry
                for i, (source, destination) in enumerate(CONSTANTS)
                for entry in (
                    {"addr": f"0x{source:08x}", "bytes": (bytes([0x10 + i]) * 16).hex()},
                    {"addr": f"0x{destination:08x}", "bytes": (bytes([0x40 + i]) * 16).hex()},
                )
            ],
            "returns": "void",
        },
        # The same, with the destinations already holding the sources' bytes: the copies still
        # happen and change nothing. An implementation that skips a copy it thinks is redundant is
        # not distinguishable here, which is the point -- this case pins that the original does not
        # do that check either.
        {
            "schema": 1,
            "address": "0x01440640",
            "id": "copies_are_unconditional",
            "args": {},
            "memory": [
                entry
                for (source, destination), data in zip(CONSTANTS, DISTINCT_SOURCES)
                for entry in (
                    {"addr": f"0x{source:08x}", "bytes": data.hex()},
                    {"addr": f"0x{destination:08x}", "bytes": data.hex()},
                )
            ],
            "returns": "void",
        },
    ]
    for case in cases:
        with open(os.path.join(room, f"{case['id']}.json"), "w") as handle:
            json.dump(case, handle, indent=1, sort_keys=True)
            handle.write("\n")

    # 0x01440680: the object constructor. Sixteen bytes of object plus the dword at +0x10.
    room = os.path.join(out_dir, "0x01440680")
    os.makedirs(room, exist_ok=True)
    arguments = [
        ("constructs_object", 0x1122334455667788, 0xAABBCCDD),
        # A zero handle and a zero mode: a replacement that writes constants, or that skips a store
        # when the incoming value is already what it would write, shows up here.
        ("constructs_object_zeroed", 0x0000000000000000, 0x00000000),
        # All four dword bytes distinct, so a narrowed or widened mode store moves different bytes.
        ("constructs_object_distinct_mode", 0xDEADBEEFCAFEF00D, 0x01020304),
    ]
    for case_id, handle, mode in arguments:
        case = {
            "schema": 1,
            "address": "0x01440680",
            "id": case_id,
            "args": {"rdi": "buf:object", "rsi": handle, "rdx": mode},
            "buffers": {"object": {"size": 0x18, "bytes": "7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f"}},
            "returns": "void",
        }
        with open(os.path.join(room, f"{case_id}.json"), "w") as handle_out:
            json.dump(case, handle_out, indent=1, sort_keys=True)
            handle_out.write("\n")

    print(f"bulk_init_cases: wrote {len(cases)} cases for 0x01440640 and {len(arguments)} for 0x01440680")
    print(f"  vector stored at +0 must be 0x{VECTOR_BASE + VECTOR_BIAS:08x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
