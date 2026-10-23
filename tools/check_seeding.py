"""The seeding gate: three links, and `guest` is the only admissible value kind for this family.

WHY THIS EXISTS. The chain family's body loads a qword from an image slot and stores through the value
it loaded. In the shipped bytes the slot sits in the zero-fill tail, so the loaded value is zero and
the store degenerates to address K2 -- the member is not testable from the image at all, and its case
must supply both the slot and the destination's contents. A case is therefore part of the evidence, and
evidence that is half-supplied makes a body look measured when it was only run:

  LINK 1  the slot at `load_target` holds 8 bytes the case wrote;
  LINK 2  that value is a GUEST address inside the writable segment's memsz, and
          value + store_k2 + store_width is inside it too;
  LINK 3  the destination at value + store_k2 is pre-set to a sentinel the immediate cannot equal,
          so the store changes a byte the differential can see.

**LINK 2 IS A SPACE RULE, NOT A BOUNDS CHECK, AND `guest` IS THE ONLY KIND THIS FAMILY ACCEPTS.** The
store goes through the loaded pointer into guest memory, so in-game the pointer is a guest address. The
schema can also say `pointer`, which resolves to a SANDBOX buffer address -- and `harness.snapshot()`
includes `self.buffers`, so a store into the sandbox **is observed** and the case would pass while
writing into a space the game does not have. Observability cannot catch a space error; only the kind
can. Same for `bytes`: a literal pointer is an address the case could only obtain by knowing IMAGE.

**LINK 3 exists because 31 of the 78 rows store `0x0`** into a destination that is zero-fill: with the
slot seeded, those still produce no byte diff and the differential compares zero to zero and passes.
The sentinel is DERIVED from the family's own immediate set (`derive_sentinel`), not fixed in this
tool, so a family whose member stores `0xa5` gets a different sentinel instead of a failure somebody
resolves at 2 a.m. by picking `0xB6`.

**EXPECTED BYTES ARE MEASURED, NEVER DERIVED.** The differential runs the original under the identical
seeded state, so what the destination must contain afterwards is whatever the original's run shows.
This gate never computes `imm & (2^(8*width)-1)`; it compares the immediate to the sentinel only to
prove the write is visible. Arithmetic on immediates belongs where a mutant's expected value is written
down in advance, and there it is printed beside the artifact.

THE READER IS SHARED. `harness.fixture_seeds` is imported, never re-implemented: a gate that re-reads
the case JSON is certifying a run the runner does not perform.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import catalogue
import harness
import leaf_shape_census as S

TABLE = os.path.join(S.ROOT, 'symbols', 'chain_family.csv')


def derive_sentinel(rows):
    """The smallest non-zero byte b whose repetition collides with no immediate at its width."""
    used = set()
    for r in rows:
        mask = (1 << (8 * r['store_width'])) - 1
        used.add(r['imm'] & mask)
    for b in range(1, 256):
        s = int(f'{b:02x}' * 8, 16)
        if all((s & ((1 << (8 * r['store_width'])) - 1)) not in used for r in rows):
            return b, used
    raise SystemExit('seeding: no sentinel byte collides with nothing -- refusing')


def _guest_int(text):
    """A guest address as the runner reads one: a hex string, never a buf: name."""
    if not isinstance(text, str) or not text.startswith('0x'):
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def _seed_len(m):
    if 'guest' in m or 'pointer' in m:
        return 8
    return len(bytes.fromhex(m['bytes'])) if 'bytes' in m else 0


def check(row, case, rw, sentinel_byte):
    """Three links for one row and its case. Returns refusal strings; empty means the case is evidence."""
    base, memsz = rw
    width, imm = row['store_width'], row['imm']
    mask = (1 << (8 * width)) - 1
    sentinel = int(f'{sentinel_byte:02x}' * 8, 16) & mask
    bad = []
    seeds = harness.fixture_seeds(case)

    def at(addr):
        return [m for m in seeds if _guest_int(m.get('addr')) == addr]

    # link 1 -- the slot
    slot = [m for m in at(row['load_target']) if _seed_len(m) >= 8]
    if not slot:
        bad.append(f"link 1: no 8-byte seed at load_target {row['load_target']:#x}; the slot reads zero")
        return bad
    m = slot[0]
    if 'guest' not in m:
        kind = 'pointer' if 'pointer' in m else 'bytes' if 'bytes' in m else 'neither'
        bad.append(f"link 2: slot value kind is {kind}, not guest -- a sandbox address is observed by "
                   f"snapshot() and would pass while writing into a space the game does not have")
        return bad
    v = _guest_int(m['guest'])
    if v is None:
        bad.append(f"link 2: slot value {m['guest']!r} is not a hex guest address")
        return bad

    # link 2 -- the destination is inside the writable segment, both ends
    lo, hi = v + row['store_k2'], v + row['store_k2'] + width
    if not (base <= lo and hi <= base + memsz):
        bad.append(f"link 2: destination {lo:#x}..{hi:#x} is outside the writable segment "
                   f"{base:#x}..{base + memsz:#x}")

    # link 3 -- the destination is pre-set to a sentinel the immediate cannot equal
    dst = [m for m in at(lo) if _seed_len(m) >= width]
    if not dst:
        bad.append(f"link 3: no seed at destination {lo:#x}; a store of {imm:#x} into zero-fill "
                   f"produces no byte diff and the differential compares zero to zero")
    else:
        d = dst[0]
        if 'bytes' not in d:
            bad.append(f"link 3: destination seed at {lo:#x} is a {'guest' if 'guest' in d else 'pointer'} "
                       f"value, not bytes -- the sentinel must be literal")
        else:
            raw = bytes.fromhex(d['bytes'])[:width]
            if any(b != sentinel_byte for b in raw):
                bad.append(f"link 3: destination at {lo:#x} holds {raw.hex()}, not the sentinel "
                           f"{sentinel_byte:#04x} x width")
            if (imm & mask) == sentinel:
                bad.append(f"link 3: immediate {imm:#x} equals the sentinel at width {width} -- "
                           f"the store would change nothing")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--table', default=TABLE)
    ap.add_argument('--cases', default=os.path.join(S.ROOT, '..', 'data', 'cases', 'chain'))
    ap.add_argument('--elf', default=S.ELF)
    a = ap.parse_args(argv)
    if not os.path.isfile(a.table):
        print(f'seeding: refusing -- cannot read {a.table}; unread is not zero', file=sys.stderr)
        return 3
    rows = []
    for r in catalogue.read_rows(a.table):        # the typed reader, never a second DictReader
        rows.append({'address': r['address'], 'load_target': int(r['load_target'], 16),
                     'store_k2': int(r['store_k2'], 16), 'store_width': int(r['store_width']),
                     'imm': int(r['imm'], 16)})
    segs = S.load_segments(open(a.elf, 'rb').read(), flags=True)
    writable = [s for s in segs if s[3] & 2]
    if not writable:
        print('seeding: refusing -- no writable PT_LOAD; unread is not zero', file=sys.stderr)
        return 3
    base, memsz = writable[-1][0], writable[-1][2]
    sentinel, used = derive_sentinel(rows)
    print(f"seeding: {len(rows)} rows | writable segment {base:#x}..{base + memsz:#x} | "
          f"sentinel {sentinel:#04x} derived from {len(used)} masked immediate(s)")
    if not os.path.isdir(a.cases):
        print(f'seeding: refusing -- no case directory {a.cases}; 0 cases is not 0 refusals',
              file=sys.stderr)
        return 3
    bad = 0
    for r in rows:
        p = os.path.join(a.cases, f"{r['address']:08x}", 'case.json')
        if not os.path.isfile(p):
            print(f"REFUSED {r['address']:#x}: no case file at {p}", file=sys.stderr)
            bad += 1
            continue
        with open(p) as f:
            case = json.load(f)
        out = check(r, case, (base, memsz), sentinel)
        if out:
            bad += 1
            for line in out:
                print(f"REFUSED {r['address']:#x}: {line}", file=sys.stderr)
    print(f"seeding: {len(rows) - bad}/{len(rows)} cases satisfy all three links")
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
