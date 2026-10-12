#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cases for the three one-shot static guards at 0x014405b0, 0x014405e0 and 0x01440610.

usage: static_guard_cases.py OUT_DIR

Each writes one JSON per case into OUT_DIR/0x<address>/, the layout tools/preflight.py and
tools/verify.py expect.

The guard and the pointer are separate fields of one object (guard at +0, pointer at +8), so the
cases set them independently. The interesting one is `guard_high_bytes`: the guard's low byte is
zero while the rest of its eight bytes are not, which the original -- reading a single byte with
CMP BYTE PTR [rax], 0x0 -- treats as uninitialized. An implementation that tests the whole qword
takes the early return there instead, and that is the only case that catches it. The same case also
pins the *write* width: the guard is written with a full MOV QWORD PTR [rax], 0x1, so the seven junk
bytes are cleared by the store, and an implementation that stores one byte leaves them.
"""
import json
import os
import sys

STORAGE_BIAS = 0x10

# guard, pointer, storage base: the three statics, in address order.
GUARDS = [
    (0x014405B0, 0x05AC59B8, 0x05AC59B0, 0x056B4840),
    (0x014405E0, 0x05AC59C8, 0x05AC59C0, 0x056B4890),
    (0x01440610, 0x05AC59D8, 0x05AC59D0, 0x056B47F0),
]

# The pointer's initial value in the cases that take the initializing path. It is a sentinel, not
# the file's value, so that a case where the function does *nothing* is distinguishable from one
# where it wrote the same bytes that were already there.
SENTINEL = 0x1122334455667788

# A value that must survive untouched on the early-return path.
PREVIOUS = 0x00AABBCCDDEEFF11


def case(address, case_id, guard_bytes, pointer, returns="void"):
    return {
        "schema": 1,
        "address": f"0x{address:08x}",
        "id": case_id,
        "args": {"rdi": 0},
        "memory": [
            {"addr": f"0x{guard_bytes[0]:08x}", "bytes": guard_bytes[1]},
            {"addr": f"0x{pointer[0]:08x}", "bytes": pointer[1]},
        ],
        "returns": returns,
    }


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = argv[1]

    for address, guard, pointer, storage in GUARDS:
        cases = []

        # The guard is set: the function returns immediately and touches nothing. The pointer holds
        # a wrong value here, so a run that "repairs" it is a visible failure rather than a no-op.
        cases.append(case(address, "guard_set_returns_early",
                          (guard, "01"), (pointer, f"{PREVIOUS:016x}")))

        # The guard's low byte is zero, so the storage is bound and the guard becomes 1.
        cases.append(case(address, "guard_clear_binds",
                          (guard, "00"),
                          (pointer, f"{SENTINEL:016x}")))

        # Low byte zero, upper seven bytes junk: still a byte read, so still uninitialized.
        cases.append(case(address, "guard_high_bytes_junk_low_clear",
                          (guard, "00ffffffffffffff"),
                          (pointer, f"{SENTINEL:016x}")))

        # Low byte zero, and a pointer that already holds the value to be stored: the pointer bytes
        # must not move, while the guard still flips. This separates "wrote the value" from "wrote
        # nothing", which no other case does.
        cases.append(case(address, "guard_clear_pointer_already_bound",
                          (guard, "00"),
                          (pointer, f"{storage + STORAGE_BIAS:016x}")))

        # A guard of 0xff, the value the original's own initializer would leave.
        cases.append(case(address, "guard_all_ones_returns_early",
                          (guard, "ff"), (pointer, f"{PREVIOUS:016x}")))

        directory = os.path.join(out_dir, f"0x{address:08x}")
        os.makedirs(directory, exist_ok=True)
        for i, doc in enumerate(cases):
            path = os.path.join(directory, f"{i:02d}_{doc['id']}.json")
            with open(path, "w") as f:
                json.dump(doc, f, indent=1, sort_keys=True)
        print(f"{address:#010x}: {len(cases)} cases -> {directory}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
