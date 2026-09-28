"""grid/diff_attest.py — diff a frozen feature checklist against a grid's
§features axis values (leaf, stdlib-only; mirrors grid/provenance.py: pure
functions, no import of review/artifact to avoid a cycle).

Because ``feature_checklist.py``'s checklist is produced independently of
and frozen before the grid's own feature axis, a non-empty diff here is a
REAL disagreement between two independently-derived feature lists — not a
grid re-deriving its own input and trivially agreeing with itself. This
module only computes the diff; it does not judge completeness or correctness
of either side.
"""
from typing import Dict, List


def compute_feature_diff(checklist_features: List[str], plan_features: List[str]) -> Dict[str, List[str]]:
    """``{"dropped": [in checklist, not in plan], "added": [in plan, not in
    checklist]}`` — order-preserving (the input list's own order), plain
    string compare (no case-folding / fuzzy match)."""
    plan_set = set(plan_features or [])
    checklist_set = set(checklist_features or [])
    dropped = [f for f in (checklist_features or []) if f not in plan_set]
    added = [f for f in (plan_features or []) if f not in checklist_set]
    return {"dropped": dropped, "added": added}
