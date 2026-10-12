# Replacement target selection

The function catalog ranks censused functions, but its ranking is only as good as the evidence
imported into it. As of the export below, every one of the 157,757 functions carries
`memory_dependencies.complete: false`, so `eligible` returns **0** candidates at every stage and
`rank` collapses to a constant score (54.3 for the whole top 250). Target selection therefore runs
on `tools/screen_easy.py`, which reads the same export and filters on properties that are actually
known.

## Building the catalog

Two things are easy to get wrong:

* `XDG_CACHE_HOME` must point inside the workspace. The default is `~/.cache/paleblood`, which is on
  a read-only filesystem here.
* `--analysis-version` is required whenever analysis artifacts are imported, even though it
  defaults to `"unknown"` in `--help`.

```sh
export XDG_CACHE_HOME=/home/bepis/modding/decomp/.cache
python3 tools/function_catalog.py build \
  --executable /home/bepis/modding/decomp/data/bb/elf/eboot.elf \
  --edges      /home/bepis/modding/decomp/data/exports/edges.csv \
  --metrics    /home/bepis/modding/decomp/data/exports/metrics.csv \
  --analysis-version "ExportFunctionAnalysis/1 ghidra-11.4.2"
python3 tools/function_catalog.py export /tmp/cat.json   # 559 MB, 157,757 functions
```

The export is what `screen_easy.py` consumes; it is not checked in.

## Screening

```sh
export BB_ELF=/home/bepis/modding/decomp/data/bb/elf/eboot.elf
python3 tools/screen_easy.py /tmp/cat.json --self-contained --limit 40
```

`--self-contained` keeps only functions that need no imports, no stubs and no case presets of image
globals: no resolved or unresolved calls, no static memory references, no relative jump anywhere in
the body, and a `RET` as the last byte. It is the shape that verifies cheapest, because the case is
nothing but register arguments and a buffer.

Measured against the 64 registered functions at the time of writing:

| class | count |
| --- | --- |
| above the 14-byte hook floor, not registered, at most 120 bytes, no unresolved indirect call, complexity <= 3 | 35,986 |
| of those, complexity 1 | 19,076 |
| `--self-contained` (strict) | 10,046 |

The strict shortlist is dominated by repeated shapes that can share one templated implementation,
the same way the three static guards share `game/frame_timing/static_guard.cpp`:

| shape | example | count in shortlist |
| --- | --- | --- |
| XMM 16-byte copy: load or store two `vmovaps`/`vmovups` pairs | `0x005e9360` `c5fb114f78c5fb118780000000c3` | 447 |
| constant stores into the argument object | `0x009e5520` `c74704ffffffff66c74708ffffc3` | 453 |
| register stores into the argument object | `0x0070e130` `4889b7e00000008997c4000000c3` | 515 |
| 64-bit immediate through `rax` to `[rdx]` | `0x009e1a60` `48b81c00000003000000488902c3` | 9 |
| predicate returning a byte | `0x004dc070` `81bf80000000000000800f95c0c3` | remainder |

## Hook floor

`QUIRKS.md:98`: the hook is a 14-byte absolute jump written over the start of the original, so a
function shorter than 14 bytes cannot be hooked and can never reach `edge-verified`, however good
its cases are. `tools/screen_easy.py` enforces the floor; the catalog does not. Known examples below
it: `0x0111a600` (8), `0x0111a5f0` (8), `0x0111a6d0` (3), `0x0111ade0` and `0x0111adf0` (6), and the
`0x02e613x0` group (5-7). Tail-call thunks hovering at 15-16 bytes are above the floor but their
bytes are a store plus a `JMP`; prefer bodies that end in `RET`.
