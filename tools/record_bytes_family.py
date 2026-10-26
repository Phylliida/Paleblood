"""Record a byte-evidence family: digest it, refuse on any mismatch, derive `source`, sort tables.

`record_many` derives nothing -- it accepted 793 rows whose `source` was a tool name where a source
hash belongs, and `check_pins` called all 793 stale. A bulk writer that trusts its caller is a guard
on the input that walked away, so this writer computes what it can and refuses when it cannot:

  * the digest comes from `check_asm_bytes.py`, run as a subprocess, parsed strictly;
  * rc != 0 or matched != members refuses, before a single row is written;
  * `source` is `verification.source_hash()` per function, and an empty hash refuses;
  * address-keyed tables are sorted after the flip, because the append is what breaks the order.

Batching (`--batch N`) exists for families big enough that one digest cannot localise a failure:
each batch carries its own digest, so a bad member decays its batch and names it. Rows still cannot
be cherry-picked inside a batch.
"""
import argparse
import csv
import datetime
import io
import os
import subprocess
import sys
import tempfile

import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blocks as B
import leaf_family_census as C

from capstone.x86_const import (X86_OP_IMM, X86_OP_MEM, X86_REG_EIP, X86_REG_FS,
                                X86_REG_GS, X86_REG_RIP)

TRAPS = frozenset({
    'int', 'int1', 'int3', 'into', 'ud0', 'ud1', 'ud2', 'syscall', 'sysenter', 'sysret',
    'sysexit', 'iret', 'iretd', 'iretq', 'hlt', 'in', 'out', 'invd', 'wbinvd', 'cli', 'sti',
    'clts', 'swapgs', 'wrfsbase', 'wrgsbase', 'rdmsr', 'wrmsr', 'lgdt', 'lidt', 'lldt', 'ltr',
    'vmcall', 'vmrun',
})
import atomicio
import install_mode
import progress as P
import verification as V

