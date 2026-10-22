"""One emitter for leaf shapes, driven by a table: each row is a parse, a body, a width.

The five-table write, rows-at-original-then-flip, size-from-the-member's-own-bytes and
per-constant mutants are the same code for every family; only the parse and the body
differ, so they live in TEMPLATES and nothing else is family-specific.
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import leaf_family_census as C

ROOT = C.ROOT
CASES = os.path.join(ROOT, '..', 'data', 'cases', 'leaf')
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
}
RAX_SEED = '0xdeadbeef00000000'


def members(name):
    spec = TEMPLATES[name]
    md, cs = open(C.ELF, 'rb').read(), capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = False
    out = []
    for addr, size, ins in C.members(md, cs):
        if len(ins) != len(spec['mnemonics']) or tuple(i.mnemonic for i in ins) != spec['mnemonics']:
            continue
        m = spec['operand'].match(ins[0].op_str)
        if not m:
            continue
        out.append({'address': addr, 'size': size,
                    'k': int(m.group(1), 0) if m.groups() else 0,
                    'k2': int(m.group(2), 0) if m.groups() and len(m.groups()) > 1 else 0})
    return out


def key(name, m):
    return f'leaf_{name}_{m["address"]:08x}'


def body_text(name, ms):
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
    lines = ['// generated by tools/emit_leaf_family.py -- do not edit',
             '#include <cstdint>', '#include <cstring>', '']
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
    if TEMPLATES[name]['kind'] == 'imm8':
        for tag, seed in zip(('m1', 'm2', 'm3'), (RAX_SEED, '0x0123456789abcdef', '0xffffffffffffffff')):
            yield f'{k}_{tag}.json', {
                'schema': 1, 'address': f'{m["address"]:#010x}', 'returns': 'i64',
                'args': {'rax': seed, 'rsi': seed},
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


def main(argv):
    name = argv[0] if argv and not argv[0].startswith('-') else 'mov_eax_mem'
    ms = members(name)
    ks = sorted({m['k'] for m in ms})
    sizes = {}
    for m in ms:
        sizes[m['size']] = sizes.get(m['size'], 0) + 1
    print(f'{name}: {len(ms)} members | distinct K {len(ks)} | K {min(ks):#x}..{max(ks):#x}')
    print(f'  sizes {sizes} -> +{sum(k * v for k, v in sizes.items())} B')
    if not TEMPLATES[name]['kind'].startswith('asm'):
        print(f'  buffer sizes {min(m["k"] for m in ms) + 12}..{max(m["k"] for m in ms) + 12}')
    if TEMPLATES[name]['kind'].startswith('asm'):
        print('  cases 0 (byte evidence: the executed bytes are the claim)')
    else:
        print(f'  cases {len(ms) * len(MARKERS)} files in {len(ms)} directories')
    if '--dry-run' in argv:
        print('  dry run: nothing written')
        return 0
    # five tables and the body from one iteration, so they cannot differ by one member
    open(os.path.join(ROOT, 'game', 'leaf', f'{name}_family.cpp'), 'w').write(body_text(name, ms))
    rows = []
    for m in ms:
        k = key(name, m)
        if TEMPLATES[name]['kind'].startswith('asm'):
            rows.append({'address': f'{m["address"]:#010x}', 'size': str(m['size']), 'name': k,
                         'system': 'leaf', 'status': 'original'})
            continue
        d = os.path.join(CASES, k)
        os.makedirs(d, exist_ok=True)
        for fn, doc in case_docs(name, m):
            with open(os.path.join(d, fn), 'w') as f:
                json.dump(doc, f, indent=1, sort_keys=True)
                f.write('\n')
        rows.append({'address': f'{m["address"]:#010x}', 'size': str(m['size']), 'name': k,
                     'system': 'leaf', 'status': 'original'})
    have = {int(r['address'], 16) for r in rows}
    for table, field, value in (('functions.csv', 'name', None),
                                ('install_mode.csv', 'mode', 'host'),
                                ('replacement_origins.csv', 'origin', 'generated')):
        path = os.path.join(ROOT, 'symbols', table)
        existing = list(csv.DictReader(open(path)))
        addrs = {int(r['address'], 16) for r in existing}
        clash = have & addrs
        assert not clash, f'{table}: {len(clash)} addresses already present'
        if field == 'name':
            existing += rows
            fields = list(existing[0].keys())
        elif field == 'mode':
            existing += [{'address': r['address'], 'mode': value} for r in rows]
            fields = ['address', 'mode']
        else:
            existing += [{'address': r['address'], 'origin': value} for r in rows]
            fields = ['address', 'origin']
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
            w.writeheader()
            w.writerows(existing)
        print(f'  {table}: +{len(rows)} rows')
    print(f'  body: game/leaf/{name}_family.cpp, {len(ms)} symbols')
    if not TEMPLATES[name]['kind'].startswith('asm'):
        print(f'  cases: {len(ms)} directories under {CASES}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
