#!/usr/bin/env python3
"""Branch census: which catalogue rows contain a branch or call, and what the two denominators are.

    python3 -P tools/branch_census.py --out symbols/branch_band.csv

Two numbers have been doing one job. 38,018/157,757 = 24.10% is SCOPE -- a fraction of Ghidra's
reach, the rows a leaf/byte selector could ever touch. 38,018/41,282 = 87.4% is PROGRESS -- a
fraction of the branch-free population, which is what the leaf toolchain can address at all. A
branch-containing row is not blocked by capability: it belongs to the function campaign, whose
generated-C path carries no single-block constraint. Widening jump_free would let leaf machinery
accept bodies whose control flow it cannot express, so this tool counts the boundary, it does not
move it.

The branch predicate is family_scan's own --any-control-flow negation (mnemonic starts with 'j' or
'call'), so the census and the selector cannot disagree about what a branch is.
"""
import argparse
import csv
import gzip
import io
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # -P strips the script dir; no PYTHONPATH help

import capstone

import join_import_pc as J
import leaf_family_census as C


def compute(out=None):
    """The two branch figures. ONE implementation: derive.py calls this, it does not recount."""
    md = open(C.ELF, 'rb').read()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    landed = C.landed_addresses()
    # Read through the typed reader: a fresh csv.DictReader over a catalogue is what check_catalogue refuses.
    import catalogue as _CAT
    bodies = {r['address'] for r in _CAT.read_rows('symbols/functions.csv')}
    extents = J.load_extents('symbols/ghidra_functions.csv')
    cat = [(int(r['address'], 16), int(r['size'])) for r in
           csv.DictReader(open('symbols/ghidra_functions.csv'))]
    rows = []
    undecoded = 0
    for a, s in cat:
        off = a - C.FILE_BIAS
        ins = list(cs.disasm(md[off:off + s], a)) if 0 <= off and off + s <= len(md) else []
        if not ins:
            undecoded += 1
            rows.append((a, s, '?', a in landed))
            continue
        rows.append((a, s, '1' if any(i.mnemonic.startswith(('j', 'call')) for i in ins) else '0',
                     a in landed))
    if out:
        buf = io.StringIO()
        w = csv.writer(buf)
        # TWO COLUMNS, TWO MEANINGS, each named for what it is. `landed` means "status is not original" --
        # what an emitter can move. `has_body` means present in symbols/functions.csv at ANY status, which
        # is what a candidate test needs. The pair exists because a reader given only `landed` read it as
        # `has_body` and re-offered a landed body as work already done.
        w.writerow(['address', 'size', 'branch', 'landed', 'has_body'])
        w.writerows([(f'{a:#010x}', s, b, l, a in bodies) for a, s, b, l in rows])
        # 3.6 MB of repetitive rows is over the repo's 2 MB artifact limit, and it is regenerable from
        # the committed tool, so it ships gzipped with mtime=0: byte-reproducible, not merely small.
        if out.endswith('.gz'):
            pathlib.Path(out).write_bytes(gzip.compress(buf.getvalue().encode(), mtime=0))
        else:
            pathlib.Path(out).write_text(buf.getvalue())
    branch = [r for r in rows if r[2] == '1']
    free = [r for r in rows if r[2] == '0']
    free_landed = [r for r in free if r[3]]
    land = [(a, s) for a, s, b, l in rows if l]
    unlanded_free = [a for a, s, b, l in free if not l]
    indep = [a for a in unlanded_free if len(J.owners(extents, a)) == 1]
    return {'total': len(rows), 'undecoded': undecoded, 'branch': len(branch),
            'branch_landed': sum(1 for r in branch if r[3]), 'free': len(free),
            'free_landed': len(free_landed), 'land': len(land),
            'unlanded_free': len(unlanded_free), 'independent': len(indep)}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='symbols/branch_band.csv.gz')
    o = ap.parse_args(argv)
    if not o.out.endswith('.gz'):
        # The READERS open gzip -- reach_line reads gzip.open(path, 'rt') and the committed file is `.gz`.
        # This writer honours the suffix (text to .csv, gzip to .gz), so a `.csv` name produced a textbook
        # census that nothing in the tree opens: the tool's stdout right and the artifact old, fifth time.
        # A writer that knows which encoding its readers need can check its own output NAME in one line, and
        # then the default no longer has to be memorised -- it can be wrong safely, because it refuses.
        print(f'branch_census: REFUSED --out {o.out}: every reader opens gzip (gzip.open), so this name '
              f'would produce an artifact nothing reads. Use {o.out.rsplit(".", 1)[0]}.gz', file=sys.stderr)
        return 2
    f = compute(out=o.out)
    print(f'branch census over {f["total"]} catalogue rows (undecoded {f["undecoded"]}):')
    print(f'  branch or call      {f["branch"]:6d}  ({f["branch"]/f["total"]:.1%})  landed {f["branch_landed"]}')
    print(f'  branch-FREE         {f["free"]:6d}  landed {f["free_landed"]}')
    print(f'  PROGRESS   {f["land"]} landed / {f["free"]} branch-free = {f["free_landed"]/f["free"]:.2%}'
          f'  (landed branch-free {f["free_landed"]})')
    print(f'  SCOPE      {f["land"]} landed / {f["total"]} catalogued = {f["land"]/f["total"]:.2%}')
    print(f'  unlanded branch-free {f["unlanded_free"]}: independent (owners==1) {f["independent"]}, '
          f'nested {f["unlanded_free"]-f["independent"]}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
