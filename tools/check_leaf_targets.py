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
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from case_dir import case_dir  # noqa: E402 - ONE definition of where a family's cases live
ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
LEAF = os.environ.get('LEAF_TARGETS_DIR') or os.path.join(ROOT, 'game', 'leaf')
BASE = 0x400000

# Files in game/leaf that are infrastructure rather than replacement families. Additions here
# are decisions, reviewed like any other: a family that dereferences belongs in ACCESS, and
# absence from both lists is a refusal (the gate is fail-closed for a reason).
INFRASTRUCTURE = {'load_base'}

ACCESS = {  # family -> SET of decls; a decl is (kind, source, *names)
    # kind: load | store | addr-only   source: static | argument | seeded
    # one family may declare SEVERAL obligations (chain_deref: a load and a store)
    # dereference a displacement computed from %rip -> static target in the body
    'rip_load': (('load', 'static',),), 'rip_load_wide': (('load', 'static',),),
    'rip_store': (('store', 'static',),),
    'rip_add_store': (('store', 'static',),),
    # dereference an argument-supplied address -> no static target to check here
    'vmovss_load': (('load', 'argument',),), 'vmovss_store': (('store', 'argument',),), 'mov_al_mem': (('load', 'argument',),),
    'mov_eax_mem': (('load', 'argument',),), 'st_byte_imm': (('store', 'argument',),), 'st_dword_esi': (('store', 'argument',),),
    'st_imm32': (('store', 'argument',),), 'st_qword_rsi': (('store', 'argument',),), 'st_sil8': (('store', 'argument',),),
    # TWO obligations, one family. The load reads a slot in the zero-fill tail -- bound at memsz AND the
    # case must supply the value -- so it names its constant. The store writes through the pointer the load
    # produced: its target is the CASE's buffer, not any constant in the body. Naming kStoreDisp here was
    # measured and rejected: 0x1520 is a displacement, a coordinate, and the gate bounded it as an address
    # and refused 78 of 78. A decl names exactly the constants that ARE addresses.
    'chain_deref': (('load', 'seeded', 'kSlot'), ('store', 'argument')),
    # Same first load as chain_deref -- the pointer slot is in the zero-fill tail, so it is bounded at
    # memsz and the case must seed it. The second dereference is through the seeded pointer at a
    # displacement; that displacement is a coordinate, not an address, and is deliberately not named.
    'movsx_deref': (('load', 'seeded', 'kSlot'),),
    # compute and return, never dereference
    'lea_disp_rdi': (('addr-only', 'static',),), 'lea_rdi': (('addr-only', 'static',),), 'lea_rip': (('addr-only', 'static',),),
    'mov_eax_k': (('addr-only', 'static',),), 'mov_al_imm': (('addr-only', 'static',),), 'mov_rax': (('addr-only', 'static',),),
    'rax_rdi': (('addr-only', 'static',),), 'ret': (('addr-only', 'static',),), 'ret_zero': (('addr-only', 'static',),),
    'leaf_ret_zero': (('addr-only', 'static',),), 'asm_pilot': (('addr-only', 'static',),),
}


# Byte tier: the body's bytes are the original's bytes, so identity is the whole claim.
TIERS = {'mov_mem_esi': 'bytes', 'mov_mem_rsi': 'bytes', 'mov_mem_imm8': 'bytes',
         'bytes': 'bytes'}   # emit_byte_leaves.py's family: 1j transcription, per decision 1l


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


def seeded_case_path(family, address):
    """The case file for a seeded row, through the only object that knows the declared layouts."""
    return case_dir(family).find(address)


