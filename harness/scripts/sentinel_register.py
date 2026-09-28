#!/usr/bin/env python3
"""sentinel_register — the Regression Sentinel Register: one binding per past
production incident (or critical user journey) that has earned a test which
must never silently regress.

Institutional memory encoded as a machine-readable index. Every P0/P1 incident
that reaches a post-mortem is expected to bind a reproducing test here; the
binding survives forever — retiring a sentinel is `archive`, never `delete`.
See `harness/rules/regression-sentinel.md` for the discipline this register
backs (when a sentinel is mandatory, flake-as-defect, quarterly audit).

Script-vs-LLM split: this script owns the deterministic structural work —
validate the required header fields, refuse a duplicate incident-id, append
without overwriting, flip status on archive, list + filter. The caller (a
post-mortem, `hs:triage`, `hs:fix`) owns the human prose (symptom, root
cause, detection, user impact) passed in on the CLI.

Storage: `harness/data/regression-sentinel.yaml` is the SSOT — a YAML
mapping `{"sentinels": [...]}`, one record per binding. This is a
human-read/human-audited index (like `docs/glossary.yaml`), not a hot
telemetry sink, so it stays whole-file read-modify-write instead of an
append-only JSONL stream. Concurrent `add`/`archive` calls serialize on a
register lock (mirrors `decision_register.py`'s register-lock pattern) so
two processes on one machine cannot drop each other's records.

Record schema:
    incident_id: the key (unique). Required.
    symptom:     one-line observed behavior. Required.
    root_cause:  one-line root cause. Required.
    detection:   how the incident was detected (metric/alert/report). Required.
    user_impact: one-line user-facing impact. Required.
    test_path:   the sentinel test file/path that reproduces it. Required.
    status:      "active" | "archived". Machine-set; "active" on add.
    actor, ts:   machine-written (resolve_actor + UTC isoformat).

Never-delete invariant: there is no `delete` verb, by design — retiring a
sentinel is `archive` (flip status, keep the record). Wording: `actor` is
attribution, never authentication.

CLI:
    sentinel_register.py --root <dir> --add --incident-id ID \\
        --symptom S --root-cause R --detection D --user-impact U \\
        --test-path P
    sentinel_register.py --root <dir> --list [--status active|archived|all]
    sentinel_register.py --root <dir> --archive --incident-id ID
"""

import argparse
import contextlib
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml_io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from register_store import atomic_write, register_lock  # noqa: E402

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import hook_runtime  # noqa: E402

# Windows consoles may default to a legacy codepage; UTF-8 JSON output must
# not crash there. reconfigure exists on 3.7+; guard for exotic stdouts.
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")

# The caller-supplied header fields every binding must carry (R1/R3 of the
# owning phase). `status`/`actor`/`ts` are machine-written, not caller input.
REQUIRED_FIELDS = ("incident_id", "symptom", "root_cause", "detection",
                    "user_impact", "test_path")
_REC_FIELDS = REQUIRED_FIELDS + ("status", "actor", "ts")
_STATUSES = ("active", "archived")


class SentinelError(ValueError):
    """Raised on a missing-field / duplicate-id / unknown-id violation
    (surfaced as a JSON finding + non-zero exit by the CLI; raised directly
    for library callers)."""


def _yaml_path(root) -> Path:
    return Path(root) / "harness" / "data" / "regression-sentinel.yaml"


def _lock_path(root) -> Path:
    return Path(root) / "harness" / "data" / ".regression_sentinel.lock"


def _load_raw(root) -> List[Dict[str, Any]]:
    """Every record from the `sentinels: [...]` SSOT. A missing/corrupt file,
    or a record missing its incident_id key, is skipped fail-soft — one bad
    row never sinks a read."""
    try:
        data = yaml_io.safe_load(_yaml_path(root).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, yaml_io.YAMLError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    sentinels = data.get("sentinels")
    if not isinstance(sentinels, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in sentinels:
        if isinstance(raw, dict) and str(raw.get("incident_id", "")).strip():
            out.append(dict(raw))
    return out


def _dump(root, records: List[Dict[str, Any]]) -> Path:
    """Write the SSOT atomically. Canonical field order per record; an absent
    optional key defaults to ""."""
    path = _yaml_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sentinels": [
        {k: r.get(k, "") for k in _REC_FIELDS} for r in records
    ]}
    text = yaml_io.safe_dump(payload, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=4096)
    atomic_write(path, text)
    return path


def list_sentinels(root, status: str = "active") -> List[Dict[str, Any]]:
    """Records filtered by status ('active' | 'archived' | 'all'), sorted
    deterministically by incident_id."""
    if status not in _STATUSES + ("all",):
        raise SentinelError(
            "unknown status filter %r — expected active|archived|all" % status)
    records = _load_raw(root)
    if status != "all":
        records = [r for r in records if r.get("status") == status]
    # str-normalize the sort key: a mix of int and str incident_ids (a
    # hand-authored `incident_id: 5` alongside CLI-written str ids) would raise
    # TypeError under Python 3's cross-type comparison and sink the whole --list.
    return sorted(records, key=lambda r: str(r.get("incident_id")))


