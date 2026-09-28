#!/usr/bin/env python3
"""self_check_confidence.py — deterministic pre-handoff confidence score for a
tầng-1 plan directory (``plan.md`` + ``phases/*.md`` + ``plan-graph.yaml``).

Port of FrankCode's ``selfCheck.ts`` (docs/product/_refs/frankcode-src/planner-executor/
engines/utils/planner/selfCheck.ts) — same 3-gate/weighted architecture
(WEIGHTS :93-97, CONFIDENCE_THRESHOLD :99, per-gate score :295-305, composite :307-311,
top-uncertainties :316-322) — but adapted to a different plan format. FrankCode validates
a plan JSON against ``plan.schema.json`` via AJV; this repo's plan is markdown
(YAML frontmatter + prose), so every item here reads the markdown directly instead of a
schema. The source's 3rd gate is named ``grid`` and reads a grid/coverage-grid
attestation (:57-63, :238-259); this port's 3rd gate is named ``structure`` and reads
``plan-graph.yaml`` instead — deliberately independent of the coverage-grid engine (no
edge from the grid-port phases), never confuse the two.

Advisory-first: exit 0 always by default. ``--strict`` (opt-in, e.g. CI) exits 1 when
confidence < CONFIDENCE_THRESHOLD; local runs never hard-block on this score alone.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import frontmatter_parser  # noqa: E402

# ─── weights + threshold (module-local; NOT the grid coverage-floor SSOT) ──────────
# Values (0.45/0.35/0.20/0.7) are disjoint from both grid-floor sets — the FrankCode
# 3-tier density {0.60,0.85,0.95} and tầng-2 4-tier risk {0.6,0.75,0.9,1.0} — so this module
# never trips the coverage-floor guard, and lives outside harness/scripts/grid/.
WEIGHTS = {"requirements": 0.45, "design": 0.35, "structure": 0.20}
CONFIDENCE_THRESHOLD = 0.7

_GATE_PRIORITY = {"requirements": 0, "design": 1, "structure": 2}

_SINGLE_ACTIVATION_RE = re.compile(
    r"\b(either|or|option A|option B|option 1|option 2)\b", re.IGNORECASE
)
_SPECULATIVE_RE = re.compile(
    r"\b(might|may be|could be|possibly|perhaps)\b.*\.(ts|js|tsx|jsx|py|go|rs|md|yaml|yml|json)",
    re.IGNORECASE,
)
_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


# ------------------------------------------------------------------- markdown helpers ---

def _find_section(sections: dict, heading_prefix: str):
    prefix = heading_prefix.lower()
    for heading, content in (sections or {}).items():
        if heading.strip().lower().startswith(prefix):
            return content
    return None


# A pipe inside a cell is written `\|`. Splitting on every pipe cuts the row at
# the escape, so the row gains a column and every cell after it shifts left —
# silently, since a longer row is not an error to anyone downstream.
_CELL_SEP_RE = re.compile(r"(?<!\\)\|")


def _split_row(line: str):
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [c.strip().replace("\\|", "|") for c in _CELL_SEP_RE.split(inner)]


def _parse_tables(text: str):
    """Every ``| ... |`` block in ``text`` that has a separator row, as
    ``(header_cells, [data_row_cells, ...])``. Generic pipe-table reader — no
    markdown library needed for this shape."""
    tables = []
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        if not _ROW_RE.match(lines[i]):
            i += 1
            continue
        start = i
        while i < len(lines) and _ROW_RE.match(lines[i]):
            i += 1
        block = lines[start:i]
        if len(block) >= 2 and _SEP_RE.match(block[1]):
            tables.append((_split_row(block[0]), [_split_row(r) for r in block[2:]]))
    return tables


def _mitigation_col(header):
    for idx, name in enumerate(header):
        if "mitigation" in name.lower():
            return idx
    return None


# --------------------------------------------------------------------------- context ---

def _load_context(plan_dir: Path) -> dict:
    plan_dir = Path(plan_dir)
    plan_doc = frontmatter_parser.parse_file(plan_dir / "plan.md")
    frontmatter = plan_doc.get("frontmatter") or {}

    phase_entries = []
    # `phases:` is a list of phase-file paths, but an older/hand-authored plan
    # may carry `phases: 5` (a count). Guard the type before iterating — a bare
    # `or []` leaves a truthy int in place and `for rel in 5` raises TypeError,
    # crashing this advisory tool on real archived plans.
    raw_phases = frontmatter.get("phases")
    for rel in (raw_phases if isinstance(raw_phases, list) else []):
        if not isinstance(rel, str):
            continue
        path = plan_dir / rel
        phase_entries.append({"rel": rel, "path": path, "exists": path.is_file()})

    docs = [("plan.md", plan_doc)]
    for entry in phase_entries:
        if entry["exists"]:
            docs.append((entry["rel"], frontmatter_parser.parse_file(entry["path"])))

    return {
        "plan_dir": plan_dir,
        "plan_doc": plan_doc,
        "phase_entries": phase_entries,
        "docs": docs,
    }


# --------------------------------------------------------------------- item checks ---
# Each check receives the context dict and returns bool. An exception during a check
# counts as a failure (never crashes the run) — mirrors selfCheck.ts :279-288.

def _check_frontmatter_valid(ctx):
    plan_doc = ctx["plan_doc"]
    fm = plan_doc.get("frontmatter")
    if not plan_doc.get("ok") or not isinstance(fm, dict):
        return False
    return all(k in fm for k in ("id", "title", "status", "phases"))


def _check_phases_exist(ctx):
    entries = ctx["phase_entries"]
    return all(e["exists"] for e in entries)  # vacuously true when nothing declared


def _check_single_activation_path(ctx):
    body = ctx["plan_doc"].get("body") or ""
    return not _SINGLE_ACTIVATION_RE.search(body)


def _check_no_speculative_paths(ctx):
    body = ctx["plan_doc"].get("body") or ""
    return not _SPECULATIVE_RE.search(body)


def _check_acceptance_measurable(ctx):
    content = _find_section(ctx["plan_doc"].get("sections"), "acceptance")
    if content is None:
        return False
    return re.search(r"-\s*\[[ xX]\]", content) is not None


def _check_risks_have_mitigation(ctx):
    for _label, doc in ctx["docs"]:
        for heading, content in (doc.get("sections") or {}).items():
            if "risk" not in heading.lower():
                continue
            for header, rows in _parse_tables(content):
                idx = _mitigation_col(header)
                if idx is None:
                    continue
                for row in rows:
                    if idx >= len(row) or not row[idx].strip():
                        return False
    return True  # vacuous pass — no risk table with a Mitigation column found


def _check_premortem_or_redteam_ran(ctx):
    plan_doc = ctx["plan_doc"]
    if "risks" in (plan_doc.get("frontmatter") or {}):
        return True
    return _find_section(plan_doc.get("sections"), "validation log") is not None


def _check_rollback_present(ctx):
    content = _find_section(ctx["plan_doc"].get("sections"), "rollback")
    return bool(content and content.strip())


def _check_plan_graph_present(ctx):
    return (ctx["plan_dir"] / "plan-graph.yaml").is_file()


def _check_plan_graph_clean(ctx):
    script = _HERE / "plan_graph.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(ctx["plan_dir"])],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    lines = proc.stdout.splitlines()
    # A missing/malformed sidecar prints "error: ..." and no cycle/conflict lines —
    # fail closed here too (PLAN_GRAPH_PRESENT already reports the absence itself;
    # this item cannot attest "clean" for a sidecar it could not read).
    if any(line.startswith("error:") for line in lines):
        return False
    return not any(line.startswith("cycle:") or line.startswith("parallel-conflict:") for line in lines)


SELF_CHECK_ITEMS = (
    {"code": "FRONTMATTER_VALID", "gate": "requirements", "check": _check_frontmatter_valid,
     "cited_field": "plan.md#frontmatter",
     "message": "plan.md frontmatter is missing or lacks id/title/status/phases."},
    {"code": "PHASES_EXIST", "gate": "requirements", "check": _check_phases_exist,
     "cited_field": "plan.md#frontmatter.phases",
     "message": "One or more frontmatter phases: entries point to a file missing on disk."},
    {"code": "SINGLE_ACTIVATION_PATH", "gate": "requirements", "check": _check_single_activation_path,
     "cited_field": "plan.md#body",
     "message": "plan.md contains an undecided either/or activation path."},
    {"code": "NO_SPECULATIVE_PATHS", "gate": "requirements", "check": _check_no_speculative_paths,
     "cited_field": "plan.md#body",
     "message": "plan.md cites a speculative file path (might/may be/could be ...)."},
    {"code": "ACCEPTANCE_MEASURABLE", "gate": "requirements", "check": _check_acceptance_measurable,
     "cited_field": "plan.md#Acceptance",
     "message": "plan.md has no ## Acceptance section with a binary checklist item."},
    {"code": "RISKS_HAVE_MITIGATION", "gate": "design", "check": _check_risks_have_mitigation,
     "cited_field": "Risk table Mitigation column",
     "message": "A risk-table row has an empty Mitigation cell."},
    {"code": "PREMORTEM_OR_REDTEAM_RAN", "gate": "design", "check": _check_premortem_or_redteam_ran,
     "cited_field": "plan.md#Validation Log / frontmatter.risks",
     "message": "No Validation Log section and no frontmatter risks: — pre-mortem/red-team evidence missing."},
    {"code": "ROLLBACK_PRESENT", "gate": "design", "check": _check_rollback_present,
     "cited_field": "plan.md#Rollback",
     "message": "plan.md has no non-empty ## Rollback section."},
    {"code": "PLAN_GRAPH_PRESENT", "gate": "structure", "check": _check_plan_graph_present,
     "cited_field": "plan-graph.yaml",
     "message": "plan-graph.yaml sidecar is missing from the plan directory."},
    {"code": "PLAN_GRAPH_CLEAN", "gate": "structure", "check": _check_plan_graph_clean,
     "cited_field": "plan-graph.yaml#cycles/conflicts",
     "message": "plan_graph.py reports a cycle or parallel-conflict (or the sidecar is unreadable)."},
)


# ------------------------------------------------------------------------ core scoring ---

def compute_confidence(requirements: float, design: float, structure: float) -> float:
    return (
        WEIGHTS["requirements"] * requirements
        + WEIGHTS["design"] * design
        + WEIGHTS["structure"] * structure
    )


def run_self_check(plan_dir) -> dict:
    ctx = _load_context(Path(plan_dir))

    failures = []
    fail_count = {"requirements": 0, "design": 0, "structure": 0}
    item_count = {"requirements": 0, "design": 0, "structure": 0}

    for item in SELF_CHECK_ITEMS:
        gate = item["gate"]
        item_count[gate] += 1
        try:
            ok = bool(item["check"](ctx))
        except Exception:  # noqa: BLE001 — a broken check counts as a failure, never crashes
            ok = False
        if not ok:
            fail_count[gate] += 1
            failures.append({
                "code": item["code"], "gate": gate,
                "cited_field": item["cited_field"], "message": item["message"],
            })

    gate_scores = {
        gate: (max(0.0, 1 - fail_count[gate] / item_count[gate]) if item_count[gate] else 1.0)
        for gate in ("requirements", "design", "structure")
    }
    confidence = compute_confidence(
        gate_scores["requirements"], gate_scores["design"], gate_scores["structure"]
    )
    top_uncertainties = [
        f["message"]
        for f in sorted(failures, key=lambda f: _GATE_PRIORITY[f["gate"]])[:3]
    ]

    return {
        "gate_scores": gate_scores,
        "confidence": confidence,
        "failures": failures,
        "top_uncertainties": top_uncertainties,
        "needs_revision": confidence < CONFIDENCE_THRESHOLD,
    }


# ------------------------------------------------------------------------------- CLI ---

def _print_summary(result: dict) -> None:
    scores = result["gate_scores"]
    print("confidence: %.2f (threshold %.2f)" % (result["confidence"], CONFIDENCE_THRESHOLD))
    print(
        "gate_scores: requirements=%.2f design=%.2f structure=%.2f"
        % (scores["requirements"], scores["design"], scores["structure"])
    )
    print("needs_revision: %s" % result["needs_revision"])
    for msg in result["top_uncertainties"]:
        print("  - %s" % msg)


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="deterministic pre-handoff confidence self-check for a plan directory"
    )
    parser.add_argument("plan_dir")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 when confidence < threshold (default stays advisory, exit 0)",
    )
    args = parser.parse_args(argv)

    result = run_self_check(args.plan_dir)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_summary(result)

    if args.strict and result["needs_revision"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
