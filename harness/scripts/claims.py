#!/usr/bin/env python3
"""claims.py — lease-based task claims over atomic filesystem primitives.

Lib + CLI for claiming a task with a lease (acquire | release | status |
reclaim). The FSM is DERIVED from the filesystem — no separate state file,
no read-modify-write:

    UNCLAIMED --acquire--> CLAIMED --(lease expires)--> STALE --reclaim--> ...
    CLAIMED --release--> RELEASED (tombstone in .done/)

STORE-CLASS EXCEPTION: harness/state/claims/ is a RENAME-LIFECYCLE
store — immutable JSON files moved by rename — NOT append-only JSONL like the
other machine-written stores. Race-free claiming needs O_CREAT|O_EXCL
acquire and rename-consumed reclaim; a log line cannot win a race. The audit
trail still lives in the append-only trace: every acquire/release/reclaim/
quarantine appends a trace event with actor + ts.

Empirically validated primitives (50-way / 20-way races, ext4 + tmpfs):
  * acquire  = open(O_CREAT|O_EXCL) — exactly one winner.
  * reclaim  = rename(claim, per-reclaimer-unique name) — the source dentry is
    consumed atomically, every later rename gets ENOENT.
  * delete-then-recreate reclaim is FORBIDDEN — proven split-brain (multiple
    self-declared winners); nothing in this module ever deletes a claim file,
    every lifecycle step is a rename.

Lease lives in the claim CONTENT (`expires_ts`), never in mtime: mtime is
same-uid writable and clobbered by cp/restore/sync. mtime is only the
staleness fallback when the content cannot be parsed (then a generous
FALLBACK_GRACE_S applies). `lease_s` is copied from team.yaml at create time;
staleness checks never read live config, so an in-flight config edit cannot
flip existing claims.

Claims are immutable post-create — no heartbeat; renewing = release + acquire
(new claim_id). The claim is a coordination signal between cooperating agents
of one user (attribution, not a security boundary).

Known, deliberate limits:
  * .reclaim/ tombstones are never garbage-collected — under repeated
    reclaim churn the directory grows without bound (visible, auditable;
    GC is tracked as future work).
  * NFS/SMB state dirs are UNSUPPORTED: O_EXCL/rename atomicity across
    remote mounts was not validated; keep harness/state/ on a local fs.
    No auto-detection is attempted.
  * Claims dir and its subdirs share one mount by construction, so every
    rename stays on one filesystem (no EXDEV).
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import harness_paths  # noqa: E402

# Claims are a multi-AGENT-on-one-machine primitive; the lease is a plain
# constant with an env override (personal-first: no roster config source).
DEFAULT_LEASE_S = 14400  # 4h


def _resolve_lease_s() -> int:
    try:
        return int(os.environ.get("HARNESS_CLAIM_LEASE_S", DEFAULT_LEASE_S))
    except (TypeError, ValueError):
        return DEFAULT_LEASE_S

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import hook_runtime  # noqa: E402
import trace_log  # noqa: E402

# Staleness fallback for claims whose content cannot be parsed: such a claim
# is treated as CLAIMED (safe default) until its mtime is older than this.
FALLBACK_GRACE_S = 24 * 3600

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_TASK_ID_MAX = 200


class ClaimInputError(Exception):
    """Raised before any filesystem access when an input cannot safely be
    used to build a path under the claims dir."""


def _validate_task_id(task_id) -> str:
    """task_id goes straight into a filename under harness/state/claims/ —
    enforce a strict charset BEFORE touching the filesystem."""
    if not isinstance(task_id, str) or not task_id:
        raise ClaimInputError(
            "task_id must be a non-empty string of [A-Za-z0-9._-] (got %r)"
            % (task_id,))
    if task_id in (".", "..") or not _TASK_ID_RE.match(task_id) \
            or len(task_id) > _TASK_ID_MAX:
        raise ClaimInputError(
            "invalid task_id %r — allowed: 1-%d chars of [A-Za-z0-9._-], "
            "no path separators, not '.' or '..'" % (task_id, _TASK_ID_MAX))
    return task_id


def _sanitize_for_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:80] or "unknown"


def _claims_dir() -> Path:
    return harness_paths.state_dir() / "claims"


def _claim_path(task_id: str) -> Path:
    return _claims_dir() / (task_id + ".claim")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw):
    try:
        ts = datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _read_claim(path: Path):
    """(claim dict | None, note | None). None claim = unparsable/missing
    fields — reader treats that as CLAIMED-by-someone, never as free."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None, "claim content unparsable — treated as CLAIMED; " \
                     "staleness falls back to mtime + grace"
    if not isinstance(data, dict) or _parse_ts(data.get("expires_ts")) is None:
        return None, "claim content unparsable — treated as CLAIMED; " \
                     "staleness falls back to mtime + grace"
    return data, None


def _trace(event, task_id, *, actor, note=None, status=None):
    trace_log.append_event("claims", event, actor=actor, target=task_id,
                           status=status, note=note)


# ---------------------------------------------------------------- acquire ---

