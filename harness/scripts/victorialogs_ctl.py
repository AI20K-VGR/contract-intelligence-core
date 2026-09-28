#!/usr/bin/env python3
"""victorialogs_ctl.py — OPT-IN, default-OFF controller for a VictoriaLogs sink.

VictoriaLogs (one Go binary) is an OPTIONAL place to ship the harness's diag/trace/
timing JSONL for LogsQL querying. It is off by default and the harness is fully
self-contained without it: verify_install never requires it, and NO hook imports this
module (it never touches the hot path). This controller starts/stops/reports the binary
(bare process, pidfile-tracked) and pushes JSONL to /insert/jsonline.

Never on the hot path; a controller error reports and exits non-zero — it never raises
a traceback at a user, and it never blocks a hook.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

DEFAULT_PORT = 9428
_PIDFILE = "victorialogs.pid"


def _state_dir() -> Path:
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent / "state"


def _home() -> Path:
    return _state_dir() / "victorialogs"


def _pidfile() -> Path:
    return _home() / _PIDFILE


def _binary() -> "str | None":
    """The VictoriaLogs binary: VICTORIALOGS_BIN, else `victoria-logs` on PATH."""
    env = os.environ.get("VICTORIALOGS_BIN")
    if env:
        return env
    return shutil.which("victoria-logs")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status() -> str:
    """'running' if the tracked pid is alive, else 'off'. Never raises."""
    try:
        pf = _pidfile()
        if not pf.is_file():
            return "off"
        pid = int(pf.read_text(encoding="utf-8").strip() or 0)
        return "running" if pid and _pid_alive(pid) else "off"
    except (OSError, ValueError):
        return "off"


def start(port: int = DEFAULT_PORT) -> int:
    """Spawn the binary (bare process) + record its pid. Returns 0 on success, non-zero
    with an actionable message (no traceback) when the binary is absent."""
    if status() == "running":
        print("victorialogs: already running")
        return 0
    binary = _binary()
    if not binary or not Path(binary).exists():
        print("victorialogs: binary not found. Install VictoriaLogs and set "
              "VICTORIALOGS_BIN (or put `victoria-logs` on PATH). See "
              "docs/harness/victorialogs-optin.md.", file=sys.stderr)
        return 1
    try:
        home = _home()
        home.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            [binary, "-storageDataPath", str(home / "data"),
             "-httpListenAddr", ":%d" % port],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        _pidfile().write_text(str(proc.pid), encoding="utf-8")
        print("victorialogs: started (pid %d, port %d)" % (proc.pid, port))
        return 0
    except OSError as e:
        print("victorialogs: could not start (%s)" % e, file=sys.stderr)
        return 1


def stop() -> int:
    """Terminate the tracked process + clear the pidfile. Idempotent."""
    try:
        pf = _pidfile()
        if pf.is_file():
            pid = int(pf.read_text(encoding="utf-8").strip() or 0)
            if pid and _pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            pf.unlink(missing_ok=True)
        print("victorialogs: stopped")
        return 0
    except (OSError, ValueError) as e:
        print("victorialogs: stop error (%s)" % e, file=sys.stderr)
        return 1


def push(records, port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> int:
    """POST records as newline-delimited JSON to /insert/jsonline. Returns 0 on a 2xx,
    non-zero otherwise. Never raises — a push failure is reported, the caller continues."""
    try:
        import httpx  # deferred: the other three subcommands never touch the network

        body = ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8")
        url = "http://%s:%d/insert/jsonline" % (host, port)
        resp = httpx.post(url, content=body, timeout=5,
                          headers={"Content-type": "application/stream+json"})
        return 0 if 200 <= resp.status_code < 300 else 1
    except Exception as e:  # noqa: BLE001 — an opt-in push must never crash the caller
        print("victorialogs: push failed (%s)" % e, file=sys.stderr)
        return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="opt-in VictoriaLogs controller (default OFF)")
    ap.add_argument("cmd", choices=["status", "start", "stop", "push"])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--file", default=None, help="JSONL file to push (push cmd)")
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(status())
        return 0
    if args.cmd == "start":
        return start(args.port)
    if args.cmd == "stop":
        return stop()
    if args.cmd == "push":
        recs = []
        if args.file and Path(args.file).is_file():
            for line in Path(args.file).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except ValueError:
                        continue
        return push(recs, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