def _write_rows(path, fields, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    atomicio.atomic_write(path, buf.getvalue())


def _sort_address_keyed_file(path):
    """Sort one table in place, atomically, and only when the order actually changes.

    `open(path, 'w')` truncates at the open: a sort that raises after the first row has already
    destroyed the table it was sorting. `TABLES` used to name this population beside this loop and
    was read by nothing; the loop is the population now.
    """
    with open(path, newline='') as f:
        rd = csv.DictReader(f)
        rows = list(rd)
        fields = rd.fieldnames
    ordered = sorted(rows, key=lambda r: int(r['address'], 16))
    if ordered == rows:
        return False
    _write_rows(path, fields, ordered)
    return True


def sort_address_keyed(root):
    # The mode table has one writer, and it sorts; these two are sorted here because their
    # writers are this file's own.
    for name in ('functions.csv', 'replacement_origins.csv'):
        _sort_address_keyed_file(os.path.join(root, 'symbols', name))
    install_mode.sort_host(root)


def digest(root, lib, elf, members):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        for m in members:
            # the digest tool resolves a SYMBOL, and the harness prepends `bb_`; the ladder name
            # does not carry it, so the writer adds it here rather than in the table
            f.write(f'bb_{m["function"]} {m["address"]} {m["size"]}\n')
        path = f.name
    try:
        r = subprocess.run([sys.executable, '-P', os.path.join('tools', 'check_asm_bytes.py'),
                            '--lib', lib, '--elf', elf, '--digest-members', path],
                           capture_output=True, text=True)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise SystemExit(f'refused: digest rc={r.returncode}\n{r.stdout}{r.stderr}')
    f = dict(tok.split('=', 1) for tok in r.stdout.split() if '=' in tok)
    if int(f['members']) != len(members) or int(f['matched']) != len(members):
        raise SystemExit(f'refused: only {f["matched"]} of {f["members"]} are byte-identical '
                         f'({len(members)} asked for) -- a row citing this digest would claim '
                         'equality it does not have')
    return f['digest']


def assert_no_control_flow(members) -> None:
    """The byte tier is legal for ONE basic block with no branch, no loop and no call.

    Above that, a byte-identical body is "ship the original": behaviour preserved, nothing
    decompiled, rows rising while the goal does not. Decided from the bytes by tools/blocks.py,
    never by judgement. See docs/decisions.md 1h.
    """
    md = open(C.ELF, 'rb').read()
    for m in members:
        c = B.census(md, int(m['address'], 16), int(m['size']))
        if c['decoded'] != c['size'] or c['unplaced']:
            raise SystemExit(f"refused: {m['function']} does not decode exactly: "
                             f"{c['decoded']}/{c['size']} B decoded, {c['unplaced']} unplaced target(s)")
        if c['blocks'] != 1 or c['calls']:
            raise SystemExit(f"refused: {m['function']} is {c['blocks']} block(s) with {c['calls']} "
                             f"call(s): byte tier is single-block only (decisions.md 1h)")


_MD = None
_CS = None


def _ctx():
    """One read of the ELF and one Capstone handle for the whole process: a per-member `open` is
    4,034 x 42 MB of I/O for the band, which is a filter that never finishes rather than a slow one."""
    global _MD, _CS
    if _MD is None:
        import capstone
        _MD = open(C.ELF, 'rb').read()
        _CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        _CS.detail = True
    return _MD, _CS


def refusal(m):
    """('', '') if this member is admissible to the byte tier, else (reason, message).

    THE single source of truth for decisions.md 1j (iv) -- RIP-relative, fs:/gs:-relative, and
    guest-space immediates -- and 1j (v) -- traps. The two assert_* wrappers below and the
    emitters all come through here, so a counter and a gate cannot disagree about the class, and
    adding a tooth is one edit rather than four.
    """
    md, cs = _ctx()
    guest, size = int(m['address'], 16), int(m['size'])
    off = guest - C.FILE_BIAS
    for ins in cs.disasm(md[off:off + size], guest):
        if ins.mnemonic in TRAPS:
            return 'trap (1j v)', (f"refused: {m['function']} executes `{ins.mnemonic} "
                                   f"{ins.op_str}`: a trap or privileged instruction is not a "
                                   f"returning body -- byte identity would preserve a fault, and "
                                   f"the differential would report it against the harness")
        if ins.mnemonic.startswith(('j', 'call')):
            return 'address dependent', (
                f"refused: {m['function']} carries a relative branch or call "
                f"(`{ins.mnemonic} {ins.op_str}`): its target is an address, so byte identity does "
                f"not preserve behaviour (decisions.md 1j (iv))")
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base in (X86_REG_RIP, X86_REG_EIP):
                return 'address dependent', (
                    f"refused: {m['function']} has a RIP-relative operand "
                    f"({ins.mnemonic} {ins.op_str}): its value depends on where it sits, so byte "
                    f"identity does not preserve behaviour")
            if op.type == X86_OP_MEM and op.mem.segment in (X86_REG_FS, X86_REG_GS):
                seg = 'fs' if op.mem.segment == X86_REG_FS else 'gs'
                return 'address dependent', (
                    f"refused: {m['function']} has a {seg}: -relative operand "
                    f"({ins.mnemonic} {ins.op_str}): it computes from a segment base the "
                    f"replacement does not control. The differential reaches a body from the host "
                    f"(harness.py: ctypes.CDLL, then getattr(lib, name)), where %{seg} is the host "
                    f"TCB; the hook path runs the same bytes with the guest base, so one body "
                    f"would mean two things depending on how it was called")
            if op.type == X86_OP_IMM and 0x400000 <= op.imm < 0x600000:
                return 'address dependent', (
                    f"refused: {m['function']} carries an address-valued immediate "
                    f"({ins.mnemonic} {ins.op_str}): {op.imm:#x} is guest space, not a constant")
    return '', ''


def admissible(m) -> bool:
    return refusal(m)[0] == ''


def assert_position_independent(members) -> None:
    """decisions.md 1j (iv): no instruction whose VALUE depends on where the body sits."""
    for m in members:
        reason, message = refusal(m)
        if reason == 'address dependent':
            raise SystemExit(message)


def assert_no_trap(members) -> None:
    """decisions.md 1j (v): a .byte body that traps is not a function that returns."""
    for m in members:
        reason, message = refusal(m)
        if reason == 'trap (1j v)':
            raise SystemExit(message)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', required=True, help='name prefix, e.g. leaf_mov_al_mem_')
    ap.add_argument('--root', default='.')
    ap.add_argument('--lib', default='build-release/game/libbbgame.so')
    ap.add_argument('--elf', default='../data/bb/elf/eboot.elf')
    ap.add_argument('--batch', type=int, default=0, help='members per digest; 0 = one family digest')
    ap.add_argument('--dry-run', action='store_true')
    o = ap.parse_args(argv)

    fpath = os.path.join(o.root, 'symbols', 'functions.csv')
    with open(fpath, newline='') as f:
        all_rows = list(csv.DictReader(f))
    # `startswith('leaf_ret_')` also matches `leaf_ret_xor_...` -- 4,721 rows that already carry
    # differential evidence. A ladder family name ends in exactly eight hex digits, so match that.
    pat = re.compile('^' + re.escape(o.family) + r'[0-9a-f]{8}$')
    fam = [r for r in all_rows if pat.match(r['name'])]
    skipped = [r for r in all_rows if r['name'].startswith(o.family) and not pat.match(r['name'])]
    if skipped:
        print(f'  not this family: {len(skipped)} rows match the prefix but not the shape '
              f'({skipped[0]["name"]})')
    if not fam:
        raise SystemExit(f'refused: no rows in functions.csv start with {o.family}')
    bad = [r['name'] for r in fam if r['status'] != 'original']
    if bad:
        raise SystemExit(f'refused: {len(bad)} rows are already past `original` ({bad[0]}...)')
    members = [{'function': r['name'], 'address': r['address'], 'size': r['size']} for r in fam]
    assert_no_control_flow(members)   # decisions.md 1h, before any digest and before any write
    assert_position_independent(members)   # decisions.md 1j (iv), incl. fs:/gs:
    assert_no_trap(members)                # decisions.md 1j (v)
    sizes = {}
    for m in members:
        sizes[int(m['size'])] = sizes.get(int(m['size']), 0) + 1
    added = sum(k * v for k, v in sizes.items())
    print(f'{o.family}: {len(members)} members | sizes {sizes} -> +{added} B')

    step = o.batch or len(members)
    batches = [members[i:i + step] for i in range(0, len(members), step)]
    digests = []
    for i, b in enumerate(batches):
        d = digest(o.root, o.lib, o.elf, b)
        digests.append(d)
        print(f'  batch {i + 1}/{len(batches)}: {len(b)} members digest={d}')
    if o.dry_run:
        print('  dry run: nothing written')
        return 0

    today = datetime.date.today().isoformat()
    new = []
    for b, d in zip(batches, digests):
        for m in b:
            src = V.source_hash(o.root, m['function'])
            if not src:
                raise SystemExit(f'refused: no source hash for {m["function"]}')
            new.append({'function': m['function'], 'cases': 'bytes', 'option': '',
                        'total': '1', 'passed': '1', 'failed': '0', 'quarantined': '0',
                        'source': src, 'cases_sha256': d, 'date': today})
    V.record_many(o.root, new)
    print(f'  ledger: +{len(new)} rows, source derived per function')

    flipped = 0
    for r in all_rows:
        if pat.match(r['name']):          # the same selector as the members, not a second one
            if r['status'] != 'original':
                raise SystemExit(f'refused: {r["name"]} is {r["status"]}, not original')
            r['status'] = 'edge-verified'
            flipped += 1
    if flipped != len(members):
        raise SystemExit(f'refused: flipped {flipped} but recorded {len(members)}')
    fields = list(all_rows[0].keys())
    _write_rows(fpath, fields, all_rows)
    sort_address_keyed(o.root)
    print(f'  functions.csv: {flipped} flipped to edge-verified; tables sorted')

    d = P.ledger(o.root)
    print(f'  now: {d["functions"]} functions | {d["byte_backed"]} byte-identical / '
          f'{d["differential_backed"]} differential | ledger {d["rows"]} rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
