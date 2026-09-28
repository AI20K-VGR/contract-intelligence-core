#!/usr/bin/env python3
"""experiment_spec — author/refine a market-experiment spec for hs:shape (BA).

The verification-tiering rule (hard, "kẹp 2 đầu" — clamp both ends): the experiment ITSELF (khách thích
/ trả tiền, đo số thật) is market territory the PO owns OUTSIDE the harness. This
module owns only the FIRST clamp: pre-register the hypothesis/design/decision_rule
as a first-class artifact BEFORE anyone runs anything (`outcomes.md` today only
records a measurement post-hoc). The second clamp
(read a PO-supplied result and apply the rule) is `experiment_verdict.py`. Neither
script fetches, polls, or shells out to RUN an experiment — multi-run unattended
orchestration is tầng-2 (`orchestrator/`), never imported here.

Storage: one file per experiment, `<root>/docs/product/shape/experiments/EXP-<n>.md`
(YAML frontmatter + free-text body) — unlike the DEC ledger's single append-only
file, each experiment is its own artifact so `experiment_verdict.py` can rewrite
just that one file's frontmatter in place when the verdict lands.

Containment: every write resolves under `experiment_path()`, which asserts
the resolved path stays inside `docs/product/shape/experiments/` and raises on
escape (`..`, absolute override, symlink). This mirrors the sibling
`shape_paths.shape_path()` invariant on its own subpath, reimplemented locally
so this module carries no import edge onto shape_paths.py — it depends only on
hs:spec's spec_graph (for linked_to resolution) and frontmatter_parser (for
frontmatter reads), both reached via `_spec_bridge`'s isolated loader, keeping
the two sidecars independently testable/cookable.
"""

from __future__ import annotations

import argparse
import fcntl
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sidecar import _default_actor, _now_iso, write_record, SidecarError  # noqa: E402
from _spec_bridge import (  # noqa: E402
    load_frontmatter_parser as _load_frontmatter_parser,
    load_spec_graph as _load_spec_graph,
)

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


class ExperimentError(ValueError):
    """Raised on a grammar/shape/containment violation (CLI -> non-zero exit)."""


class ExperimentContainmentError(ExperimentError, PermissionError):
    """Raised when an hs:shape experiment write would escape
    `docs/product/shape/experiments/`. Multiple-inherits `ExperimentError`
    (so `main()`'s `except ExperimentError` catches an escape instead of it
    surfacing as a raw traceback) and `PermissionError` (matching the sibling
    `shape_paths.ShapeContainmentError` family, and preserving the existing
    `pytest.raises(PermissionError)` escape-test contract)."""


_EXP_ID_RE = re.compile(r"^EXP-([0-9]+)$")
_EXP_FILE_RE = re.compile(r"^EXP-([0-9]+)\.md$")

# Only these node types are valid `linked_to` targets (brd_goal/prd/epic) —
# a story id is out of scope for an experiment link, so it is treated as
# dangling even when it resolves in the underlying spec graph.
_LINKABLE_TYPES = frozenset({"goal", "prd", "epic"})

_DECISION_RULE_KEYS = ("direction", "target", "hit_floor", "partial_floor")


# ---------------------------------------------------------------------------
# Containment
# ---------------------------------------------------------------------------

def experiments_dir(root: RootLike) -> Path:
    return Path(root) / "docs" / "product" / "shape" / "experiments"


def experiment_path(root: RootLike, rel: str) -> Path:
    """Resolve ``rel`` under the experiments dir, raising on escape.

    Equivalent invariant to the sibling ``shape_paths.shape_path()`` (resolve ->
    assert contained -> raise), reimplemented here on purpose so this module
    carries no import edge onto shape_paths.py (this module depends only on
    hs:spec's spec_graph, not on shape_paths.py).
    """
    base = experiments_dir(root).resolve()
    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ExperimentContainmentError(
            "experiment write escapes containment: %r resolves outside %s" % (rel, base)
        )
    return candidate


