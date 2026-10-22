"""Decision 1/2: every asm body carries a byte assertion.

Reads the bytes the CPU will execute (ctypes, at the function pointer) and compares them to the
original extent in eboot.elf. In-process because the image has no section table and because a
file's bytes are a claim while the executed bytes are the fact.

SCOPE, stated because a control that passes on the shape it exists to catch proves nothing:
for a multi-byte shape, a C body differs at some offset and the mismatch is a real control.
for the 1-byte `ret` family, BYTE EQUALITY IS NECESSARY AND NOT SUFFICIENT -- an empty C body at
-O2 emits exactly one `c3`, byte-identical to naked `asm("ret")`. That family's asm form is
carried by the stability argument (decision 1), never by this check.
"""
import argparse, ctypes, hashlib, sys

FILE_BIAS = 0x3FC000

def original_bytes(elf, address, size):
    with open(elf, 'rb') as f:
        f.seek(address - FILE_BIAS)
        return f.read(size)

def executed_bytes_from(lib_handle, symbol, size):
    addr = ctypes.cast(getattr(lib_handle, symbol), ctypes.c_void_p).value
    return ctypes.string_at(addr, size)


def executed_bytes(lib, symbol, size):
    return executed_bytes_from(ctypes.CDLL(lib), symbol, size)

def compare(lib, elf, symbol, address, size):
    want, got = original_bytes(elf, address, size), executed_bytes(lib, symbol, size)
    if want == got:
        return None
    first = next(i for i, (a, b) in enumerate(zip(want, got)) if a != b)
    return f'{symbol} 0x{address:08x}: differ at offset {first} original {want.hex()} executed {got.hex()}'

def corpus_digest(lib, elf, members):
    """The `cases_sha256` for a byte-evidence row, over BOTH byte strings and the library.

    A byte-equality claim has two sides, so a digest over the executed bytes alone would still
    verify after the reference changed. It covers, per member, the original extent's bytes and the
    executed bytes, plus `so_sha256` -- a digest that survives a rebuild certifies bytes that no
    longer exist, which is the lesson capture_ok.csv has paid for three times.
    """
    so = hashlib.sha256(open(lib, 'rb').read()).hexdigest()
    h = hashlib.sha256()
    matched = 0
    lib_handle = ctypes.CDLL(lib)
    for symbol, address, size in members:
        want = original_bytes(elf, address, size)
        got = executed_bytes_from(lib_handle, symbol, size)
        matched += want == got
        h.update(f'{address:08x}|{want.hex()}|{got.hex()}|{so}\n'.encode())
    return h.hexdigest()[:16], so, len(members), matched


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--lib', required=True)
    p.add_argument('--elf', required=True)
    p.add_argument('--symbol')
    p.add_argument('--address', type=lambda s: int(s, 0))
    p.add_argument('--size', type=int)
    p.add_argument('--digest-members', metavar='FILE',
                   help='lines of "symbol address size"; prints the corpus digest and refuses on '
                        'any mismatch, so a row can never cite a digest over non-equal bytes')
    p.add_argument('--expect', choices=('match', 'mismatch'),
                   help='match = asm body equals the original; mismatch = a C body that must differ')
    a = p.parse_args(argv)
    if a.digest_members:
        members = []
        for line in open(a.digest_members):
            if line.strip():
                sym, addr, size = line.split()
                members.append((sym, int(addr, 0), int(size)))
        digest, so, n, matched = corpus_digest(a.lib, a.elf, members)
        if matched != n:
            print(f'BYTE DIGEST REFUSED: only {matched} of {n} members are byte-identical; a row '
                  'citing this digest would claim equality it does not have')
            return 1
        print(f'digest={digest} so_sha256={so[:16]} members={n} matched={matched}')
        return 0
    if not a.expect:
        print('need --expect or --digest-members'); return 2
    diff = compare(a.lib, a.elf, a.symbol, a.address, a.size)
    if a.expect == 'match':
        if diff:
            print('BYTE ASSERTION FAILED ' + diff); return 1
        print(f'{a.symbol}: {a.size} byte(s) identical to the original extent'); return 0
    if diff is None:
        print(f'CONTROL DID NOT FIRE {a.symbol}: byte-identical, so this shape cannot distinguish '
              'a C body from an asm body -- say so, do not claim the green as evidence')
        return 1
    print('control fired: ' + diff); return 0

if __name__ == '__main__':
    sys.exit(main())
