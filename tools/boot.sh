#!/bin/sh
# The build rides on running, not on remembering: this wrapper builds BOTH artifacts that can change what a
# boot line means, prints each one's sha256 before the guest runs, then execs pbboot and prints its rc.
#
# WHY: on 2026-xx-xx pbboot had failed to compile since before d18786a and several boots ran the stale binary
# while libbbgame.so supplied the new text. The hash convention existed and the run did not invoke it; the
# only visible sign was a -Wunused-result error triggered by a comment-only header edit. Attribution is the
# point: a line is evidence about the build named above it. Never merge the streams -- build log and hashes
# go to stderr, the guest's own output stays on stdout.
#
# usage: tools/boot.sh [pbboot args...]        env: BB_PLUGIN (defaults to build-release/game/libbbgame.so)
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/build-release"
elf=${1:-}
[ -n "$elf" ] || { echo "boot.sh: usage: tools/boot.sh <guest elf> [args...]" >&2; exit 3; }
[ -f "$elf" ] || { echo "boot.sh: no such guest elf: $elf" >&2; exit 3; }

build_log=$(mktemp) || exit 1
trap 'rm -f "$build_log"' EXIT INT TERM
if ! cmake --build "$build" --target pbboot libbbgame.so >"$build_log" 2>&1; then
    echo "boot.sh: BUILD FAILED -- refusing to run a stale binary (this is how a stale boot looks)" >&2
    cat "$build_log" >&2
    exit 78   # EX_CONFIG: not the guest's rc, and never mistakable for one
fi

pp="$build/runtime/pbboot"
plugin=${BB_PLUGIN:-$build/game/libbbgame.so}
[ -x "$pp" ]      || { echo "boot.sh: pbboot missing at $pp" >&2; exit 3; }
[ -f "$plugin" ]  || { echo "boot.sh: plugin missing at $plugin" >&2; exit 3; }
export BB_PLUGIN="$plugin"

echo "pbboot sha256 $(sha256sum "$pp" | cut -c1-12)  ($pp)" >&2
echo "plugin sha256 $(sha256sum "$plugin" | cut -c1-12)  ($plugin)" >&2
# The subject, not just the runtime: the guest ELF is untracked and 93 MB, so a hash-valid run from before it
# changed would silently describe a different file. A run without the identity of what it ran is a number
# without a subject; this is the largest part of the subject.
echo "eboot sha256 $(sha256sum "$elf" | cut -c1-12)  ($elf)" >&2

rc=0
"$pp" "$@" || rc=$?
echo "pbboot rc=$rc" >&2
exit "$rc"
