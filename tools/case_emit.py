"""Emit a case in the schema `verify.py` reads, so an in-game capture is immediately replayable.

The point of this file is that a capture and a case are the same object. `runtime-witnessed` says a body
ran once on an input the game produced; emitting that input as a case turns it into **a differential over
a real input**, which is the closest thing to in-game evidence available without a full in-game
differential. A capture format of its own would be a format nobody replays.

Two rules are encoded rather than documented:

  * **The guest PC is the identifier.** A capture, a ledger row and a replay then share one key, so a
    reader can go from a witness to the case that reproduces it without a lookup table.
  * **What could not be reconstructed is reported, never invented.** A body's arguments come from the
    entry registers; anything the body reads beyond them needs a preset the capture may not have. The
    emitter writes only what it has and lists the rest in `uncovered`, so the replay reports a gap
    instead of a fabricated input that would silently pass.
"""
from __future__ import annotations

import json

SCHEMA = 1


def emit(pc: str, registers: dict[str, str], buffers: dict[str, dict] | None = None,
         returns: str = 'i64', uncovered: list[str] | None = None, note: str = '') -> dict:
    """Build a case dict. `registers` maps a register name to a literal or `buf:<name>`."""
    if not pc.startswith('0x') or len(pc) != 10:
        # Ten characters, like every address in the catalog: a capture keyed by a short address is a
        # key that will not join the ledger.
        raise ValueError(f'pc must be a ten-character 0x address, got {pc!r}')
    case = {'schema': SCHEMA, 'address': pc, 'id': pc, 'returns': returns, 'args': dict(sorted(registers.items()))}
    if buffers:
        case['buffers'] = {k: buffers[k] for k in sorted(buffers)}
    if uncovered:
        case['uncovered'] = sorted(uncovered)
    if note:
        case['note'] = note
    return case


def write(path: str, case: dict) -> None:
    """One case per file, the same layout the repository already uses (one-space indent, sorted keys)."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(case, f, indent=1, sort_keys=False)
        f.write('\n')


def read(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def classify(pointer: int, objects: list[dict]) -> str | None:
    """Which object owns this guest address, or None if no object does.

    `pbboot` maps several objects (`eboot`, `libc.elf`, `libSceFios2.elf`); the harness maps one image.
    A pointer captured inside a non-eboot object therefore names **the same number over different bytes**
    when it is replayed -- the differential would pass and the answer would be about a buffer the game
    never had. So a pointer is written into a case only when its owning object is the one being replayed,
    and everything else is reported.
    """
    for o in objects:
        if o['base'] <= pointer < o['base'] + o['size']:
            return o['name']
    return None


def emit_capture(pc: str, registers: dict[str, int], objects: list[dict],
                 buffers: dict[str, dict] | None = None, replayed: str = 'eboot',
                 returns: str = 'i64') -> dict:
    """Emit a case from captured entry state, reporting every pointer the replay cannot speak for.

    `buffers` is keyed by object-qualified name (`eboot:0x10`) so a caller can supply bytes for the
    addresses it actually reconstructed. Anything named in `uncovered` is a read the replay does not
    cover: a fabricated preset at that number would be the input the game never produced.
    """
    emitted: dict[str, str] = {}
    uncovered: list[str] = []
    for name in sorted(registers):
        value = registers[name]
        owner = classify(value, objects)
        if owner is None:
            emitted[name] = f'0x{value:x}'
        elif owner == replayed:
            key = f'{replayed}:0x{value:x}'
            if buffers and key in buffers:
                emitted[name] = f'buf:{key}'
            else:
                uncovered.append(f'{name}: 0x{value:x} in {owner} (no bytes captured)')
        else:
            uncovered.append(f'{name}: 0x{value:x} in {owner}')
    used = {k: buffers[k] for k in sorted(buffers or {}) if f'buf:{k}' in emitted.values()}
    return emit(pc, emitted, used, returns=returns, uncovered=uncovered)
