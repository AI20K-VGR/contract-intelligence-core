#!/usr/bin/env python3
"""risk_register.py — the PERSISTENT, project-wide risk register.

Distinct from the plan-scoped `risks:` frontmatter (`red-team-gate.md`, dies with
its plan): `docs/risk-register.yaml` is a human-curated SSOT that lives ACROSS
plans, so a risk left un-mitigated in one plan keeps surfacing in the next.
Anchor: docs/product/_refs/frankcode-src/planner-executor/methodology/planner/
risk-register.md — Workflow (:36-43, enumerate lens -> score P x I -> classify
response -> trigger+rollback), Scoring rubric (:70-78, 1-5 scale, severity
cutoffs). STRIPPED from the source: `trigger.metric_id` anchored a Sentry/
PostHog query (risk-register.md:59-62) — this harness is file-based, so
`trigger` stays a plain observable-condition STRING (e.g. "test suite X đỏ"),
never a SaaS query. `system_ref §15` is also dropped (no tầng-1 doc at that
address).

Three surfaces, cleanly split:

- `load_register` / `--check` — a READ-ONLY deterministic scorer (same shape as
  `plan_graph.py`: parse, derive findings, never mutate). `severity` is ALWAYS
  recomputed as probability x impact; an authored `severity` field that drifted
  from that product is ignored — this defeats scoring-drift (a stale number
  left behind after a hand-edit to probability/impact). A row is `blocking`
  when severity >= BLOCKING_SEVERITY AND its EFFECTIVE status is `open` AND it
  carries no mitigation summary.
- `add_risk` / `--add` — append-only: a new row is appended to the `risks:`
  sequence. Validation runs BEFORE any write (probability/impact in [1,5];
  lens/response/status in their enum; id/title/trigger/rollback/owner
  non-empty) — a bad row raises `RiskValidationError` and nothing is written.
- `set_status` / `--set-status` — append-only: a status change is appended as
  an EVENT `{action, risk_id, actor, ts}` to the `log:` sequence. It never
  rewrites the row's own `status` field — the CURRENT status of a risk is the
  row's authored status overridden by the most recent matching log event
  (`effective_status`), the same replay-not-rewrite shape as
  `findings_store.py`.

Storage is a single YAML file (`docs/risk-register.yaml`), so every writer here
does parse -> append-in-memory -> rewrite-whole-file. That is read-modify-write
at the FILE level, not at the RECORD level: no existing row or event is ever
mutated or dropped, only appended to. Accepted because the register is
low-volume, human-curated config (see phase design note) — if the volume of
status-change events ever needs true byte-append audit trail, that graduates
to a separate `.jsonl` sink (out of scope here).

CLI:
    risk_register.py --check [--path FILE]
    risk_register.py --add --id R-1 --title T --lens security --probability 4 \\
        --impact 5 --response mitigate --trigger "..." --rollback "..." \\
        --owner user:x --status open --residual-severity 4 \\
        [--mitigation-summary S] [--mitigation-task-ref REF] [--path FILE]
    risk_register.py --set-status --risk-id R-1 --status mitigated [--path FILE]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml_io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from register_store import atomic_write, register_lock  # noqa: E402

LENS_ENUM = frozenset({"functional", "operational", "security", "adoption"})
RESPONSE_ENUM = frozenset({"mitigate", "transfer", "accept", "avoid"})
STATUS_ENUM = frozenset({"open", "mitigated", "accepted", "resolved"})
BLOCKING_SEVERITY = 12  # risk-register.md:78 — 12-19 HIGH is the blocking band
_REQUIRED_STR_FIELDS = ("id", "title", "trigger", "rollback", "owner")


class RiskValidationError(ValueError):
    """Raised BEFORE any write — the row/event is never persisted."""


# --- paths ---------------------------------------------------------------

def _default_path() -> Path:
    """docs/risk-register.yaml at the repo root (this file lives at
    harness/scripts/risk_register.py -> parents[2] is the repo root)."""
    return Path(__file__).resolve().parents[2] / "docs" / "risk-register.yaml"


def _resolve(path) -> Path:
    return Path(path) if path is not None else _default_path()


def _lock_path(path) -> Path:
    """Sidecar lock next to the register file — serializes concurrent
    add_risk/set_status writers so a load->append->rewrite race can't drop a
    row (sibling pattern: sentinel_register._lock_path)."""
    p = _resolve(path)
    return p.parent / (".%s.lock" % p.name)


# --- actor / ts (pattern: findings_store.py:128-140) ----------------------

def _actor() -> str:
    try:
        hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
        if str(hooks_dir) not in sys.path:
            sys.path.append(str(hooks_dir))
        import hook_runtime
        return hook_runtime.resolve_actor()
    except Exception:
        return "user:unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- scoring ---------------------------------------------------------------

def compute_severity(probability: int, impact: int) -> int:
    return int(probability) * int(impact)


def has_mitigation(row: Dict[str, Any]) -> bool:
    mitigation = row.get("mitigation") or {}
    return bool(mitigation.get("summary"))


def effective_status(row: Dict[str, Any], log_events: List[Dict[str, Any]]) -> str:
    """The row's authored `status`, overridden by the most recent `log:` event
    naming this risk id (append order == chronological order — the log is
    never reordered, only appended to)."""
    risk_id = row.get("id")
    for event in reversed(log_events):
        if event.get("risk_id") == risk_id and event.get("action"):
            return event["action"]
    return row.get("status")


# --- validation --------------------------------------------------------------

def _validate_score(name: str, value: Any, errors: List[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= 5):
        errors.append("%s must be an int in [1,5], got %r" % (name, value))


def validate_row(row: Dict[str, Any]) -> None:
    """Raise RiskValidationError with every problem found (never partial-raise
    on the first one — a human fixing a hand-authored row wants the full
    list). Called before EVERY write."""
    errors: List[str] = []
    for field in _REQUIRED_STR_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append("missing required field: %s" % field)
    _validate_score("probability", row.get("probability"), errors)
    _validate_score("impact", row.get("impact"), errors)
    if row.get("lens") not in LENS_ENUM:
        errors.append("lens must be one of %s, got %r" % (sorted(LENS_ENUM), row.get("lens")))
    if row.get("response") not in RESPONSE_ENUM:
        errors.append("response must be one of %s, got %r" % (sorted(RESPONSE_ENUM), row.get("response")))
    if row.get("status") not in STATUS_ENUM:
        errors.append("status must be one of %s, got %r" % (sorted(STATUS_ENUM), row.get("status")))
    if errors:
        raise RiskValidationError("; ".join(errors))


def validate_status_value(status: str) -> None:
    if status not in STATUS_ENUM:
        raise RiskValidationError("status must be one of %s, got %r" % (sorted(STATUS_ENUM), status))


# --- load / write (whole-file, append-semantics enforced by the callers) ---

def load_register(path=None) -> Dict[str, List[Dict[str, Any]]]:
    """Parse the register. A missing file, or one that exists but is empty,
    reads as an empty register (risks: [], log: []) — never raises on a
    fresh or not-yet-seeded file. A file that exists and fails to PARSE
    (malformed YAML) is a different case entirely and must NOT read as
    empty: that would turn a corrupt human-curated register into a silent
    fail-open (`--check` reporting "no risks, all clear" on a file nobody
    could actually read). Raises RiskValidationError instead, so every
    caller (--check/--add/--set-status) routes it through the existing
    exit-2 bad-input path — distinct from exit-1 (verdict == blocking)."""
    p = _resolve(path)
    if not p.is_file():
        return {"risks": [], "log": []}
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
    except (yaml_io.YAMLError, UnicodeDecodeError) as exc:
        raise RiskValidationError(
            "%s failed to parse as YAML — repair it by hand: %s" % (p, exc)
        ) from exc
    if not isinstance(data, dict):
        data = {}
    risks = data.get("risks")
    log = data.get("log")
    # Filter non-dict elements — every reader calls row.get(...), so a stray
    # scalar/list row (hand-authored slip) must be skipped, not crash the
    # whole scan (sibling pattern: sentinel_register._load_raw).
    return {
        "risks": [r for r in risks if isinstance(r, dict)] if isinstance(risks, list) else [],
        "log": [e for e in log if isinstance(e, dict)] if isinstance(log, list) else [],
    }


def _write_register(path, data: Dict[str, List[Dict[str, Any]]]) -> None:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic (tmp + os.replace) so an interrupted write can't leave a half-
    # rewritten register on disk — a whole-file RMW is only safe if the swap
    # is atomic (sibling pattern: sentinel_register._dump -> atomic_write).
    atomic_write(
        p,
        yaml_io.safe_dump({"risks": data["risks"], "log": data["log"]},
                       sort_keys=False, allow_unicode=True),
    )


# --- --check: read-only deterministic scorer --------------------------------

def check_register(path=None) -> Dict[str, Any]:
    """Recompute severity for every row (ignore drift), derive its effective
    status via the log, and flag the blocking ones. Detection-only — this
    function never writes."""
    data = load_register(path)
    rows_out: List[Dict[str, Any]] = []
    blocking_ids: List[str] = []
    for row in data["risks"]:
        validate_row(row)
        severity = compute_severity(row["probability"], row["impact"])
        status = effective_status(row, data["log"])
        blocking = severity >= BLOCKING_SEVERITY and status == "open" and not has_mitigation(row)
        scored = dict(row)
        scored["severity"] = severity
        scored["effective_status"] = status
        scored["blocking"] = blocking
        rows_out.append(scored)
        if blocking:
            blocking_ids.append(row["id"])
    return {
        "rows": rows_out,
        "verdict": "blocking" if blocking_ids else "clean",
        "blocking_ids": blocking_ids,
    }


# --- --add / --set-status: append-only machine writers -----------------------

def add_risk(path, row: Dict[str, Any], *, actor: Optional[str] = None,
             ts: Optional[str] = None) -> Dict[str, Any]:
    """Validate, stamp actor+ts, recompute severity, append to `risks:`.
    Raises RiskValidationError (nothing written) on a bad row. Existing rows
    are copied forward untouched — never rewritten."""
    validate_row(row)
    stamped = dict(row)
    stamped["severity"] = compute_severity(row["probability"], row["impact"])
    stamped["actor"] = actor or _actor()
    stamped["ts"] = ts or _now_iso()
    # Lock the load->append->rewrite so a concurrent writer can't clobber a row,
    # and reject a duplicate id inside the lock (sibling: sentinel_register
    # refuses a repeat incident-id on an append-only register).
    with register_lock(_lock_path(path)):
        data = load_register(path)
        if any(str(r.get("id")) == str(stamped["id"]) for r in data["risks"]):
            raise RiskValidationError(
                "duplicate risk id %r — the register is append-only; use "
                "--set-status to change an existing row" % stamped["id"]
            )
        data["risks"] = list(data["risks"]) + [stamped]
        _write_register(path, data)
    return stamped


def set_status(path, risk_id: str, action: str, *, actor: Optional[str] = None,
                ts: Optional[str] = None) -> Dict[str, Any]:
    """Append one event to `log:` — never rewrites the risk row or a prior
    event. Raises RiskValidationError (nothing written) for an unknown
    status value or an unknown risk id."""
    validate_status_value(action)
    event = {
        "action": action,
        "risk_id": risk_id,
        "actor": actor or _actor(),
        "ts": ts or _now_iso(),
    }
    with register_lock(_lock_path(path)):
        data = load_register(path)
        known_ids = {r.get("id") for r in data["risks"]}
        if risk_id not in known_ids:
            raise RiskValidationError("no risk with id %r in register" % risk_id)
        data["log"] = list(data["log"]) + [event]
        _write_register(path, data)
    return event


# --- CLI ---------------------------------------------------------------------

def _print_check(result: Dict[str, Any]) -> None:
    print(json.dumps({
        "tool": "risk_register",
        "action": "check",
        "verdict": result["verdict"],
        "blocking_ids": result["blocking_ids"],
        "rows": [
            {"id": r["id"], "title": r.get("title"), "severity": r["severity"],
             "effective_status": r["effective_status"], "blocking": r["blocking"]}
            for r in result["rows"]
        ],
    }, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Persistent, project-wide risk register.")
    ap.add_argument("--path", default=None, help="register file (default: docs/risk-register.yaml)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="read-only scorer; exit!=0 if any row blocks")
    mode.add_argument("--add", action="store_true", help="append a new risk row")
    mode.add_argument("--set-status", action="store_true", dest="set_status_mode",
                       help="append a status-change event for --risk-id")

    ap.add_argument("--id", default=None, help="risk id (--add)")
    ap.add_argument("--title", default=None, help="risk title (--add)")
    ap.add_argument("--lens", default=None, choices=sorted(LENS_ENUM), help="--add")
    ap.add_argument("--probability", type=int, default=None, help="1-5 (--add)")
    ap.add_argument("--impact", type=int, default=None, help="1-5 (--add)")
    ap.add_argument("--response", default=None, choices=sorted(RESPONSE_ENUM), help="--add")
    ap.add_argument("--mitigation-summary", default=None, help="--add")
    ap.add_argument("--mitigation-task-ref", default=None, help="--add")
    ap.add_argument("--trigger", default=None, help="observable-condition string, never a SaaS query (--add)")
    ap.add_argument("--rollback", default=None, help="--add")
    ap.add_argument("--owner", default=None, help="--add")
    ap.add_argument("--status", default=None,
                     help="row status (--add) or new status (--set-status)")
    ap.add_argument("--residual-severity", type=int, default=None, help="--add")
    ap.add_argument("--risk-id", default=None, help="target risk id (--set-status)")
    return ap


def main(argv=None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)

    if args.check:
        try:
            result = check_register(args.path)
        except RiskValidationError as exc:
            print("risk_register: invalid row in register: %s" % exc, file=sys.stderr)
            return 2
        _print_check(result)
        return 1 if result["verdict"] == "blocking" else 0

    if args.add:
        mitigation = {}
        if args.mitigation_summary:
            mitigation["summary"] = args.mitigation_summary
        if args.mitigation_task_ref:
            mitigation["task_ref"] = args.mitigation_task_ref
        row = {
            "id": args.id,
            "title": args.title,
            "lens": args.lens,
            "probability": args.probability,
            "impact": args.impact,
            "response": args.response,
            "mitigation": mitigation,
            "trigger": args.trigger,
            "rollback": args.rollback,
            "owner": args.owner,
            "status": args.status,
            "residual_severity": args.residual_severity,
        }
        try:
            stamped = add_risk(args.path, row)
        except RiskValidationError as exc:
            print("risk_register: %s" % exc, file=sys.stderr)
            return 2
        print(json.dumps({"tool": "risk_register", "action": "add", "id": stamped["id"]},
                         ensure_ascii=False, indent=2))
        return 0

    if args.set_status_mode:
        if not args.risk_id or not args.status:
            ap.error("--set-status requires --risk-id and --status")
        try:
            event = set_status(args.path, args.risk_id, args.status)
        except RiskValidationError as exc:
            print("risk_register: %s" % exc, file=sys.stderr)
            return 2
        print(json.dumps({"tool": "risk_register", "action": "set-status", "event": event},
                         ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
