"""`symbols/site_ok.csv`: the 14 bytes at every hook site, taken from the image, for the installer to compare.

The guard's width is the patch's width. `install_hook` writes a 14-byte absolute jump, so a guard that compared
fewer bytes would leave the rest of the first instruction unverified -- exactly the bytes a 16 KiB-shifted patch
still passes. One constant, three places: guard, write, readback.

The join to `symbols/install_mode.csv` is asserted with **both totals printed** and a failure on surplus in either
direction. Two tables keyed on address is how `surplus 101` happened; a join asserted is not the same as two tables
that merely look consistent.
"""
import csv, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODE = ROOT / "symbols" / "install_mode.csv"
OUT = ROOT / "symbols" / "site_ok.csv"
ELF = ROOT.parent / "data" / "bb" / "elf" / "eboot.elf"
FILE_BIAS = 0x3FC000
GUARD_BYTES = 14          # ABSOLUTE_JUMP_SIZE


def rows():
    mode = [r for r in csv.DictReader(MODE.open()) if r["mode"] == "hook"]
    image = ELF.read_bytes()
    out = []
    for r in mode:
        address = int(r["address"], 16)
        size = int(r.get("size") or 0)
        if size and size < GUARD_BYTES:
            raise SystemExit(f"0x{address:08x}: site is {size} bytes, shorter than the {GUARD_BYTES}-byte patch")
        code = image[address - FILE_BIAS: address - FILE_BIAS + GUARD_BYTES]
        if len(code) != GUARD_BYTES:
            raise SystemExit(f"0x{address:08x}: only {len(code)} bytes available at the file bias")
        out.append((f"0x{address:08x}", code.hex()))
    return mode, out


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
