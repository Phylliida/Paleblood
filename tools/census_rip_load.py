"""
The behaviour this measures is pre-registered in docs/probe-rip-load-static.md: the 11
filesz members, which five of them a +4 mutant can see, and the board numbers a commit is
checked against. A pre-registration that lives in a chat message cannot be read by the
person it constrains.
Count static-target rip-relative loads, split by containment, with the matcher's own drops.

The gate's table has one empty cell -- ('load','static') inside filesz -- and this asks the
catalogue how many members would fill it, split filesz / bss / outside BEFORE anything is
emitted (a member in zero-fill is unemittable, not unverified).

Every filter prints the number it dropped: a count without its filters is a count of the
matcher's opinions. Two matchers are reported:
  strict  first insn is the load, exactly two insns, size <= 16
  wide    first insn is the load, no branch, size <= 64, any tail length
Neither covers a leaf whose load is not its first instruction, a load that is not `mov`
(movzx/movsxd/cmp/test/add against a global), or a body over 64 bytes. Those are the filters
this tool does NOT apply, and therefore the populations it does not price.

Displacements come from the encoding: Capstone reports mem.disp already sign-extended from the
imm8/imm32 field. Never take K from rendered text -- Capstone renders immediates below ten in
decimal and at or above ten in hex, and a mask over rendered text loses the sign.

Perf note (paid for): image[off:][:size] copies the tail of the image before truncating --
~42 MB per row. Index first: o = off; code = image[o:o + size].
"""
import csv
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from addrs import parse_address
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_REG_RIP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELF = os.environ.get('BB_ELF') or os.path.join(os.path.dirname(ROOT), 'data', 'bb', 'elf', 'eboot.elf')
BASE = 0x400000
BRANCH = {'jmp', 'call', 'loop', 'je', 'jne', 'jz', 'jnz', 'jg', 'jl', 'jge', 'jle', 'ja', 'jb',
          'js', 'jns', 'jo', 'jno', 'jp', 'jnp'}


def segments(path):
    b = open(path, 'rb').read()
    phoff, = struct.unpack_from('<Q', b, 0x20)
    phentsize, phnum = struct.unpack_from('<HH', b, 0x36)
    out = []
    for i in range(phnum):
        o = phoff + i * phentsize
        if struct.unpack_from('<I', b, o)[0] != 1:      # PT_LOAD
            continue
        p_offset, p_vaddr = struct.unpack_from('<QQ', b, o + 0x08)
        p_filesz, p_memsz = struct.unpack_from('<QQ', b, o + 0x20)
        out.append((p_offset, p_vaddr, p_filesz, p_memsz))
    return out


def classify(target, segs):
    """filesz = the loader fills it; bss = inside memsz past filesz, a constant zero; outside."""
    for _off, vaddr, filesz, memsz in segs:
        lo = vaddr + BASE
        if lo <= target < lo + filesz:
            return 'filesz'
        if lo + filesz <= target < lo + memsz:
            return 'bss'
    return 'outside'


def looks_like_rip_load(b):
    """Encoding prefilter: optional REX, 0x8B /r, ModRM mod=00 rm=101 (RIP-relative)."""
    i = 1 if b and 0x40 <= b[0] <= 0x4f else 0
    return i + 1 < len(b) and b[i] == 0x8b and (b[i + 1] & 0xc7) == 0x05


