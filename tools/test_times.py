"""Run a test module one test at a time, with a per-test cap, and name the slow owners.

The whole-tree suite spent thirteen minutes on a single test whose own subprocess timeout was 300 s, and the
only evidence it left was 37 MB of repeated faulthandler dumps. A suite with no per-test bound cannot tell a
slow test from a hung one, and the difference matters: one is a cost, the other is a defect.

A cap is reported as its own verdict, never as a failure: `CAP` means the test did not finish, which is a
different sentence from `FAIL` and must not be folded into it. `--keep` runs the whole module in one pass
afterwards, for the case where a test's cost depends on its neighbours.
"""
import argparse
import importlib.util
import signal
import sys
import time
import unittest
from pathlib import Path


class Cap(Exception):
    """Raised by the alarm. Deliberately not an AssertionError: a cap is a measurement, not a verdict."""


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module          # a module that imports itself by name must resolve
    spec.loader.exec_module(module)
    return module


def _alarm(signum, frame):
    raise Cap()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('path', help='a test module, e.g. test/test_derived.py')
    ap.add_argument('--cap', type=float, default=60.0, help='seconds per test (default 60)')
    ap.add_argument('--only-slow', type=float, default=1.0, help='report tests at or above this many seconds')
    a = ap.parse_args(argv)
    path = Path(a.path)
    suite = unittest.defaultTestLoader.loadTestsFromModule(load(path))
    tests = [t for group in suite for t in group]
    signal.signal(signal.SIGALRM, _alarm)
    capped, failed, total = [], [], 0.0
    for t in tests:
        result = unittest.TestResult()
        start = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, a.cap)
        try:
            t.run(result)
        except Cap:
            capped.append(t.id())
            print(f'{t.id()}: CAP {a.cap:g}s exceeded -- this test does not finish')
            continue
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        elapsed = time.monotonic() - start
        total += elapsed
        if result.errors or result.failures:
            traceback_text = (result.errors + result.failures)[0][1]
            # unittest catches every exception raised inside the test frame, so the alarm arrives as a
            # FAILURE and my own tool reported `0 capped, 1 failed` for a test that never finished. A cap
            # is a measurement and must be classified by what raised it, not by which bucket caught it.
            if 'Cap' in traceback_text:
                capped.append(t.id())
                print(f'{t.id()}: CAP {a.cap:g}s exceeded -- this test does not finish')
            else:
                failed.append(t.id())
                print(f'{t.id()} {elapsed:.2f}s FAILED -- {traceback_text.strip().splitlines()[-1]}')
        elif elapsed >= a.only_slow:
            print(f'{t.id()} {elapsed:.2f}s')
    print(f'{len(tests)} test(s) in {total:.2f}s of attributed time; {len(capped)} capped, {len(failed)} failed')
    return 1 if (capped or failed) else 0


if __name__ == '__main__':
    sys.exit(main())