def resolve_linked_to(root: RootLike, linked_to: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Split ``linked_to`` into (valid, dangling) against hs:spec's spec graph.

    A dangling id is either absent from the graph entirely, or present but not
    a goal/prd/epic (a story link is out of scope for an experiment, flagged
    the same as a truly missing id).
    """
    linked_to = list(linked_to or [])
    if not linked_to:
        return [], []
    spec_graph_mod = _load_spec_graph()
    graph = spec_graph_mod.build_graph(Path(root))
    known = {
        n.get("id")
        for n in graph.get("nodes", [])
        if isinstance(n, dict) and n.get("type") in _LINKABLE_TYPES and n.get("id")
    }
    valid = [i for i in linked_to if i in known]
    dangling = [i for i in linked_to if i not in known]
    return valid, dangling


# ---------------------------------------------------------------------------
# EXP id allocation (grep-existing-files max+1, monotonic, gap-preserving)
# ---------------------------------------------------------------------------

def _existing_exp_nums(root: RootLike) -> List[int]:
    d = experiments_dir(root)
    if not d.exists():
        return []
    nums = []
    for p in sorted(d.glob("EXP-*.md")):
        m = _EXP_FILE_RE.match(p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


# ---------------------------------------------------------------------------
# decision_rule shape (shared by author-time and verdict-time validation)
# ---------------------------------------------------------------------------

def validate_decision_rule(rule: Dict[str, Any]) -> None:
    """Raise ExperimentError on a malformed decision_rule; else return None.

    Same 3-tier ratio-floor shape as the "Verdict math" paragraph in
    frontmatter-and-id-spec.md's Outcome records section (``outcome_verdict.py``
    itself is a module in the separate, out-of-skill product-spec project --
    never imported here): direction higher/lower, a positive numeric target
    (target must be > 0 -- the fraction-of-target verdict `compute_verdict`
    computes is a plain ratio against `target`, which sign-flips on a
    negative target: e.g. direction="higher", target=-5, actual=-10 gives
    ratio = -10/-5 = 2.0 >= hit_floor -> "hit", even though -10 is WORSE than
    -5. A 0 target also divides by zero under "higher". Rejecting target<=0
    here converts that silent-wrong-verdict into a clear upfront error), and
    0 <= partial_floor < hit_floor <= 1.
    """
    if not isinstance(rule, dict):
        raise ExperimentError("decision_rule must be a mapping")
    missing = [k for k in _DECISION_RULE_KEYS if k not in rule]
    if missing:
        raise ExperimentError("decision_rule missing key(s): %s" % ", ".join(missing))
    direction = rule.get("direction")
    if direction not in ("higher", "lower"):
        raise ExperimentError("decision_rule.direction must be 'higher' or 'lower'")
    try:
        target = float(rule["target"])
        hit_floor = float(rule["hit_floor"])
        partial_floor = float(rule["partial_floor"])
    except (TypeError, ValueError):
        raise ExperimentError("decision_rule.target/hit_floor/partial_floor must be numbers")
    if not math.isfinite(target) or target <= 0:
        raise ExperimentError(
            "decision_rule.target must be a positive finite number -- the "
            "fraction-of-target verdict is undefined for non-positive or "
            "NaN/Inf targets (NaN slips a bare `target <= 0` check, since every "
            "NaN comparison is False, and then makes every ratio NaN -> a "
            "constant 'miss' regardless of the actual result)"
        )
    if not (0 <= partial_floor < hit_floor <= 1):
        raise ExperimentError(
            "invalid decision_rule floors: need 0 <= partial_floor (%r) "
            "< hit_floor (%r) <= 1" % (partial_floor, hit_floor)
        )


# ---------------------------------------------------------------------------
# Frontmatter render / read
# ---------------------------------------------------------------------------

def _render_body(exp_id: str, title: str, hypothesis: str, dangling: Sequence[str]) -> str:
    lines = ["# %s — %s" % (exp_id, title or hypothesis), "", hypothesis, ""]
    if dangling:
        lines.append("> dangling linked_to (not found in the PO spec graph): %s"
                     % ", ".join(dangling))
    return "\n".join(lines)


def read_experiment(root: RootLike, exp_id: str) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter dict, body) for ``exp_id``. Raises ExperimentError on
    a missing file or malformed/non-mapping frontmatter -- never crashes with a
    raw parser traceback.

    Routed through `frontmatter_parser.parse_text` (the hardened SSOT)
    instead of a locally hand-tuned `_FRONTMATTER_RE` + `yaml.safe_load` +
    `(yaml.YAMLError, ValueError)` catch: PyYAML raises a wider family than
    that pair on malformed frontmatter -- e.g. a bare `AttributeError` from
    `construct_yaml_timestamp` on an explicit-tag `ts: !!timestamp 'not a
    ts'` -- and the SSOT already fails soft on the whole family in one place."""
    if not _EXP_ID_RE.match(exp_id or ""):
        raise ExperimentError("not a valid experiment id: %r" % exp_id)
    path = experiment_path(root, "%s.md" % exp_id)
    return _read_experiment_at(path, exp_id)


def _read_experiment_at(path: Path, label: str) -> Tuple[Dict[str, Any], str]:
    """Read (frontmatter, body) from an ACTUAL on-disk experiment path. Split out
    from `read_experiment` so `list_experiments` can read the real glob-matched
    file (e.g. a zero-padded `EXP-01.md`) instead of re-deriving a canonical
    `EXP-<num>.md` path that may not exist -- mirrors task_model.list_tasks."""
    if not path.is_file():
        raise ExperimentError("experiment not found: %s" % label)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExperimentError("cannot read experiment file (%s): %s" % (label, exc))
    fp = _load_frontmatter_parser()
    parsed = fp.parse_text(text, file_label=str(path))
    if not parsed["ok"]:
        raise ExperimentError("malformed experiment frontmatter (%s): %s" % (label, parsed["error"]))
    return parsed["frontmatter"], parsed["body"]


