#!/usr/bin/env python3
"""sweep_engine_refs.py — migrate plugin prose run-refs to the env-path form.

Plugin skill/agent prose runs harness scripts with a hardcoded relative path
(`python3 harness/scripts/foo.py`). Under the courier the engine no longer sits at
`./harness` in every repo, so those refs must resolve through the per-project
env: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/foo.py`. The fallback `.`
keeps a fresh self-host clone (env UNSET) running exactly as today from the repo
root; a courier repo's setup-written env wins the fallback.

The transform is a PURE substring replacement — deterministic + lossless + idempotent
(the new form no longer contains the old substring), so it never reflows a line or
touches structure (memory: a deterministic script beats a model free-rewrite).
Read-refs (`harness/rules/…`, `harness/data/…`) are NOT touched — they ride the
SessionStart engine-root inject, not a shell path.
"""
import argparse
import subprocess
import sys
from pathlib import Path

# The one place the tokens live. The grep-guard test rebuilds OLD from fragments
# so it never self-trips; here the literal is fine (this file is outside the
# scanned plugin tree).
#
# The prefix is the whole `python3 harness/` root, NOT just `harness/scripts/`:
# shipped plugin prose runs scripts across `harness/scripts/`, `harness/plugins/
# .../scripts/`, and `harness/hooks/` — ALL must resolve through the env under the
# courier, not only the scripts/ dir. `python3 -m pytest harness/tests/` is safe
# (the ` -m pytest ` between breaks the `python3 harness/` substring), and refs into
# courier-dropped subtrees (harness/e2e/, harness/tests/) still get the env-prefix so
# a self-host clone runs them from `.`; they simply are not shipped in a courier repo.
OLD = "python3 harness/"
NEW = 'python3 "${HARNESS_BIN_ROOT:-.}"/harness/'

# Only these subtrees carry runnable plugin prose.
_TARGET_GLOBS = ("harness/plugins/hs/skills", "harness/plugins/hs/agents")


def transform_text(text: str) -> str:
    """Replace every old run-ref with the env-path form. Idempotent."""
    return text.replace(OLD, NEW)


def _tracked_md(root: Path) -> list:
    out = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=false", "ls-files", "-z",
         "--", *_TARGET_GLOBS],
        capture_output=True, text=True, check=True)
    return [root / rel for rel in out.stdout.split("\0")
            if rel.strip() and rel.endswith(".md")]


def sweep(root: Path, *, dry_run: bool) -> dict:
    files = _tracked_md(root)
    before = after = touched = 0
    diffs = []
    for f in files:
        if not f.is_file():
            continue  # git ls-files reports tracked-but-deleted paths; skip them
        text = f.read_text(encoding="utf-8")
        n_old = text.count(OLD)
        if n_old == 0:
            continue
        new_text = transform_text(text)
        before += n_old
        after += new_text.count(NEW) - text.count(NEW)  # NEW added by this file
        touched += 1
        if dry_run:
            diffs.append("%s: %d ref(s)" % (f, n_old))
        else:
            f.write_text(new_text, encoding="utf-8")
    return {"files_touched": touched, "refs_before": before,
            "refs_added": after, "diffs": diffs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    res = sweep(Path(args.root).resolve(), dry_run=args.dry_run)
    # Mechanical invariant: every old ref became exactly one new ref.
    if res["refs_before"] != res["refs_added"]:
        sys.stderr.write(
            "sweep invariant broken: %d old refs but %d new added\n"
            % (res["refs_before"], res["refs_added"]))
        return 1
    print("%s: %d file(s), %d ref(s) %s"
          % ("dry-run" if args.dry_run else "swept", res["files_touched"],
             res["refs_before"], "would migrate" if args.dry_run else "migrated"))
    for d in res["diffs"]:
        print("  " + d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
