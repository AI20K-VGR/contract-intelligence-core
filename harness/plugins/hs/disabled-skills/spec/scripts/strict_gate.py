#!/usr/bin/env python3
"""
strict_gate — shell-runnable `--strict` enforcement for CI.

The validation-rules-spec defines `--strict` as "errors block, warns advisory".
That gating originally lived only in the LLM orchestration layer, which made it
useless from a CI hook (no LLM in the loop → no enforcement → silent green on
broken specs). This script consumes the structural checkers' JSON output and
exits non-zero when any finding has severity=error.

Cross-layer shape-serves check (conditional): when the workspace has a BA shape
sidecar (`docs/product/shape/tasks/*.md`), this gate additionally READS each
task's `serves` frontmatter field as DATA (via `frontmatter_parser`, never by
importing `shape`'s `serves_resolver` — that would couple this PO gate to the
BA layer's code, breaking the one-way layering rule) and flags any `serves` id
that does not resolve to a live story in this spec's own graph. Shape absent
-> the check is a no-op (a spec-only workspace is unaffected). The `serves`
value itself is normalized via `id_grammar.normalize_serves` — the SAME shared
reading `serves_resolver` and the roadmap rollup use, so this PO gate cannot
silently disagree with the BA resolver about what a malformed `serves` means.

CLI:
    strict_gate.py --root <project-dir>
        Runs check_traceability + check_consistency (+ the conditional shape
        serves check), merges findings.
        Exits 0 when no error-severity findings.
        Exits 2 when at least one error-severity finding is present.
        Always writes a human summary to stderr.

Use in CI:
    python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/spec/scripts/strict_gate.py --root <ws>
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from encoding_utils import configure_utf8_console
from spec_graph import build_graph, make_finding as _f
from frontmatter_parser import parse_file
from id_grammar import normalize_serves
from check_traceability import check as check_trace
from check_consistency import check as check_cons, _enrich_with_ac

configure_utf8_console()

EXIT_OK = 0
EXIT_BLOCKED = 2

# The BA shape sidecar's task directory, read-only, DATA-only (never imported
# as code — see the cross-layer shape-serves module docstring above).
SHAPE_TASKS_DIRNAME = ("docs", "product", "shape", "tasks")

# Matches task_model.py's own `_TASK_FILE_RE` grammar so this gate walks
# TASK-<n>.md files in the same NUMERIC order task_model.list_tasks() does.
# A plain `sorted(glob(...))` is lexicographic (TASK-10 before TASK-2).
_TASK_FILE_RE = re.compile(r"^TASK-([0-9]+)\.md$")


def _sorted_task_files(tasks_dir: Path) -> List[Path]:
    """Return every TASK-<n>.md under `tasks_dir`, sorted by the numeric <n>
    (mirrors task_model._existing_task_nums / list_tasks).

    Only files matching the TASK-<n>.md grammar are returned — task_model's
    own `list_tasks()` and shape's `serves_resolver.list_task_records()` both
    require this same `_TASK_FILE_RE` and never count a non-matching file as
    a task, so a stray non-task .md dropped in tasks/ (e.g. hand-authored
    notes) must not be gated here either — it isn't a task the BA tooling
    tracks.

    The sort key is `(numeric-id, path)`, not the numeric id alone: two files
    colliding on the same <n> (a hand-authored `TASK-02.md` beside
    `TASK-2.md`) would otherwise tie and fall back to filesystem glob order,
    diverging from task_model/serves_resolver (which sort `(int, Path)` tuples
    and break the tie deterministically on the path)."""
    matches = [
        (p, m) for p in tasks_dir.glob("*.md")
        if (m := _TASK_FILE_RE.match(p.name)) is not None
    ]
    return [p for p, m in sorted(matches, key=lambda pm: (int(pm[1].group(1)), pm[0]))]


def _live_story_ids(graph: Dict[str, Any]) -> set:
    return {n["id"] for n in graph.get("nodes", []) if n.get("type") == "story"}


def check_shape_serves(root: Path, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flag a shape task whose `serves` names a story id absent from this
    spec's live graph (`dangling_serves`, error).

    A no-op — returns [] — when `docs/product/shape/tasks/` does not exist
    (a spec-only workspace, no BA layer wired yet), or when a task carries no
    `serves` key at all (ABSENT stays a no-op — `id_grammar.normalize_serves`
    only receives a present value). Every field read is otherwise
    KeyError-safe / fail-soft: a task file that fails to parse is simply
    skipped rather than crashing the gate — the shape schema is not yet a
    locked dependency of this check.

    The `serves` VALUE is read through `id_grammar.normalize_serves` — the one
    shared reading `serves_resolver` (BA layer) and the roadmap rollup also
    use, so a `serves` this PO gate calls dangling can never resolve clean in
    the BA resolver (or vice versa). That covers both malformed shapes:
    a `serves` that is PRESENT but not a list at all (a bare string or a
    mapping from a hand-edit), and a list entry that is not a string (an
    int/null/float, or a YAML-auto-resolved date from `serves: [2026-07-13]`)
    — either is flagged as `dangling_serves`, never silently skipped (a skip
    here let an orphan task pass the gate clean).

    An EMPTY list (`serves: []`) normalizes to `([], [])` and stays a no-op:
    a shape task not yet wired to any story is a valid draft state, not an
    error — only a story id that fails to resolve is a defect.
    """
    tasks_dir = Path(root)
    for part in SHAPE_TASKS_DIRNAME:
        tasks_dir = tasks_dir / part
    if not tasks_dir.is_dir():
        return []

    story_ids = _live_story_ids(graph)
    findings: List[Dict[str, Any]] = []
    seen_ids: Dict[str, str] = {}
    for task_path in _sorted_task_files(tasks_dir):
        parsed = parse_file(task_path)
        if not parsed.get("ok"):
            continue
        fm = parsed.get("frontmatter") or {}
        # Carrier id must stay a string: a hand-edited `id: [TASK-1, TASK-2]`
        # is truthy but a list, so a bare `fm.get("id") or stem` would leak the
        # raw list into artifact_id (every other finding site keeps it
        # str-or-None). Fall back to the filename stem for any non-string id --
        # the task is still surfaced (validator role), just labelled by file.
        _raw_id = fm.get("id")
        task_id = _raw_id if isinstance(_raw_id, str) and _raw_id else task_path.stem
        carrier = {"id": task_id, "file": str(task_path)}
        # A real (string) frontmatter id shared by two DISTINCT task files is a
        # duplicate task id (a copy-paste that forgot to bump the inner id). Flag
        # it like spec flags dup_id for PO artifacts -- left unflagged it makes
        # serves_resolver's two coverage maps silently disagree. The stem-fallback
        # id is unique per file, so only a real string id can collide here.
        if isinstance(_raw_id, str) and _raw_id:
            if _raw_id in seen_ids:
                findings.append(_f(
                    "dup_task_id", "error", carrier,
                    f"Shape task id {_raw_id} is already used by "
                    f"{seen_ids[_raw_id]}; task ids must be unique.",
                    ref=seen_ids[_raw_id],
                ))
            else:
                seen_ids[_raw_id] = task_path.name
        serves = fm.get("serves")
        if serves is None:
            continue
        valid_ids, invalid_entries = normalize_serves(serves)
        # Dedupe order-preserving: a hand-edited `serves:[S1,S1]` is one real
        # edge, not two findings (mirrors serves_resolver.resolve_serves +
        # spec_graph._as_id_list). invalid_entries are already str-coerced by
        # normalize_serves, so both are hashable here.
        valid_ids = list(dict.fromkeys(valid_ids))
        invalid_entries = list(dict.fromkeys(invalid_entries))
        for bad in invalid_entries:
            findings.append(_f(
                "dangling_serves", "error", carrier,
                f"Shape task {task_id} serves {bad}, which cannot resolve to "
                f"any live story.",
                ref=bad,
            ))
        for story_id in valid_ids:
            if story_id not in story_ids:
                findings.append(_f(
                    "dangling_serves", "error", carrier,
                    f"Shape task {task_id} serves {story_id}, which is not a "
                    f"live story in this spec.",
                    ref=story_id,
                ))
    return findings


