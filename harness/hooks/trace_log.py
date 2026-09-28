#!/usr/bin/env python3
"""trace_log.py — append-only AUDIT trace (telemetry-class lib).

One JSONL line per event into state/trace/trace-YYYYMMDD.jsonl. This is the
audit ledger: gate decisions, session starts, approvals, DEC writes.
It NEVER rotates or truncates — usage counters live in telemetry_paths and
rotate there; audit history must survive intact.

Schema (learned from CK hook-logger shape; written new):
  ts, actor, session, hook, event, tool, target, status, exit, dur_ms, note,
  payload_hash (sha256 12-hex of tool_input when given — payload itself is
  NOT stored: hash links the trace line to the op without leaking content),
  chain_hash (sha256 64-hex linking record-to-record within the daily file).

Fail-open: tracing must never break the operation being traced.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"

# The date whose rollover was already checked this process. The rollover scan
# (glob of the trace dir) only matters when the day changes, so caching the
# last-checked date collapses the steady-state cost from one glob per write to
# zero. Reset per process; a date change invalidates it and re-arms the scan.
_ROLLOVER_CHECKED_DATE = None


def _trace_dir() -> Path:
    return hook_runtime._state_dir() / "trace"


def _legacy_trace_files(d: Path) -> "list[Path]":
    """Legacy daily files only: `trace-YYYYMMDD.jsonl` (the middle is exactly 8
    digits). Excludes per-session shards `trace-YYYYMMDD-<disc>.jsonl` so the
    rollover/checkpoint machinery never misparses a shard name as a date."""
    out = []
    for p in d.glob("trace-*.jsonl"):
        mid = p.name[len("trace-"):-len(".jsonl")]
        if len(mid) == 8 and mid.isdigit():
            out.append(p)
    return out


def _payload_hash(tool_input) -> "str | None":
    """sha256 (first 12 hex) of the tool_input, or None when it is not
    JSON-serializable. Returning None — instead of letting json.dumps raise —
    is what lets the caller drop ONLY this field and still write the audit
    record; a hashing failure must never erase the event itself."""
    try:
        blob = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _chain_hash(prev: "str | None", record: dict) -> str:
    """Compute chain_hash = sha256((prev or '') + canonical(record_without_chain_hash)).

    Canonical form: json.dumps with sort_keys=True, compact separators (',',':'),
    ensure_ascii=False. The 'chain_hash' key is excluded from the input so the
    hash is self-referential-free.

    Always returns a 64-hex string. Never raises (caller guards with try/except).
    """
    rec_no_chain = {k: v for k, v in record.items() if k != "chain_hash"}
    canonical = json.dumps(
        rec_no_chain, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(
        ((prev or "") + canonical).encode("utf-8")
    ).hexdigest()


def _read_last_chain_hash(path: Path) -> "str | None":
    """Read the chain_hash field from the last non-empty line of a JSONL file.

    Returns None if the file does not exist, is empty, the last line is not
    valid JSON, or the last record has no chain_hash. None signals "genesis"
    (no prev) — the chain starts fresh from this record. Never raises.
    """
    try:
        if not path.is_file():
            return None
        size = path.stat().st_size
        if size == 0:
            return None
        with open(path, "rb") as fh:
            seek_back = min(4096, size)
            fh.seek(-seek_back, 2)
            tail = fh.read()
        lines = tail.decode("utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line:
                rec = json.loads(line)
                return rec.get("chain_hash") or None
        return None
    except Exception:
        return None


def _checkpoint_path(trace_dir: Path, date_str: str) -> Path:
    return trace_dir / ("trace-checkpoint-%s.json" % date_str)


def _read_checkpoint(trace_dir: Path, date_str: str) -> "dict | None":
    """Read a checkpoint file for a given date. Returns None on missing/error."""
    try:
        p = _checkpoint_path(trace_dir, date_str)
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _finalize_checkpoint(trace_dir: Path, date_str: str, trace_file: Path,
                         chain_cutover_ts: "str | None" = None) -> None:
    """Write a checkpoint for a completed day file. Fail-open."""
    try:
        final_hash = _read_last_chain_hash(trace_file) or ""
        count = 0
        if trace_file.is_file():
            count = sum(1 for l in trace_file.read_text(encoding="utf-8").splitlines() if l.strip())
        cp = {"date": date_str, "final_hash": final_hash, "record_count": count}
        if chain_cutover_ts is not None:
            cp["chain_cutover_ts"] = chain_cutover_ts
        p = _checkpoint_path(trace_dir, date_str)
        p.write_text(json.dumps(cp, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # checkpoint write failure is fail-open


def _read_chain_cutover_ts(trace_dir: Path) -> "str | None":
    """Read chain_cutover_ts from the earliest checkpoint that has it."""
    try:
        for cp_file in sorted(trace_dir.glob("trace-checkpoint-*.json")):
            try:
                cp = json.loads(cp_file.read_text(encoding="utf-8"))
                if "chain_cutover_ts" in cp:
                    return cp["chain_cutover_ts"]
            except Exception:
                continue
    except Exception:
        pass
    return None


def append_event(hook, event, *, actor=None, session=None, tool=None,
                 target=None, status=None, exit_code=None, dur_ms=None,
                 note=None, tool_input=None) -> None:
    """Append one audit event. Every record carries actor + ts.
    Swallows all errors — fail-open by class."""
    try:
        # One instant for both ts and the daily filename — two separate now()
        # calls can straddle UTC midnight and file a record under a date that
        # disagrees with its own ts.
        now = datetime.now(timezone.utc)
        rec = {
            "ts": now.isoformat(),
            "actor": actor if actor is not None else hook_runtime.resolve_actor(
                session_id=session),
            "session": session,
            "hook": hook,
            "event": event,
        }
        if tool is not None:
            rec["tool"] = tool
        if target is not None:
            rec["target"] = target
        if status is not None:
            rec["status"] = status
        if exit_code is not None:
            rec["exit"] = exit_code
        if dur_ms is not None:
            rec["dur_ms"] = dur_ms
        if note is not None:
            rec["note"] = note
        if tool_input is not None:
            _h = _payload_hash(tool_input)
            if _h is not None:
                rec["payload_hash"] = _h

        d = _trace_dir()
        d.mkdir(parents=True, exist_ok=True)
        today_str = now.strftime("%Y%m%d")
        # Per-session shard (P2): a real session writes trace-YYYYMMDD-<disc>.jsonl,
        # an INDEPENDENT chain rooted at its own genesis. The rollover/checkpoint
        # machinery below is for the shared legacy file ONLY — a shard never rolls
        # over into a cross-day checkpoint (its prev is just its own last line).
        # No session -> the legacy trace-YYYYMMDD.jsonl, byte-identical to before.
        disc = hook_runtime.shard_discriminator(session)
        if disc is not None:
            fname = "trace-%s-%s.jsonl" % (today_str, disc)
        else:
            fname = "trace-%s.jsonl" % today_str
        fpath = d / fname

        prev_from_checkpoint = None
        if disc is None:
            # Checkpoint-on-rollover: detect if the date changed since the last
            # record. Look for an existing legacy trace file for a different date,
            # and if found, finalize a checkpoint for that day. Best-effort /
            # fail-open. The scan runs at most once per (process, date): once
            # today's date is confirmed there is nothing to finalize until the day
            # rolls over, so the per-process cache skips the glob on every
            # subsequent same-day write. Shards are excluded (they carry a `-`).
            global _ROLLOVER_CHECKED_DATE
            if _ROLLOVER_CHECKED_DATE != today_str:
                try:
                    existing = sorted(_legacy_trace_files(d))
                    if existing:
                        last_file = existing[-1]
                        last_date = last_file.name[len("trace-"):-len(".jsonl")]
                        if last_date != today_str and last_file != fpath:
                            # Day rolled over — finalize checkpoint for the old day
                            cutover_ts = _read_chain_cutover_ts(d)
                            if cutover_ts is None:
                                # First checkpoint: record now as the cutover ts
                                cutover_ts = now.isoformat()
                            _finalize_checkpoint(d, last_date, last_file, cutover_ts)
                except Exception:
                    pass  # rollover detection failure is fail-open
                _ROLLOVER_CHECKED_DATE = today_str

            # Determine prev chain_hash: from checkpoint if file is new for today
            # and a checkpoint exists for the previous day
            try:
                if not fpath.exists():
                    # New day file — look for checkpoint from the previous file
                    existing = [f for f in sorted(_legacy_trace_files(d)) if f != fpath]
                    if existing:
                        prev_date = existing[-1].name[len("trace-"):-len(".jsonl")]
                        cp = _read_checkpoint(d, prev_date)
                        if cp and cp.get("final_hash"):
                            prev_from_checkpoint = cp["final_hash"]
            except Exception:
                pass

        # Best-effort flock: read last chain_hash + compute + append under lock
        _locked = False
        _fh = None
        try:
            import fcntl
            _fh = open(fpath, "a", encoding="utf-8")
            fcntl.flock(_fh, fcntl.LOCK_EX)
            _locked = True
        except Exception:
            pass  # lock unavailable — continue without lock

        try:
            if prev_from_checkpoint is not None:
                prev = prev_from_checkpoint
            else:
                prev = _read_last_chain_hash(fpath)
            rec["chain_hash"] = _chain_hash(prev, rec)
        except Exception:
            pass  # chain computation failed — write record without chain_hash

        try:
            if _fh is not None and _locked:
                _fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                _fh.flush()
            else:
                with open(fpath, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        finally:
            if _fh is not None:
                try:
                    if _locked:
                        # fcntl is already bound from the lock-acquire above
                        # (reached only when _locked is True, i.e. import succeeded)
                        fcntl.flock(_fh, fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    _fh.close()
                except Exception:
                    pass

    except Exception as e:  # noqa: BLE001 — tracing never breaks the traced op
        hook_runtime.log_hook_error("trace_log", e)
