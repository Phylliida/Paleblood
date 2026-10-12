#!/usr/bin/env python3
"""Shortlist low-risk replacement targets out of the function catalog export.

usage: screen_easy.py CATALOG.json [--min 14] [--max 100] [--limit 40]

Reads the JSON produced by `function_catalog.py export` and keeps functions that are cheap to
replace and cheap to verify:

  * not already registered in symbols/functions.csv
  * 14 bytes or longer, so hooks can patch them (QUIRKS.md: the 14-byte absolute jump)
  * no unresolved indirect calls -- vtable dispatch cannot be scripted with a stub
  * within a complexity budget
  * optionally self-contained: no direct calls, no static memory references, ends in RET
    and contains no relative jump, which is the shape that needs no imports and no stubs

--self-contained is the strict mode used to pick the first batches; the default mode lists
everything above the floor by size.
"""
import argparse
import csv
import json
import os
import pathlib
import sys

HOOK_FLOOR = 14


def registered(path):
    addresses = set()
    if not os.path.exists(path):
        return addresses
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            if row and row[0].startswith("0x"):
                addresses.add(int(row[0], 16))
    return addresses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog")
    parser.add_argument("--functions", default="symbols/functions.csv")
    parser.add_argument("--elf", default=os.environ.get("BB_ELF", ""))
    parser.add_argument("--min", type=int, default=HOOK_FLOOR)
    parser.add_argument("--max", type=int, default=100)
    parser.add_argument("--max-complexity", type=int, default=3)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--self-contained", action="store_true")
    args = parser.parse_args()

    taken = registered(args.functions)
    blob = pathlib.Path(args.elf).read_bytes() if (args.self_contained and args.elf) else None

    functions = json.load(open(args.catalog))["functions"]
    kept = []
    for function in functions:
        address = int(function["address"], 16)
        if address in taken:
            continue
        size = function.get("size_bytes") or 0
        if not args.min <= size <= args.max:
            continue
        calls = function.get("calls") or {}
        if not calls.get("analysis_complete") or calls.get("unresolved_indirect"):
            continue
        if function.get("complexity", {}).get("value", 99) > args.max_complexity:
            continue
        if args.self_contained:
            if calls.get("direct"):
                continue
            if (function.get("memory_dependencies") or {}).get("static_references"):
                continue
            if blob is None:
                raise SystemExit("--self-contained needs --elf or BB_ELF")
            body = blob[address - 0x3FC000:address - 0x3FC000 + size]
            if not body or body[-1] != 0xC3:
                continue
            if b"\xe9" in body or b"\xeb" in body:
                continue
        kept.append({
            "address": f"0x{address:08x}",
            "size": size,
            "instructions": function.get("instruction_count"),
            "complexity": function.get("complexity", {}).get("value"),
            "callers": len(calls.get("callers") or []),
            "body": blob[address - 0x3FC000:address - 0x3FC000 + size].hex() if blob else None,
        })

    kept.sort(key=lambda entry: (entry["instructions"] or 0, entry["size"], entry["address"]))
    print(f"{len(kept)} candidate(s)")
    for entry in kept[:args.limit]:
        tail = f"  {entry['body']}" if entry["body"] else ""
        print(f"  {entry['address']}  size={entry['size']:3d}  instr={entry['instructions']:2d}  "
              f"cx={entry['complexity']}  callers={entry['callers']}{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
