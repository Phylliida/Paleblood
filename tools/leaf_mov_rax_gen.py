#!/usr/bin/env python3
"""Family #5: `mov rax, [rdi + K]; ret` -> return the 8 bytes at rdi + K.

Selection is the census shape: an exact two-instruction decode over raw image
bytes at `file = guest - 0x3fc000`, with the displacement's render width
checked too (a 4-byte mov needs a 5-byte body, a 7-byte mov an 8-byte one).
It is never a byte-pattern scan: the 45-member tranche that hit `31 c0 c3`
inside larger functions is why.

The first family that reads memory, so its cases are authored, not derived: a
marker is written at a fixed guest address and `rdi` is set to
`marker_guest - K`, so a body using the wrong displacement returns a different
value. Two markers, two cases: a constant-returning body passes the first and
fails the second.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86_const import X86_REG_RAX, X86_REG_RDI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from case_dir import case_dir

ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
CATALOG = os.path.join(ROOT, '..', 'data', 'catalog.sqlite3')
CASES = case_dir('mov_rax')
SYMBOLS = os.path.join(ROOT, 'symbols')
FILE_BASE = 0x3FC000
PREFIX = 'leaf_mov_rax_'
BODY_FILE = os.path.join(ROOT, 'game', 'leaf', 'mov_rax_family.cpp')
DATA_GUEST = 0x0440000
MARKERS = (('00_marker_a', 'efcdab8967452301'), ('01_marker_b', '1032547698badcfe'))
EXPECTED_MEMBERS = 3619
X86_OP_REG, X86_OP_MEM = 1, 3  # imported register numbers, never guessed: RAX=35, RDI=39


def members():
    """(address, size, K) for every census member, straight from the image."""
    blob = open(ELF, 'rb').read()
    cat = sqlite3.connect(CATALOG)
    sizes = {}
    for ahex, data in cat.execute('select address, data from functions'):
        size = json.loads(data).get('size_bytes')
        if size in (5, 8):
            sizes[ahex] = size
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    out = []
    for ahex, size in sizes.items():
        addr = int(ahex, 16)
        off = addr - FILE_BASE
        if off < 0 or off + size > len(blob):
            continue
        ins = list(md.disasm(blob[off:off + size], addr))
        if len(ins) != 2:
            continue
        mov, ret = ins
        if mov.mnemonic != 'mov' or ret.mnemonic != 'ret' or ret.address + 1 != addr + size:
            continue
        if len(mov.operands) != 2:
            continue
        dst, src = mov.operands
        if dst.type != X86_OP_REG or dst.reg != X86_REG_RAX:
            continue
        if src.type != X86_OP_MEM or src.mem.base != X86_REG_RDI or src.mem.index != 0:
            continue
        if not ((mov.size == 4 and size == 5) or (mov.size == 7 and size == 8)):
            continue
        out.append((addr, size, src.mem.disp))
    return sorted(out)


def name_for(addr):
    return f'{PREFIX}{addr:08x}'


def cases(addr, K):
    rdi = DATA_GUEST - K
    if rdi < 0x400000:
        raise SystemExit(f'0x{addr:08x}: rdi guest 0x{rdi:x} is outside the image for K=0x{K:x}')
    yield 'abi.json', f'''{{
  "calling_convention": "sysv_amd64",
  "confidence": "supported",
  "evidence": [
    "0x{addr:08x} is exactly mov rax, qword ptr [rdi + 0x{K:x}]; ret; the body reads one 8-byte word",
    "rdi arrives as a guest: translation, so the replacement dereferences it as a host pointer"
  ],
  "stack_alignment": 16,
  "arguments": ["rdi"]
}}
'''
    for stem, payload in MARKERS:
        yield f'{stem}.json', f'''{{
  "address": "0x{addr:08x}",
  "args": {{"rdi": "guest:0x{rdi:x}", "rax": "0xdeadbeef"}},
  "memory": [{{"addr": "0x{DATA_GUEST:x}", "bytes": "{payload}"}}],
  "registers": ["rax"]
}}
'''


def bodies(batch):
    # The order here is the order on disk, not the order I first emitted: the `readable` fix
    # inserted the named constant above the comment block by hand, and a generator whose header
    # no longer matches the reviewed file is a generator that rewrites it on the next batch.
    out = ['#include <cstdint>', '#include <cstring>', '',
           'constexpr std::size_t k_word_bytes = sizeof(std::uint64_t);  // one 8-byte word',
           '',
           '// Generated: mov rax, [rdi + K]; ret. Each body reads the 8 bytes at the pointer',
           "// the caller passed, at that member's own displacement. The read is asserted through",
           '// the returned rax: the harness does not instrument guest load/store instructions,',
           '// and the marker sits in a non-writable segment so the post-call snapshot misses it.',
           '// memcpy, not a dereference through a cast: K=0x1 leaves the pointer unaligned.',
           '']
    for addr, size, K in batch:
        out.append(f'constexpr std::uint64_t k_{name_for(addr)} = 0x{K:x}u;  // size {size}')
        out.append(f'extern "C" std::uint64_t bb_{name_for(addr)}(std::uint64_t rdi) {{')
        out.append('    std::uint64_t value;')
        out.append(f'    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_{name_for(addr)}), k_word_bytes);')
        out.append('    return value;')
        out.append('}')
    return '\n'.join(out) + '\n'


def merged(path, additions, fields):
    """Sorted-unique-ascending: the generator inserts, it never appends."""
    rows = list(csv.DictReader(open(path)))
    seen = {r[fields[0]] for r in rows}
    rows += [r for r in additions if r[fields[0]] not in seen]
    rows.sort(key=lambda r: int(r[fields[0]], 16))
    sio = io.StringIO()
    w = csv.DictWriter(sio, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return sio.getvalue()


def write(limit):
    allm = members()
    print(f'members {len(allm)} (census {EXPECTED_MEMBERS})')
    if len(allm) != EXPECTED_MEMBERS:
        raise SystemExit('refusing: measured count differs from the census; reconcile first')
    fcsv = os.path.join(SYMBOLS, 'functions.csv')
    known = {r['address'] for r in csv.DictReader(open(fcsv))}
    batch = [m for m in allm if f'0x{m[0]:08x}' not in known][:limit]
    if not batch:
        print('nothing to do: every member is already in functions.csv')
        return 0
    staged = tempfile.mkdtemp(prefix='movrax.')
    dirs = [CASES.row_dir(a, 'table') for a, _, _ in batch]
    try:
        os.makedirs(os.path.join(staged, 'cases'))
        for addr, _, K in batch:
            d = os.path.join(staged, 'cases', f'0x{addr:08x}')
            os.makedirs(d)
            for name, text in cases(addr, K):
                open(os.path.join(d, name), 'w').write(text)
        body_text = bodies(batch)
        open(os.path.join(staged, 'mov_rax_family.cpp'), 'w').write(body_text)
        fc_fields = list(csv.DictReader(open(fcsv)).fieldnames)
        fc_text = merged(fcsv, [{'address': f'0x{a:08x}', 'size': str(s), 'name': name_for(a),
                                 'system': 'leaf', 'status': 'original', 'notes': ''}
                                for a, s, _ in batch], fc_fields)
        or_path = os.path.join(SYMBOLS, 'replacement_origins.csv')
        or_text = merged(or_path, [{'address': f'0x{a:08x}', 'origin': 'generated'}
                                   for a, _, _ in batch], ['address', 'origin'])
        im_path = os.path.join(SYMBOLS, 'install_mode.csv')
        im_text = merged(im_path, [{'address': f'0x{a:08x}', 'mode': 'host'}
                                   for a, _, _ in batch], ['address', 'mode'])
        backups = {}
        try:
            for path in (fcsv, or_path, im_path, BODY_FILE):
                if os.path.exists(path):
                    backups[path] = path + '.genbak'
                    shutil.copy2(path, backups[path])
            # Insert, never replace: this file already holds members that are recorded and
            # flipped, and a generator that re-emits a batch must not delete the batch before it.
            existing = open(BODY_FILE).read() if os.path.exists(BODY_FILE) else ''
            header = bodies([])
            if existing and not existing.startswith(header):
                raise SystemExit(f'{BODY_FILE}: does not start with the emitted header; '
                                 'refusing to rewrite a file this generator did not write')
            blocks = body_text[len(header):]
            open(BODY_FILE, 'w').write((existing.rstrip('\n') + '\n\n' + blocks)
                                       if existing else header + blocks)
            open(fcsv, 'w').write(fc_text)
            open(or_path, 'w').write(or_text)
            open(im_path, 'w').write(im_text)
            for d, src in zip(dirs, sorted(os.listdir(os.path.join(staged, 'cases')))):
                target = os.path.join(staged, 'cases', src)
                shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(target, d)
        except BaseException:
            for path, bak in backups.items():
                shutil.copy2(bak, path)
            for d in dirs:
                shutil.rmtree(d, ignore_errors=True)
            raise
        finally:
            for bak in backups.values():
                if os.path.exists(bak):
                    os.remove(bak)
        print(f'wrote {len(batch)} members · {len(batch) * len(MARKERS)} cases · '
              f'{len(body_text)} bytes of bodies')
        print('next: build, verify.py --record, then --flip')
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def flip():
    """Set edge-verified only for members whose every ledger row is clean."""
    led = {}
    for r in csv.DictReader(open(os.path.join(SYMBOLS, 'verification.csv'))):
        if r['function'].startswith(PREFIX):
            led.setdefault(r['function'], []).append(r)
    path = os.path.join(SYMBOLS, 'functions.csv')
    rows = list(csv.DictReader(open(path)))
    flipped, refused = 0, []
    for r in rows:
        if not r['name'].startswith(PREFIX) or r['status'] != 'original':
            continue
        got = led.get(r['name'], [])
        clean = got and all(x['failed'] == '0' and x['total'] == x['passed']
                            and int(x['total']) > 0 for x in got)
        if clean:
            r['status'] = 'edge-verified'
            flipped += 1
        else:
            refused.append(r['name'])
    if refused:
        print(f'refusing {len(refused)}: no clean ledger row, e.g. {refused[:3]}')
    if not flipped:
        print('nothing flipped')
        return 1 if refused else 0
    sio = io.StringIO()
    w = csv.DictWriter(sio, fieldnames=list(rows[0].keys()), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    open(path, 'w').write(sio.getvalue())
    print(f'flipped {flipped} to edge-verified')
    return 1 if refused else 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--flip', action='store_true')
    ap.add_argument('--limit', type=int, default=25)
    o = ap.parse_args(argv)
    if o.scan:
        m = members()
        ks = sorted({k for _, _, k in m})
        print(f'members {len(m)} (census {EXPECTED_MEMBERS}) · distinct bodies {len(ks)} · '
              f'K 0x{ks[0]:x}..0x{ks[-1]:x}')
        return 0
    if o.write:
        return write(o.limit)
    if o.flip:
        return flip()
    ap.error('one of --scan, --write, --flip')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
