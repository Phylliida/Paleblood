"""Strict census of the leaf shapes a declarative emitter would need, one row per template.

One emitter per family is 1,430 emitters. This file is the data a single emitter would read:
for each shape, the exact operand predicate and the instruction count, so a body template can
be written against a parse that refuses everything it does not recognise.
"""
import collections, csv, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELF = os.path.join(ROOT, '..', 'data', 'bb', 'elf', 'eboot.elf')
CATALOG = os.path.join(ROOT, 'symbols', 'ghidra_functions.csv')
LADDER = os.path.join(ROOT, 'symbols', 'functions.csv')
FILE_BIAS = 0x3FC000
MAX_SIZE = 16

# name -> (mnemonics sequence, operand regexes, note). A member matches only if every
# instruction matches exactly; `None` in the regex slot means "accept whatever it prints",
# which is a decision per shape, made here and visible, never a substring filter.
TEMPLATES = {
    'mov_al_imm':        (('mov', 'ret'), (r'^al, (0x[0-9a-f]+|\d+)$', None), 'writes AL only: RAX upper bits come from entry'),
    'mov_eax_mem':       (('mov', 'ret'), (r'^eax, (?:dword ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\]$', None), 'dereferences rdi: needs a declared buffer'),
    'mov_al_mem':        (('mov', 'ret'), (r'^al, (?:byte ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\]$', None), 'dereferences rdi'),
    'mov_mem_esi':       (('mov', 'ret'), (r'^(?:(?:dword|qword|byte) ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\], esi$', None), 'stores through rdi: check_memory cannot see it'),
    'mov_mem_rsi':       (('mov', 'ret'), (r'^(?:(?:dword|qword|byte) ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\], rsi$', None), 'stores through rdi'),
    'mov_mem_imm8':      (('mov', 'ret'), (r'^(?:byte ptr )?\[rdi \+ (0x[0-9a-f]+|\d+)\], (0x[0-9a-f]+|\d+)$', None), 'stores through rdi'),
    'lea_add_mov_mem':   (('lea', 'add', 'mov', 'ret'), (r'^rax, \[rip \+ (0x[0-9a-f]+|\d+)\]$', r'^rax, (0x[0-9a-f]+|\d+)$', r'^(?:qword ptr )?\[rdi\], rax$', None), 'rip-relative read plus a store'),
    'test_je_jmp':       (('test', 'je', 'jmp', 'mov'), None, 'branching shape: end state depends on a comparison'),
}


def members(md, cs):
    for r in csv.DictReader(open(CATALOG)):
        addr, size = int(r['address'], 16), int(r['size'])
        if not 1 <= size <= MAX_SIZE:
            continue
        off = addr - FILE_BIAS
        blob = md[off:off + size]
        if len(blob) != size:
            continue
        ins, used = [], 0
        for i in cs.disasm(blob, addr):
            ins.append(i)
            used += i.size
        if used != size or not ins or ins[-1].mnemonic != 'ret':
            continue
        yield addr, size, ins


def main():
    md = open(ELF, 'rb').read()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = False
    landed = {int(r['address'], 16) for r in csv.DictReader(open(LADDER))}
    hits = collections.defaultdict(list)
    for addr, size, ins in members(md, cs):
        for name, (mnems, pats, _) in TEMPLATES.items():
            if len(ins) != len(mnems) or tuple(i.mnemonic for i in ins) != mnems:
                continue
            ok = True
            for i, pat in zip(ins, pats or (None,) * len(ins)):
                if pat and not re.match(pat, i.op_str):
                    ok = False
                    break
            if ok:
                hits[name].append((addr, size))
    print(f'{"template":20s} {"members":>7s} {"unlanded":>8s}  note')
    for name, (_, _, note) in TEMPLATES.items():
        ms = hits[name]
        un = [m for m in ms if m[0] not in landed]
        print(f'{name:20s} {len(ms):7d} {len(un):8d}  {note}')
    total = sum(len(v) for v in hits.values())
    print(f'{"total":20s} {total:7d}')


if __name__ == '__main__':
    main()


def landed_addresses():
    """Delegates to landed.landed_addresses -- one implementation, capstone-free.

    The body formerly lived here; it moved because progress.py needs the same selector and runs in a
    pre-commit hook whose interpreter has no capstone.
    """
    import landed
    return landed.landed_addresses()


def write_table(path, header, rows, key='address'):
    """THE writer of an address-keyed table: sort -> adjacent-dup count -> write -> re-read.

    The sort has now been omitted by three separate writers, each correct about everything except
    the one rule that lives nowhere: sort the object you write, print the dups before writing, and
    prove the write by re-reading it. Callers pass rows; nobody re-implements the order.
    """
    import csv
    rows = sorted(rows, key=lambda r: int(r[key], 16))
    dups = sum(1 for a, b in zip(rows, rows[1:]) if a[key] == b[key])
    print(f'{path}: {len(rows)} rows, adjacent dup {dups}')
    if dups:
        raise SystemExit(f'refused: {path}: {dups} adjacent duplicate {key}(es) -- nothing written')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    back = list(csv.DictReader(open(path)))
    if len(back) != len(rows) or [r[key] for r in back] != [r[key] for r in rows]:
        raise SystemExit(f'refused: {path}: re-read does not match what was written')
    return len(rows)
