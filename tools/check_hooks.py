#!/usr/bin/env python3
"""Check that the gate which enforces every other gate is installed by script and sourced from the repo.

`git ls-files` cannot see .git/hooks, so a hand-edited hook is unreviewable -- but this repo does not
hand-edit them: tools/install_hooks.sh (tracked) writes a 17-line dispatcher into every hook name, and the
dispatcher execs a TRACKED source under tools/hooks/, mapping commit-msg and post-commit onto
pre-commit and post-commit-backup.sh. The property worth checking is therefore:

  * every installed hook is the dispatcher (marker line), not a hand edit;
  * every source it can exec is tracked by git -- an untracked gate is a gate with no reviewer;
  * and, the failure this check was written for: a `core.hooksPath` pointing at a directory that lacks
    `commit-msg` or `post-commit` SILENTLY DELETES those gates. Git looks for those names directly in
    the configured directory and there is no dispatch layer there. `--hooks-path DIR` answers that
    question before anyone runs `git config`.
"""
import argparse
import pathlib
import subprocess
import sys

MARKER = "# bb-worktree-hook-v1"
NAMES = ("pre-commit", "commit-msg", "pre-push", "post-commit")
SOURCES = {"pre-commit": "tools/hooks/pre-commit", "commit-msg": "tools/hooks/pre-commit",
           "pre-push": "tools/hooks/pre-push", "post-commit": "tools/hooks/post-commit-backup.sh"}


def tracked(root):
    out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True)
    return set(out.stdout.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hooks-path", help="check a candidate core.hooksPath directory instead of .git/hooks")
    a = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    if a.hooks_path:
        d = pathlib.Path(a.hooks_path)
        if not d.is_absolute():
            d = root / d
        missing = [n for n in NAMES if not (d / n).exists()]
        for n in missing:
            print(f"REFUSED: core.hooksPath={a.hooks_path} has no `{n}` -- git would run nothing for it, "
                  f"silently deleting that gate (there is no dispatcher to map it onto "
                  f"{SOURCES[n]})")
        if missing:
            print(f"hooks: {len(missing)} of {len(NAMES)} gate(s) would be silently deleted -- refusing")
            return 1
        print(f"hooks: all {len(NAMES)} names present under {a.hooks_path}")
        return 0
    d = pathlib.Path(subprocess.run(["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
                                    capture_output=True, text=True, check=True).stdout.strip())
    if not d.is_absolute():
        d = root / d
    # The REQUIRED set is the repo's policy, not my expectation: tools/install_hooks.sh installs
    # pre-commit and commit-msg always, and pre-push / post-commit only under --maintainer (backup only
    # when bb.backupDir is set). A check that demands all four refuses the repo's own documented state --
    # which is exactly what this one did on its first run.
    def cfg(key):
        r = subprocess.run(["git", "-C", str(root), "config", "--get", key],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""

    required = {"pre-commit", "commit-msg"}
    if cfg("bb.maintainerIdent"):
        required.add("pre-push")
    if cfg("bb.backup") == "true":
        required.add("post-commit")
    problems, notes = [], []
    for name in NAMES:
        p = d / name
        if not p.exists():
            if name in required:
                problems.append(f"installed hook `{name}` is missing but ENABLED by config -- run "
                                f"tools/install_hooks.sh")
            else:
                notes.append(f"`{name}` not installed (not enabled: --maintainer / BB_BACKUP_DIR)")
            continue
        if MARKER not in p.read_text(errors="replace"):
            problems.append(f"installed hook `{name}` is not the dispatcher (no `{MARKER}`) -- a hand "
                            f"edit git does not track")
    have = tracked(root)
    for src in sorted(set(SOURCES.values())):
        if src not in have:
            problems.append(f"hook source `{src}` is not tracked -- a gate with no reviewer")
    for p in problems:
        print("REFUSED:", p)
    for n in notes:
        print(f"hooks: {n}")
    if problems:
        print(f"hooks: {len(problems)} problem(s) -- refusing")
        return 1
    print(f"hooks: ok ({len(required)} required dispatcher(s) installed, "
          f"{len(set(SOURCES.values()))} sources tracked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
