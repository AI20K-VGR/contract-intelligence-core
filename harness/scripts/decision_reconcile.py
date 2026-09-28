#!/usr/bin/env python3
"""decision_reconcile — drift counter for the Decision Register.

A marker snapshots (max-dec, superseded-count) at the last reconcile; status()
reports how far the register has drifted since. Two consumers: the Stop nudge
(advisory when over threshold) and the release preflight (hard-gate: refuse a cut
while drift is unreconciled).

flip-count is derived from the superseded-count DIFF and is APPROXIMATE — it
undercounts a flip+re-flip and skews while the repo dogfoods its own DECs. It is
advisory-only, NOT audit-grade (R10). That is sufficient for a fail-open nudge and
a "have you reconciled lately" preflight; it is not a forensic flip ledger.
"""
import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

import yaml_io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import decision_register  # noqa: E402 — sibling; SSOT parse + id scan (DRY)

_DEFAULTS = {
    "reconcile_threshold_new_decs": 15,
    "reconcile_threshold_flips": 8,
    "confirm_ttl_s": 1800,
}


def _state_dir(root) -> Path:
    """Runtime-state dir for the reconcile marker. Rides the shared state env
    seams (HARNESS_STATE_DIR > HARNESS_DATA_ROOT/state) so a global install
    lands the marker project-side in `.harness/state`, the same tiering
    decision_confirm._state_dir uses for its own token dir; the explicit
    `root` arg is the legacy/test fallback honored only when no state env is
    set. (A bare call to harness_paths.state_dir() would ignore `root` and
    break the root-param test seam, so the tiers are mirrored here instead.)"""
    st = os.environ.get("HARNESS_STATE_DIR")
    if st:
        return Path(st)
    data = os.environ.get("HARNESS_DATA_ROOT")
    if data:
        return Path(data) / "state"
    return Path(root) / "harness" / "state"


def _marker_path(root) -> Path:
    return _state_dir(root) / "decision-reconcile.json"


def default_root() -> str:
    """The tree to count when no `--root` is given.

    `"."` was the old default, which under a global install counts whichever register sits
    in the current directory. Measured with a bin register at DEC-500 and a project
    register at DEC-363: run from the bin directory, the counter reported cur_max 500 —
    another tree's decisions, compared against the bin's own marker, while `mark()` writes
    to the project's data home. The two never meet.

    Every other resolver here already rides the shared seams, and the shared one already
    knows the answer: `project_root()` returns the project even when the cwd is the bin.
    Fail-open to `"."` — a counter that cannot resolve a project is advisory, and crashing
    a Stop hook over it would be worse than counting the wrong tree."""
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        import harness_paths
        return str(harness_paths.project_root())
    except Exception:
        return "."


def _governance(root) -> Dict:
    """Knobs from <root>/harness/data/decision-governance.yaml, falling back to
    the shipped defaults for any missing/invalid key (a broken knob file never
    silently disables the counter — it just reads as defaults)."""
    env = os.environ.get("HARNESS_DECISION_GOVERNANCE")
    p = Path(env) if env else Path(root) / "harness" / "data" / "decision-governance.yaml"
    out = dict(_DEFAULTS)
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for k in _DEFAULTS:
                if isinstance(raw.get(k), int):
                    out[k] = raw[k]
    except (FileNotFoundError, OSError, yaml_io.YAMLError, ValueError):
        pass
    return out


def confirm_ttl_s(root) -> int:
    """Public read of the confirm-token TTL knob (P3 gate reads this)."""
    return _governance(root)["confirm_ttl_s"]


def _current(root) -> Dict[str, int]:
    """(max-dec-number, superseded-count) of the register right now. Empty/missing
    register → both 0 (decision_register.alloc_id returns DEC-1 on empty)."""
    alloc = decision_register.alloc_id(root)  # max+1 — already a raw id scan
    try:
        cur_max = int(alloc.split("-")[1]) - 1
    except (IndexError, ValueError):
        cur_max = 0
    # The superseded count used to come from a full parse_decisions(), i.e. a
    # yaml.safe_load of the whole register on EVERY Stop event: 178.61 ms at the
    # register's current 343 645 B, growing forever. scan_counts reads the same
    # answer off the lines in 3.10 ms, and returns None rather than guess when the
    # file is not the flat shape it can judge — keep that fallback, it is the only
    # reason the cheap path is allowed to be cheap.
    scanned = decision_register.scan_counts(root)
    if scanned is not None:
        return {"max": cur_max, "superseded": scanned[1]}
    superseded = sum(1 for r in decision_register.parse_decisions(root)
                     if r.get("status") == "superseded")
    return {"max": cur_max, "superseded": superseded}


