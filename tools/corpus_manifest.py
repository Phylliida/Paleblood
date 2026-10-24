"""The membership behind a recorded corpus figure, committed.

A count about an untracked subject is unverifiable the moment the file changes: `git` preserves the count and
not the membership. So the population a document quotes is written down as one row per member --
`sha256<TAB>bytes<TAB>predicates<TAB>relpath`, sorted by path, gzipped with `mtime=0` -- which is
byte-reproducible, so a diff of two manifests IS a set difference and the next `+1` is a name rather than a
timestamp hunt.

A hash alone would not be enough: it tells you the population moved, and not what entered or left.

    python3 tools/corpus_manifest.py --out symbols/corpus_manifest.csv.gz
    python3 tools/corpus_manifest.py --check        # rc=1, naming every added / removed / changed member
    python3 tools/corpus_manifest.py --count memory  # from the COMMITTED manifest; no corpus access

`--root` and `--manifest` exist so the refusals can be proved on a fixture instead of asserted on the corpus.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CORPUS = ROOT.parent / "data" / "cases"
MANIFEST = ROOT / "symbols" / "corpus_manifest.csv.gz"

# The predicates a document quotes, as (token, needle). The needle is the same literal `test_doc_numbers`
# scans for: the corpus is JSON text, and the figures in `docs/capture-protocol.md` were produced this way.
PREDICATES = (("memory", '"memory"'), ("pointer", '"pointer"'))


def live_rows(root=None):
    """One row per file matching any recorded predicate: (sha256, bytes, predicates, relpath). Sorted by path."""
    root = pathlib.Path(root or CORPUS)
    rows = []
    for p in sorted(root.rglob("*.json")):
        text = p.read_text(errors="replace")
        hit = "+".join(tok for tok, needle in PREDICATES if needle in text)
        if not hit:
            continue
        rows.append((hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size,
                     hit, p.relative_to(root).as_posix()))
    return rows


def format_rows(rows):
    return b"".join(
        ("%s\t%d\t%s\t%s\n" % (sha, size, preds, rel)).encode() for sha, size, preds, rel in rows
    )


def parse_rows(blob):
    rows = []
    for line in blob.decode().splitlines():
        if not line.strip():
            continue
        sha, size, preds, rel = line.split("\t")
        rows.append((sha, int(size), preds, rel))
    return rows


def write_manifest(rows, path=None):
    """Byte-reproducible: sorted input, no timestamp in the gzip header, no trailing dependence on names."""
    path = pathlib.Path(path or MANIFEST)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as fh:
        fh.write(format_rows(rows))
    blob = buf.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def read_manifest(path=None):
    path = pathlib.Path(path or MANIFEST)
    return parse_rows(gzip.open(path, "rb").read())


def diff(committed, live):
    """The set difference, both directions, plus members whose content or predicate changed."""
    old = {rel: (sha, size, preds) for sha, size, preds, rel in committed}
    new = {rel: (sha, size, preds) for sha, size, preds, rel in live}
    out = []
    for rel in sorted(set(new) - set(old)):
        out.append(("+", rel, "added"))
    for rel in sorted(set(old) - set(new)):
        out.append(("-", rel, "removed"))
    for rel in sorted(set(old) & set(new)):
        if old[rel][0] != new[rel][0]:
            out.append(("~", rel, "content changed"))
        elif old[rel][1:] != new[rel][1:]:
            out.append(("~", rel, "size or predicate changed"))
    return out


def counts(rows):
    """Per-predicate counts, derived from the manifest alone -- no corpus access, no re-scan."""
    n = {tok: 0 for tok, _ in PREDICATES}
    for _sha, _size, preds, _rel in rows:
        for tok in preds.split("+"):
            n[tok] = n.get(tok, 0) + 1
    return n


def check(root=None, manifest=None):
    """Return (rc, lines). rc=1 when anything differs, and every differing member is named."""
    manifest = pathlib.Path(manifest or MANIFEST)
    if not manifest.exists():
        return 3, ["corpus manifest: unread (no %s) -- and unread is not zero" % manifest]
    committed = read_manifest(manifest)
    live = live_rows(root)
    d = diff(committed, live)
    n = counts(committed)
    head = ("corpus manifest: %d member(s) · %s · sha256 %s" % (
        len(committed), " · ".join("%s %d" % (k, v) for k, v in sorted(n.items())),
        hashlib.sha256(manifest.read_bytes()).hexdigest()))
    if not d:
        return 0, [head, "corpus manifest: identical to the corpus (0 added, 0 removed, 0 changed)"]
    return 1, [head] + ["%s %s (%s)" % (op, rel, why) for op, rel, why in d]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None, help="corpus root (default ../data/cases)")
    ap.add_argument("--manifest", default=None, help="manifest path (default symbols/corpus_manifest.csv.gz)")
    ap.add_argument("--out", action="store_true", help="write the manifest from the corpus")
    ap.add_argument("--check", action="store_true", help="recompute and refuse on any difference")
    ap.add_argument("--count", metavar="PREDICATE", default=None, help="count from the committed manifest")
    a = ap.parse_args(argv)
    if a.out:
        sha = write_manifest(live_rows(a.root), a.manifest)
        print("corpus manifest: wrote %s (sha256 %s)" % (a.manifest or MANIFEST, sha))
        return 0
    if a.check:
        rc, lines = check(a.root, a.manifest)
        for line in lines:
            print(line, file=sys.stderr if rc else sys.stdout)
        return rc
    if a.count:
        rows = read_manifest(a.manifest)
        n = counts(rows)
        if a.count not in n:
            print("corpus manifest: %r is not a recorded predicate (have %s)" % (a.count, sorted(n)),
                  file=sys.stderr)
            return 2
        print(n[a.count])
        return 0
    ap.error("one of --out, --check or --count is required: a tool that does nothing by default is a "
             "permissive zero in the place that decides what runs")


if __name__ == "__main__":
    sys.exit(main())
