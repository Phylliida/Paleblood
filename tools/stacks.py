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
    return True


if __name__ == '__main__':
    arm()
    print(f'armed: a stack dump every {DEFAULT_SECONDS:g} s to stderr')