def write_experiment(root: RootLike, exp_id: str, record: Dict[str, Any], body: str) -> Path:
    target = experiment_path(root, "%s.md" % exp_id)
    write_record(target, record, body)
    return target


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------

def author(
    root: RootLike,
    hypothesis: str,
    linked_to: Optional[Sequence[str]] = None,
    design: Optional[Dict[str, Any]] = None,
    success_metric: str = "",
    decision_rule: Optional[Dict[str, Any]] = None,
    title: str = "",
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Allocate the next EXP-<n>, resolve linked_to against hs:spec's spec graph
    (flagging dangling ids, not rejecting them), validate the decision_rule
    shape, and write the spec under experiment_path(). status starts "draft".
    """
    if not hypothesis or not isinstance(hypothesis, str):
        raise ExperimentError("hypothesis is required")
    if not success_metric or not isinstance(success_metric, str):
        raise ExperimentError("success_metric is required")
    linked_to = list(linked_to or [])
    design = dict(design or {})
    decision_rule = dict(decision_rule or {})
    validate_decision_rule(decision_rule)

    d = experiments_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".experiments.lock"
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            nums = _existing_exp_nums(root)
            new_num = (max(nums) + 1) if nums else 1
            exp_id = "EXP-%d" % new_num

            valid_links, dangling = resolve_linked_to(root, linked_to)

            resolved_actor = actor or _default_actor()
            record: Dict[str, Any] = {
                "id": exp_id,
                "hypothesis": hypothesis,
                "linked_to": linked_to,
                "design": design,
                "success_metric": success_metric,
                "decision_rule": decision_rule,
                "status": "draft",
                "verdict": None,
                "actual": None,
                "measured_on": None,
                "dangling_linked_to": dangling,
                "actor": resolved_actor,
                "ts": _now_iso(),
            }
            body = _render_body(exp_id, title, hypothesis, dangling)
            target = write_experiment(root, exp_id, record, body)

            result = dict(record)
            result["path"] = str(target)
            result["valid_linked_to"] = valid_links
            return result
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def list_experiments(root: RootLike) -> List[Dict[str, Any]]:
    """Return frontmatter dicts for every EXP-<n>.md under the experiments dir,
    sorted by numeric id. A malformed experiment file is skipped rather than
    raising -- `--list` must never surface a raw traceback over one bad
    hand-edited record."""
    d = experiments_dir(root)
    if not d.exists():
        return []
    numbered = []
    for p in sorted(d.glob("EXP-*.md")):
        m = _EXP_FILE_RE.match(p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    out = []
    for _num, p in sorted(numbered):
        try:
            fm, _body = _read_experiment_at(p, p.name)
        except ExperimentError:
            continue
        out.append(fm)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="experiment_spec.py",
        description="Author a market-experiment spec (first clamp of the verification-tiering rule). "
        "Does not run anything; see experiment_verdict.py for the second clamp.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--add", action="store_true", help="allocate + author a new EXP spec")
    mode.add_argument("--list", action="store_true", help="list existing EXP specs")
    p.add_argument("--hypothesis", default="")
    p.add_argument("--linked-to", default="", help="comma-separated goal/prd/epic ids")
    p.add_argument("--method", default="")
    p.add_argument("--control", default="")
    p.add_argument("--variant", default="")
    p.add_argument("--metric", default="", help="success_metric slug")
    p.add_argument("--direction", default="higher", choices=("higher", "lower"))
    p.add_argument("--target", type=float, default=None)
    p.add_argument("--hit-floor", type=float, default=0.9)
    p.add_argument("--partial-floor", type=float, default=0.5)
    p.add_argument("--title", default="")
    p.add_argument("--actor", default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.add:
        if args.target is None:
            print("error: --target is required with --add", file=sys.stderr)
            return 1
        linked_to = [i.strip() for i in args.linked_to.split(",") if i.strip()]
        design = {"method": args.method, "control": args.control, "variant": args.variant}
        decision_rule = {
            "direction": args.direction,
            "target": args.target,
            "hit_floor": args.hit_floor,
            "partial_floor": args.partial_floor,
        }
        try:
            record = author(
                args.root,
                hypothesis=args.hypothesis,
                linked_to=linked_to,
                design=design,
                success_metric=args.metric,
                decision_rule=decision_rule,
                title=args.title,
                actor=args.actor,
            )
        except (ExperimentError, SidecarError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        print(record["id"])
        if record["dangling_linked_to"]:
            print("warning: dangling linked_to: %s" % ", ".join(record["dangling_linked_to"]),
                  file=sys.stderr)
        return 0
    if args.list:
        for rec in list_experiments(args.root):
            print("%s\t%s\t%s" % (rec.get("id", ""), rec.get("status", ""), rec.get("verdict", "")))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