def _load_marker(path: Path) -> Optional[Dict]:
    """A marker, or None — and "is a dict" is not the same question as "is a marker".

    An empty object, or one whose keys were renamed by a schema change, carries no
    baseline: `status` falls back to `cur["max"]` and reports zero drift. That silently
    undoes the legacy fallback, because a `{}` at the resolved path wins precedence over a
    good marker sitting in the legacy tree. Measured against a register at DEC-363 with a
    legacy marker at DEC-313 — the good marker answers 50, `{}` answers 0.

    The counts are coerced HERE rather than trusted downstream. `int(data["last_max_dec"])`
    on a null, a string, or a list raises out of `status`, the CLI exits with empty stdout,
    and the release gate reads `json.loads(stdout or "{}")` — an empty dict whose
    `new_decs` defaults to 0. A corrupt marker would not block a release; it would wave one
    through. Before the fallback landed this file was never read, so this is the fallback's
    own regression to close.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out = {}
    for key in ("last_max_dec", "last_superseded"):
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        out[key] = int(value)
    return out or None


def _legacy_candidates(root):
    """The legacy `harness/state` markers this project can claim, in precedence order.

    Two, not one, because the callers do not agree on `root`. The CLI resolves
    `default_root()` -> `harness_paths.project_root()`, which redirects a linked worktree to
    its HOST repo; the Stop nudge passes `hook_runtime.project_dir(cwd)`, which in a hook
    context is CLAUDE_PROJECT_DIR — the worktree itself. Looking under the argument alone
    means each caller asks about a different tree.

    The data home is the tie-breaker: HARNESS_DATA_ROOT names ONE project for both callers
    (`<project>/.harness`), so its parent is the project the state env actually means. It is
    appended, never preferred — an explicit `root` still answers first, which keeps `--root`
    honest and keeps a neighbouring project's marker from speaking for this one.

    Yields distinct existing-or-not paths; `HARNESS_STATE_DIR` (a direct state pin, no
    project implied) contributes nothing here."""
    seen = []
    roots = [Path(root)]
    data = os.environ.get("HARNESS_DATA_ROOT")
    if data:
        roots.append(Path(data).parent)
    for r in roots:
        p = r / "harness" / "state" / "decision-reconcile.json"
        if p not in seen:
            seen.append(p)
    return seen


def _read_marker(root) -> Optional[Dict]:
    """The resolved marker, falling back to the legacy `harness/state` one.

    The fallback is not redundancy, it is a migration seam. `_state_dir` gained its
    env tiers after markers were already on disk, so a repo that reconciled before
    HARNESS_DATA_ROOT was wired keeps its only marker in the legacy tree. Reading
    just the resolved path returns None there — and `status` reads None as "never
    reconciled", i.e. baseline = now. Measured on this repo: a marker at DEC-313
    against a register at DEC-363 reported new_decs=0. Fifty decisions of drift
    read as clean.

    Measured again once that fallback landed: from a linked worktree the CLI answered 50 and
    the Stop nudge answered 0 for the same register in the same second, because the fallback
    resolves under whichever `root` the caller computed and the two compute different ones.
    Hence `_legacy_candidates` rather than a single path.

    Precedence, never merger: the resolved marker wins outright when present, so a
    stale legacy file cannot drag the baseline backwards once a reconcile has run
    under the env. Only its ABSENCE lets a legacy one answer."""
    resolved = _marker_path(root)
    marker = _load_marker(resolved)
    if marker is not None:
        return marker
    for legacy in _legacy_candidates(root):
        if legacy == resolved:
            continue
        marker = _load_marker(legacy)
        if marker is not None:
            return marker
    return None


def status(root) -> Dict:
    """Drift since the last marker: {new_decs, flips, over, cur_max, cur_superseded}.
    No marker → baseline = now (new_decs=flips=0, over=False): a fresh install never
    nudges until a reconcile has actually been marked once."""
    cur = _current(root)
    marker = _read_marker(root)
    if marker is None:
        last_max, last_sup = cur["max"], cur["superseded"]
    else:
        last_max = int(marker.get("last_max_dec", cur["max"]))
        last_sup = int(marker.get("last_superseded", cur["superseded"]))
    new_decs = max(0, cur["max"] - last_max)
    flips = max(0, cur["superseded"] - last_sup)
    gov = _governance(root)
    over = (new_decs >= gov["reconcile_threshold_new_decs"]
            or flips >= gov["reconcile_threshold_flips"])
    return {"new_decs": new_decs, "flips": flips, "over": over,
            "cur_max": cur["max"], "cur_superseded": cur["superseded"]}


def mark(root) -> Dict:
    """Snapshot the current register state as the new reconcile baseline. Called by
    the reconcile agent when it finishes, or by hand."""
    cur = _current(root)
    payload = {
        "last_max_dec": cur["max"],
        "last_superseded": cur["superseded"],
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    p = _marker_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Temp file then rename, never write_text. `write_text` truncates in place, so a
    # concurrent `status` reads a half-written marker, falls through to the legacy tier,
    # and answers with a baseline nobody set. Measured with two real processes against zero
    # true drift: 1449 of 3000 reads returned a non-zero count — which BLOCKS a release
    # that was clean. `build_manifest` learned the same lesson on the same day.
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False))
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None,
                    help="tree to count (default: the resolved project, not the cwd)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--status", action="store_true", help="print drift counts JSON")
    g.add_argument("--mark", action="store_true", help="snapshot current as baseline")
    args = ap.parse_args(argv)
    root = str(Path(args.root if args.root is not None else default_root()).resolve())
    if args.status:
        print(json.dumps(status(root), ensure_ascii=False))
    else:
        print(json.dumps(mark(root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
