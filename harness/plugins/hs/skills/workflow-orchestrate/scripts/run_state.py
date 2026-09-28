#!/usr/bin/env python3
"""run_state.py — resumable orchestration run-state (state.json).

A large fan-out that crashes mid-run should not restart from zero. state.json holds the last
transition per job: rerun with `--resume <run-dir>` and completed jobs are skipped while
in-flight jobs re-dispatch as a new attempt. State only earns its keep for a real fan-out
(the skill writes it above a small threshold — a two-sub spawn does not need a resume file).

Writes are atomic (write a `.tmp` sibling, then os.replace) so a crash mid-write never leaves
a half-written state.json that would wedge the resume. Pure stdlib — importable by file path
with no cross-tree dependency.

Schema:
    {"run_id": "orchestrate-<ts>",
     "jobs": {"<job-id>": {"id", "status", "attempts", "runtime", "model", "task",
                            "exitCode", "durationMs", "timedOut", "worktree"}}}
`status` is one of planned|in_progress|success|failed|blocked|timeout.
"""
import json
import os
import sys
import time
from pathlib import Path

# statuses that count as finished-and-good — a resume skips these.
_DONE = ("success",)


def _wire_harness_paths() -> bool:
    """Walk up from this file to the harness root (marked by a `hooks/` dir
    named `harness`) and prepend both its `scripts/` and `hooks/` dirs to
    sys.path so `spawn_provenance` (scripts) and `hook_runtime` (hooks)
    import cleanly. Returns False if unresolved (a layout this module
    cannot recognize) — every caller degrades gracefully on False."""
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "hooks").is_dir() and anc.name == "harness":
            for d in (anc / "scripts", anc / "hooks"):
                if str(d) not in sys.path:
                    sys.path.insert(0, str(d))
            return True
    return False


def state_dir() -> Path:
    """The harness runtime state home — machine-written run-state and the metrics corpus live
    here (gitignored), NOT under plans/reports/ (that is human-facing report scratch).

    Resolves through the canonical harness_paths.state_dir() (which honors HARNESS_STATE_DIR
    and the per-project data home under a global install). Walks up to the harness root to
    import it; degrades to $HARNESS_STATE_DIR or <harness-root>/state so a metrics/state write
    never crashes on an odd layout."""
    try:
        here = Path(__file__).resolve()
        for anc in here.parents:
            hp = anc / "scripts" / "harness_paths.py"
            if hp.is_file():
                if str(anc / "scripts") not in sys.path:
                    sys.path.insert(0, str(anc / "scripts"))
                import harness_paths  # noqa: E402
                return harness_paths.state_dir()
    except Exception:  # noqa: BLE001 — resolver is best-effort, never a crash surface
        pass
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "hooks").is_dir() and anc.name == "harness":
            return anc / "state"
    return here.parent / "state"


def run_state_path(run_id) -> str:
    """Absolute path to a run's state.json under the harness state dir:
    `<state_dir>/orchestrate/<run_id>/state.json`."""
    return str(state_dir() / "orchestrate" / str(run_id) / "state.json")


def read(state_path) -> dict:
    """Return the parsed state, or {} when the file is absent/unreadable (a fresh run)."""
    try:
        with open(state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def write(state_path, state) -> None:
    """Atomically persist `state`: write a .tmp sibling, fsync-free flush, then os.replace so a
    reader never observes a partial file."""
    parent = os.path.dirname(os.path.abspath(state_path))
    os.makedirs(parent, exist_ok=True)
    tmp = "%s.tmp" % state_path
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, state_path)


def should_dispatch(state, job_id):
    """Resume decision for one job: (dispatch: bool, attempt: int).

    - unknown job        -> (True, 1)        first attempt
    - status == success  -> (False, attempts) already done, skip
    - anything else      -> (True, attempts+1) in-flight/failed -> re-dispatch, bump attempt
    """
    jobs = state.get("jobs") if isinstance(state, dict) else None
    entry = jobs.get(job_id) if isinstance(jobs, dict) else None
    if not isinstance(entry, dict):
        return True, 1
    attempts = entry.get("attempts", 1) or 1
    if entry.get("status") in _DONE:
        return False, attempts
    return True, attempts + 1


