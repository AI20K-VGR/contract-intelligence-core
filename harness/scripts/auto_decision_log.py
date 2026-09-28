#!/usr/bin/env python3
"""auto_decision_log.py — advisory sink for AI-autonomous decisions.

An auto-mode (default cook, hs:fix, hs:code-review, hs:review-pr, hs:ship …) decides
things with no human in the loop — a module boundary, a scope trim, an overridden choice.
Nothing records them for a next-morning skim. This sink appends ONE JSONL line per such
decision, carrying a closed-vocab label + FORCED evidence, so the trail exists without
blocking anything. Advisory by design: it never gates a stage.

Borrows emit_observation.py's contract verbatim at the load-bearing points — closed-vocab
validate → fail LOUD (exit 2, no write); append-only serialize-before-open; actor+ts via
hook_runtime.resolve_actor; a 2KB free-text cap; a store I/O failure → fail OPEN (exit 0,
telemetry-class). It DIVERGES in three ways: (1) an 11-field decision model (not
skill/signal/payload); (2) a plan-anchored absolute store path that resolves to the MAIN
worktree via git-common-dir — a line emitted from a linked worktree (git-removed after the
run) must never be lost; (3) `evidence` is mandatory.

Writer-model: a worktree-isolated cook subagent does NOT call this directly (its tree is
removed); the cook MAIN agent records at the integration barrier. The git-common-dir
resolve + worktree-guard here is the BACKSTOP for a stray direct call, not the primary path.

CLI (default = append one decision):
    auto_decision_log.py --skill hs:cook --mode auto --label ARCH \\
        --what "..." --why "..." --evidence "foo.py:12" [--in-plan] [--plan-dir ABS] \\
        [--session ID] [--store PATH] [--labels PATH] [--config PATH]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

PAYLOAD_CAP_BYTES = 2048  # 2KB free-text budget (what + why + evidence), mirrors emit_observation
_DATA = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_LABELS = _DATA / "auto-decision-labels.yaml"
_DEFAULT_CONFIG = _DATA / "auto-decision.yaml"
# Captured once at import, matching the emit_observation / telemetry_paths pattern so this
# sink shares the same session dimension as the other telemetry sinks.
_SESSION = os.environ.get("HARNESS_SESSION_ID") or None

# The record fields a valid decision line must carry (id/ts/actor filled at write).
_REQUIRED_MODEL = ("type", "id", "ts", "actor", "skill", "mode",
                   "label", "in_plan", "reviewed", "what", "why", "evidence")


# --------------------------------------------------------------------------- vocab / toggle
def load_labels(path=None) -> Dict[str, str]:
    """The closed vocabulary as a {label: basket} map. A missing or malformed file yields
    an EMPTY map — every label then reads out-of-vocab and the emit fails loud, rather than
    silently accepting anything (fail-closed on the vocab, like emit_observation.load_vocab).
    The basket is what the nudge counts, so the map — not a bare set — is the contract."""
    import yaml_io
    p = Path(path) if path is not None else _DEFAULT_LABELS
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml_io.YAMLError):
        return {}
    out: Dict[str, str] = {}
    for row in (data.get("labels") or []):
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = str(row.get("basket") or "trace_only")
    return out


def is_enabled(config_path=None) -> bool:
    """The master toggle. Default ON: a missing or unreadable config never silences
    the sink — the ledger is a built-in advisory, not an opt-in feature. Only an explicit
    `enabled: false` turns it into a no-op. Precedence: arg > HARNESS_AUTO_DECISION_CONFIG >
    shipped default."""
    import yaml_io
    p = config_path or os.environ.get("HARNESS_AUTO_DECISION_CONFIG") or _DEFAULT_CONFIG
    try:
        data = yaml_io.safe_load(Path(p).read_text(encoding="utf-8")) or {}
    except (OSError, yaml_io.YAMLError):
        return True
    return bool(data.get("enabled", True))


# --------------------------------------------------------------------------- actor / session
def _hook_runtime():
    hd = str(Path(__file__).resolve().parent.parent / "hooks")
    if hd not in sys.path:
        sys.path.append(hd)
    import hook_runtime
    return hook_runtime


def _actor(session: Optional[str] = None) -> str:
    """Attribution, never authentication — resolve the SAME cached actor the other telemetry
    sinks use by passing the session id (resolve_actor re-derives from env otherwise)."""
    try:
        return _hook_runtime().resolve_actor(session_id=session or _SESSION)
    except Exception:  # noqa: BLE001 — actor is best-effort; a broken chain must not crash the sink
        return "user:unknown"


def _safe_session(session: Optional[str]) -> str:
    sid = session or _SESSION or "unknown"
    try:
        return _hook_runtime().safe_session_id(sid)
    except Exception:  # noqa: BLE001
        return "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)


# --------------------------------------------------------------------------- path resolve
_MAIN_TREE_CACHE: Dict[str, Optional[Path]] = {}  # per-process memo, keyed on cwd


def _main_tree_root() -> Optional[Path]:
    """The MAIN worktree root via git-common-dir — correct EVEN from a linked worktree, where
    `CLAUDE_PROJECT_DIR` is absent in the Bash-tool env. This does not depend on project_root()
    agreeing: git-common-dir is authoritative for "which repo owns this checkout", whereas
    project_root() answers "which project is being worked on" and resolves through the data
    home. `--git-common-dir` always points at the shared `<main>/.git`, so its parent is the
    main root — a line written there survives the worktree being removed. None if not a git
    repo. Memoized per (process, cwd): the git-common-dir of a
    fixed cwd is invariant, so a process that resolves more than once (sink append + render)
    pays a single `git rev-parse` instead of one per call."""
    try:
        key = os.getcwd()
    except OSError:
        key = ""
    if key in _MAIN_TREE_CACHE:
        return _MAIN_TREE_CACHE[key]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5)
        gd = Path(out.stdout.strip())
        result = gd.parent if (out.returncode == 0 and gd.name == ".git") else None
    except (OSError, subprocess.SubprocessError):
        result = None
    _MAIN_TREE_CACHE[key] = result
    return result


def _in_linked_worktree(path) -> bool:
    """True if `path` sits inside a linked git worktree (a removable tree), regardless of
    whether that worktree nests under the main root — the outside-main check alone misses a
    worktree nested under main/.claude/worktrees/. Delegates to the shared detector
    harness_paths.worktree_host_root (DRY — one `.git`-FILE + commondir walk-up for the whole
    harness). The getattr is a defensive fallback: an older harness_paths without the detector
    yields False rather than crashing. Fail-open: any error → False."""
    try:
        import harness_paths
    except Exception:  # noqa: BLE001
        return False
    detector = getattr(harness_paths, "worktree_host_root", None)
    if detector is None:
        return False  # older harness_paths without the detector — degrade to the outside-main guard
    try:
        return detector(Path(path)) is not None
    except Exception:  # noqa: BLE001
        return False


def resolve_store(plan_dir=None, session=None) -> Path:
    """The JSONL store path to WRITE. Precedence:
      1) --plan-dir <abspath> from the caller (cook MAIN agent at the barrier) — but still
         worktree-guarded: a plan-dir OUTSIDE the main tree (a peer worktree) OR NESTED inside
         a linked worktree under main (main/.claude/worktrees/*) is REFUSED and routed to the
         main tree's plans/reports/, never written into the removable worktree.
      2) the active in_progress plan under the MAIN tree (git-common-dir) → its artifacts/.
      3) project_root()/plans (last resort, non-git).
    No active plan → plans/reports/auto-decisions.jsonl on the main tree (a single shared,
    append-only reports ledger — each record already carries its own session, so the filename
    needs none; a per-session filename would also desync the Bash-tool writer, whose session
    is unset, from the hook-env reader). The primary protection is the writer-model (a
    worktree subagent never calls the sink; main writes at the barrier); this guard is the
    backstop for a stray direct call."""
    main = _main_tree_root()

    if plan_dir:
        plan = Path(plan_dir).resolve()
        cand = plan / "artifacts" / "auto-decisions.jsonl"
        outside_main = main is not None and not _under(cand, main)
        if outside_main or _in_linked_worktree(plan):
            sys.stderr.write(
                "[auto_decision_log] plan-dir %s is inside a linked worktree or outside the "
                "main tree; routing to main plans/reports (worktree writes are lost on "
                "removal)\n" % plan_dir)
            return _reports_store(main)
        return cand

    root = main
    if root is None:
        try:
            import harness_paths
            root = harness_paths.project_root()
        except Exception:  # noqa: BLE001
            root = Path.cwd()

    active = _active_plan_dir(root)
    if active is not None:
        return Path(active) / "artifacts" / "auto-decisions.jsonl"
    return _reports_store(root)


def _under(path, base) -> bool:
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False


def _reports_store(root) -> Path:
    base = Path(root) if root is not None else Path.cwd()
    return base / "plans" / "reports" / "auto-decisions.jsonl"


def _active_plan_dir(root):
    try:
        import artifact_check
        return artifact_check.resolve_active_plan(root)
    except Exception:  # noqa: BLE001 — resolver hiccup falls back to reports, never crashes
        return None


def resolve_ledger_stores(session=None) -> List[Path]:
    """Every ledger store to READ for a count — the active plan's plus the reports fallback,
    both anchored on the SAME main tree (git-common-dir) the writer uses, so a reader in the
    hook env and a writer in the Bash-tool env agree on the path. The nudge uses this; the
    writer uses resolve_store (one path). `session` is unused (kept for signature symmetry)."""
    main = _main_tree_root()
    root = main
    if root is None:
        try:
            import harness_paths
            root = harness_paths.project_root()
        except Exception:  # noqa: BLE001
            root = Path.cwd()
    stores: List[Path] = []
    active = _active_plan_dir(root)
    if active is not None:
        stores.append(Path(active) / "artifacts" / "auto-decisions.jsonl")
    stores.append(_reports_store(root))
    return stores


# --------------------------------------------------------------------------- touched-flag
def _touched_flag_path(store) -> Path:
    """Keyed on the resolved STORE PATH, not the session. The sink runs via the Bash tool
    (no HARNESS_SESSION_ID) while the nudge runs in the hook env (a real session id), so a
    session-keyed marker never matches across the two. The store path is identical on both
    sides — that is the durable shared key."""
    key = hashlib.sha256(str(Path(store).resolve()).encode("utf-8")).hexdigest()[:16]
    tmp = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
    return tmp / ("harness-adl-touched-%s" % key)


def set_touched_flag(store) -> Path:
    """Mark "an auto-mode wrote THIS store" so the review-nudge fires only for a ledger that was
    actually written — not on an interactive session over a store nothing touched. The flag is
    ephemeral ($TMPDIR) and NOT per-session: it lives from the write until $TMPDIR is cleared
    (e.g. reboot), so any session in that window may surface the reminder once. Best-effort: a
    write failure must never break a successful append."""
    path = _touched_flag_path(store)
    try:
        path.write_text("1", encoding="utf-8")
    except OSError:
        pass
    return path


def touched_flag_set(store) -> bool:
    return _touched_flag_path(store).exists()


# --------------------------------------------------------------------------- append + fold
def emit(*, skill: str, mode: str, label: str, what: str, why: str, evidence: str,
         in_plan: bool, vocab: Set[str], store, actor: Optional[str] = None,
         ts: Optional[str] = None, rec_id: Optional[str] = None,
         session: Optional[str] = None) -> dict:
    """Validate then APPEND one decision. Raises ValueError on an out-of-vocab label, empty
    evidence, or an over-cap free-text — the caller turns that into exit 2. Never writes on a
    validation failure. `id` is a random short hex (no read-modify-write, no index collision
    when --parallel writers append concurrently)."""
    if label not in vocab:
        raise ValueError("label %r is not in the closed vocabulary (%s). Add it to "
                         "auto-decision-labels.yaml or fix the typo." % (label, sorted(vocab)))
    if not (evidence or "").strip():
        raise ValueError("evidence is required — every recorded decision must cite a "
                         "file:line / id / quote.")
    free_len = len((str(what) + str(why) + str(evidence)).encode("utf-8"))
    if free_len > PAYLOAD_CAP_BYTES:
        raise ValueError("free-text is %d bytes (> %d cap) — trim what/why/evidence."
                         % (free_len, PAYLOAD_CAP_BYTES))
    rec = {
        "type": "decision",
        "id": rec_id or uuid.uuid4().hex[:12],  # 48-bit: collision negligible; a shorter id can
              # silently overwrite a distinct decision in the fold (dict keyed on id)
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "actor": actor or _actor(session),
        "skill": str(skill),
        "mode": str(mode),
        "label": str(label),
        "in_plan": bool(in_plan),
        "reviewed": False,
        "what": str(what),
        "why": str(why),
        "evidence": str(evidence),
    }
    sess = session or _SESSION
    if sess:
        rec["session"] = sess
    p = Path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False) + "\n"  # serialize before opening
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line)
    return rec


def load_events(store) -> List[dict]:
    """Every JSONL record in the store, in order. A missing/unreadable store → [] (never
    raises): a reader over an empty ledger is a valid, common case."""
    p = Path(store)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip a torn line, never crash the reader
    return events


def fold_state(events: List[dict]) -> List[dict]:
    """Collapse append-only events into current decision state, processed IN APPEND ORDER.
    A review event overlays reviewed=True onto the decision it targets by `id`; target=="*"
    is a SNAPSHOT — it marks the decisions seen SO FAR, never a decision appended after it
    (no auto-mark-future). A review for an id not yet seen is ignored. The store is never
    mutated in place — the fold is the read model."""
    decisions: Dict[str, dict] = {}
    for e in events:
        etype = e.get("type")
        if etype == "decision" and e.get("id"):
            decisions[e["id"]] = dict(e)
        elif etype == "review":
            target = e.get("target") or e.get("id")
            if target == "*":
                for d in decisions.values():          # snapshot: only what exists now
                    d["reviewed"] = True
            elif target and target in decisions:
                decisions[target]["reviewed"] = True
    return list(decisions.values())


def append_review(target: str, *, store, actor: Optional[str] = None,
                  ts: Optional[str] = None, session: Optional[str] = None) -> dict:
    """APPEND a review event flipping `target` (a decision id, or "*" for the whole ledger)
    to reviewed. Never edits a recorded decision line — the flip is fold-overlay, not an edit
    (append-only). A target that matches no decision is a harmless dangling event fold ignores."""
    rec = {
        "type": "review",
        "target": str(target),
        "reviewed": True,
        "actor": actor or _actor(session),
        "ts": ts or datetime.now(timezone.utc).isoformat(),
    }
    sess = session or _SESSION
    if sess:
        rec["session"] = sess
    p = Path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line)
    return rec


# --------------------------------------------------------------------------- CLI
def _refresh_view(store, no_render: bool) -> None:
    """On-write incremental refresh so the view is fresh when a human opens it. Lazy import
    (breaks the log<->render cycle); a render failure is view-only and must not fail the write
    that already succeeded."""
    if no_render:
        return
    try:
        import auto_decision_render
        auto_decision_render.render(store)
    except Exception as exc:  # noqa: BLE001 — view is derived; rebuild anytime with --render
        sys.stderr.write("[auto_decision_log] view render failed (ignored): %s\n" % exc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Append one AI-autonomous decision to the ledger.")
    ap.add_argument("--skill", help="emitting skill, e.g. hs:cook (required to append a decision)")
    ap.add_argument("--mode", default="auto", help="the auto-mode that decided (auto/fix/...)")
    ap.add_argument("--label", help="closed-vocab label (required to append a decision)")
    ap.add_argument("--what", default="", help="what was decided")
    ap.add_argument("--why", default="", help="why")
    ap.add_argument("--evidence", default="", help="file:line / id / quote (REQUIRED for a decision)")
    ap.add_argument("--in-plan", action="store_true", help="the decision stayed inside the plan lane")
    ap.add_argument("--mark-reviewed", metavar="ID", default=None,
                    help="flip a decision (by id) to reviewed — appends a review event, edits nothing")
    ap.add_argument("--mark-reviewed-all", action="store_true",
                    help="flip the whole ledger to reviewed (snapshot of decisions recorded so far)")
    ap.add_argument("--plan-dir", default=None, help="absolute plan dir (caller-resolved, main tree)")
    ap.add_argument("--session", default=None, help="session id for actor + touched-flag")
    ap.add_argument("--store", default=None, help="explicit JSONL store (test seam / caller override)")
    ap.add_argument("--labels", default=None, help="vocabulary YAML (default: auto-decision-labels.yaml)")
    ap.add_argument("--config", default=None, help="policy YAML (default: auto-decision.yaml)")
    ap.add_argument("--no-render", action="store_true", help="skip the on-write view refresh (test/speed)")
    args = ap.parse_args(argv)

    if not is_enabled(args.config):
        return 0  # toggle off → no-op, no write

    store = args.store or resolve_store(plan_dir=args.plan_dir, session=args.session)

    # --- review flow: flip reviewed by appending a review event (never edits a decision) ---
    if args.mark_reviewed_all or args.mark_reviewed is not None:
        target = "*" if args.mark_reviewed_all else args.mark_reviewed
        if target != "*":
            known = {e.get("id") for e in load_events(store) if e.get("type") == "decision"}
            if target not in known:
                # advisory: warn but never block — a stale id paste is not fatal.
                sys.stderr.write("[auto_decision_log] no decision with id %r; review event "
                                 "recorded but fold ignores it\n" % target)
        try:
            append_review(target, store=store, session=args.session)
        except OSError as exc:
            sys.stderr.write("[auto_decision_log] review write failed (ignored): %s\n" % exc)
            return 0
        _refresh_view(store, args.no_render)
        return 0

    # --- decision flow ---
    if not args.skill or not args.label:
        sys.stderr.write("[auto_decision_log] --skill and --label are required to append a decision\n")
        return 2
    vocab = set(load_labels(args.labels).keys())
    try:
        emit(skill=args.skill, mode=args.mode, label=args.label, what=args.what,
             why=args.why, evidence=args.evidence, in_plan=args.in_plan,
             vocab=vocab, store=store, session=args.session)
    except ValueError as exc:
        sys.stderr.write("[auto_decision_log] REJECTED: %s\n" % exc)
        return 2
    except OSError as exc:
        # telemetry-class: a store I/O failure must fail OPEN — never crash the auto-mode's work.
        sys.stderr.write("[auto_decision_log] store write failed (ignored): %s\n" % exc)
        return 0
    set_touched_flag(store)
    _refresh_view(store, args.no_render)
    return 0


if __name__ == "__main__":
    sys.exit(main())