def acquire(task_id, lease_s=None, actor=None) -> dict:
    """Claim `task_id` via O_CREAT|O_EXCL — exactly one winner under race.

    Returns {ok: True, state: CLAIMED, claim} or
    {ok: False, reason: "exists", existing: claim|None}.
    """
    _validate_task_id(task_id)
    if lease_s is None:
        lease_s = _resolve_lease_s()
    try:
        lease_s = int(lease_s)
    except (TypeError, ValueError):
        raise ClaimInputError(
            "lease_s must be an integer number of seconds (got %r)" % (lease_s,))
    if lease_s <= 0:
        # a non-positive lease makes expires_ts <= now -> the claim is born STALE and
        # any reclaim wins instantly. the lease resolver enforces this on the default path;
        # the direct/CLI path must too.
        raise ClaimInputError(
            "lease_s must be a positive integer of seconds (got %r)" % (lease_s,))
    actor = actor or hook_runtime.resolve_actor()

    d = _claims_dir()
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = _claim_path(task_id)

    now = _now()
    rec = {
        "task_id": task_id,
        "actor": actor,
        "ts": now.isoformat(),
        "claim_id": uuid.uuid4().hex,
        "expires_ts": (now + timedelta(seconds=int(lease_s))).isoformat(),
        "lease_s": int(lease_s),
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        existing, _note = _read_claim(path)
        return {"ok": False, "reason": "exists", "existing": existing}
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False))
    _trace("claim_acquired", task_id, actor=actor, status="CLAIMED",
           note="claim_id=%s lease_s=%d" % (rec["claim_id"], rec["lease_s"]))
    return {"ok": True, "state": "CLAIMED", "claim": rec}


# A won acquire used to also post a breadcrumb comment on the matching remote
# task. The remote task store is gone (this harness is solo/local-only), so the
# breadcrumb had no destination. Claiming itself is unaffected: it was always
# filesystem-only, and the append-only trace above is still the audit trail.


# ----------------------------------------------------------------- status ---

def status(task_id) -> dict:
    """Derive the FSM state from the filesystem — read-only, creates nothing."""
    _validate_task_id(task_id)
    path = _claim_path(task_id)
    if not path.exists():
        return {"task_id": task_id, "state": "UNCLAIMED", "claim": None}

    claim, note = _read_claim(path)
    if claim is None:
        # Unparsable content: CLAIMED by default; mtime-grace fallback only.
        try:
            age_s = _now().timestamp() - path.stat().st_mtime
        except OSError:
            return {"task_id": task_id, "state": "UNCLAIMED", "claim": None}
        state = "STALE" if age_s > FALLBACK_GRACE_S else "CLAIMED"
        return {"task_id": task_id, "state": state, "claim": None, "note": note}

    expires = _parse_ts(claim["expires_ts"])
    state = "STALE" if _now() > expires else "CLAIMED"
    return {"task_id": task_id, "state": state, "claim": claim}


# ---------------------------------------------------------------- release ---

def release(task_id, claim_id, actor=None, _after_read=None) -> dict:
    """Owner-done: verify claim_id matches, then rename the claim into
    .done/ (tombstone). Never deletes — a mismatched id is refused so an
    owner whose lease expired cannot destroy a reclaimed-and-reissued claim.

    The claim_id is re-verified immediately BEFORE the tombstone rename:
    between the first read and the rename the original lease can expire and a
    reclaim + fresh acquire can re-occupy the same path. Renaming on the
    stale first read would tombstone the NEW holder's valid claim — so we
    re-read and abort the release if the id (or holder) no longer matches.

    `_after_read` is a test-only seam to interleave a competing writer
    deterministically inside the read->re-verify window.
    """
    _validate_task_id(task_id)
    actor = actor or hook_runtime.resolve_actor()
    path = _claim_path(task_id)

    claim, _note = _read_claim(path) if path.exists() else (None, None)
    if not path.exists():
        return {"ok": False, "reason": "unclaimed"}
    if claim is None or claim.get("claim_id") != claim_id:
        return {"ok": False, "reason": "claim_id_mismatch"}

    if _after_read is not None:
        _after_read()

    # Re-verify just before the rename: a reclaim + fresh acquire in the
    # window above means the claim at `path` is now someone else's. Tombstone
    # only if the id we own still occupies the slot.
    current, _note = _read_claim(path) if path.exists() else (None, None)
    if not path.exists():
        return {"ok": False, "reason": "unclaimed"}
    if current is None or current.get("claim_id") != claim_id:
        return {"ok": False, "reason": "claim_id_mismatch"}

    done_dir = _claims_dir() / ".done"
    done_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = done_dir / ("%s.%s.json" % (task_id, claim_id))
    try:
        os.rename(path, target)
    except FileNotFoundError:
        return {"ok": False, "reason": "unclaimed"}
    _trace("claim_released", task_id, actor=actor, status="RELEASED",
           note="claim_id=%s" % claim_id)
    return {"ok": True, "state": "RELEASED", "claim": claim}


