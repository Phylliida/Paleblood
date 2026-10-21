#!/usr/bin/env python3
"""Generate the one-shot guard family: 1,117 catalog entries, three behaviours.

The body is the compiler's function-local-static guard, forty-one bytes and always the same
nine instructions:

    lea  rax, [rip + A]        ; the guard, also the byte read one instruction later
    cmp  byte ptr [rax], 0
    jne  done
    lea  rcx, [rip + B]        ; the storage base
    add  rcx, 0x10             ; the value stored is the base plus sixteen
    lea  rdx, [rip + C]        ; the pointer beside the guard
    mov  qword ptr [rdx], rcx
    mov  qword ptr [rax], 1    ; the guard is read one byte wide and written eight
done:
    ret

game/frame_timing/static_guard.cpp already implements this shape as bind_static<Guard, Pointer,
Storage> for the first three members. This tool finds every other member in the catalog partition,
refuses anything that does not match all nine instructions and the five invariants, and can append
rows, hook rows, wrappers and case directories.

Three facts decided the design:

* The displacement in each `lea` is relative to the next instruction, so two members with the same
  guard, pointer and storage have different bytes. Byte identity is not the family test; the
  instruction sequence plus the resolved addresses is.
* All 1,117 members resolve to three (guard, storage, pointer) triples. They are one guard per
  translation unit for three statics, not 1,117 different statics. The burndown gains entries; the
  information gain is three. Say so wherever this is reported.
* A function shorter than fourteen bytes cannot be hooked (QUIRKS.md), so the family is filtered on
  size before anything else. The earlier attempt at a 3,664-member family of four- to eight-byte
  bodies was rejected by tools/validate_functions.py for exactly this reason.

`--scan` writes nothing. `--write` validates its own output and restores the tree if a checker
refuses, because a generator that does not run the checker on its output can write an invalid tree
and did, once.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    from capstone.x86 import X86_OP_MEM, X86_REG_RIP
except ImportError:  # pragma: no cover
    sys.exit('static_guard_gen: capstone is required (../.venvs/paleblood/bin/python3)')

ROOT = Path(__file__).resolve().parent.parent
PARTITION = ROOT / 'symbols' / 'ghidra_functions.csv'
FUNCTIONS = ROOT / 'symbols' / 'functions.csv'
ORIGINS = ROOT / 'symbols' / 'replacement_origins.csv'
HOOKS = ROOT / 'game' / 'hooks.csv'
SOURCE = ROOT / 'game' / 'frame_timing' / 'static_guard.cpp'
CASES = ROOT.parent / 'data' / 'cases' / 'static_guard'

CODE_BIAS = 0x3FC000   # file offset = guest - CODE_BIAS; derived from both PT_LOADs, off - vaddr = 0x4000
SIZE = 41
SYSTEM = 'frame_timing'
BIAS = 0x10
GUARD_WRITE = 1
HOOK_MINIMUM = 14      # QUIRKS.md: the hook is a 14-byte absolute jump

SHAPE = ['lea', 'cmp', 'jne', 'lea', 'add', 'lea', 'mov', 'mov', 'ret']


class Refusal(Exception):
    pass


def image_path() -> Path:
    path = Path(os.environ.get('BB_IMAGE', ROOT.parent / 'data' / 'bb' / 'elf' / 'eboot.elf'))
    if not path.is_file():
        raise Refusal(f'image unavailable: {path}; set BB_IMAGE')
    return path


def parse_body(md: Cs, blob: bytes, address: int) -> dict:
    """The three resolved addresses, or a Refusal naming which invariant failed."""
    raw = blob[address - CODE_BIAS:address - CODE_BIAS + SIZE]
    if len(raw) != SIZE:
        raise Refusal('truncated body')
    instructions = list(md.disasm(raw, address))
    if [item.mnemonic for item in instructions] != SHAPE:
        raise Refusal('not the nine-instruction guard shape: '
                      + ' '.join(item.mnemonic for item in instructions))
    if sum(item.size for item in instructions) != SIZE:
        raise Refusal('instructions do not sum to the declared size')
    first, compare, branch, storage_lea, add, pointer_lea, store, guard_store, _ = instructions
    if first.op_str.split(',')[0].strip() != 'rax':
        raise Refusal('first lea does not target rax')
    if compare.op_str.split(',')[0].strip() != 'byte ptr [rax]' or compare.operands[1].imm != 0:
        raise Refusal('guard is not compared as one byte against zero')
    if branch.operands[0].imm != address + SIZE - 1:  # the ret, which is the last byte
        raise Refusal('branch does not leave to the return')
    if storage_lea.op_str.split(',')[0].strip() != 'rcx' or add.op_str.split(',')[0].strip() != 'rcx':
        raise Refusal('storage address is not built in rcx')
    if add.operands[1].imm != BIAS:
        raise Refusal(f'storage bias is {add.operands[1].imm:#x}, want {BIAS:#x}')
    if pointer_lea.op_str.split(',')[0].strip() != 'rdx':
        raise Refusal('pointer address is not built in rdx')
    if store.op_str.split(',')[0].strip() != 'qword ptr [rdx]' or store.op_str.split(',')[1].strip() != 'rcx':
        raise Refusal('pointer slot is not written from rcx, whole eight bytes')
    if guard_store.op_str.split(',')[0].strip() != 'qword ptr [rax]' or guard_store.operands[1].imm != GUARD_WRITE:
        raise Refusal('guard is not written whole with one')
    leas = [item.operands[1] for item in (first, storage_lea, pointer_lea)]
    if any(item.type != X86_OP_MEM or item.mem.base != X86_REG_RIP for item in leas):
        raise Refusal('an address is not rip-relative')
    guard = leas[0].mem.disp + first.address + first.size
    storage = leas[1].mem.disp + storage_lea.address + storage_lea.size
    pointer = leas[2].mem.disp + pointer_lea.address + pointer_lea.size
    if pointer != guard - 8:
        raise Refusal(f'pointer {pointer:#x} is not eight bytes below guard {guard:#x}')
    return {'guard': guard, 'storage': storage, 'pointer': pointer}


def partition(md: Cs, blob: bytes) -> tuple[list[dict], dict]:
    """Every 41-byte catalog entry that parses, and a census of the refusals."""
    members, refused, seen = [], {}, set()
    with io.open(PARTITION, newline='') as handle:
        for row in csv.DictReader(handle):
            if int(row['size']) != SIZE:
                continue
            address = int(row['address'], 16)
            if address in seen:
                raise Refusal(f'duplicate partition address {row["address"]}')
            seen.add(address)
            try:
                body = parse_body(md, blob, address)
            except Refusal as error:
                reason = str(error).split(':')[0]
                refused[reason] = refused.get(reason, 0) + 1
                continue
            triple = (body['guard'], body['storage'], body['pointer'])
            members.append({'address': address, 'key': f'0x{address:08x}', 'size': SIZE,
                            'triple': triple, **body})
    return members, refused


def registered() -> dict[int, str]:
    with io.open(FUNCTIONS, newline='') as handle:
        return {int(row['address'], 16): row['name'] for row in csv.DictReader(handle)}


def templates(md: Cs, blob: bytes) -> dict[tuple, int]:
    """One already-registered member per triple, whose case directory this tool clones.

    Discovered by parsing the members already in the ledger rather than naming them here: tools/
    may carry no game address (tools/check_agnostic.py), and a table of three literals would be a
    second copy of facts the ledger already holds.
    """
    out = {}
    with io.open(FUNCTIONS, newline='') as handle:
        for row in csv.DictReader(handle):
            if not row['name'].startswith(f'{SYSTEM}_static_guard_'):
                continue
            address = int(row['address'], 16)
            body = parse_body(md, blob, address)
            directory = CASES / f'0x{address:08x}'
            if not directory.is_dir():
                raise Refusal(f'template case directory missing: {directory}')
            triple = (body['guard'], body['storage'], body['pointer'])
            out.setdefault(triple, address)
    if not out:
        raise Refusal('no registered member of this family to take a template from')
    return out


def wrapper(member: dict) -> str:
    address = member['address']
    return (f'\nextern "C" void bb_{SYSTEM}_static_guard_{address:08x}()\n'
            f'{{\n'
            f'    bind_static<guard_of_{address:08x}, pointer_of_{address:08x}, '
            f'storage_of_{address:08x}>();\n'
            f'}}\n')


def constants(member: dict) -> str:
    address = member['address']
    return (f'\nconstexpr std::uint32_t guard_of_{address:08x} = 0x{member["guard"]:08x};\n'
            f'constexpr std::uint32_t pointer_of_{address:08x} = 0x{member["pointer"]:08x};\n'
            f'constexpr std::uint32_t storage_of_{address:08x} = 0x{member["storage"]:08x};\n')


def write_cases(members: list[dict], template_by_triple: dict[tuple, int]) -> int:
    written = 0
    for member in members:
        triple = (member['guard'], member['storage'], member['pointer'])
        template = template_by_triple.get(triple)
        if template is None:
            raise Refusal(f'{member["address"]:#x}: no template cases for triple {triple}')
        source = CASES / f'0x{template:08x}'
        target = CASES / f'0x{member["address"]:08x}'
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(source.glob('*.json')):
            case = json.loads(path.read_text())
            if case.get('address', '').lower() != f'0x{template:08x}':
                raise Refusal(f'{path}: address field does not match its directory')
            case['address'] = f'0x{member["address"]:08x}'
            (target / path.name).write_text(json.dumps(case, indent=1, sort_keys=True))
            written += 1
    return written


def merge_rows(path: Path, header: list[str], rows: list[list[str]]) -> str:
    with io.open(path, newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != header:
            raise Refusal(f'{path}: header is {reader.fieldnames}, want {header}')
        existing = list(reader)
    merged = {row['address']: row for row in existing}
    for row in rows:
        if row[0] in merged:
            raise Refusal(f'{path}: {row[0]} is already present')
        merged[row[0]] = dict(zip(header, row))
    ordered = sorted(merged.values(), key=lambda row: int(row['address'], 16))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator='\n')
    writer.writeheader()
    writer.writerows(ordered)
    return buffer.getvalue()


TRANSIENT = "is 'original', only replaced, edge-verified or verified functions are hooked"


def check(path: Path, command: list[str], allow: str = '') -> None:
    """Refuse unless the checker passes, or fails on exactly the named transient class.

    verify.py resolves a replacement through game/hooks.csv, and validate_functions.py forbids a
    hooks row on an 'original' row. A newly generated member therefore passes through a state where
    both cannot hold: the hook exists and the status has not been flipped by --record yet. The
    narrow allowance below is that state and nothing else -- any other error refuses and restores.
    """
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            env={**os.environ, 'PYTHONPATH': 'tools'})
    lines = [line for line in (result.stdout + result.stderr).splitlines() if line.strip()]
    if allow:
        residue = [line for line in lines if allow not in line]
        if residue:
            sys.stderr.write('\n'.join(residue) + '\n')
            raise Refusal(f'{path} rejected by {command[0]}: {len(residue)} errors beyond the '
                          'expected transient status/hook state')
        if lines:
            sys.stderr.write(f'{path}: {len(lines)} transient status/hook errors, cleared by '
                             f'--record\n')
        return
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise Refusal(f'{path} rejected by {command[0]}')


def main(argv: list[str]) -> int:
    """Three passes over one family, because each answers a different question.

    --scan   what is there, and what does it resolve to
    --write  catalog rows (status original), C++ bodies, case directories
    --hooks  hook rows, only for members registered and still original: the state between --write
             and --record, which is the only window in which verify.py can resolve a replacement
             for a member validate_functions.py will not yet let be hooked
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan', action='store_true', help='report the family, write nothing')
    parser.add_argument('--write', action='store_true', help='append rows, bodies and case files')
    parser.add_argument('--hooks', action='store_true', help='append hook rows for waiting members')
    parser.add_argument('--limit', type=int, default=0, help='cap the members touched by a pass')
    args = parser.parse_args(argv)
    if not (args.scan or args.write or args.hooks):
        parser.error('choose --scan, --write or --hooks')

    blob = image_path().read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    members, refused = partition(md, blob)
    template_by_triple = templates(md, blob)
    with io.open(FUNCTIONS, newline='') as handle:
        status = {row['address']: row['status'] for row in csv.DictReader(handle)}
    with io.open(HOOKS, newline='') as handle:
        hooked = {row['address'] for row in csv.DictReader(handle)}

    triples: dict[tuple, list[int]] = {}
    for member in members:
        triples.setdefault((member['guard'], member['storage'], member['pointer']), []).append(
            member['address'])
    registered = [member for member in members if member['key'] in status]
    unregistered = [member for member in members if member['key'] not in status]
    print(f'members: {len(members)} of 41-byte entries; refused: {refused or "none"}')
    print(f'distinct triples: {len(triples)}')
    for triple, addresses in sorted(triples.items(), key=lambda item: -len(item[1])):
        print(f'  guard 0x{triple[0]:08x} pointer 0x{triple[2]:08x} storage 0x{triple[1]:08x}'
              f'  {len(addresses)} copies  first 0x{min(addresses):08x}')
    print(f'registered: {len(registered)}; unregistered: {len(unregistered)}')
    if args.scan:
        return 0

    if args.write:
        chosen = unregistered[:args.limit] if args.limit else unregistered
        if not chosen:
            print('no unregistered member to add')
            return 0
        untemplated = [member for member in chosen if member['triple'] not in template_by_triple]
        if untemplated:
            raise Refusal(f'{len(untemplated)} members have no template case set, first '
                          f'{untemplated[0]["key"]}')
        rows = [[member['key'], str(SIZE), f'{SYSTEM}_static_guard_{member["address"]:08x}', SYSTEM,
                 'original',
                 f'Binds the static vtable pointer at 0x{member["pointer"]:08x} to storage '
                 f'0x{member["storage"]:08x} + 0x10 when the guard byte at 0x{member["guard"]:08x} '
                 'is clear, then sets it; one guard per translation unit, sharing '
                 'static_guard.cpp'] for member in chosen]
        staged = {FUNCTIONS: merge_rows(FUNCTIONS,
                                       ['address', 'size', 'name', 'system', 'status', 'notes'], rows),
                  ORIGINS: merge_rows(ORIGINS, ['address', 'origin'],
                                      [[m['key'], 'generated'] for m in chosen])}
        source = SOURCE.read_text()
        insertion = source.index('\n}  // namespace')
        if insertion < 0:
            raise Refusal(f'{SOURCE}: anonymous namespace not found')
        staged[SOURCE] = (source[:insertion] + ''.join(constants(m) for m in chosen) + source[insertion:]
                          + ''.join(wrapper(m) for m in chosen))
        apply(staged, lambda: write_cases(chosen, template_by_triple), chosen,
              [(FUNCTIONS, [sys.executable, '-P', 'tools/validate_functions.py'], ''),
               (ORIGINS, [sys.executable, '-P', 'tools/validate_functions.py'], ''),
               (SOURCE, [sys.executable, '-P', 'tools/check_readable.py'], '')])
        return 0

    # The hook comes after the status flip, not before it: validate_functions.py refuses a hooks
    # row for a function still at 'original', and verify.py refuses to run a replacement that has
    # no hooks row. So the order is write -> (session flips) -> hooks -> record, and a member is
    # waiting for its hook row when it is past 'original' and not yet hooked. An earlier version
    # treated that state as an anomaly and skipped 1,111 members that were waiting exactly as
    # designed.
    waiting = [member for member in registered if status[member['key']] != 'original'
               and member['key'] not in hooked]
    chosen = waiting[:args.limit] if args.limit else waiting
    if not chosen:
        print('no member is waiting for a hook row')
        return 0
    rows = [[member['key'], f'bb_{SYSTEM}_static_guard_{member["address"]:08x}', SYSTEM]
            for member in chosen]
    staged = {HOOKS: merge_rows(HOOKS, ['address', 'replacement', 'system'], rows)}
    apply(staged, lambda: 0, chosen,
          [(HOOKS, [sys.executable, '-P', 'tools/validate_functions.py'], '')])
    return 0


def apply(staged: dict, extra, members: list[dict], checks: list[tuple]) -> None:
    """Write, check, and restore on refusal. A generator that cannot undo is a generator that
    trusts itself, which is how an invalid tree got written once."""
    backup = Path(tempfile.mkdtemp(prefix='static_guard_gen.'))
    for path in staged:
        shutil.copy2(path, backup / path.name)
    directories = [CASES / member['key'].replace('0x', '0x') for member in members]
    try:
        for path, text in staged.items():
            path.write_text(text)
        count = extra()
        for path, command, allow in checks:
            check(path, command, allow=allow)
        print(f'wrote {len(members)} members and {count} case files')
    except BaseException:
        for path in staged:
            shutil.copy2(backup / path.name, path)
        for directory in directories:
            shutil.rmtree(directory, ignore_errors=True)
        sys.stderr.write('static_guard_gen: restored the tree\n')
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Refusal as refusal:
        sys.exit(f'static_guard_gen: {refusal}')