def add_sentinel(root, incident_id, symptom, root_cause, detection,
                  user_impact, test_path) -> Path:
    """Append one sentinel binding. Refuses a missing required field or a
    duplicate incident_id — the register is append-only, so a repeat
    incident-id must archive the prior binding rather than shadow it. Runs
    inside the register lock so two concurrent `add` calls cannot drop each
    other's records (mirrors `decision_register.py`'s register-lock)."""
    values = {
        "incident_id": incident_id, "symptom": symptom,
        "root_cause": root_cause, "detection": detection,
        "user_impact": user_impact, "test_path": test_path,
    }
    for field in REQUIRED_FIELDS:
        if not str(values.get(field, "")).strip():
            raise SentinelError(
                "sentinel record missing required field %r" % field)
    with register_lock(_lock_path(root)):
        records = _load_raw(root)
        # str-normalize the id compare: a hand-authored YAML may carry
        # `incident_id: 5` (int) while the CLI always passes a str, and `5 ==
        # "5"` is False — an un-normalized compare silently bypasses the
        # append-only dup guard.
        if any(str(r.get("incident_id")) == str(incident_id) for r in records):
            raise SentinelError(
                "duplicate incident-id %r — the register is append-only; "
                "archive the prior sentinel instead of re-adding it"
                % incident_id)
        actor = hook_runtime.resolve_actor()
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        records.append({
            "incident_id": str(incident_id).strip(),
            "symptom": str(symptom).strip(),
            "root_cause": str(root_cause).strip(),
            "detection": str(detection).strip(),
            "user_impact": str(user_impact).strip(),
            "test_path": str(test_path).strip(),
            "status": "active",
            "actor": actor,
            "ts": ts,
        })
        return _dump(root, records)


def archive_sentinel(root, incident_id) -> Path:
    """Retire a sentinel: flip status active -> archived, KEEP the record.
    Never deletes — the archived binding stays in the register forever, the
    never-delete invariant this register exists to enforce. Raises
    SentinelError when the incident_id is not found (no record vanishes
    silently, none gets archived by accident)."""
    with register_lock(_lock_path(root)):
        records = _load_raw(root)
        hit = False
        for r in records:
            if str(r.get("incident_id")) == str(incident_id):
                r["status"] = "archived"
                hit = True
                break
        if not hit:
            raise SentinelError(
                "no sentinel with incident-id %r — cannot archive a record "
                "that does not exist" % incident_id)
        return _dump(root, records)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--add", action="store_true",
                      help="append a sentinel binding")
    mode.add_argument("--list", action="store_true",
                      help="print sentinel bindings as JSON")
    mode.add_argument("--archive", action="store_true",
                      help="retire a sentinel (flip status, keep the record)")
    # deliberately NO --delete: never-delete invariant is enforced by absence,
    # not by rejecting a flag at runtime — see the module docstring.
    ap.add_argument("--incident-id")
    ap.add_argument("--symptom")
    ap.add_argument("--root-cause")
    ap.add_argument("--detection")
    ap.add_argument("--user-impact")
    ap.add_argument("--test-path")
    ap.add_argument("--status", default="active",
                    choices=["active", "archived", "all"])
    args = ap.parse_args()

    root = Path(args.root).resolve()
    try:
        if args.list:
            print(json.dumps(
                {"sentinels": list_sentinels(root, status=args.status)},
                indent=2, ensure_ascii=False))
            return 0
        if args.archive:
            if not args.incident_id:
                raise SentinelError("--archive needs --incident-id")
            path = archive_sentinel(root, args.incident_id)
            print(json.dumps(
                {"incident_id": args.incident_id, "archived": True,
                 "path": str(path)}, ensure_ascii=False))
            return 0
        # --add
        path = add_sentinel(
            root,
            incident_id=args.incident_id or "",
            symptom=args.symptom or "",
            root_cause=args.root_cause or "",
            detection=args.detection or "",
            user_impact=args.user_impact or "",
            test_path=args.test_path or "",
        )
        print(json.dumps(
            {"incident_id": args.incident_id, "written": True,
             "path": str(path)}, ensure_ascii=False))
        return 0
    except SentinelError as exc:
        # Rejection contract for THIS register (deliberately non-zero, unlike
        # the exit-0-JSON-finding convention of decision_register/glossary_
        # register): a bad add/archive must be actionable AND fail loud enough
        # that a caller checking $? catches it without parsing stdout.
        print(json.dumps({"error": "invalid_input", "message": str(exc),
                          "written": False}, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001 — surface as finding, never traceback
        print(json.dumps({"error": "invalid_input", "message": str(exc),
                          "written": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