# ---------------------------------------------------------------- reclaim ---

def reclaim(task_id, lease_s=None, actor=None, reacquire=True,
            _after_read=None, _after_rename=None) -> dict:
    """Take over a STALE claim — the exact four-step rename sequence:

      1. read the claim; stale iff now > expires_ts (content, not mtime);
      2. rename it to a per-reclaimer-unique tombstone under .reclaim/
         (rename consumes the source atomically: ENOENT = lost the race);
      3. verify-after-rename: if the tombstone's claim_id differs from the
         one read in step 1, a fresh claim was stolen through the
         read→rename window — restore it to the claim path (exclusive
         hardlink, so an already-reoccupied path is never clobbered; in
         that case the stolen file is renamed *.quarantine and traced);
      4. trace the reclaim, then (by default) acquire a fresh claim.

    `_after_read` / `_after_rename` are test-only seams to interleave a
    competing writer deterministically inside the race windows.
    """
    _validate_task_id(task_id)
    actor = actor or hook_runtime.resolve_actor()
    path = _claim_path(task_id)

    # Step 1 — staleness from content.
    st = status(task_id)
    if st["state"] == "UNCLAIMED":
        return {"ok": False, "reason": "unclaimed"}
    if st["state"] != "STALE":
        return {"ok": False, "reason": "not_stale"}
    old = st["claim"]  # None when content was unparsable (mtime-grace stale)
    old_claim_id = old["claim_id"] if old else "unparsable"

    if _after_read is not None:
        _after_read()

    # Step 2 — rename to a per-reclaimer-unique target (same dir tree, same
    # mount). Losers get ENOENT and stop.
    reclaim_dir = _claims_dir() / ".reclaim"
    reclaim_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = reclaim_dir / ("%s.%s.%s.%d.json" % (
        task_id, _sanitize_for_filename(old_claim_id),
        _sanitize_for_filename(actor), os.getpid()))
    try:
        os.rename(path, target)
    except FileNotFoundError:
        return {"ok": False, "reason": "lost_race"}

    # Step 3 — verify-after-rename (rename targets a path, not the inode we
    # stat'ed: a release + fresh acquire in the window means we stole a LIVE
    # claim and must hand it back).
    moved, _note = _read_claim(target)
    moved_claim_id = moved["claim_id"] if moved else "unparsable"
    if moved_claim_id != old_claim_id:
        if _after_rename is not None:
            _after_rename()
        try:
            # Exclusive restore: link refuses an existing path, so a claim
            # that re-occupied the slot meanwhile is never overwritten.
            os.link(target, path)
        except FileExistsError:
            quarantine = Path(str(target) + ".quarantine")
            os.rename(target, quarantine)
            _trace("claim_quarantined", task_id, actor=actor,
                   note="stolen fresh claim_id=%s parked at %s; claim path "
                        "was re-occupied before restore" % (
                            moved_claim_id, quarantine.name))
            return {"ok": False, "reason": "quarantined",
                    "quarantine": str(quarantine)}
        os.rename(target, Path(str(target) + ".restored"))
        return {"ok": False, "reason": "fresh_claim_restored"}

    # Step 4 — audit, then optionally re-acquire.
    _trace("claim_reclaimed", task_id, actor=actor, status="RECLAIMED",
           note="stale claim_id=%s tombstone=%s" % (old_claim_id, target.name))
    if not reacquire:
        return {"ok": True, "state": "UNCLAIMED",
                "reclaimed_from": old_claim_id, "tombstone": str(target)}
    out = acquire(task_id, lease_s=lease_s, actor=actor)
    out["reclaimed_from"] = old_claim_id
    return out


# -------------------------------------------------------------------- CLI ---

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Lease-based task claims (file-backed, rename-lifecycle).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_acq = sub.add_parser("acquire", help="claim a task")
    p_acq.add_argument("task_id")
    p_acq.add_argument("--lease-s", type=int, default=None,
                       help="lease seconds (default: claims.lease_s from team.yaml)")

    p_rel = sub.add_parser("release", help="release an owned claim")
    p_rel.add_argument("task_id")
    p_rel.add_argument("--claim-id", required=True)

    p_st = sub.add_parser("status", help="derive claim state")
    p_st.add_argument("task_id")

    p_rec = sub.add_parser("reclaim", help="take over a stale claim")
    p_rec.add_argument("task_id")
    p_rec.add_argument("--lease-s", type=int, default=None)
    p_rec.add_argument("--no-reacquire", action="store_true",
                       help="only tombstone the stale claim, do not re-acquire")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "acquire":
            result = acquire(args.task_id, lease_s=args.lease_s)
        elif args.cmd == "release":
            result = release(args.task_id, args.claim_id)
        elif args.cmd == "status":
            result = status(args.task_id)
        else:
            result = reclaim(args.task_id, lease_s=args.lease_s,
                             reacquire=not args.no_reacquire)
    except ClaimInputError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2

    print(json.dumps(result, ensure_ascii=False))
    if args.cmd == "status":
        return 0
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
