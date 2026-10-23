#!/usr/bin/env python3
"""Refuse a landed leaf family whose dereference targets are not where it thinks they are.

A family must DECLARE what it does with a computed address, because the containment bound is
opposite for the two kinds and unconstrained for the third:

  load      reads the target          -> must lie inside a PT_LOAD's FILESZ. [filesz, memsz) is
                                          zero-fill: a constant 0 that no address shift can
                                          perturb, so no case over it is evidence. (rip_load: 161
                                          of 161 members were here, and a +4 mutant survived.)
  store     writes the target         -> must lie inside MEMSZ. Writing BSS is ordinary guest
                                          behaviour and exactly the memory snapshot() cannot see,
                                          since it iterates declared buffers.
  addr-only computes and returns it   -> unconstrained. A BSS address is a perfectly good VALUE
                                          when nothing dereferences it (lea_rip: 7,847 of 8,072).

THE TIER DECIDES WHETHER THE GATE HAS A QUESTION AT ALL. At the differential tier the evidence
is a comparison, so a target the body dereferences must lie in filled bytes and an
argument-supplied target is an obligation that lives in the CASE (the buffer must be declared).
At the BYTE tier the evidence is the encoding: the body's bytes are the original's bytes, so byte
identity is the whole claim and no containment question is owed anywhere -- there is no case, no
declared buffer and no snapshot to move the obligation to. Naming an obligation nobody holds is
the same class of defect as a green over nothing, phrased as diligence.

A classifier that buckets an immediate as an address cannot tell a violation from a spelling --
mov_eax_k's 132 "outside" constants are immediates -- so the family declares, and an undeclared
family file is a refusal rather than a guess.
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
LEAF = os.environ.get('LEAF_TARGETS_DIR') or os.path.join(ROOT, 'game', 'leaf')
BASE = 0x400000

ACCESS = {  # family -> (kind, source)
    # kind: load | store | addr-only        source: static | argument
    # dereference a displacement computed from %rip -> static target in the body
    'rip_load': ('load', 'static'), 'rip_store': ('store', 'static'),
    'rip_add_store': ('store', 'static'),
    # dereference an argument-supplied address -> no static target to check here
    'vmovss_load': ('load', 'argument'), 'vmovss_store': ('store', 'argument'), 'mov_al_mem': ('load', 'argument'),
    'mov_eax_mem': ('load', 'argument'), 'st_byte_imm': ('store', 'argument'), 'st_dword_esi': ('store', 'argument'),
    'st_imm32': ('store', 'argument'), 'st_qword_rsi': ('store', 'argument'), 'st_sil8': ('store', 'argument'),
    # compute and return, never dereference
    'lea_disp_rdi': ('addr-only', 'static'), 'lea_rdi': ('addr-only', 'static'), 'lea_rip': ('addr-only', 'static'),
    'mov_eax_k': ('addr-only', 'static'), 'mov_al_imm': ('addr-only', 'static'), 'mov_rax': ('addr-only', 'static'),
    'rax_rdi': ('addr-only', 'static'), 'ret': ('addr-only', 'static'), 'ret_zero': ('addr-only', 'static'),
    'leaf_ret_zero': ('addr-only', 'static'), 'asm_pilot': ('addr-only', 'static'),
}


# Byte tier: the body's bytes are the original's bytes, so identity is the whole claim.
TIERS = {'mov_mem_esi': 'bytes', 'mov_mem_rsi': 'bytes', 'mov_mem_imm8': 'bytes'}


def segments():
    with open(ELF, 'rb') as fh:
        head = fh.read(64)
        phoff, = struct.unpack_from('<Q', head, 0x20)
        entsize, num = struct.unpack_from('<HH', head, 0x36)
        fh.seek(phoff)
        ph = fh.read(entsize * num)
    out = []
    for k in range(num):
        p_type, = struct.unpack_from('<I', ph, k * entsize)
        if p_type != 1:
            continue
        vaddr, = struct.unpack_from('<Q', ph, k * entsize + 0x10)
        filesz, = struct.unpack_from('<Q', ph, k * entsize + 0x20)
        memsz, = struct.unpack_from('<Q', ph, k * entsize + 0x28)
        out.append((vaddr + BASE, vaddr + BASE + filesz, vaddr + BASE + memsz))
    return out


def family_of(fname):
    stem = fname[:-len('.cpp')]
    return stem[:-len('_family')] if stem.endswith('_family') else stem


def main():
    segs = segments()
    errs = []
    for fname in sorted(os.listdir(LEAF)):
        if not fname.endswith('.cpp'):
            continue
        fam = family_of(fname)
        if fam.startswith('leaf_ret_zero'):
            fam = 'leaf_ret_zero'
        decl = ACCESS.get(fam)
        if decl is None:
            errs.append(f'{fname}: family {fam!r} declares no access kind -- add it to ACCESS '
                        'with (load|store|addr-only, static|argument) rather than letting a guess '
                        'classify it')
            continue
        kind, source = decl
        tier = TIERS.get(fam, 'differential')
        text = open(os.path.join(LEAF, fname)).read()
        # The form the target takes is part of the family's contract. `rip_*` families dereference
        # a constant they emit as `constexpr std::uint64_t v = 0x...u;`; a dereferencing family that
        # does not expose its target in a parseable form is mis-emitted, not exempt. The first
        # version of this gate printed "nothing to check" for 8,558 rows of lea_rip, rip_add_store
        # and rip_store -- a green over an empty scan, which is the defect this gate exists to catch.
        if tier == 'bytes':
            print(f"{fam:20s} {kind:10s} byte tier: the body's bytes are the original's "
                  '-- nothing owed')
            continue
        if kind == 'addr-only':
            print(f'{fam:20s} {kind:10s} unconstrained by design (reads no target)')
            continue
        targets = [int(x, 16) for x in re.findall(r'constexpr std::uint64_t v = (0x[0-9a-f]+)u', text)]
        if not targets and source == 'argument':
            print(f'{fam:20s} {kind:10s} argument-supplied -- the bound lives in the case: '
                  'the buffer must be declared')
            continue
        if not targets:
            errs.append(f'{fname}: family {fam!r} declares ({kind}, static) but exposes no dereferenced '
                        'constant (expected `constexpr std::uint64_t v = 0x...u;`) -- a dereferencing '
                        'family must name its target in a form the gate can parse; "nothing to check" '
                        'is legal only for addr-only')
            continue
        bad = []
        for t in targets:
            ok = any(lo <= t < (hi if kind == 'load' else ms) for lo, hi, ms in segs)
            if not ok:
                bad.append(t)
        where = 'filesz' if kind == 'load' else 'memsz'
        if bad:
            errs.append(f'{fam}: {len(bad)} of {len(targets)} {kind} targets outside every PT_LOAD '
                        f'{where}; first {bad[0]:#x}'
                        + (' (zero-fill: a constant 0 no case can discriminate)' if kind == 'load' else ''))
        else:
            print(f'{fam:20s} {kind:10s} {len(targets)} targets inside {where} -- ok')
    for e in errs:
        print(f'leaf-targets: {e}', file=sys.stderr)
    return 1 if errs else 0


if __name__ == '__main__':
    # A crash is not a refusal. Once this runs under ctest, an exception is a red that names a
    # traceback instead of a property, and the runner cannot act on it. Every path ends in a named
    # ok or a named refusal -- the same rule as an rc vocabulary the caller can read.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberate: name it, do not traceback
        print(f'leaf-targets: gate failed to complete ({type(exc).__name__}: {exc}) -- '
              'this is a refusal, not a pass', file=sys.stderr)
        sys.exit(1)