def record_transition(state_path, job_id, status, **fields) -> dict:
    """Upsert a job's transition into state.json and persist atomically. Returns the new state.
    Read-modify-write is safe here: run-state is single-writer (one orchestrator owns one
    run-dir), unlike the append-only metrics corpus."""
    state = read(state_path)
    if not isinstance(state.get("jobs"), dict):
        state["jobs"] = {}
    entry = state["jobs"].get(job_id) or {"id": job_id, "attempts": 1}
    entry["status"] = status
    for k, v in fields.items():
        entry[k] = v
    state["jobs"][job_id] = entry
    write(state_path, state)
    return state


def write_token(run_id, strategy, session) -> str:
    """Mint the Layer-1b orchestrate spawn-budget token AT APPROVAL (never
    agent-callable at will — the forgery guard, memory
    anchor-cli-self-auth-hole: a rejected strategy must never bless a
    fan-out). Writes `<state_dir>/orchestrate/<run_id>/token.json`:
    `{run_id, mode, sub_count, groups, report_dir, session, actor, ts
    (epoch float), expires_at}` — what `spawn_provenance.window_start()` /
    `.budget()` read to resolve the Layer-1b BLOCK-form epoch and budget.

    `sub_count` is clamped to `spawn_provenance.sub_count_cap()` AT WRITE
    TIME (defense in depth — `spawn_provenance.budget()` clamps again on
    read, so a forged or stale-huge claim can never bless an unbounded
    fan-out even if one clamp is ever bypassed). Atomic write (a `.tmp`
    sibling + `os.replace`); one token per `run_id`, never mutated after —
    append-only in spirit, matching `write()`'s own atomicity. Returns the
    written path."""
    strategy = strategy if isinstance(strategy, dict) else {}
    _wire_harness_paths()
    try:
        import spawn_provenance
        cap = spawn_provenance.sub_count_cap()
        ttl = spawn_provenance.token_ttl_seconds()
    except Exception:  # noqa: BLE001 — an unresolved harness layout degrades to the SSOT defaults
        cap, ttl = 32, 1800
    sub_count = strategy.get("sub_count")
    sub_count = sub_count if isinstance(sub_count, int) and not isinstance(sub_count, bool) and sub_count > 0 else 0
    sub_count = min(sub_count, cap)
    try:
        import hook_runtime
        actor = hook_runtime.resolve_actor(session if isinstance(session, str) else None)
    except Exception:  # noqa: BLE001 — actor is attribution, never a hard dependency
        actor = "user:%s" % os.environ.get("HARNESS_USER", os.environ.get("USER", "unknown"))
    ts = time.time()
    token = {
        "run_id": str(run_id),
        "mode": strategy.get("mode"),
        "sub_count": sub_count,
        "groups": strategy.get("groups"),
        "report_dir": strategy.get("report_dir"),
        "session": session if isinstance(session, str) else "",
        "actor": actor,
        "ts": ts,
        "expires_at": ts + ttl,
    }
    path = str(state_dir() / "orchestrate" / str(run_id) / "token.json")
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp = "%s.tmp" % path
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(token, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return path


if __name__ == "__main__":
    # Tiny CLI: `run_state.py read <path>` prints the state (resume inspection).
    if len(sys.argv) >= 3 and sys.argv[1] == "read":
        json.dump(read(sys.argv[2]), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif len(sys.argv) >= 2 and sys.argv[1] == "write-token":
        # run_state.py write-token --run-id ID --mode M --sub-count N \
        #     --groups '<json>' --report-dir DIR --session SID
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--run-id", required=True)
        p.add_argument("--mode")
        p.add_argument("--sub-count", type=int, default=0)
        p.add_argument("--groups", default="[]")
        p.add_argument("--report-dir", default="")
        p.add_argument("--session", default="")
        args = p.parse_args(sys.argv[2:])
        try:
            groups = json.loads(args.groups)
        except ValueError:
            groups = []
        out = write_token(args.run_id, {
            "mode": args.mode, "sub_count": args.sub_count,
            "groups": groups, "report_dir": args.report_dir,
        }, args.session)
        sys.stdout.write(out + "\n")
