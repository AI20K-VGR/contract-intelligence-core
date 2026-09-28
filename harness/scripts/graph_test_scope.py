#!/usr/bin/env python3
"""graph_test_scope.py — for one plan-graph node, the test files it DECLARES.

Pure function `resolve_test_scope(plan_dir, node_id)`: reads `files_to_create`
+ `files_to_modify` for `node_id` out of `plan-graph.yaml`, filters through the
SAME `_TEST_PATH_RE` change_class_derivation already owns (no second
matcher), and cross-checks each match against disk. Never raises: every broken
input (missing/malformed sidecar, unknown node, wrong-typed `subtasks`)
degrades to a named `status` branch instead.

Six statuses:
  resolved         >=1 declared test path exists on disk
  declared_absent  >=1 declared test path matched, but NONE exist on disk
  no_test_paths    files_to_* declared, but nothing in it matches _TEST_PATH_RE
  malformed_declaration
                    files_to_* IS present but wrong-typed (a scalar where a
                    list belongs), so nothing could be read out of it — kept
                    apart from nothing_declared, whose wording would send the
                    author looking for a declaration that is already there
  nothing_declared node is a real subtask, but files_to_* is empty/absent —
                    kept distinct from no_test_paths: no scanner in this tree
                    already catches an empty files_to_* (it is valid YAML, not
                    a TBD sentinel), so an author who declared nothing looks
                    identical to plan_graph unless this function says so
  unknown_node      node_id is not a key under `subtasks:`
  no_graph          the sidecar is missing, malformed, or wrong-typed —
                    parse_phase_graph's own {"error": ...} surfaces verbatim

Content is never inspected (KISS) — a source file whose NAME matches the
test-path convention (harness/scripts/test_result_readers.py is the known
case) still resolves. `content_unverified` is True on every `resolved` result
so a caller running pytest over `files` knows to treat exit 5 (no tests
collected) as an expected outcome of this function's contract, not a crash.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
import harness_paths  # noqa: E402
import plan_graph  # noqa: E402
from change_class_derivation import _TEST_PATH_RE  # noqa: E402

STATUSES = ("resolved", "declared_absent", "no_test_paths", "nothing_declared",
            "malformed_declaration", "unknown_node", "no_graph")


def _result(status, files=(), declared=(), content_unverified=False, error=None):
    return {
        "status": status,
        "files": sorted(set(files)),
        "declared": sorted(set(declared)),
        "content_unverified": content_unverified,
        "error": error,
    }


def _resolve_within_root(root: Path, rel_path: str):
    """`rel_path` resolved against `root`, or None when it escapes `root`
    (an absolute path elsewhere, or a `../` climb) — never raises."""
    cand = Path(rel_path)
    cand = cand if cand.is_absolute() else root / cand
    try:
        resolved = cand.resolve(strict=False)
        resolved.relative_to(root)
    except (ValueError, OSError):
        return None
    return resolved


def _root_for(plan_dir: Path) -> Path:
    """The tree `plan_dir` itself lives in — the one its relative declarations
    are written against.

    Declared paths in a sidecar are relative to the project that OWNS the plan,
    so the disk cross-check has to ask that project. Asking the ambient root
    instead (env/CWD-derived) answers correctly about a different tree: measured
    under a plan outside the ambient project, the declared test sitting next to
    the plan read `declared_absent`, and a same-named file in the ambient tree
    read `resolved`. Both are wrong about the plan in hand.

    Derived structurally: `<root>/plans/<plan>/` is the layout every plan dir
    has, so the grandparent of a dir under `plans/` is the root. A plan dir not
    laid out that way falls back to the ambient project root, which is the
    behavior every caller had before and stays correct under self-host.
    """
    try:
        resolved = Path(plan_dir).resolve(strict=False)
    except OSError:
        return harness_paths.project_root().resolve()
    for parent in resolved.parents:
        if parent.name == "plans":
            return parent.parent
    return harness_paths.project_root().resolve()


def resolve_test_scope(plan_dir, node_id: str) -> dict:
    """The test-file scope `node_id` declares in `plan_dir`'s plan-graph.yaml.
    Never raises — see module docstring for the 6-way status contract."""
    graph = plan_graph.parse_phase_graph(plan_dir)
    err = graph.get("error")
    if err:
        return _result("no_graph", error=err)

    subtasks = graph.get("subtasks") or {}
    if node_id not in subtasks:
        return _result("unknown_node")

    declared = plan_graph._files(graph, node_id, "files_to_create", "files_to_modify")
    if not declared:
        # A WRONG-TYPED declaration is not an absent one. `_files` drops a scalar
        # written where a list belongs (`files_to_create: path.py`, no dash), and
        # calling that `nothing_declared` — "this node declares no files at all" —
        # sends the author hunting for a declaration sitting right on the line.
        subtask = (graph.get("subtasks") or {}).get(node_id)
        if isinstance(subtask, dict) and any(
                subtask.get(k) is not None
                for k in ("files_to_create", "files_to_modify")):
            return _result("malformed_declaration")
        return _result("nothing_declared")

    test_paths = sorted(p for p in declared if _TEST_PATH_RE.search(p))
    if not test_paths:
        return _result("no_test_paths")

    root = _root_for(plan_dir)
    on_disk, absent = [], []
    for p in test_paths:
        real = _resolve_within_root(root, p)
        if real is not None and real.is_file():
            on_disk.append(p)
        else:
            absent.append(p)

    if on_disk:
        return _result("resolved", files=on_disk, declared=absent,
                        content_unverified=True)
    return _result("declared_absent", declared=absent)
