#!/bin/sh
# Same shape as tools/boot.sh, one layer over a test binary: build it, print its sha256, run it, print its rc.
# A manual rc is not attributable to a named build; this closes the named gap for test_syslib and friends.
# usage: tools/test.sh <target> [args...]        e.g. tools/test.sh test_syslib
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/build-release"
[ "$#" -gt 0 ] || { echo "test.sh: usage: tools/test.sh <target> [args...]" >&2; exit 3; }
target=$1; shift
build_log=$(mktemp) || exit 1
trap 'rm -f "$build_log"' EXIT INT TERM
if ! cmake --build "$build" --target "$target" >"$build_log" 2>&1; then
    echo "test.sh: BUILD FAILED -- nothing ran (this is not a failing test)" >&2
    cat "$build_log" >&2
    exit 78
fi
bin="$build/$target"
[ -x "$bin" ] || { echo "test.sh: no executable at $bin (rc=127 is a path fact, not a verdict)" >&2; exit 78; }
echo "$target sha256 $(sha256sum "$bin" | cut -c1-12)  ($bin)" >&2
rc=0
"$bin" "$@" || rc=$?
echo "$target rc=$rc" >&2
exit "$rc"
