#!/usr/bin/env python3
"""plan_layout_check.py — soft advisory that a plan dir matches the scaffold layout.

A model that hand-authors a plan dir (instead of running scaffold.py) can place
phase files where the gates do not hash them — the approval hash then silently
omits phase content, so a phase edit slips past drift detection. This checker
surfaces that class of drift WITHOUT blocking (always exit 0): it is a nudge, not
a gate. The blocking guarantee still lives in plan_approval's hash; this only
tells a human/agent to re-run scaffold or re-approve.

Three signals, each derived from the filesystem (+ the approval record if present):
  - misplaced: a phase-*.md outside the hashed locations (root / phases/).
  - mixed:     phase files split across BOTH the flat and phases/ layouts.
  - stale approval: an APPROVED record whose file_hashes miss a phase now on disk.

Read-only. Never edits the plan, the approval record, or any gate config.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _root_phases(plan_dir: Path):
    return sorted(plan_dir.glob("phase-*.md"))


def _nested_phases(plan_dir: Path):
    return sorted(plan_dir.glob("phases/phase-*.md"))


def _misplaced_phases(plan_dir: Path):
    """phase-*.md anywhere under the plan dir that is NEITHER at root NOR in
    phases/ — exactly the files plan_approval's two globs do not hash."""
    hashed = {p.resolve() for p in _root_phases(plan_dir) + _nested_phases(plan_dir)}
    out = []
    for p in sorted(plan_dir.rglob("phase-*.md")):
        if p.resolve() not in hashed:
            out.append(p)
    return out


def _approval_record(plan_dir: Path):
    """The parsed plan-approval record (yaml preferred, json legacy) or None.
    Fail-soft: a malformed record yields None — this is advisory, never a crash."""
    art = plan_dir / "artifacts"
    for name in ("plan-approval.yaml", "plan-approval.json"):
        cand = art / name
        if not cand.is_file():
            continue
        try:
            text = cand.read_text(encoding="utf-8")
            if cand.suffix == ".yaml":
                import yaml_io
                rec = yaml_io.safe_load(text)
            else:
                rec = json.loads(text)
            return rec if isinstance(rec, dict) else None
        except Exception:  # noqa: BLE001 — advisory read must not raise
            return None
    return None


def layout_warnings(plan_dir) -> list:
    """Advisory messages for a plan dir. Empty list == clean. Never raises on a
    readable dir; a missing dir yields a single 'not found' note."""
    plan_dir = Path(plan_dir)
    if not plan_dir.is_dir():
        return ["plan dir not found: %s" % plan_dir]

    warnings = []
    root_p = _root_phases(plan_dir)
    nested_p = _nested_phases(plan_dir)

    for p in _misplaced_phases(plan_dir):
        rel = p.relative_to(plan_dir)
        warnings.append(
            "phase file %s is outside the hashed locations (root / phases/) — move "
            "it under phases/; it is currently OUT of the approval hash." % rel)

    if root_p and nested_p:
        warnings.append(
            "plan uses BOTH the flat (phase-*.md at root) and phases/ layouts "
            "(mixed) — consolidate phase files under phases/ so the layout is "
            "unambiguous.")

    rec = _approval_record(plan_dir)
    if rec and str(rec.get("verdict", "")).upper() == "APPROVED":
        # file_hashes keys are plan-dir-relative POSIX paths. Legacy records
        # (stamped before the key changed) carry bare basenames, so accept
        # either — a basename-only match is back-compat, not a widened pass:
        # both forms still name exactly one file on disk.
        covered = set((rec.get("file_hashes") or {}).keys())
        for p in root_p + nested_p:
            rel = p.relative_to(plan_dir).as_posix()
            if rel not in covered and p.name not in covered:
                warnings.append(
                    "approved plan's hash does not cover phase file %s — the "
                    "approval predates this file; re-approve via plan_approval.py."
                    % p.name)
    return warnings


def _resolve_plan(root: str, explicit: str):
    if explicit:
        return Path(explicit)
    try:
        import artifact_check
        d = artifact_check.resolve_active_plan(root)
        return Path(d) if d else None
    except Exception:  # noqa: BLE001
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Advisory check that a plan dir matches the scaffold layout "
                    "(never blocks; exit 0).")
    ap.add_argument("--plan", default=None, help="plan dir (default: active plan)")
    ap.add_argument("--root", default=".", help="repo root for active-plan resolve")
    args = ap.parse_args(argv)

    plan_dir = _resolve_plan(args.root, args.plan)
    if not plan_dir:
        sys.stderr.write("plan-layout: no active plan to check\n")
        return 0

    warnings = layout_warnings(plan_dir)
    if not warnings:
        sys.stderr.write("plan-layout: %s — layout OK\n" % plan_dir)
        return 0
    sys.stderr.write("plan-layout: %d advisory warning(s) for %s\n"
                     % (len(warnings), plan_dir))
    for w in warnings:
        sys.stderr.write("  - %s\n" % w)
    sys.stderr.write("  fix: rerun `scaffold.py plan` for the layout, or re-approve "
                     "via `plan_approval.py`. (advisory — nothing blocked)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
