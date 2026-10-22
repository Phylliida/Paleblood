#!/bin/sh
# Build, then run -- joined by && so a failed build can never be followed by a run of the previous binary.
# Three incidents (stale link, stale default path, failed compile) were each caught by a human noticing;
# this retires the fourth. The binary is kept under its own sha256 so a fault can be re-read later.
set -e
cd "$(dirname "$0")/.."
cmake --build build-release -j 8 >&2
mkdir -p build-release/kept
sha=$(sha256sum build-release/runtime/pbboot | cut -c1-12)
cp build-release/runtime/pbboot "build-release/kept/$sha"
exec build-release/runtime/pbboot "$@"
