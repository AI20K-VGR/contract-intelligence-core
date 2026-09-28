#!/usr/bin/env python3
"""verification_snapshot.py — shared per-phase snapshot + plan-lifecycle core.

A plan's canonical verification.{json,yaml} is OVERWRITTEN every phase (it is the
current-phase verdict the gate reads O(1)). That makes it useless for "are all N
phases done?" — only the last phase's verdict survives. So completion is DERIVED,
not asserted: when a verification carrying verdict PASS + a phase id is written,
copy it once to verification-<phase>.json (first-wins, never overwriting).

This module is the SINGLE home of that logic so the two write paths share it
byte-for-byte: the PostToolUse hook (phase_progress_writer.py) for verifications
written through the Write tool, and write_verification.py for verifications
written from Bash — which never trips PostToolUse and so must call this directly.
Keeping one module is why direction B beats a script-only fix: hook and script
provably cannot drift.

Telemetry-grade helpers: snapshot/lifecycle degrade to no-op on bad input, never
raise. Path resolution is off __file__ (PS discipline), never CWD.
"""

import json
import os
import re
import sys
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
import artifact_check  # noqa: E402

# A canonical verification write: plans/<slug>/artifacts/verification.{json,yaml}.
# The literal `verification.<ext>` tail (not verification-*.<ext>) is what keeps a
# direct write of a per-phase snapshot from matching — the hook never fires on its
# own output.
_VERIF_RE = re.compile(r"^plans/[^/]+/artifacts/verification\.(json|yaml)$")

# A phase id safe to embed in a filename: the plan-graph node ids ([A-Za-z0-9_-]).
# Anything else (path separators, dots) is rejected so a forged phase cannot
# escape the artifacts dir — and is simply not snapshotted (degrade, not crash).
_SAFE_PHASE_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_PASS_VERDICTS = {"PASS", "PASS_WITH_RISK"}

# HARNESS_AUTO_FINALIZE kill-switch: any of these (case-insensitive) turns the
# STATUS FLIPS off while leaving the evidence snapshot intact. Default ON.
_FALSEY = {"0", "false", "no", "off", ""}


def auto_finalize_enabled() -> bool:
    """Is the auto open/close lifecycle enabled? Default ON; falsey
    HARNESS_AUTO_FINALIZE turns only the FLIPS off (snapshot still happens).
    Shared by the ship-belt hook so the one knob gates both seams."""
    raw = os.environ.get("HARNESS_AUTO_FINALIZE")
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSEY


def verification_plan_dir(file_path, root: Path):
    """The plan dir if `file_path` is a canonical verification write under
    plans/<p>/artifacts/, else None."""
    if not file_path or not isinstance(file_path, str):
        return None
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    try:
        rel = p.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    if not _VERIF_RE.match(rel.as_posix()):
        return None
    # rel = plans/<slug>/artifacts/verification.<ext>
    return root / "plans" / rel.parts[1]


def _safe_phase(phase):
    return phase if isinstance(phase, str) and _SAFE_PHASE_RE.match(phase) else None


def _warn_missing_phase(plan_dir: Path) -> None:
    """A PASS verification with no usable `phase` id can't be snapshotted, so the
    plan silently never reaches N/N and the ship gate later blocks with no clue.
    Surface it (stderr, fail-open): name the file, the fix, and the declared post
    artifacts of the nodes still missing a snapshot — so the author knows exactly
    what to add. Any failure here degrades to a generic line, never raises."""
    try:
        vpath = (plan_dir / "artifacts" / "verification.json").as_posix()
        declared = []
        try:
            import plan_graph
            import derive_plan_completion as dpc
            graph = plan_graph.parse_phase_graph(plan_dir)
            if "error" not in graph:
                st = dpc.completion_state(plan_dir)
                missing = sorted(set(plan_graph._all_nodes(graph)) - st["passed_phases"])
                for node in missing:
                    declared.extend(plan_graph.node_artifacts(graph, node)["post"])
        except Exception:
            declared = []  # degrade to the generic hint, never raise
        hint = ", ".join(sorted(set(declared))) if declared else "verification-<phase>.json"
        sys.stderr.write(
            "[advisory] %s has verdict PASS but no `phase` id — NOT snapshotted, "
            "so the plan can't auto-close and the ship gate will block. Add "
            "`phase: <node-id>` (a plan-graph node) to the verification. Declared "
            "post still missing: %s\n" % (vpath, hint))
    except Exception:
        return


def snapshot(plan_dir: Path) -> None:
    """Copy the plan's canonical verification to verification-<phase>.json once,
    when it is a PASS carrying a safe phase id and no snapshot exists yet."""
    rec, problem = artifact_check._load_artifact(plan_dir, "verification")
    if rec is None or not isinstance(rec, dict):
        return  # unreadable / not an object -> degrade, no snapshot
    if rec.get("verdict") not in _PASS_VERDICTS:
        return
    phase = _safe_phase(rec.get("phase"))
    if phase is None:
        # PASS but no usable phase: silently dropped before (the original bug).
        # Warn so the missed snapshot is actionable, not invisible. Still no snapshot.
        _warn_missing_phase(plan_dir)
        return  # missing/unsafe phase -> degrade (under-count is safe)
    target = plan_dir / "artifacts" / ("verification-%s.json" % phase)
    if target.exists():
        return  # first-wins: keep the first evidence, never overwrite
    # Re-serialize the parsed record as JSON so a verification.yaml source still
    # lands as the .json form derive globs, with identical content. Durable write:
    # fsync'd tmp before replace so a crash never leaves empty gate evidence.
    import artifact_io
    artifact_io.atomic_write_text(target, json.dumps(rec, ensure_ascii=False, indent=2))


def drive_lifecycle(plan_dir: Path) -> None:
    """Auto-open this plan, then finalize it (close only at N/N). Scoped to the
    plan just written — no corpus sweep. Each call is idempotent."""
    from open_plan import open_plan
    from finalize_plan import finalize_plan
    # auto-open: pending|approved -> in_progress on EVERY phase write, so a plan that
    # was never hand-opened becomes visible to the gate from phase 1. A
    # completed/cancelled/in_progress status is left untouched.
    open_plan(plan_dir)
    # finalize: closes only when derive says N/N phases have a PASS snapshot.
    res = finalize_plan(plan_dir)
    if res.changed:
        sys.stderr.write("[auto-finalize] closed %s (N/N phases PASS)\n"
                         % plan_dir.name)
