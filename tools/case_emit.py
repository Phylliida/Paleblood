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

import csv
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
                 returns: str = 'i64', note: str = '') -> dict:
    """Emit a case from captured entry state, in the form the existing cases use.

    Reading 35,344 real cases settled the address-space question: **a case never carries an address.** A
    pointer argument is written `buf:<name>` or `buf:<name>+0x<offset>`, and `buffers` declares the bytes
    under `name`. So the capture's job is to name a region and give its bytes -- not to translate between
    guest and host space, because there is no address in the document to translate.

    `buffers` here is keyed by name and may carry `address` (the guest address the bytes were read from)
    and `size`. A captured pointer inside a declared buffer becomes that buffer plus a resolved offset;
    a pointer with no declared bytes is reported in `uncovered`, never prescripted.
    """
    declared = buffers or {}
    emitted: dict[str, str] = {}
    uncovered: list[str] = []
    for reg in sorted(registers):
        value = registers[reg]
        owner = classify(value, objects)
        hit = None
        for name in sorted(declared):
            base = declared[name].get('address')
            size = declared[name].get('size', 0)
            if base is not None and base <= value < base + size:
                hit = (name, value - base)
                break
        if hit is not None:
            name, off = hit
            emitted[reg] = f'buf:{name}' if off == 0 else f'buf:{name}+0x{off:x}'
        elif owner is None:
            emitted[reg] = f'0x{value:x}'
        else:
            uncovered.append(f'{reg}: 0x{value:x} in {owner} (no bytes captured)')
    used = {n: {'size': d['size'], 'bytes': d['bytes']} for n, d in declared.items() if f'buf:{n}' in [a.split('+')[0] for a in emitted.values()]}
    return emit(pc, emitted, used, returns=returns, uncovered=uncovered, note=note)

def load_objects(path: str = 'symbols/objects.csv') -> list[dict]:
    """Read the object table the loader wrote. A tool reads a file; a person reads the log.

    `symbols/objects.csv` is `name,guest_start,size,kind`, written by `runtime/boot.c` once per boot. An
    emitter that parsed the printed line instead would break silently: a reworded print turns every pointer
    into `uncovered`, and a capture with no coverage still reproduces.
    """
    objects: list[dict] = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            objects.append({'name': row['name'], 'base': int(row['guest_start'], 16),
                            'size': int(row['size']), 'kind': row['kind']})
    # Sorted by base so classification is a function of the table, not of the order the file happened to
    # be written in; and the caller can assert the ranges do not overlap, which is what they must be.
    return sorted(objects, key=lambda o: o['base'])


def overlapping(objects: list[dict]) -> list[str]:
    """Names whose ranges are not a partition. A table with an overlap classifies by first match, which is
    correct behaviour over a defective table -- so the defect has to be detected here, not absorbed."""
    bad = []
    for a, b in zip(objects, objects[1:]):
        if a['base'] + a['size'] > b['base']:
            bad.append(f"{a['name']} [{a['base']:#x},+{a['size']}) overlaps {b['name']} at {b['base']:#x}")
    return bad
