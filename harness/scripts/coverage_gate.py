#!/usr/bin/env python3
"""coverage_gate.py — per-group line-coverage floors over a coverage.py JSON report.

A single global percentage is the wrong instrument here, and the measurement that
proved it is worth restating: this tree reported 89% overall while the guard hooks —
the code whose entire job is to refuse something — sat at 60%, with `mutation_guard` at
16% and `protected_ref_guard` at 20%. Coverage is a line-weighted mean, so 29,277
well-covered lines elsewhere buried the 1,345 that mattered most. `fail_under = 85`
would have been green through all of it.

So floors are declared per GROUP in `harness/data/coverage-floors.yaml`, grouped by
consequence rather than by directory.

Two rules, both about refusing to guess:

  * a report that is missing, unparseable, or has no `files` key is UNMEASURABLE and
    fails. Never 0%, never a pass. Borrowed from the tier-2 gate
    (`orchestrator/phases/drive_test.py:22-25`), which learned it the same way — a
    false 0% lets a real regression through while looking like a measurement;
  * a group whose globs match nothing IN THE REPORT is also unmeasurable. A rename
    that empties a group would otherwise average an empty set and read as clean.

Usage:
    python3 harness/scripts/coverage_gate.py --report cov.json
    python3 harness/scripts/coverage_gate.py --report cov.json --floors path/to.yaml
"""

import argparse
import fnmatch
import json
import sys
from pathlib import Path, PurePosixPath

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_FLOORS = _REPO / "harness" / "data" / "coverage-floors.yaml"


def files_in_group(patterns, root: Path):
    """Repo-relative paths on DISK matching any pattern. Used to prove a group's globs
    are not a typo, independently of whatever a report happens to contain."""
    out = set()
    for pattern in patterns:
        for path in root.glob("**/*.py"):
            rel = path.relative_to(root).as_posix()
            if "__pycache__" in rel:
                continue
            if fnmatch.fnmatch(rel, pattern):
                out.add(rel)
    return sorted(out)


def _matches(rel_path, patterns):
    return any(fnmatch.fnmatch(rel_path, p) for p in patterns)


def rel_key(path, root) -> "str | None":
    """A report key as a repo-relative posix path, or None when it names no file of ours.

    The line this replaced was `path.lstrip("./")`, which strips CHARACTERS from the set
    `{'.', '/'}` rather than the prefix `./`, and it was wrong in both directions at once:

      * `/repo/harness/hooks/x.py` lost only its leading slash and matched no glob — every
        group read UNMEASURABLE on a report that had the numbers in it. coverage.py writes
        absolute keys unless `relative_files` was set at COLLECTION time, so this is the
        ordinary shape of a report, not a corrupt one;
      * `.harness/state/x.py` became `harness/state/x.py` — a file in the per-project state
        tree scored as if it were harness source, which is the direction that produces a
        wrong number instead of no number.

    Comparison is lexical on purpose: resolving would follow symlinks, and a root reached
    through a link would then disagree with a report written through the real path. When the
    two prefixes genuinely differ the answer is None — the group goes UNMEASURABLE, which is
    this gate's standing choice of a refusal over a guess.
    """
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if not (p.startswith("/") or (len(p) > 1 and p[1] == ":")):
        return p
    base = PurePosixPath(str(root).replace("\\", "/"))
    try:
        return PurePosixPath(p).relative_to(base).as_posix()
    except ValueError:
        return None


def evaluate(report, groups, root=_REPO):
    """Return a list of human-readable breach lines; empty means every group cleared."""
    files = report.get("files") or {}
    breaches = []
    for name, spec in sorted(groups.items()):
        statements = missing = 0
        matched = 0
        seen = set()
        for path, entry in files.items():
            rel = rel_key(path, root)
            if rel is None or not _matches(rel, spec["include"]):
                continue
            matched += 1
            seen.add(rel)
            summary = entry.get("summary") or {}
            statements += summary.get("num_statements", 0)
            missing += summary.get("missing_lines", 0)
        if not matched or statements == 0:
            breaches.append(
                "%s: UNMEASURABLE — %d file(s) matched %s in the report. An empty group "
                "averages to nothing, and nothing reads as clean; check the globs before "
                "trusting this." % (name, matched, spec["include"]))
            continue
        # A group covering SOME of its files is not this group's number, it is a subset's,
        # printed under this group's name — and the absentees are uncovered by definition,
        # so every one of them pushes the percentage up. Measured: `--cov=harness` names a
        # directory with no `__init__.py`, coverage's importable-file walk yields nothing
        # there, and only files a test happened to import reached the report — `scripts` at
        # 217 of 224, `plugins` at 116 of 219. `scripts` then read 81.17% against a floor of
        # 81; whole, it is 79.72%.
        #
        # An empty disk side means the report came from a tree we cannot see, which is no
        # evidence of an omission — gating there would gate on a missing checkout.
        on_disk = set(files_in_group(spec["include"], Path(root)))
        absent = sorted(on_disk - seen)
        if absent:
            breaches.append(
                "%s: UNMEASURABLE — %d of %d file(s) on disk are absent from the report "
                "(%s%s). Absent files are uncovered, so leaving them out can only raise "
                "the number." % (name, len(absent), len(on_disk), ", ".join(absent[:3]),
                                 ", …" if len(absent) > 3 else ""))
            continue
        pct = 100.0 * (statements - missing) / statements
        if pct + 1e-9 < spec["floor"]:
            breaches.append(
                "%s: %.1f%% is below the floor of %s (%d/%d statements missed). %s"
                % (name, pct, spec["floor"], missing, statements, spec.get("why", "")))
    return breaches


def _load_groups(path: Path):
    import yaml_io
    doc = yaml_io.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return doc.get("groups") or {}


def run(report_path, groups, root: Path):
    """(exit_code, message). Never raises on a bad report — that path IS the gate."""
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return 2, ("coverage UNMEASURABLE: cannot read %s (%s: %s). This is a failure, "
                   "not 0%% — a report that did not run must never look like a clean one."
                   % (report_path, type(exc).__name__, exc))
    if not isinstance(report, dict) or "files" not in report:
        return 2, ("coverage UNMEASURABLE: %s carries no `files` key, so nothing was "
                   "measured." % report_path)
    breaches = evaluate(report, groups, root)
    if breaches:
        return 1, "coverage floor breached:\n  " + "\n  ".join(breaches)
    return 0, "coverage floors OK (%d group(s))" % len(groups)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", required=True, help="coverage.py JSON report")
    ap.add_argument("--floors", default=str(_DEFAULT_FLOORS))
    # The tree the report describes. It is a separate question from where this script
    # lives: a report collected in a checkout elsewhere is compared against ITS files, and
    # the disk-vs-report check needs to look at the right ones.
    ap.add_argument("--root", default=str(_REPO),
                    help="tree the report was collected from (default: this checkout)")
    args = ap.parse_args(argv)

    groups = _load_groups(args.floors)
    if not groups:
        sys.stderr.write("no groups declared in %s — nothing to gate\n" % args.floors)
        return 2
    rc, msg = run(args.report, groups, Path(args.root))
    (sys.stdout if rc == 0 else sys.stderr).write(msg + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
