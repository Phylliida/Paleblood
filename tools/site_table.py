"""`symbols/site_ok.csv`: the 14 bytes at every hook site, taken from the image, for the installer to compare.

The guard's width is the patch's width. `install_hook` writes a 14-byte absolute jump, so a guard that compared
fewer bytes would leave the rest of the first instruction unverified -- exactly the bytes a 16 KiB-shifted patch
still passes. One constant, three places: guard, write, readback.

The join to `symbols/install_mode.csv` is asserted with **both totals printed** and a failure on surplus in either
direction. Two tables keyed on address is how `surplus 101` happened; a join asserted is not the same as two tables
that merely look consistent.
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import install_mode  # noqa: E402  -- the one reader of symbols/install_mode.csv

try:
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
except ImportError:  # the population check is the point; a missing decoder must not read as a pass
    Cs = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "symbols" / "site_ok.csv"
ELF = ROOT.parent / "data" / "bb" / "elf" / "eboot.elf"
FILE_BIAS = 0x3FC000
GUARD_BYTES = 14          # ABSOLUTE_JUMP_SIZE


def rows():
    mode = [r for r in install_mode.rows(ROOT) if r["mode"] == "hook"]
    image = ELF.read_bytes()
    out = []
    for r in mode:
        address = r["address"]
        size = int(r.get("size") or 0)
        if size and size < GUARD_BYTES:
            raise SystemExit(f"0x{address:08x}: site is {size} bytes, shorter than the {GUARD_BYTES}-byte patch")
        code = image[address - FILE_BIAS: address - FILE_BIAS + GUARD_BYTES]
        if len(code) != GUARD_BYTES:
            raise SystemExit(f"0x{address:08x}: only {len(code)} bytes available at the file bias")
        out.append((f"0x{address:08x}", code.hex()))
    return mode, out


def population_check(table):
    """A check no single site can make: over every prologue, at once.

    A 16 KiB bias error fails this loudly -- 16 KiB away sit thunks and padding, whose first bytes are `e9`/`ff`
    or which decode to nothing -- and it costs one pass over eboot with no build. Duplicates are printed and not
    refused: `xor eax,eax; ret` bodies recur, so a refusal there fires on the first real run.
    """
    md = Cs(CS_ARCH_X86, CS_MODE_64) if Cs else None
    if md is None:
        return ["capstone is not importable: the decode half of this check did not run"]
    problems, seen = [], {}
    for address, hexs in table:
        code = bytes.fromhex(hexs)
        seen[hexs] = seen.get(hexs, 0) + 1
        if code[0] in (0xE9, 0xCC, 0xFF):
            problems.append(f"{address}: begins 0x{code[0]:02x} -- a prior patch, or the wrong bias reading into a "
                            f"thunk; bytes {hexs}")
        if not any(True for _ in md.disasm(code, int(address, 16))):
            problems.append(f"{address}: the {GUARD_BYTES} bytes decode to no instruction; bytes {hexs}")
    dupes = {h: n for h, n in seen.items() if n > 1}
    print(f"prologues shared with another site: {len(dupes)} distinct ({sum(dupes.values())} rows); not refused")
    for h, n in list(dupes.items())[:3]:
        print(f"  {n} sites share {h}")
    return problems


def main() -> int:
    mode, table = rows()
    OUT.write_text("address,prologue\n" + "".join(f"{a},{p}\n" for a, p in table))
    hooks, sites = len(mode), len(table)
    if hooks == 0:
        print("install_mode.csv names no hook rows: the join cannot be checked and this table proves nothing")
        return 2
    print(f"install_mode hook rows: {hooks}")
    print(f"site_ok rows: {sites}")
    if hooks != sites:
        print(f"surplus {abs(hooks - sites)} in {'install_mode' if hooks > sites else 'site_ok'}: refusing")
        return 1
    problems = population_check(table)
    if problems:
        print(f"{len(problems)} site(s) failed the population check; first one verbatim:")
        print(f"  {problems[0]}")
        return 1
    print(f"{sites} prologues: none begins e9/cc/ff, every one decodes, no bias shift")
    return 0


if __name__ == "__main__":
    sys.exit(main())
