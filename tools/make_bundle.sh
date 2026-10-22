#!/bin/sh
# Decision 10: the human pushes; the agent's job is to make that one command, never a decision.
# Usage: tools/make_bundle.sh [outdir]   -> writes <outdir>/paleblood-<short sha>.bundle
set -eu
out=${1:-../bundles}
mkdir -p "$out"
sha=$(git rev-parse --short HEAD)
ref=$(git rev-parse --abbrev-ref HEAD)
git bundle create "$out/paleblood-$sha.bundle" --all >/dev/null
printf 'wrote %s/paleblood-%s.bundle (%s, %s commits ahead of origin/%s)\n' \
  "$out" "$sha" "$ref" "$(git rev-list --count "origin/$ref..HEAD" 2>/dev/null || echo '?')" "$ref"
printf 'human step: git -C <clone> fetch %s/paleblood-%s.bundle %s:%s\n' "$out" "$sha" "$ref" "$ref"
