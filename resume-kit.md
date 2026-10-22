
## `BB_PBBOOT` — a default path that silently resolves to a stale build

`tools/boot.py:261` resolves the harness from `$BB_PBBOOT` or **`build/runtime/pbboot`**. The tree
this campaign builds is **`build-release`**, so an unset `BB_PBBOOT` runs a binary that predates
every recent runtime change -- and does so silently, producing stops that look like findings.

```
export BB_PBBOOT=$PWD/build-release/runtime/pbboot
```

The `eboot+0xb9` / `+0xc1` progression was produced without this line and is therefore **void**:
the same two stops that "validated" PLT ordinals 0 and 1 came through a stale binary, so
per-library ordinals stay alive rather than refuted. Also export `BB_BIND_DUMP=1` to see the
loader's bind order (`runtime/boot.c`, `resolve()`).