def collect_findings(root: Path):
    graph = build_graph(root)
    _enrich_with_ac(graph, root)
    findings = []
    findings.extend(check_trace(graph))
    findings.extend(check_cons(graph))
    findings.extend(check_shape_serves(root, graph))
    return findings, graph


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="project root (contains docs/product/)")
    ap.add_argument(
        "--allow-empty", action="store_true",
        help="pass instead of blocking when the workspace has zero spec artifacts",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    findings, graph = collect_findings(root)
    errors = [f for f in findings if f.get("severity") == "error"]
    warns = [f for f in findings if f.get("severity") == "warn"]

    n_artifacts = len(graph.get("nodes", []))
    summary = (
        f"[strict_gate] {n_artifacts} artifacts checked · "
        f"{len(errors)} errors · {len(warns)} warns"
    )
    print(summary, file=sys.stderr)

    # A gate keyed on exit code must NOT report green when it validated nothing:
    # a wrong --root, a moved/renamed docs/product, or a run-before-any-spec
    # would otherwise silently pass CI having checked zero artifacts. Block that
    # vacuous-pass unless the caller explicitly opts in with --allow-empty.
    if n_artifacts == 0 and not args.allow_empty:
        print(
            "[strict_gate] BLOCKED: zero spec artifacts found under %s "
            "(wrong --root, or no spec yet?). Pass --allow-empty to allow." % root,
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    if not errors:
        return EXIT_OK

    print("[strict_gate] BLOCKED on errors:", file=sys.stderr)
    for f in errors:
        aid = f.get("artifact_id") or "?"
        chk = f.get("check") or "?"
        detail = f.get("detail") or ""
        print(f"  - {chk} · {aid} · {detail}", file=sys.stderr)
    return EXIT_BLOCKED


if __name__ == "__main__":
    sys.exit(main())
