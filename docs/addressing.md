# Addresses

A function has four addresses. They are all the same function, and every one of them has been
mistaken for another at least once, so this page states each frame, how to convert between them,
and which file uses which.

| Frame | Example (`frame_timing_static_guard_014405b0`) | Written by |
| --- | --- | --- |
| Guest (PS4) address | `0x014405b0` | `symbols/functions.csv`, case files (`guest:`), game code, docs |
| Host address | `0x8014405b0` | the assembler and debugger; `harness.describe()` output |
| Image offset | `0x010405b0` | `boot['loads'][i]['vaddr']` in `tools/harness.py` |
| File offset in `eboot.elf` | `0x010445b0` | anything that reads the file directly |

## Conversions

Constants live in `tools/harness.py`: `IMAGE = 0x800000000`, `EBOOT_BASE = 0x400000`.

```
host    = IMAGE + guest - EBOOT_BASE          IMAGE + (guest - 0x400000)
image   = guest - EBOOT_BASE                  guest - 0x400000
file    = image + 0x4000 = guest - 0x3fc000   (0x3fc000 = EBOOT_BASE - 0x4000)
```

`0x4000` is not a magic number: both `PT_LOAD` segments sit exactly `0x4000` bytes into the file,
because the ELF header, the program headers and their alignment fill the first part of it. The
`eboot.elf` in this tree has two segments, `(file 0x4000, vaddr 0x0, memsz 0x50d96dc, flags 5)` and
`(file 0x50e0000, vaddr 0x50dc000, memsz 0x5f70f4, flags 6)`, and `off - vaddr` is `0x4000` for
both, which is why one bias works for the whole file.

`memsz` above is the size in memory, and for the second segment it is much larger than what the
file holds: its `filesz` is `0x309b38`, so the file stops backing the image at image `0x53e9b38`
and guest `0x057e9b38`. Everything from there to the end of the image (`0x05ad30f4`) is zero-fill:
`0x2e95bc` bytes (3,052,988, 2.9 MiB) that exist in the guest but not in the file. Nothing is
decoded from that range -- the highest function in `symbols/functions.csv` ends at guest
`0x02f7efde`, `0x286ab5a` bytes (40.4 MiB) below it -- but data the replacements name can live
there: the static guard at `0x05ac59b8` is inside the zero-fill, while the vtable base
`0x056fe140` is below it. A preset at a zero-fill address is describing data nothing loaded, so
its value comes from the case, never from the file: the image is mapped anonymous
(`tools/harness.py:160-162` is `MAP_PRIVATE | MAP_ANONYMOUS`, at `:227` for `IMAGE`), which the
kernel zero-fills, and the loader stores only each segment's `filesz` (`runtime/loader.c:380`).
The zeros are the mapping's guarantee, not something the loader writes -- which is why a case is
the only thing that can put a nonzero value there.

The file is larger than the image, and the difference is accounted for by the program headers
rather than left as a mystery. After the two `PT_LOAD`s the file's last mapped byte is `0x53e9b38`;
beyond it sit `PT_DYNAMIC` (`0x5952c38`, `0xc80` bytes), the SCE metadata segment (`0x61000000`,
`0x53e9b40`, `0x569d78` bytes), and two `PT_LOPROC` entries (`0x70000000` at `0x59538c0`,
`0x70000001` at `0x5953910`), the last of which ends at `0x5954138` -- exactly the file size. So
`objdump` refusing this object is about `e_shoff = 0`, not about the tail. Every one of the 157,757
addresses in the function catalog and all 625 rows of `symbols/functions.csv` fall inside a
`PT_LOAD`, none in the zero-fill, which is the check worth re-running if the image ever changes.

Worked example, `frame_timing_static_guard_014405b0`:

```
guest  0x014405b0
host   0x800000000 + 0x014405b0 - 0x400000 = 0x8014405b0
image  0x014405b0 - 0x400000               = 0x010405b0
file   0x010405b0 + 0x4000                 = 0x010445b0
```

Reading the file at `0x010445b0` gives `48 8d 05 01 54 68 04` (`8d`, not `8b`: `lea`, not `mov`), `lea rax, [rip + 0x4685401]`
loading `0x05ac59b8`. Reading it at the guest address instead gives bytes from four megabytes
further on, which decode to plausible-looking garbage -- that is the failure mode this page exists
to prevent, and it is why a wrong symbol description survived several sessions before someone read
the instruction.

## Which frame a given file speaks

- **Case files** (`data/cases/...`), `symbols/*.csv`: guest addresses. A `guest:` prefix in a case
  is the marker that an address is in this frame rather than a `buf:NAME+off`.
- **`tools/harness.py`**: host addresses internally, and `describe()` converts back to guest,
  `buf:NAME+off`, or `stack` for messages. `guest()` is the one conversion into host space.
- **`boot['loads']`**: image offsets, *not* guest addresses. The first load's `vaddr` is `0`, and
  the two loads' vaddr+memsz sum to exactly `boot['size']` (`0x56d30f4`), so they are offsets into
  the image mapped at `IMAGE`. The segment check therefore uses `IMAGE + vaddr`, with no
  `EBOOT_BASE` term. That is deliberately asymmetric with `guest()` above.
- **`runtime/include/runtime/recorder.hpp`**: `guest_of()` is the inverse of `guest()`
  (`host - rt_image + RT_EBOOT_BASE`); recorded image addresses are guest addresses.
- **`runtime/loader.c`**: copies `image + loads[i].vaddr` from `file + load_offsets[i]`, i.e. it
  works in image offsets and file offsets, never guest addresses.

## Two conversions that look wrong and are not

`harness.guest()` subtracts `EBOOT_BASE`; the segment check does not. Both are correct: `guest()`
takes a PS4 address, the segment check takes an image offset. Making them "consistent" -- adding
the bias in one place or removing it in the other -- breaks every scripted access in the cases and
reports it as an address outside all segments, which points at the case file rather than at the
translation. The same warning is in `tools/harness.py` next to the constants.

## Row identities used by the accounting comments

`runtime/`, `test/` and `tools/` may not contain a tracked address, even in a comment
(`tools/check_agnostic.py`). The arithmetic in those comments therefore names only sizes; the
identities live here.

| Catalogue address | Size | Why it matters |
| --- | --- | --- |
| `0x0196f030` | 15 B | the `movsx_deref` member; its bytes are at file offset `0x1573030` (`0x0196f030 - 0x400000 + 0x4000`) and nowhere else |
| `0x004632d0` | 67 B | no emitted body; excluded from both byte totals |
| `0x024264d0` | 34 B | the retired `rip_load` row; no emitted body; excluded from both byte totals |
| `0x00414040` | 1072 B | an `original` row whose body exists; one of the three bodied originals |
| `0x0111a600` | 8 B | an `original` row whose body exists; one of the three bodied originals |

The two bodiless rows are why `bytes_transcribed` is `67 + 34 = 101` bytes below the file's size
sum; the three bodied originals are why `has_body - not_original = 3` even though all three carry
bodies. `symbols/functions.csv` remains the authority for every value above.