def scan(max_size, exact_two):
    """One pass over the catalogue for one size regime. THE selector -- census and emitter both call it.

    Returns (counts, contain, samples, records). `records` carries one dict per kept member with the
    facts a writer needs (address, size, target, the two dwords, the discrimination verdict); the
    printing in main() and the emission in emit_leaf_family.members() are two READERS of one scan, so
    a family cannot be selected by one matcher and priced by another.
    """
    segs = segments(ELF)
    image = open(ELF, 'rb').read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    drops = dict(no_prefilter=0, not_full_decode=0, no_ret_tail=0, branch=0, load_not_first=0,
                 second_rip_operand=0)
    counts, contain, samples, records = {}, {}, [], []
    kept = 0
    for row in csv.DictReader(open(os.path.join(ROOT, 'symbols', 'ghidra_functions.csv'))):
        addr, size = parse_address(row['address']), int(row['size'])
        if size < 3 or size > max_size or addr < BASE:
            continue
        o = addr - 0x3FC000
        code = image[o:o + size]
        if not looks_like_rip_load(code):
            drops['no_prefilter'] += 1
            continue
        insns = list(md.disasm(code, addr))
        if sum(i.size for i in insns) != size:
            drops['not_full_decode'] += 1
            continue
        if exact_two and len(insns) != 2:
            continue
        if not insns or insns[-1].mnemonic != 'ret':
            drops['no_ret_tail'] += 1
            continue
        if any(i.mnemonic in BRANCH for i in insns):
            drops['branch'] += 1
            continue
        a = insns[0]
        # load_not_first can only ever be 0 here, because looks_like_rip_load() looks at
        # byte 0: a row whose load is its SECOND instruction never reaches this branch. The
        # zero is not a finding about the catalogue, it is a property of the prefilter -- a
        # counter whose domain excludes its only false value. Read it as "the matcher is
        # structurally blind to this shape", never as "this shape does not occur".
        if a.mnemonic != 'mov' or len(a.operands) != 2:
            drops['load_not_first'] += 1
            continue
        src = a.operands[1]
        if src.type != X86_OP_MEM or src.mem.base != X86_REG_RIP or a.operands[0].type != X86_OP_REG:
            drops['load_not_first'] += 1
            continue
        if any(o2.type == X86_OP_MEM and o2.mem.base == X86_REG_RIP
               for i in insns[1:] for o2 in i.operands):
            drops['second_rip_operand'] += 1
            continue
        target = a.address + a.size + src.mem.disp
        where = classify(target, segs)
        key = (len(insns) - 1, where)
        counts[key] = counts.get(key, 0) + 1
        contain[where] = contain.get(where, 0) + 1
        kept += 1
        d0 = d1 = None
        disc = ''
        if where == 'filesz':
            # Whether a +4 mutation of this member's constant could be SEEN, computed from the
            # image rather than from a mutant run: the body reads a dword, so the mutant reads
            # the next dword. If they are equal the differential returns the same value whether
            # the constant is right or wrong by four, and the row would be evidence from a
            # comparison that cannot discriminate the number defining the family. Such a member
            # stays `original` with a recorded reason; it is the 161's defect at one member's
            # width. The mutant then checks this prediction instead of producing it.
            o2 = target - 0x3FC000
            d0, = struct.unpack_from('<I', image, o2)
            d1, = struct.unpack_from('<I', image, o2 + 4)
            disc = 'discriminating' if d0 != d1 else 'NEIGHBOUR-UNIFORM within +4'
            samples.append((hex(addr), size, hex(target), '%08x' % d0, '%08x' % d1, disc))
            if d0 == d1:
                contain['filesz_indiscriminate'] = contain.get('filesz_indiscriminate', 0) + 1
        # `size` is BODY LENGTH (instruction + ret); the width of the load is a property of the
        # DECODED DESTINATION OPERAND. Keying on len==7 vs 8 is a proxy that breaks on a 66/44 prefix.
        width = a.operands[0].size
        records.append({'address': addr, 'size': size, 'target': target, 'where': where,
                        'width': width,
                        'd0': d0, 'd1': d1, 'discriminating': (d0 is not None and d0 != d1)})
    return counts, contain, samples, records, drops, kept


def main():
    for label, max_size, exact_two in (('strict', 16, True), ('wide', 64, False)):
        counts, contain, samples, records, drops, kept = scan(max_size, exact_two)
        print('[%s] max_size=%d exactly_two=%s' % (label, max_size, exact_two))
        for k in sorted(counts):
            print('  tail_insns=%-3d %-8s %6d' % (k[0], k[1], counts[k]))
        print('  containment: %s  total %d' % ({k: contain[k] for k in sorted(contain)}, kept))
        print('  filesz sample: %s' % (samples,))
        if label == 'wide':
            print('wide matcher drops (the populations this tool does not price): %s' % (drops,))
    return 0


if __name__ == '__main__':
    sys.exit(main())
