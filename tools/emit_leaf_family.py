"""One emitter for leaf shapes, driven by a table: each row is a parse, a body, a width.

The five-table write, rows-at-original-then-flip, size-from-the-member's-own-bytes and
per-constant mutants are the same code for every family; only the parse and the body
differ, so they live in TEMPLATES and nothing else is family-specific.

THE OPERATING RULE FOR A FAMILY, and the only order that does not cost the whole family:

    author every member to final  ->  verify.py --record edge over all of them  ->  stop editing

`source_hash` is a function of the defining FILE list and those files' contents, so every member of a
generated family shares one hash (3,619 mov_rax members, one translation unit). One body edited after a
record therefore staleness-refuses the other members of the family, not just itself: the refusal is
conservative and correct, and the rework is the entire family.

**An emitter run after a record invalidates the family's evidence by definition, so a post-record emission
is a re-record, not an edit.** Author to final, record once, and if a body must change, change it before
the record or plan to re-record all of them.
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import catalogue
import leaf_family_census as C
from atomicio import atomic_write   # after the path insert: bare means bare

ROOT = C.ROOT
from case_dir import case_dir  # ONE definition of the case root; check_seeding imports the same one
# (was: a second literal 'data/cases/leaf' -- the string check_seeding disagreed with)
# The chain family's sentinel byte: no masked immediate (0x0 31x, 0x1 36x, 0x2, 0x3, 0x4, 0x8, 0xa, 0xf,
# 0xffffffff) collides with its own repetition at either width. Derived from the family, not guessed.
CHAIN_SENTINEL = 0x05
MARKERS = ('1122334455667788', 'deadbeefcafef00d', '0102030405060708')

TEMPLATES = {
    'mov_eax_mem': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^eax, (?:dword ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\]$'),
        'width': 4,
        'note': 'load32 at rdi+K; zero-extends, aligned by construction (K%4==0 in all 765)',
        'kind': 'load32',
    },
    # DO NOT EMIT. Measured twice, wrong once.
    # `mov al,K` writes 8 of 64 bits and preserves rax[63:8]; `returns: i64` compares that, and a
    # C body cannot NAME entry rax (`harness.py:77` seeds the register; `uint64_t a0` is rdi), so
    # all 793 members failed with `ret.rax: original 0xdeadbeef00000001 replacement 0x1`.
    # The alias form (seed rax for the original and rsi for the body, one constant) passes
    # 793 of 793 -- and is WRONG: the replacement then reads entry rsi, which equals entry rax in
    # the case by construction and essentially never in the game, so it returns a different value
    # on every real invocation while both controls pass. A success criterion whose inputs the
    # experimenter chose cannot fail; this family IS a register state.
    # It needs inline asm (policy question with the user, together with `ret`) or exclusion.
    'mov_al_imm': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^al, (0x[0-9a-f]+|\d+)$'),
        'width': 1,
        'note': 'writes 8 of 64 bits; asm by design (decision 1) -- a C body cannot name entry rax',
        'kind': 'asm_imm8',
    },
    'mov_al_mem': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^al, (?:byte ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\]$'),
        'width': 1,
        'note': 'load8 at rdi+K; asm by design -- byte evidence, so no buffer and no case schema',
        'kind': 'asm_al_mem',
    },
    'ret': {
        'mnemonics': ('ret',),
        'operand': re.compile(r'^$'),
        'note': 'one byte c3; asm by design (decision 1). No parameter, so no mutant exists for it.',
        'kind': 'asm_ret',
    },
    # The 624 stores: the three shapes that carry 225 + 200 + 199 members. Under cases='bytes'
    # there is no returns/void to worry about -- the claim is byte identity, and `returns:'void'`
    # was only ever a differential-tier concern.
    'st_dword_esi': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^dword ptr \[rdi \+ (0x[0-9a-f]+|\d+)\], esi$'),
        'note': 'store32 of esi at rdi+K; asm by design, byte evidence',
        'kind': 'asm_st_reg', 'reg': '%esi', 'sfx': 'l',
    },
    'st_qword_rsi': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^qword ptr \[rdi \+ (0x[0-9a-f]+|\d+)\], rsi$'),
        'note': 'store64 of rsi at rdi+K; asm by design, byte evidence',
        'kind': 'asm_st_reg', 'reg': '%rsi', 'sfx': 'q',
    },
    'st_byte_imm': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^byte ptr \[rdi \+ (0x[0-9a-f]+|\d+)\], (0x[0-9a-f]+|\d+)$'),
        'note': 'store8 of an immediate at rdi+K; two constants, asm by design',
        'kind': 'asm_st_imm8',
    },
    # NOT 'mov_rax_rdi': docs quote a count for the `leaf_mov_rax` prefix (3,619 = the
    # mov rax,[rdi+K] family), and a prefix is a *prefix* -- a second family under it made
    # test_doc_numbers read 3,794 and test_approval_request's member-set hash stale. A family
    # name has to be distinguishable from every prefix already quoted in a document.
    'rax_rdi': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^rax, rdi$'),
        'note': 'returns rdi; no parameter, no control flow',
        'kind': 'asm_fixed', 'asm': 'movq %rdi, %rax',
    },
    # Census over all 7,888 unlanded leaves: 6,937 decode to ONE block with no call and are
    # transcribable today (1,176 shapes); 951 need a body and a differential. These are the eight
    # largest shapes of that set -- 2,161 members. Names are chosen so that none is a prefix of a
    # family a document already quotes (leaf_lea_rdi is the 483-member family, so this one is
    # leaf_lea_disp_rdi).
    'lea_disp_rdi': {
        'mnemonics': ('lea', 'ret'),
        'operand': re.compile(r'^rax, \[rdi \+ (0x[0-9a-f]+|\d+)\]$'),
        'note': 'address of rdi+K; no branch, no call',
        'kind': 'asm_lines', 'asm': ['leaq {K}(%rdi), %rax'],
    },
    'rip_add_store': {
        'mnemonics': ('lea', 'add', 'mov', 'ret'),
        'operand': re.compile(r'^rax, \[rip \+ (0x[0-9a-f]+|\d+)\]$'),
        'k2_from': (1, re.compile(r'^rax, (0x[0-9a-f]+|\d+)$')),
        'note': 'resolved rip-relative address + K2, stored at [rdi]; returns it',
        'kind': 'c_addr_add_store', 'resolved': True,
    },
    'vmovss_load': {
        'mnemonics': ('vmovss', 'ret'),
        'operand': re.compile(r'^xmm0, dword ptr \[rdi \+ (0x[0-9a-f]+|\d+)\]$'),
        'note': 'float load at rdi+K',
        'kind': 'asm_lines', 'asm': ['vmovss {K}(%rdi), %xmm0'],
    },
    'rip_load': {
        'mnemonics': ('lea', 'mov', 'ret'),
        'operand': re.compile(r'^rax, \[rip \+ (0x[0-9a-f]+|\d+)\]$'),
        'k2_from': (1, re.compile(r'^eax, dword ptr \[rax\]$')),
        'note': 'dereference a rip-relative pointer: a 4-byte load, zero-extended into rax',
        'kind': 'c_addr_load', 'resolved': True, 'read_width': 4,
    },
    'rip_load_wide': {
        # THE PROBE'S POPULATION, not the narrow 3-instruction shape above. `rip_load` matches exactly
        # `lea rax,[rip+K]; mov eax,[rax]; ret` and finds 161 members -- every one of them reading the
        # RW segment's zero-fill tail, which _refuse_zerofill exists to stop. The wide census
        # (census_rip_load.scan(64, False)) keeps any non-branching load-first RIP-relative body
        # inside filesz: 11 members, 6 of them neighbour-uniform within +4. Selected by the census's
        # own scan so the family cannot be chosen by one matcher and priced by another.
        'mnemonics': ('lea', 'mov', 'ret'), 'operand': re.compile(r'^rax, \[rip \+ (0x[0-9a-f]+|\d+)\]$'),
        'note': 'any-size rip-relative load inside filesz; reads pbl_image_base+(target-kGuestLoadBase)',
        'kind': 'c_addr_load', 'resolved': True, 'read_width': 4, 'wide_selector': True,
    },
    'chain_deref': {
        # mov rax,[rip+K] ; mov [rax+K2],imm ; ret -- 78 rows, measured from the ELF and never from a name.
        # The table is symbols/chain_family.csv, which carries what the case must satisfy (slot, k2, imm,
        # width). The address column of THAT table is GUEST space: leaf_shape_census reads it at
        # `addr - BIAS`, so `addr + EBOOT_BASE` is a double add and lands 4 MiB past the body.
        'mnemonics': ('mov', 'mov', 'ret'), 'operand': re.compile(r'^rax, \[rip \+ '),
        'note': 'load a pointer from the RW slot, store imm at +K2 through it, return the pointer',
        'kind': 'c_chain_store', 'chain_selector': True,
    },
    'st_sil8': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^byte ptr \[rdi \+ (0x[0-9a-f]+|\d+)\], sil$'),
        'note': 'store8 of sil at rdi+K',
        'kind': 'asm_lines', 'asm': ['movb %sil, {K}(%rdi)'],
    },
    # RETRACTED FROM THE BYTE TIER (ee1ac58) AND REBUILT HERE. These two were `asm_lines` with
    # `leaq {K}(%rip)`: the assembler resolved K against the .so's own layout, so the executed
    # bytes were identical and the VALUE was the wrong address -- `.so + K` where the original
    # computed `guest + K`. The bytes were right; the claim was false. Now the address is resolved
    # at emission time (end of the lea + disp) into a constant and returned, the convention the
    # 8,072 leaf_lea_rip bodies already use, and the evidence is a differential against cases that
    # seed a buffer and compare both the return and the bytes written.
    'rip_store': {
        'mnemonics': ('lea', 'mov', 'ret'),
        'operand': re.compile(r'^rax, \[rip \+ (0x[0-9a-f]+|\d+)\]$'),
        'k2_from': (1, re.compile(r'^qword ptr \[rdi\], rax$')),
        'note': 'store the resolved address of a rip-relative object at [rdi]; returns it',
        'kind': 'c_addr_store', 'resolved': True,
    },
    'st_imm32': {
        'mnemonics': ('mov', 'ret'),
        'operand': re.compile(r'^dword ptr \[rdi \+ (0x[0-9a-f]+|\d+)\], (0x[0-9a-f]+|\d+)$'),
        'note': 'store32 of an immediate at rdi+K',
        'kind': 'asm_lines', 'asm': ['movl ${K2}, {K}(%rdi)'],
    },
    'vmovss_store': {
        'mnemonics': ('vmovss', 'ret'),
        'operand': re.compile(r'^dword ptr \[rdi \+ (0x[0-9a-f]+|\d+)\], xmm0$'),
        'note': 'float store of xmm0 at rdi+K',
        'kind': 'asm_lines', 'asm': ['vmovss %xmm0, {K}(%rdi)'],
    },
}
RAX_SEED = '0xdeadbeef00000000'


def landed_rows(name):
    """{address: ladder name} for the rows this emitter owns: `leaf_<name>_<address>`.

    Read here and in members(), from the same file, so the landing path and a re-emit cannot
    disagree about how many members a family has.
    """
    key_prefix = f'leaf_{name}'
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'symbols', 'functions.csv'))):
        head, _, tail = r['name'].rpartition('_')
        if head == key_prefix and len(tail) == 8 and all(c in '0123456789abcdef' for c in tail):
            out[int(r['address'], 16)] = r['name']
    return out


def members(name, landed=False):
    """Members of one family, from the census -- one selector, whichever path is asking.

    landed=False (the landing path): every address that carries no row yet. A family must never
    emit over an address that already has a row, because two ladder names for one address is a
    duplicate coverage row and validate_functions refuses it ("addresses must be unique").
    lea_disp_rdi was the first shape whose total (1,462) differed from its unlanded population
    (979): the 483 already carried leaf_lea_rdi_* rows.

    landed=True (the re-emit path): exactly the addresses that already carry a
    `leaf_<name>_*` row. This is what makes "what did I emit" answerable by a program instead
    of by parsing the artifact -- the 647 retraction was a name filter over a file and matched
    362 of 647, which is the shape of a question the generator could not answer.
    """
    spec = TEMPLATES[name]
    if spec.get('chain_selector'):
        # The family's population is symbols/chain_family.csv -- the table the pre-registration refuses
        # against -- so the emitter and the refusal cannot disagree about how many members exist.
        owned0 = set(landed_rows(name))
        # `landed` IS HONOURED HERE, one predicate for both modes, the same shape as the wide path.
        # The branch returned `for r in rows` filtered unconditionally -- so landed=True returned the
        # UNLANDED set, and a post-record re-emit would regenerate all 78 members and invalidate the
        # family's evidence by definition. Found because a test asserted 78 over the union and got 154.
        rows = [r for r in catalogue.read_rows(os.path.join(ROOT, 'symbols', 'chain_family.csv'))
                if (r['address'] in owned0) == bool(landed)]
        # read_rows parses `address` and `size` and leaves every other column as written; the hex columns
        # are hex text (`0x1520`), so they are converted at the boundary, once, not at each use site.
        return [{'address': r['address'], 'size': r['size'], 'k': int(str(r['load_disp']), 0),
                 'slot': int(str(r['load_target']), 0), 'k2': int(str(r['store_k2']), 0),
                 'imm': int(str(r['imm']), 0), 'width': int(str(r['store_width']), 0)}
                for r in rows]
    if spec.get('wide_selector'):
        import census_rip_load as W
        taken0 = {int(r['address'], 16) for r in
                  csv.DictReader(open(os.path.join(ROOT, 'symbols', 'functions.csv')))}
        owned0 = set(landed_rows(name))
        recs = W.scan(64, False)[3]
        # RETIRED members are excluded by a TABLE, not by a filter living in someone's head.
        # symbols/retired.csv: address,reason,date,revisit. An exclusion with no row is refused
        # by tools/check_retired.py; this line only implements the table's verdict.
        retired = set()
        rp = os.path.join(ROOT, 'symbols', 'retired.csv')
        if os.path.exists(rp):
            retired = {int(r['address'], 16) for r in csv.DictReader(open(rp)) if r.get('reason', '').strip()}
        out = []
        for r in recs:
            if r['where'] != 'filesz':
                continue
            if r['address'] in retired:
                continue
            # KEEP the members this mode is about -- landed: the owned ones; landing: the free ones.
            # The first version of this test dropped exactly the rows it was asked to reproduce, and
            # the re-emit gate refused 0 of 11 landed members: the filter was inverted, not the body.
            keep = (r['address'] in owned0) if landed else (r['address'] not in taken0)
            if not keep:
                continue
            out.append({'address': r['address'], 'size': r['size'], 'k': r['target'],
                        'width': r.get('width', 4), 'k2': 0, 'res': r['target']})
        return sorted(out, key=lambda m: m['address'])
    md, cs = open(C.ELF, 'rb').read(), capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = False
    taken = {int(r['address'], 16) for r in
             csv.DictReader(open(os.path.join(ROOT, 'symbols', 'functions.csv')))}
    owned = set(landed_rows(name))

    def want(addr):
        return addr in owned if landed else addr not in taken

    out = []
    for addr, size, ins in C.members(md, cs):
        if not want(addr):
            continue
        if len(ins) != len(spec['mnemonics']) or tuple(i.mnemonic for i in ins) != spec['mnemonics']:
            continue
        m = spec['operand'].match(ins[0].op_str)
        if not m:
            continue
        k2 = int(m.group(2), 0) if m.groups() and len(m.groups()) > 1 else 0
        if 'k2_from' in spec:
            idx, rx = spec['k2_from']
            mm = rx.match(ins[idx].op_str)
            if not mm:
                continue
            k2 = int(mm.group(1), 0) if mm.groups() else 0
        rec = {'address': addr, 'size': size,
               'k': int(m.group(1), 0) if m.groups() else 0, 'k2': k2}
        if spec.get('resolved'):
            # end of the lea + disp: the address the original computes at run time. A constant in
            # the body, so nothing about the .so's layout can leak into the value.
            rec['res'] = addr + ins[0].size + rec['k']
        out.append(rec)
    return out


def key(name, m):
    return f'leaf_{name}_{m["address"]:08x}'


def _refuse_zerofill(name, ms, store=False):
    """Refuse a family whose read/write targets land in a PT_LOAD's zero-fill tail.

    WHAT THIS CHECK MEASURES: addresses against the program headers. That is all. It cannot see a
    case file, so it cannot conclude anything about discrimination -- and for a long time this
    docstring did exactly that, saying a target in the zero-fill tail is "a constant 0 no case can
    discriminate". The premise is true (the loader fills nothing there) and the conclusion is not
    reachable from the premise: `harness.py:458` admits a `fixture_setup` write anywhere inside a
    segment's memsz, and `snapshot()` at :657 reads memsz, so a case that SEEDS the slot supplies
    the discriminating value itself -- measured by mapping the image, writing a pointer into the
    tail of RW, and reading it back through the image.

    So there are two conditions and they are not the same refusal:

      * address in no PT_LOAD memsz  -> a read or a write FAULTS. Nothing can be emitted.
      * past p_filesz, inside p_memsz -> the slot holds zero until something writes it, so the
        member needs a SEEDING CASE. Emitting it without one would produce a body and its mutant
        both reading zero: 78 greens certifying the harness.

    The seeding belongs in the case file, not in a new tier value or a fourth status -- a seeded
    slot is covered by `cases_sha256`, the column that already pins every other fixture input.

    `rip_load`'s 161 members all read 0x5820e88..0x58b9d44 against RW filesz ending at 0x57e5b38 --
    inside memsz, past filesz. Under the corrected reading they are SEEDING-REQUIRED, not dead, and
    are re-derived deliberately rather than in passing.
    """
    # No pyelftools in the venv: parse the program headers directly. eboot.elf has e_shoff = 0
    # (no section table), so PT_LOADs are the only authority on what the loader maps and fills.
    import struct
    with open(C.ELF, 'rb') as fh:
        blob = fh.read(64)
        phoff, = struct.unpack_from('<Q', blob, 0x20)
        phentsize, phnum = struct.unpack_from('<HH', blob, 0x36)
        fh.seek(phoff)
        ph = fh.read(phentsize * phnum)
    segs, reserves = [], []
    for k in range(phnum):
        p_type, = struct.unpack_from('<I', ph, k * phentsize)
        vaddr, = struct.unpack_from('<Q', ph, k * phentsize + 0x10)
        filesz, = struct.unpack_from('<Q', ph, k * phentsize + 0x20)
        memsz, = struct.unpack_from('<Q', ph, k * phentsize + 0x28)
        if p_type == 1:  # PT_LOAD
            base = vaddr + 0x400000
            segs.append((base, base + filesz))       # FILLED by the loader
            reserves.append((base, base + memsz))    # RESERVED (filled with zeros first)
    unmapped, seeded, past_by = [], [], None
    for m in ms:
        r = m.get('res')
        if r is None:
            continue
        inside = segs if not store else reserves
        if any(lo <= r < hi for lo, hi in inside):
            continue
        if not store and any(lo <= r < hi for lo, hi in reserves):
            seeded.append((m['address'], r))
            continue
        unmapped.append((m['address'], r))
    if unmapped:
        a, r = unmapped[0]
        raise SystemExit(
            f'emit {name} refused: {len(unmapped)} of {len(ms)} members name an address in NO PT_LOAD '
            f'{"memsz (a store there faults)" if store else "memsz"}; first {a:#x} -> {r:#x}. '
            f'Question this answers: is the address backed by a segment at all. Nothing else.')
    if seeded:
        a, r = seeded[0]
        raise SystemExit(
            f'emit {name} refused: {len(seeded)} of {len(ms)} members load past p_filesz but inside '
            f'p_memsz -- SEEDING REQUIRED; first {a:#x} -> {r:#x}. Question this answers: is the '
            f'slot file-backed. Not answered here: whether a case can discriminate -- a '
            f'`fixture_setup` write inside memsz can, so these members are blocked on a seeding case '
            f'and a gate that checks the case seeds the slot, not on the address.')


def pilot_choice(ms):
    """The one member that exercises the most mechanisms. A function, not a block in main(), because a
    selection rule that only exists inside `main` is a rule no test can call and no reader can re-run."""
    groups = {}
    for m in ms:
        groups.setdefault((m['slot'], m['k2'], m['imm'], m['width']), []).append(m)
    shared = [(k, v) for k, v in groups.items() if len(v) > 1]
    assert shared, 'no shared behavioural key -- the pilot rule has nothing to select'
    kk, vv = sorted(shared, key=lambda kv: (-kv[0][3], -len(kv[1]), kv[1][0]['address']))[0]
    return min(vv, key=lambda m: m['address']), kk, len(vv)


def body_text(name, ms):
    if TEMPLATES[name]['kind'] == 'c_chain_store':
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// mov rax,[rip+K] ; mov [rax+K2],imm ; ret -- a pointer loaded from the RW slot and',
                 '// stored through. The slot is read in IMAGE space via pbl_image_base; the value it',
                 '// holds is a GUEST pointer, which is what the case seeds and what the game holds.',
                 '#include <cstdint>',
                 '#include "load_base.h"',
                 '']
        for m in ms:
            k = key(name, m)
            w = m['width']
            cty = {1: 'std::uint8_t', 4: 'std::uint32_t'}[w]
            # NAMED, because the readability gate refuses a bare literal in game/ and it is right to:
            # `0xf0` is a coordinate, `kStoreDisp` is its meaning. Local constexpr, so 78 bodies in one
            # translation unit cannot collide, and the names live where the numbers are used.
            lines += [f'extern "C" __attribute__((used)) std::uint64_t bb_{k}(void) {{',
                      f'  constexpr std::uintptr_t kSlot = {m["slot"]:#x};',
                      f'  constexpr std::uintptr_t kStoreDisp = {m["k2"]:#x};',
                      f'  constexpr std::uint64_t kImm = {m["imm"]:#x};',
                      '  (void)kImm;',
                      f'  auto *slot = reinterpret_cast<std::uintptr_t *>('
                      'reinterpret_cast<char *>(pbl_image_base) + kSlot - kGuestLoadBase);',
                      '  std::uintptr_t p = *slot;',
                      f'  *reinterpret_cast<{cty} *>(p + kStoreDisp) = static_cast<{cty}>(kImm);',
                      '  return p;',
                      '}', '']
        return '\n'.join(lines)
    _refuse_zerofill(name, ms)
    spec = TEMPLATES[name]
    if spec['kind'] == 'asm_ret':
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// asm by design (docs/decisions.md 1). BYTE-IDENTICAL to the original extent;',
                 '// the SOURCE FORM is a decision and is NOT evidenced by those bytes -- an empty C',
                 '// void body is a claim about today\'s flags, not a proof about this one.',
                 '']
        for m in ms:
            k = key(name, m)
            lines += [f'extern "C" __attribute__((naked)) void bb_{k}(void) {{',
                      '  __asm__ volatile("ret");',
                      '}', '']
        return '\n'.join(lines)
    if spec['kind'] == 'asm_lines':
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// asm by design (docs/decisions.md 1): one basic block, no branch, no call.',
                 '']
        for m in ms:
            k = key(name, m)
            parts = [ln.format(K=f'{m["k"]:#x}', K2=f'{m["k2"]:#x}') for ln in spec['asm']]
            lines += [f'extern "C" __attribute__((naked)) void bb_{k}(void) {{',
                      '  __asm__ volatile("' + '\\n\\t'.join(parts) + '\\n\\tret");',
                      '}', '']
        return '\n'.join(lines)
    if spec['kind'] == 'asm_fixed':
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// asm by design (docs/decisions.md 1): one basic block, no branch, no call.',
                 '']
        for m in ms:
            k = key(name, m)
            lines += [f'extern "C" __attribute__((naked)) void bb_{k}(void) {{',
                      '  __asm__ volatile("' + spec['asm'] + '\\n\\tret");',
                      '}', '']
        return '\n'.join(lines)
    if spec['kind'] in ('asm_st_reg', 'asm_st_imm8'):
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// asm by design (docs/decisions.md 1): the store IS the function; byte evidence.',
                 '#define BB_STR_(x) #x', '#define BB_STR(x) BB_STR_(x)', '']
        for m in ms:
            k = key(name, m)
            if spec['kind'] == 'asm_st_reg':
                body = f'"mov{spec["sfx"]} {spec["reg"]}, " BB_STR(k_{k}) "(%rdi)'
            else:
                body = ('"movb $" BB_STR(k_' + k + '_v) ", " BB_STR(k_' + k + ') "(%rdi)')
            extra = ([f'#define k_{k}_v {m["k2"]:#x}'] if spec['kind'] == 'asm_st_imm8' else [])
            lines += [f'#define k_{k} {m["k"]:#x}'] + extra + [
                f'extern "C" __attribute__((naked)) void bb_{k}(void) {{',
                '  __asm__ volatile(' + body + '\\n\\tret");',
                '}', '']
        return '\n'.join(lines)
    if spec['kind'] in ('asm_imm8', 'asm_al_mem'):
        form = ('movb $" BB_STR(k_%s) ", %%al' if spec['kind'] == 'asm_imm8'
                else 'movb " BB_STR(k_%s) "(%%rdi), %%al')
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// asm by design (docs/decisions.md 1): one instruction plus terminator, and the',
                 '// evidence is that these bytes equal the original extent (evidence=byte-identical).',
                 '#define BB_STR_(x) #x', '#define BB_STR(x) BB_STR_(x)', '']
        for m in ms:
            k = key(name, m)
            lines += [
                f'#define k_{k} {m["k"]:#x}',
                f'extern "C" __attribute__((naked)) void bb_{k}(void) {{',
                # basic asm (no operands): `%` is literal, so `%%al` would reach the assembler as
                # `%%al` and read as an invalid register name. Single `%` is correct here.
                '  __asm__ volatile("' + (form % k).replace('%%', '%') + '\\n\\tret");',
                '}', '']
        return '\n'.join(lines)
    if spec['kind'] == 'asm_imm8':
        # BYTE-EVIDENCE family: the executed bytes ARE the claim, so there are no cases. The macro
        # needs TWO levels or the operand never interpolates: BB_STR(k) stringifies the macro's
        # value, while a single level would hand the assembler the NAME and it would read as a bad
        # constant rather than a bad macro.
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// asm by design (docs/decisions.md 1): one instruction plus terminator, and the',
                 '// evidence is that these bytes equal the original extent (evidence=byte-identical).',
                 '#define BB_STR_(x) #x', '#define BB_STR(x) BB_STR_(x)', '']
        for m in ms:
            k = key(name, m)
            lines += [
                f'#define k_{k} {m["k"]:#x}',
                f'extern "C" __attribute__((naked)) void bb_{k}(void) {{',
                f'  __asm__ volatile("movb $" BB_STR(k_{k}) ", %al\\n\\tret");',
                '}', '']
        return '\n'.join(lines)
    if spec['kind'] == 'imm8':
        raise SystemExit(f'{name}: refuses to emit -- a body that reads a case-seeded register other '
                         'than the one the original reads is a fabricated input; see the row comment')
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '#include <cstdint>', '']
        for m in ms:
            k = key(name, m)
            lines += [
                f'extern "C" std::uint64_t bb_{k}(std::uint64_t a0) {{',
                f'  constexpr std::uint64_t k_{k} = {m["k"]:#x}u;',
                f'  constexpr std::uint64_t k_{k}_low8 = 0xffu;',
                f'  return (a0 & ~k_{k}_low8) | k_{k};',
                '}', '']
        return '\n'.join(lines)
    if spec['kind'] in ('c_addr_store', 'c_addr_add_store'):
        lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
                 '// The address is RESOLVED AT EMISSION TIME (end of the lea + disp) into a',
                 '// constant. Assembled rip-relative it would have been `.so + K`, which is the',
                 '// defect that retracted these rows from the byte tier (ee1ac58): identical',
                 '// bytes, wrong value. A C body cannot make that mistake, and the differential',
                 '// can see it if it ever does.',
                 '#include <cstdint>', '']
        for m in ms:
            k = key(name, m)
            v = m['res'] + m['k2'] if spec['kind'] == 'c_addr_add_store' else m['res']
            lines += [
                f'extern "C" std::uint64_t bb_{k}(std::uint64_t *a1) {{',
                f'  constexpr std::uint64_t v = {v:#x}u;',
                '  *a1 = v;',
                '  return v;',
                '}', '']
        return '\n'.join(lines)
    lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
             '#include <cstdint>', '#include <cstring>', '']
    if spec['kind'] == 'c_addr_load':
        # THE BASE IS NOT THIS FAMILY'S TO DEFINE. This template predated load_base.h and carried its
        # own weak `pbl_image_base` plus a bare 0x400000 literal. Generated code reads the shared
        # header instead: one definition, one place to change, and no weak definition in a body that
        # load_base.h rejected that design in writing. The style gate also refuses a bare 0x400000 --
        # rightly, since the constant decides which space the read lands in.
        out = ['// generated by tools/emit_leaf_family.py -- do not edit',
               '#include <cstdint>',
               '#include <cstring>',
               '',
               '#include "load_base.h"',
               '']
        for m in ms:
            k = key(name, m)
            out += [f'extern "C" std::uint64_t bb_{k}(std::uint64_t a1) {{',
                    '  (void)a1;',
                    f'  constexpr std::uint64_t at = {m["res"]:#x}u;   // GUEST address',
                    '  const void *src = reinterpret_cast<const void *>',
                    '      (pbl_image_base + (at - kGuestLoadBase));',
                    # WIDTH PER MEMBER from the decode: 8 only for a `48 8b` qword load. A
                    # 4-byte read of a relocated pointer returns the low half and the discarded
                    # half IS the base -- which is why 00dfb9e0 looked like a space bug.
                    ('  std::uint64_t out = 0;\n  std::memcpy(&out, src, sizeof out);\n  return out;'
                     if m.get('width') == 8 else
                     '  std::uint32_t out = 0;\n  std::memcpy(&out, src, sizeof out);\n  return out;'),
                    '}', '']
        return '\n'.join(out)
    if any(m for m in ms) and spec['kind'] == 'c_addr_load':
        # The base a dereferencing body runs against, supplied by the RUNNER: the harness sets it to
        # IMAGE (cs 0x800000000, where harness.py:257 maps the image); the runtime leaves it 0, which
        # is in-game semantics because the guest address IS the load address (Map is identity or
        # refusal). Default 0 and not IMAGE, so a runner that forgets to set it faults loudly on the
        # dereference instead of silently running a body tuned to the harness's mapping.
        # Weak + default visibility: one definition wins, and ctypes.CDLL(...).pbl_image_base works.
        lines = lines[:2] + [
            'extern "C" __attribute__((weak, visibility("default")))',
            'std::uintptr_t pbl_image_base = 0;', ''] + lines[2:]
    for m in ms:
        k = key(name, m)
        lines += [
            f'extern "C" std::uint64_t bb_{k}(std::uint64_t a0) {{',
            f'  constexpr std::uint64_t k_{k} = {m["k"]:#x}u;',
            f'  constexpr std::uint64_t k_{k}_width = {spec["width"]}u;',
            f'  std::uint32_t v = 0;',
            f'  std::memcpy(&v, reinterpret_cast<void*>(a0 + k_{k}), k_{k}_width);',
            '  return v;',
            '}', '']
    return '\n'.join(lines)


def case_docs(name, m):
    k = key(name, m)
    if TEMPLATES[name]['kind'] == 'c_addr_load':
        # NO args and NO buffers. `k` in `%rip+K` is a DISPLACEMENT, not an offset into a buffer, so
        # the generic branch seeded buffers of k+16 = 44-75 MB for a body that never reads a1: the
        # 503 MB lesson repeated at a hundred times the scale. One case per member; the harness sets
        # pbl_image_base to the runner's base, and the base is the runner's business, not a case's.
        # Adequacy is not a marker: it is the measured fact that the dword at `res` differs from its
        # neighbour in 161/161 members, so a wrong constant cannot reproduce the value it returns.
        yield f'{k}.json', {'schema': 1, 'address': f'{m["address"]:#010x}',
                            'returns': 'i64', 'args': {}}
        return
    if TEMPLATES[name]['kind'] == 'c_chain_store':
        # One case per BEHAVIOURAL key (slot, k2, imm, width): the identity is the resolved slot, not the
        # load displacement, so 78 rows share 62 cases. The slot holds a GUEST pointer -- never `pointer`,
        # which resolves into the sandbox, where observability passes while the space is wrong. The
        # destination is pre-set to a sentinel so a store of `imm == 0` into zero-fill still discriminates:
        # 31 of 78 rows store 0, where seed and no-seed are otherwise indistinguishable.
        # THE SENTINEL GOES WHERE THE BODY STORES, not where the pointer points. The body writes at
        # `p + k2`; pre-setting `p` left the store target in zero-fill, so an imm==0 store changed no
        # byte and the FIRST pilot run reported `writes: []` -- green, and blind, in the same run.
        dest = m['slot'] + 0x100
        target = dest + m['k2']
        sentinel = f'{CHAIN_SENTINEL:02x}' * m['width']
        mask = (1 << (8 * m['width'])) - 1
        assert (m['imm'] & mask) != CHAIN_SENTINEL, \
            f'{k}: imm {m["imm"]:#x} collides with the sentinel byte -- nothing would discriminate'
        yield f'{k}.json', {
            'schema': 1, 'address': f'{m["address"]:#010x}', 'returns': 'i64',
            'args': {},
            # `addr` is `buf:NAME` or a BARE guest address (harness.py:395: hexint(target) -> guest()).
            # 'guest:' is a VALUE form, not an address form -- emitting it here made the trace path fail
            # with `invalid literal for int() with base 0`, on the first case of the family.
            'memory': [{'addr': f'{m["slot"]:#x}', 'guest': f'{dest:#x}'},
                       {'addr': f'{target:#x}', 'bytes': sentinel}],
        }
        return
    if TEMPLATES[name]['kind'] == 'imm8':
        for tag, seed in zip(('m1', 'm2', 'm3'), (RAX_SEED, '0x0123456789abcdef', '0xffffffffffffffff')):
            yield f'{k}_{tag}.json', {
                'schema': 1, 'address': f'{m["address"]:#010x}', 'returns': 'i64',
                'args': {'rax': seed, 'rsi': seed},
            }
        return
    if TEMPLATES[name]['kind'] in ('c_addr_store', 'c_addr_add_store'):
        # One 8-byte buffer, three different seeds. The seed is not decoration: a body that stored
        # only four bytes would leave the other four as the marker and its `writes` would differ
        # from the original's, which is the only way this family fails short of a wrong constant.
        for tag, marker in zip(('m1', 'm2', 'm3'), MARKERS):
            yield f'{k}_{tag}.json', {
                'schema': 1, 'address': f'{m["address"]:#010x}', 'returns': 'i64',
                'args': {'rdi': 'buf:out'},
                'buffers': {'out': {'size': 16}},
                'memory': [{'addr': 'buf:out+0x8', 'bytes': marker}],
                # The stored value IS an address, and the original runs relocated in the host
                # mapping, so the slot is compared in guest space with the ORIGINAL's bytes
                # translated (harness.SIDE). Without this a correct replacement fails 3/3.
                'guest_address_slots': [{'addr': 'buf:out+0x0', 'width': 8}],
            }
        return
    for tag, marker in zip(('m1', 'm2', 'm3'), MARKERS):
        yield f'{k}_{tag}.json', {
            'schema': 1, 'address': f'{m["address"]:#010x}', 'returns': 'i64',
            'args': {'rdi': 'buf:buf0'},
            # The buffer is allocated by size and left zero; the marker is written AT the displacement
            # the body reads. Padding `bytes` to K cost 503 MB of corpus; a preset costs 8 bytes.
            'buffers': {'buf0': {'size': m['k'] + 16}},
            'memory': [{'addr': f'buf:buf0+{m["k"]:#x}', 'bytes': marker}],
        }


def compare_text(generated, committed):
    """(ok, message). Byte comparison that names the first differing line.

    A re-emit that prints "ok" without saying where two texts differ cannot distinguish its own
    success from a file nobody changed, so the message carries the line and both forms.
    """
    if committed is None:
        return False, 'the committed body does not exist'
    if generated == committed:
        return True, 'byte-for-byte'
    g, c = generated.splitlines(), committed.splitlines()
    for i, (x, y) in enumerate(zip(g, c)):
        if x != y:
            return False, (f'first difference at line {i + 1}: '
                           f'disk {y.strip()!r} vs generator {x.strip()!r}')
    return False, f'line count differs: disk {len(c)}, generator {len(g)}'


def retired_addresses(root=None):
    """Addresses with a verdict against a body, from symbols/retired.csv.

    ONE implementation: the emitter's exclusion, the test's expected count and promote.py's skip
    all mean the same set, and a row with a blank reason is not a verdict -- absence refuses.
    """
    rp = os.path.join(root or ROOT, 'symbols', 'retired.csv')
    if not os.path.exists(rp):
        return set()
    return {int(r['address'], 16) for r in csv.DictReader(open(rp)) if r.get('reason', '').strip()}


def reemit(name, write=False):
    """Re-derive a landed family's body from its rows and compare it with the committed file.

    The population is the family's own landed rows, and the census must reproduce every one of
    them: a member that cannot be re-derived is a member whose body no program can vouch for, so
    this refuses and names the addresses rather than emitting a slightly smaller family. Writing
    is opt-in, because regenerate-from-source means the generator's output replaces the file --
    after which `git status` is what shows whether they differed.
    """
    path = os.path.join(ROOT, 'game', 'leaf', f'{name}_family.cpp')
    owned = landed_rows(name)
    if not owned:
        return 1, f're-emit {name}: no `leaf_{name}_*` rows -- nothing was emitted for this family'
    ms = members(name, landed=True)
    have = {m['address'] for m in ms}
    # A RETIRED member is a landed row with no body, BY VERDICT. Both directions are refusals:
    # a retired row that still has a body is code running under a verdict, and a member that is
    # missing and NOT retired is a body the generator can no longer vouch for.
    retired = retired_addresses()
    still_there = sorted(have & retired)
    if still_there:
        return 1, (f're-emit {name} refused: {len(still_there)} retired member(s) still carry a body '
                   f'-- {[hex(a) for a in still_there]}; retirement is a verdict about the body')
    missing = sorted(set(owned) - have - retired)
    extra = sorted(have - set(owned))
    unlisted = sorted((set(owned) - have) & retired)
    if missing or extra:
        return 1, (f're-emit {name} refused: {len(have)} of {len(owned)} landed members '
                   f'reproduce ({len(unlisted)} retired); missing {len(missing)} '
                   f'{[hex(a) for a in missing[:4]]}; unexpected {len(extra)} {[hex(a) for a in extra[:4]]}')
    generated = body_text(name, ms)
    committed = open(path).read() if os.path.exists(path) else None
    ok, message = compare_text(generated, committed)
    if ok:
        return 0, f're-emit {name}: {path} reproduced byte-for-byte ({len(ms)} members)'
    if write:
        # The generator's text replaces the file. Print the difference being fixed, then prove the
        # write by re-reading it: a truncated write is otherwise found only at the next --reemit.
        atomic_write(path, generated)
        back = open(path).read()
        if back != generated:
            return 1, (f're-emit {name}: WROTE {path} and the re-read does not match the generator '
                       f'({len(back)} vs {len(generated)} bytes) -- the write is not the file')
        return 0, (f're-emit {name}: wrote {path} ({len(ms)} members, re-read identical); fixed: '
                   f'{message} -- run git status: the generator has to be the thing that changed it')
    return 1, f're-emit {name}: {message}'


def main(argv):
    # THE SUBJECT IS REQUIRED. This line used to fall back to 'mov_eax_mem', so
    # `--reemit rip_load_wide` (family after the flag) re-emitted 765 mov_eax_mem bodies,
    # exited 0, and printed a success line naming a family nobody asked about. A tool whose
    # subject defaults can succeed about the wrong thing; the third instance this session
    # after build/ vs build-release and --lib defaulting to Path('.').
    if not argv or argv[0].startswith('-'):
        print(f'emit_leaf_family: family name required as the FIRST argument, before any flag. '
              f'Known families: {", ".join(sorted(TEMPLATES))}', file=sys.stderr)
        return 2
    name = argv[0]
    if name not in TEMPLATES:
        print(f'emit_leaf_family: unknown family {name!r}; refusing rather than guessing. '
              f'Known families: {", ".join(sorted(TEMPLATES))}', file=sys.stderr)
        return 2
    if '--reemit' in argv:
        rc, message = reemit(name, write='--write' in argv)
        print(message)
        return rc
    ms = members(name)
    if '--pilot' in argv:
        # SELECTED BY RULE, NOT BY ORDER. `--limit 1` takes the first address, which is width 1; the pilot
        # must exercise the widest truncation AND a shared case, because those are the two mechanisms the
        # other 77 rows reuse. Keyed on the behavioural identity (slot, k2, imm, width): most members
        # sharing one key, then widest width, then lowest address.
        chosen, kk, n_shared = pilot_choice(ms)
        print(f'{name}: PILOT -- behavioural key slot={kk[0]:#x} k2={kk[1]:#x} imm={kk[2]:#x} '
              f'width={kk[3]} shared by {n_shared} row(s); selected {chosen["address"]:#010x} of '
              f'{len(ms)} members. The family is not complete until this runs without --pilot')
        ms = [chosen]
    if '--limit' in argv:
        # A pilot is one member through the whole chain, chosen so a 78-row failure is a 1-row failure.
        n = int(argv[argv.index('--limit') + 1])
        print(f'{name}: PILOT -- limiting to {n} of {len(ms)} members; the family is not complete '
              f'until this runs without --limit')
        ms = ms[:n]
    owned = landed_rows(name)
    if not ms:
        # Zero members is a refusal with a reason, never `min() iterable argument is empty`:
        # an emitter that cannot re-emit cannot repair either, so the message names the door.
        if owned:
            print(f'{name}: 0 unlanded members ({len(owned)} already landed). Nothing to land here; '
                  f'`--reemit {name}` checks that the committed body is what this emitter produces.')
        else:
            print(f'{name}: 0 members -- the census found no unlanded extent matching this shape, '
                  f'so there is nothing to land and nothing to re-emit.')
        return 1
    ks = sorted({m['k'] for m in ms})
    sizes = {}
    for m in ms:
        sizes[m['size']] = sizes.get(m['size'], 0) + 1
    print(f'{name}: {len(ms)} members | distinct K {len(ks)} | K {min(ks):#x}..{max(ks):#x}')
    print(f'  sizes {sizes} -> +{sum(k * v for k, v in sizes.items())} B')
    if TEMPLATES[name]['kind'] in ('c_addr_store', 'c_addr_add_store'):
        print(f'  buffers 16 B seeded at +0x8; resolved addresses {len({m["res"] for m in ms})} distinct')
    elif TEMPLATES[name]['kind'] == 'c_chain_store':
        # `k` is a rip displacement, not a buffer offset: printing `k + 12` as a buffer size described a
        # 69 MB buffer for a body that reads none. Print what the case must satisfy instead.
        print(f'  slots {len({m["slot"] for m in ms})} distinct | k2 {min(m["k2"] for m in ms):#x}..'
              f'{max(m["k2"] for m in ms):#x} | imm {sorted({m["imm"] for m in ms})} | '
              f'widths {sorted({m["width"] for m in ms})}')
    elif not TEMPLATES[name]['kind'].startswith('asm'):
        print(f'  buffer sizes {min(m["k"] for m in ms) + 12}..{max(m["k"] for m in ms) + 12}')
    if TEMPLATES[name]['kind'].startswith('asm'):
        print('  cases 0 (byte evidence: the executed bytes are the claim)')
    else:
        # Counted by asking case_docs, not by multiplying by MARKERS: the printed count was a second
        # implementation of the same fact and still printed 483 after the family went to one case
        # per member. A count printed beside the thing it counts must come from that thing.
        n_cases = sum(1 for m in ms for _ in case_docs(name, m))
        print(f'  cases {n_cases} files in {len(ms)} directories')
    # The body is built BEFORE anything is opened. `open(path,'w').write(body_text(...))` evaluates
    # the open first, so a refusal truncated game/leaf/<family>_family.cpp to zero bytes and left it
    # there -- the check that refused the family destroying the artifact it was protecting. It also
    # made --dry-run dishonest: the guard returned above body_text, so a dry run printed "nothing
    # written" and exited 0 for a family that refuses. Build, then ask, then write.
    generated = body_text(name, ms)   # the refusal fires HERE, before any file is opened
    dry_run = '--dry-run' in argv
    # Everything is assembled first and written second, so a dry run does all of it but the write:
    # the refusal above, the cases, the tables and the clash assertions are the parts that can fail.
    rows, pending = [], []
    for m in ms:
        k = key(name, m)
        rows.append({'address': f'{m["address"]:#010x}', 'size': str(m['size']), 'name': k,
                     'system': 'leaf', 'status': 'original'})
        if TEMPLATES[name]['kind'].startswith('asm'):
            continue
        # THE LAYOUT IS THE PRE-REGISTERED SCHEMA, not the legacy one. check_seeding looks for
        # `chain/<address:08x>/case.json` -- one directory per ROW, decided before any body existed --
        # while this emitter copied `<key>/<key>.json` from the leaf families. Two layouts, one family:
        # the decision that predates the artifact is the spec, and the artifact moved.
        if TEMPLATES[name].get('chain_selector'):
            d = os.path.join(case_dir(name), f'{m["address"]:08x}')
        else:
            d = os.path.join(case_dir(name), k)
        docs = case_docs(name, m)
        if TEMPLATES[name].get('chain_selector'):
            docs = [('case.json', doc) for _, doc in docs]
        for fn, doc in docs:
            pending.append((os.path.join(d, fn), json.dumps(doc, indent=1, sort_keys=True) + '\n'))
    have = {int(r['address'], 16) for r in rows}
    tables = (
        ('functions.csv', lambda ex: (ex + rows, list(ex[0].keys()))),
        ('install_mode.csv', lambda ex: (ex + [{'address': r['address'], 'mode': 'host'}
                                              for r in rows], ['address', 'mode'])),
        ('replacement_origins.csv', lambda ex: (ex + [{'address': r['address'], 'origin': 'generated'}
                                                      for r in rows], ['address', 'origin'])),
    )
    resolved = []
    for table, build in tables:
        path = os.path.join(ROOT, 'symbols', table)
        existing = list(csv.DictReader(open(path)))
        clash = have & {int(r['address'], 16) for r in existing}
        assert not clash, f'{table}: {len(clash)} addresses already present'
        all_rows, fields = build(existing)
        resolved.append((path, fields, all_rows))
    if dry_run:
        print(f'  dry run: would have written {len(generated)} bytes to game/leaf/{name}_family.cpp, '
              f'{len(pending)} case file(s), {len(resolved)} table(s); nothing written, no file opened')
        return 0
    atomic_write(os.path.join(ROOT, 'game', 'leaf', f'{name}_family.cpp'), generated)
    for path, text in pending:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write(path, text)
    for path, fields, all_rows in resolved:
        # One writer for every address-keyed table: sort, dup count, write, re-read. The sort has
        # been omitted by three separate writers; a fourth re-implementation arrives otherwise.
        C.write_table(path, fields, all_rows)
    print(f'  body: game/leaf/{name}_family.cpp, {len(ms)} symbols')
    if not TEMPLATES[name]['kind'].startswith('asm'):
        print(f'  cases: {len(ms)} directories under {case_dir(name)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
