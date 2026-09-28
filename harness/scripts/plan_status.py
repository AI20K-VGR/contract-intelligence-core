"""plan_status.py — surgical, idempotent plan.md frontmatter status flips.

Shared core for the two lifecycle endpoints that move a plan through the only
two states the gate actually consumes:

  open_plan:  pending | approved -> in_progress   (cook's first step)
  close_plan: in_progress        -> completed     (cook's finalize step)

Discipline (mirrored from both callers' original behaviour):
  - Status is read/written ONLY inside the opening `---` … closing `---`/`...`
    block, never from the body — a plan body may quote `status: ...` in prose.
  - Only the status VALUE is rewritten; every other byte is preserved.
  - Idempotent: a plan already at the target status is a successful no-op.
  - Containment: refuses any plan dir outside <root>/plans/, so a misaimed path
    cannot rewrite an unrelated file's frontmatter.

`error_on_other` is the open/close asymmetry. close leaves an off-source status
(e.g. pending) alone as a benign no-op — a misaimed close must never mark
unstarted work done. open instead fails LOUD on an off-source status (e.g.
completed/cancelled): if it cannot reach in_progress, cook must halt rather than
cook a plan the resolver will never see as active.
"""
import re
from dataclasses import dataclass
from pathlib import Path

# Mirror artifact_check's frontmatter discipline: the status line lives only
# inside the opening `---` … closing `---`/`...` block.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)^(?:---|\.\.\.)\s*$",
                             re.MULTILINE | re.DOTALL)
_STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)

# The only status values a plan may carry. The board, the gate resolver, and
# reconcile all read against this set; anything else is drift to be surfaced,
# never silently re-bucketed.
CANONICAL_STATUSES = (
    "pending", "approved", "in_progress", "completed", "cancelled",
)

# Retired labels and the canonical state they fold to. `draft` was an exact
# synonym of `pending` (no code ever branched on the difference); the dead
# `awaiting_human_approval` is replaced by `pending` (no approval artifact yet).
# They fold for every consumer — so a legacy plan reads as a valid state with no
# board-drift window — yet they are NOT in CANONICAL_STATUSES, so is_canonical
# reports them False and reconcile can migrate them by evidence (an APPROVED
# artifact lifts a folded plan to `approved` rather than blind-folding to pending).
_LEGACY_FOLD = {"draft": "pending", "awaiting_human_approval": "pending"}


def normalize_status(raw):
    """Fold a status token to its canonical form, or return None if the result is
    not a known status.

    Lossless + retired-label only: strip surrounding quotes/whitespace, fold the
    `in-progress` dash spelling to underscores (the exact fold the gate resolver
    applies), then map a retired label (`draft`, `awaiting_human_approval`, incl.
    dash spelling) to its canonical home `pending`. It does NOT guess a semantic
    mapping for an off-vocabulary value such as `done` — that is a judgment call
    left to reconcile, which decides from evidence, not spelling.
    """
    if not raw:
        return None
    folded = _norm(str(raw).strip())
    folded = _LEGACY_FOLD.get(folded, folded)
    return folded if folded in CANONICAL_STATUSES else None


def is_canonical(raw) -> bool:
    """True iff `raw` is already exactly one of the canonical status values
    (no fold applied — a raw dash form or a retired label is reported as
    non-canonical so it can be normalized/migrated in place)."""
    return raw in CANONICAL_STATUSES


@dataclass
class Result:
    ok: bool
    changed: bool
    message: str


def root_dir(root=None) -> Path:
    """The fallback root used only when fs_guard is unavailable (see
    _splice_status). An explicit `root` wins; otherwise resolve project-aware
    via harness_paths — a bare CWD fallback silently resolves to whatever
    directory the caller happened to be run from rather than the project that
    actually owns plans/. Byte-identical twin of reconcile_plan_status.root_dir
    (the module reconcile calls for its actual writes); keep the two in sync."""
    if root is not None:
        return Path(root)
    import harness_paths
    return harness_paths.project_root()


