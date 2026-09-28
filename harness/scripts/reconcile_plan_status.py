"""reconcile_plan_status.py — surface (and conservatively repair) the drift
between each plan's declared `status:` and the evidence of what really happened.

Why this exists: a plan's status only moves when cook explicitly calls
open_plan/close_plan. The cook body (which writes artifacts/verification.json)
and those flips are decoupled, so a plan can be cooked to a PASS verdict and
still read `pending`. Separately, the field has no schema, so off-vocabulary
spellings (`done`, `approved`, `awaiting-human-approval`) accrete and the board
mis-buckets them. This tool reads the whole corpus and classifies each plan:

  ok            — canonical status, consistent with evidence
  spelling      — same state, lossless dash/quote variant (safe to auto-fix)
  retired       — a dropped label (draft/awaiting_human_approval); migrated by
                  evidence: an APPROVED plan-approval artifact lifts it to
                  `approved`, otherwise it folds to `pending` (safe to auto-fix)
  under_reported— pending/approved but carries a PASS verification artifact
  vocab         — off-vocabulary value; intent not guessable from spelling
  missing       — no status field at all

Repair tiers mirror the repo's discipline: `apply_fixes` auto-applies the
lossless spelling fixes AND the retired-label migration (both are evidence- or
spelling-derived, never a guess). An evidenced completion is reported with the
exact close_plan command but never auto-flipped — marking work done is a call the
harness does not make silently.
"""
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import harness_paths  # noqa: E402
import plan_status as ps  # noqa: E402

# statuses that mean "not yet finished" — a PASS artifact under one of these is
# the smoking-gun drift (cook ran, status never moved).
_UNFINISHED = {"pending", "approved"}


@dataclass
class PlanState:
    name: str
    status_raw: str | None      # exactly as written, or None if no field
    status_norm: str | None     # canonical form, or None if off-vocabulary
    has_pass: bool              # artifacts/verification.json verdict == PASS
    drift: str                  # ok|spelling|retired|under_reported|vocab|missing
    suggestion: str | None      # canonical value to set, when safe to name


def root_dir(root=None) -> Path:
    """The corpus root to scan. An explicit `root` (tests, a caller that already
    resolved one) wins; otherwise resolve project-aware via harness_paths — never
    a bare CWD fallback, which silently scans the wrong (or an empty) corpus and
    reports a false all-clear whenever this is invoked from a directory other
    than the project root."""
    if root is not None:
        return Path(root)
    return harness_paths.project_root()


def _read_status_raw(plan_md: Path):
    """Return the frontmatter status value verbatim, or None if absent. Reuses
    plan_status's frontmatter discipline so prose `status:` lines are ignored."""
    try:
        text = plan_md.read_text(encoding="utf-8")
    except OSError:
        return None
    fm = ps._FRONTMATTER_RE.match(text)
    if not fm:
        return None
    m = ps._STATUS_RE.search(fm.group(1))
    return m.group(1) if m else None


