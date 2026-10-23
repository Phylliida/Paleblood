"""Run the whole-tree suite in a child and require it to reach a VERDICT.

A unittest run that ends without its terminal line -- `Ran N tests` and `OK`/`FAILED` -- has not passed: it has
stopped. The distinction is not pedantic here. One full run of this suite produced 37 MB of repeating
faulthandler dumps and no summary at all, and `grep -c '^FAIL'` over it returned 0, which reads exactly like a
clean tree. A run with no verdict is a run nobody can quote.

So the absence of a terminal line is reported as `NO VERDICT` in the verdict's own slot, with its own exit code,
and never folded into a pass. Exit codes: 0 ok · 1 tests failed · 2 no verdict · 3 could not start.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERDICT = re.compile(r'^(Ran \d+ tests? in [\d.]+s|OK|FAILED)', re.MULTILINE)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `argv[0] if argv else default` is not enough: an EMPTY first argument passes the truthiness test in
    # the caller's head and fails argparse as `-p: expected one argument`, which is how a 302-byte usage
    # message became the whole log of a thirteen-minute run. `or` is the operator that means "or else".
    pattern = (argv[0] if argv else '') or 'test_*.py'
    out = ROOT / 'build-release' / 'suite.log'
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault('PYTHONPATH', 'tools:.')
    child = subprocess.run([sys.executable, '-P', '-m', 'unittest', 'discover', '-s', 'test', '-p', pattern],
                           cwd=str(ROOT), env=env, capture_output=True, text=True)
    text = child.stderr + child.stdout
    out.write_text(text)
    verdicts = VERDICT.findall(text)
    tail = [line for line in text.splitlines() if line.strip()][-3:]
    print('suite: child rc=%d, %d terminal line(s), log %s' % (child.returncode, len(verdicts), out.relative_to(ROOT)))
    for line in tail:
        print('  ' + line[:160])
    if not verdicts:
        print('suite: NO VERDICT -- the child stopped without "Ran N tests" or OK/FAILED. '
              'This is not a pass, and a zero count of FAIL lines is not evidence of anything.')
        return 2
    if child.returncode == 0:
        return 0
    print('suite: FAILED -- rc=%d; failures are in %s' % (child.returncode, out.relative_to(ROOT)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
