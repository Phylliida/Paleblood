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
import argparse, ctypes, sys

FILE_BIAS = 0x3FC000

def original_bytes(elf, address, size):
    with open(elf, 'rb') as f:
        f.seek(address - FILE_BIAS)
        return f.read(size)

def executed_bytes(lib, symbol, size):
    addr = ctypes.cast(getattr(ctypes.CDLL(lib), symbol), ctypes.c_void_p).value
    return ctypes.string_at(addr, size)

def compare(lib, elf, symbol, address, size):
    want, got = original_bytes(elf, address, size), executed_bytes(lib, symbol, size)
    if want == got:
        return None
    first = next(i for i, (a, b) in enumerate(zip(want, got)) if a != b)
    return f'{symbol} 0x{address:08x}: differ at offset {first} original {want.hex()} executed {got.hex()}'

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--lib', required=True)
    p.add_argument('--elf', required=True)
    p.add_argument('--symbol', required=True)
    p.add_argument('--address', required=True, type=lambda s: int(s, 0))
    p.add_argument('--size', required=True, type=int)
    p.add_argument('--expect', choices=('match', 'mismatch'), required=True,
                   help='match = asm body equals the original; mismatch = a C body that must differ')
    a = p.parse_args(argv)
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
