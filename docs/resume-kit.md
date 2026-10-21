# Resume kit

Literal commands. `-P` and `PYTHONPATH` are not decoration: without them Capstone
and the tools fail in ways that look like mismatches (see QUIRKS).

    # Python (capstone 5.0.7; .operands needs detail=True)
    ../.venvs/paleblood/bin/python3

    # Suite. NO `-t .` -- test/ has no __init__.py, so `-t .` raises ImportError.
    ../.venvs/paleblood/bin/python3 -m unittest discover -s test

    # One test file
    ../.venvs/paleblood/bin/python3 -m unittest discover -s test -p 'test_install_mode.py' -v

    # CTest. The build dir is build-release; configure carries the interpreter.
    cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release \
          -DPython3_EXECUTABLE=$PWD/../.venvs/paleblood/bin/python3
    cmake --build build-release -j
    ctest --test-dir build-release
    # progress_readme is Not Run: it has a name and no `command` field in the
    # CTest JSON -- a missing registration, not a red gate.

    # Validator: PYTHONPATH=tools, and NEVER read $? after a pipe.
    PYTHONPATH=tools ../.venvs/paleblood/bin/python3 -P tools/validate_functions.py >/tmp/v.txt 2>&1; echo "rc=$?"; tail -2 /tmp/v.txt

    # Record evidence (host or hook replacement, resolved by
    # verification.replacement_symbol). Banner is on stderr: never 2>&1 into the JSON.
    PYTHONPATH=tools ../.venvs/paleblood/bin/python3 -P tools/verify.py run \
        --function NAME --captures ../data/cases/<family>/<address> \
        --elf ../data/bb/elf/eboot.elf --lib build-release/game/libbbgame.so --record edge

    # Join claimed status against recorded evidence. rc=1 means a status claim
    # has no ledger row -- or that the ledger could not be read at all.
    PYTHONPATH=tools ../.venvs/paleblood/bin/python3 -P tools/progress.py --join

## Baselines carry their commit

A number without a SHA beside it is a remembered number wearing a measured
number's clothes. Measured at `1919c21` and `bc9067b`, identically:

    ledger rows - functions rows = 99   (1838-1739, 1839-1740)

The long-carried `101` was remembered, not measured. The invariant held the
whole time; the baseline did not.

## A negative test asserts its own precondition

A counterexample that never constructs the condition it tests passes by
testing nothing. Assert the deletion happened and the evidence is gone,
*then* assert the check refuses. Same failure as reading `$?` instead of the
message, one level up.