def _norm(value: str) -> str:
    """Normalize a status token the way the resolver does: strip quotes, fold
    the `in-progress`/`in_progress` spelling to one canonical form."""
    return value.strip("'\"").replace("-", "_")


def _splice_status(plan_dir, root):
    """Locate the frontmatter status value. Returns (text, val_start, val_end,
    current_raw, pm) or a Result on any structural problem."""
    plan_dir = Path(plan_dir)
    # Containment goes through the shared "plans" zone rather than a local
    # root_dir(root)/plans check. Under a global install the plan lives in the
    # PROJECT while `root` is the shared BIN, so the local rule refused every
    # real plan — plan_approval wrote its artifact through this same zone and
    # then reported "status flip skipped" on the very plan it had just
    # approved. One containment rule, not two; the zone still refuses a plan
    # under neither plans/ root.
    try:
        import fs_guard
        fs_guard.assert_under(plan_dir, "plans", root=root)
    except ImportError:
        plans = (root_dir(root) / "plans").resolve()
        try:
            plan_dir.resolve().relative_to(plans)
        except ValueError:
            return Result(False, False,
                          "plan dir %s is not under %s" % (plan_dir, plans))
    except Exception as e:  # noqa: BLE001 — fs_guard.FenceError and friends
        return Result(False, False, str(e))
    pm = (plan_dir / "plan.md").resolve()
    try:
        text = pm.read_text(encoding="utf-8")
    except OSError:
        return Result(False, False, "no plan.md at %s" % pm)
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return Result(False, False, "no frontmatter block in %s" % pm)
    m = _STATUS_RE.search(fm.group(1))
    if not m:
        return Result(False, False, "no status line in frontmatter of %s" % pm)
    return text, fm.start(1) + m.start(1), fm.start(1) + m.end(1), m.group(1), pm


def set_status_value(plan_dir, to, *, root=None) -> Result:
    """Unconditionally rewrite the frontmatter status VALUE to `to`, surgically.

    Unlike flip_status, this does not fold spellings before comparing, so it is
    the right tool for a lossless spelling repair (`in-progress` -> `in_progress`)
    where flip_status would see the normalized forms as already equal and no-op.
    Containment and the frontmatter-only discipline still hold; only the status
    token changes.
    """
    spliced = _splice_status(plan_dir, root)
    if isinstance(spliced, Result):
        return spliced
    text, val_start, val_end, current, pm = spliced
    if text[val_start:val_end] == to:
        return Result(True, False, "already %s" % to)
    new_text = text[:val_start] + to + text[val_end:]
    pm.write_text(new_text, encoding="utf-8")
    return Result(True, True, "%s: %s -> %s" % (Path(plan_dir).name, current, to))


def flip_status(plan_dir, *, allowed_from, to, error_on_other=False,
                root=None) -> Result:
    """Flip plan_dir/plan.md frontmatter status to `to`.

    - current == to              -> successful no-op (changed=False).
    - current in allowed_from    -> rewritten (changed=True).
    - otherwise                  -> left as-is; ok=False when error_on_other,
                                    else a benign ok=True no-op.

    Any structural problem (containment, missing plan.md, no status line) is an
    error (ok=False) and the file is never partially written.
    """
    # Reuse the locate-status splice (containment + read + frontmatter + status),
    # then apply flip's normalization/compare on top of it.
    spliced = _splice_status(plan_dir, root)
    if isinstance(spliced, Result):
        return spliced
    text, val_start, val_end, current_raw, pm = spliced

    current = _norm(current_raw)
    target = _norm(to)
    if current == target:
        return Result(True, False, "already %s" % target)
    if current not in {_norm(s) for s in allowed_from}:
        msg = ("status %r is not one of %s — left as-is"
               % (current_raw, sorted(allowed_from)))
        return Result(not error_on_other, False, msg)

    new_text = text[:val_start] + to + text[val_end:]
    pm.write_text(new_text, encoding="utf-8")
    return Result(True, True, "%s: %s -> %s" % (Path(plan_dir).name, current, to))