def _has_pass(plan_dir: Path) -> bool:
    vf = plan_dir / "artifacts" / "verification.json"
    try:
        data = json.loads(vf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    # tolerate the few shapes seen in the corpus: verdict / status / result
    for key in ("verdict", "status", "result"):
        val = data.get(key)
        if isinstance(val, str) and val.strip().upper() == "PASS":
            return True
    return False


def _has_approval(plan_dir: Path) -> bool:
    """True iff artifacts/plan-approval.yaml records verdict APPROVED. Tolerant,
    fail-closed: any read/parse problem reads as 'not approved' (so a retired
    label folds to pending, never spuriously to approved). The file is a tiny
    flat YAML, so a line-level `verdict:` scan is enough and needs no yaml dep."""
    af = plan_dir / "artifacts" / "plan-approval.yaml"
    try:
        text = af.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("verdict:"):
            val = stripped.split(":", 1)[1].strip().strip("'\"").upper()
            return val == "APPROVED"
    return False


def classify(plan_dir: Path) -> PlanState:
    name = plan_dir.name
    raw = _read_status_raw(plan_dir / "plan.md")
    norm = ps.normalize_status(raw)
    has_pass = _has_pass(plan_dir)

    if raw is None:
        return PlanState(name, None, None, has_pass, "missing", None)
    # retired label (draft / awaiting_human_approval, incl. dash spelling): fold
    # to pending for consumers, but migrate by EVIDENCE — an APPROVED artifact
    # means the plan really reached `approved`, and a blind fold to pending would
    # erase that (the bug this cleanup fixes, applied upstream).
    folded = ps._norm(str(raw).strip())
    if folded in ps._LEGACY_FOLD:
        suggestion = "approved" if _has_approval(plan_dir) else "pending"
        return PlanState(name, raw, norm, has_pass, "retired", suggestion)
    if norm is None:
        # off-vocabulary (done/implemented): real intent, but the harness will
        # not infer it from spelling — a human/evidence decides.
        return PlanState(name, raw, None, has_pass, "vocab", None)
    if not ps.is_canonical(raw):
        # canonical state, lossless spelling variant (dash / quotes) — safe fix.
        return PlanState(name, raw, norm, has_pass, "spelling", norm)
    if norm in _UNFINISHED and has_pass:
        # cooked to PASS but status never advanced past pending/approved.
        return PlanState(name, raw, norm, has_pass, "under_reported", None)
    return PlanState(name, raw, norm, has_pass, "ok", None)


def scan(root=None):
    plans = root_dir(root) / "plans"
    states = []
    for plan_md in sorted(plans.glob("*/plan.md")):
        d = plan_md.parent
        if d.name in ("reports", "templates"):
            continue
        states.append(classify(d))
    return states


# drift classes safe to auto-apply: a lossless spelling repair and a retired-label
# migration whose target is evidence-derived (APPROVED -> approved, else pending).
_AUTO_FIXABLE = {"spelling", "retired"}


def apply_fixes(states, root=None) -> int:
    """Auto-apply the lossless spelling fixes and the retired-label migrations.
    Returns the count applied. Evidenced completions (under_reported) are
    intentionally left untouched — marking work done is not auto-applied."""
    fixed = 0
    plans = root_dir(root) / "plans"
    for s in states:
        if s.drift not in _AUTO_FIXABLE or not s.suggestion:
            continue
        res = ps.set_status_value(plans / s.name, s.suggestion, root=root_dir(root))
        if res.changed:
            fixed += 1
    return fixed


_GLYPH = {"ok": "✓", "spelling": "~", "retired": "↻", "under_reported": "!",
          "vocab": "?", "missing": "∅"}


def _report(states) -> str:
    drifted = [s for s in states if s.drift != "ok"]
    lines = ["plan status reconcile — %d plans, %d drifted"
             % (len(states), len(drifted)), ""]
    for s in sorted(drifted, key=lambda x: (x.drift, x.name)):
        tail = ""
        if s.drift == "spelling":
            tail = " -> %s (lossless, auto-fixable)" % s.suggestion
        elif s.drift == "retired":
            tail = " -> %s (retired label, evidence-migrated, auto-fixable)" % s.suggestion
        elif s.drift == "under_reported":
            tail = " (PASS artifact present; run close_plan if truly done)"
        elif s.drift == "vocab":
            tail = " (off-vocabulary; pick a canonical value)"
        elif s.drift == "missing":
            tail = " (no status field)"
        lines.append("  %s %-14s %-26s %s%s"
                     % (_GLYPH[s.drift], s.drift,
                        s.status_raw if s.status_raw is not None else "—",
                        s.name, tail))
    if not drifted:
        lines.append("  all canonical and consistent.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reconcile plan status vs evidence.")
    ap.add_argument("--fix", action="store_true",
                    help="auto-apply lossless spelling fixes + retired-label "
                         "migrations (evidence-derived)")
    args = ap.parse_args(argv)
    states = scan()
    print(_report(states))
    if args.fix:
        n = apply_fixes(states)
        print("\napplied %d status fix(es) (lossless spelling + retired-label "
              "migration)." % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
