#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Two-sided comparison for a function that has no symbols/functions.csv row yet.

usage: preflight.py SYMBOL ADDRESS CAPTURES [LIB]

tools/verify.py run needs registry rows in both symbols/functions.csv and game/hooks.csv before it
will touch a function, and a row is only meaningful once the implementation is known to agree with
the original. This runs the same comparison as verify.py without the rows: every case in CAPTURES
against the original bytes and against SYMBOL in LIB, reported case by case.

Prints one line per case and a summary; exits nonzero if any case differs or faults. Nothing is
written to symbols/verification.csv -- record a real run with tools/verify.py run once the rows
exist.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import verify  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) not in (4, 5):
        print(__doc__, file=sys.stderr)
        return 2
    symbol, address, captures = argv[1], argv[2], argv[3]
    lib = argv[4] if len(argv) == 5 else os.path.join(verify.ROOT, 'build', 'game', 'libbbgame.so')
    boot = os.environ.get('BB_ELF') or verify.default_elf()
    if not boot:
        print('preflight: no executable: set BB_ELF', file=sys.stderr)
        return 2
    results = verify.run_cases(boot, captures, address, symbol, lib)
    orig = {'schema': verify.SCHEMA, 'address': address, 'cases': results['original']}
    repl = {'schema': verify.SCHEMA, 'address': address, 'cases': results['replacement']}
    summary = verify.compare(orig, repl)
    by_id = {c['id']: c for c in results['original']}
    for c in results['original']:
        if 'fault' in c:
            print(f'  {c["id"]}: ORIGINAL FAULTED: {c["fault"]}')
    for c in results['replacement']:
        if 'fault' in c:
            print(f'  {c["id"]}: REPLACEMENT FAULTED: {c["fault"]}')
    for f in summary['failures']:
        print(f'  {f["case"]}:')
        for d in f['diffs']:
            print(f'      {d}')
        print(f'      original: {by_id.get(f["case"], {}).get("ret")}')
    print(f'{symbol} at {address}: {summary["passed"]}/{summary["cases"]} match, '
          f'{summary["failed"]} differ')
    return 1 if summary['failed'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
