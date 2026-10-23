#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Periodic stack dumps, so a tool that stops returning says where it stopped.

Written six slices ago to diagnose a validator that took 8 m 27 s and never run, then used twice
from the shell to find a regex compile and a line loop that together made check_agnostic unable to
finish. It belongs in the tools, not in my history: a gate armed with this prints its own frame when
it hangs, and the frame names the cause in one line.

    import stacks; stacks.arm()          # every 60 s, to stderr, process keeps running

BB_STACKS_SECONDS overrides the interval. Arming never raises: a diagnostic that can itself be the
failure would be a new defect of the same family.
"""
from __future__ import annotations

import atexit
import faulthandler
import os

DEFAULT_SECONDS = 60.0


def arm(seconds: float | None = None) -> bool:
    """Start periodic dumps; return False if the interpreter declines. Never raises."""
    every = seconds if seconds is not None else float(os.environ.get('BB_STACKS_SECONDS') or DEFAULT_SECONDS)
    try:
        faulthandler.dump_traceback_later(every, repeat=True, exit=False)
    except (RuntimeError, ValueError):
        return False
    # THE TIMER MUST NOT OUTLIVE THE CALLER. repeat=True means a single arm() keeps dumping every `every`
    # seconds for the life of the interpreter, and nothing in this file could stop it -- which is how a run of
    # the suite produced 37 MB of dumps from a process that had already finished the work. atexit covers the
    # normal exit; a caller that keeps running must call cancel() itself.
    atexit.register(cancel)
    return True


def cancel() -> None:
    """Stop periodic dumps. Safe to call when nothing is armed, and safe to call twice."""
    try:
        faulthandler.cancel_dump_traceback_later()
    except (RuntimeError, ValueError):
        pass


if __name__ == '__main__':
    arm()
    print(f'armed: a stack dump every {DEFAULT_SECONDS:g} s to stderr')