def main():
    segs = segments()
    errs = []
    for fname in sorted(os.listdir(LEAF)):
        if not fname.endswith('.cpp'):
            continue
        fam = family_of(fname)
        if fam.startswith('leaf_ret_zero'):
            fam = 'leaf_ret_zero'
        if fam in INFRASTRUCTURE:
            # Not a family and not a guess: a file in game/leaf that declares no target because it
            # dereferences nothing. It holds the two facts every based family needs -- the guest load
            # base as a name and the image base the runner sets -- so it has no access kind to
            # declare. Listing it here is a decision in the artifact; leaving it unlisted is the
            # refusal below, which is what fired on its first day.
            print(f'{fam:<20} infrastructure -- declares no target, nothing to check')
            continue
        tier = TIERS.get(fam, 'differential')
        if tier == 'bytes':
            # A byte-tier body is the original's bytes under a new name: it emits no constant of its
            # own, so there is no target to classify and nothing can be mistranslated. Demanding an
            # access kind here asked the family for a fact that cannot exist -- the order was the
            # defect, not the missing declaration. Families that DO emit constants still need ACCESS.
            print(f'{fam:<20} bytes tier -- transcription, nothing to classify')
            continue
        decls = ACCESS.get(fam)
        if decls is None:
            errs.append(f'{fname}: family {fam!r} declares no access kind -- add it to ACCESS '
                        'with (load|store|addr-only, static|argument) rather than letting a guess '
                        'classify it')
            continue
        # `kind, source, *names` unpacks a 2-tuple and a 3-tuple alike: an entry that names its own
        # constants gets them here, and one that does not gets (). A family that forgets its name
        # therefore fails the empty-targets refusal below rather than passing on a default spelling.
        for decl in decls:
            kind, source, *names = decl
            text = open(os.path.join(LEAF, fname)).read()
            # The form the target takes is part of the family's contract. `rip_*` families dereference
            # a constant they emit as `constexpr std::uint64_t|uintptr_t v = 0x...u?;` -- the TYPE spelling is
        # part of what a scanner may not assume either: chain_deref emits std::uintptr_t with no `u` suffix,
        # so a regex hardcoded to (std::uint64_t, u) found 0 of 78 and reported it as no targets. Naming the
        # constants in ACCESS was necessary and not sufficient. A dereferencing family that
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
            # `v` and `at` are the two spellings in the tree and both are constants the gate can parse:
            # `v` is a stored value, `at` is a GUEST ADDRESS the body dereferences (rip_load_wide, where
            # the constant IS the target and the body adds pbl_image_base - kGuestLoadBase to it). One
            # regex, two names -- a gate that parses only the spelling its author wrote first reports a
            # correct family as unparseable, which is the zero-by-predicate failure in a checker.
            # A name in a table is not an assumption, it is an input. With no names declared the family must
            # expose its target under one of the two spellings the tree already uses; with names declared the
            # scanner reads the spelling the emitter actually emits (`kSlot`, `kStoreDisp`), so two conventions
            # can coexist without either family being invisible to the gate -- 647's shape, closed by data.
            spelling = '|'.join(names) if names else 'v|at'
            targets = [int(x, 16) for x in
                       re.findall(r'constexpr std::u(?:int64|intptr)_t\s+(?:%s)\s*=\s*'
                              r'(0x[0-9a-f]+)u?' % spelling, text)]
            if names and not targets:
                errs.append(f'{fname}: family {fam!r} declares constants {names} but the body declares none of '
                            f'them -- empty targets is a REFUSAL for a kind that needs one, never a nothing-to-check')
                continue
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
            # ONE decision, in ONE place. The bound is chosen once, and the name travels with it, so the
            # comparison and the sentence cannot disagree -- extent_line's defect is two copies of one decision
            # that agreed until one of them changed. The predicate is what the loop FOUND, never a parallel
            # `any()`: `any()` cannot say which segment admitted a target, and two PT_LOADs can overlap here.
            bound = 'memsz' if (kind != 'load' or source == 'seeded') else 'filesz'
            inside, gap, outside = [], [], []
            for t in targets:
                hit = next(((hi if bound == 'filesz' else ms, bound)
                            for lo, hi, ms in segs if lo <= t < (hi if bound == 'filesz' else ms)), None)
                if hit:
                    inside.append(t)
                    continue
                # Not admitted by its own bound. Distinguish "admitted by the OTHER bound" -- past filesz, inside
                # memsz, the zero-fill tail where tonight's whole `seeded` distinction lives -- from "in no
                # segment at all", which is a mis-emission. A two-way verdict over a three-way fact is a formatter.
                other = next((True for lo, hi, ms in segs
                              if (bound == 'filesz' and lo <= t < ms) or (bound == 'memsz' and lo <= t < hi)),
                             False)
                (gap if other else outside).append(t)
            where = bound
            if outside:
                errs.append(f'{fam}: {len(outside)} of {len(targets)} {kind} targets outside every PT_LOAD '
                            f'{where}; first {outside[0]:#x}'
                            + (' (zero-fill: a constant 0 no case can discriminate)' if kind == 'load' else ''))
            elif gap and source != 'seeded':
                errs.append(f'{fam}: {len(gap)} of {len(targets)} {kind} targets past {where} but inside the '
                            f'other bound; first {gap[0]:#x} -- a target in the zero-fill tail is neither inside '
                            'filesz nor absent, and only `seeded` may claim it')
            elif source == 'seeded':
                # BOUNDED is not SUPPLIED. The case must reach the number the body NAMES, and the two
                # artifacts compared here read nothing in common: the body is the TU, the seed is the case
                # JSON. Absence REFUSES -- a missing case is not a family with nothing to check, it is a
                # family whose differential has no subject.
                body_slot = {}
                parts = re.split(r'(bb_leaf_%s_[0-9a-f]{8})' % fam, text)
                for i in range(1, len(parts) - 1, 2):
                    a = int(parts[i].rsplit('_', 1)[1], 16)
                    m = re.search(r'constexpr std::uintptr_t\s+(?:%s)\s*=\s*(0x[0-9a-f]+)' % spelling,
                                  parts[i + 1])
                    if m:
                        body_slot[a] = int(m.group(1), 16)
                if not body_slot:
                    errs.append(f'{fam}: {source} declared but no body could be associated with an address '
                                '-- the association is part of the check, not a convenience')
                missing, mism, supplied = [], [], 0
                for a, slot in sorted(body_slot.items()):
                    cj = seeded_case_path(fam, a)
                    if cj is None:
                        missing.append(a)
                        continue
                    seeds = [int(e['addr'], 16) for e in json.load(open(cj)).get('memory', [])
                             if 'guest' in e]
                    if slot in seeds:
                        supplied += 1
                    else:
                        mism.append((a, slot, seeds[:2]))
                if missing:
                    errs.append(f'{fam}: {len(missing)} of {len(body_slot)} bodies have NO case file '
                                f'(first {missing[0]:#010x}) -- absence refuses: a family whose differential '
                                'has no subject is not a family with nothing to check')
                if mism:
                    a, slot, seeds = mism[0]
                    errs.append(f'{fam}: body {a:#010x} names {slot:#x} but its case seeds '
                                f'{[hex(x) for x in seeds]} -- bounded correctly, NOT supplied')
                if not missing and not mism:
                    print(f'{fam:20s} {kind:10s} {supplied} of {len(body_slot)} bodies: the named slot '
                          'EQUALS the case seed address (two artifacts, neither reading the other)')
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
