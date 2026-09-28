#!/usr/bin/env python3
"""sandbox_run.py — run an LLM-generated code-fill inside a layered jail
against a card's case matrix + a mandatory edge set, emit a JSON evidence
artifact for the human R9 gate (L3 lock).

This is [CODE, deterministic]: which cases run and what they expect come
solely from the approved card (`--config`); this script makes no judgment
calls about the fill's correctness — it runs it and reports.

CLI
---
    python3 sandbox_run.py --fill <fill.py> --entry <func> \
        --config <eval_config.json> [--case-timeout 10] \
        --evidence-out <path.json> [--extra-file name=path ...]

Exit codes
----------
    0 -- every case (matrix + edge) PASSed.
    1 -- at least one case FAILed/CRASHed/TIMEDOUT (evidence is still written
         so the human gate can read it and decide).
    2 -- input error: --fill/--config missing, unparseable, or malformed
         (including a fill that fails to even parse as Python, and a card
         whose case_matrix[i].expect contains NaN — rejected at load time,
         never scored).
    3 -- denylist refuse (the static pre-execute scan found something); the
         fill was NEVER executed.
    4 -- containment_error: the OS-jail infrastructure itself is broken (a
         `bwrap` launch failed, or the seam demanded bwrap and it is
         missing) — a whole-run infra failure, distinct from a fill that ran
         and crashed. No case ran in this state.

The layered jail (order is load-bearing)
-----------------------------------------
0.  OS containment — seam `HARNESS_R9_CONTAINMENT` = bwrap|fallback|
    auto (default auto). `bwrap` wraps each case subprocess with
    `bwrap --ro-bind ... --bind <sandbox> <sandbox> --chdir <sandbox>
    --unshare-all --unshare-net --die-with-parent --new-session`. This is
    the ONLY layer that is a real OS jail; everything else here is a
    best-effort python-level pre-filter. `fallback` forces the python-filter
    path with a loud stdout warning + `containment: "python-filter-fallback"`
    in the evidence. `bwrap` forced-but-unavailable is a HARD FAIL (exit 4),
    never a silent downgrade to fallback — a CI job asserting "bwrap mode"
    must not pass by secretly skipping the jail.
1.  Denylist pre-execute (`sandbox_denylist.scan_source`) — any finding
    refuses (exit 3) before the fill ever runs.
2.  Sandbox outside the host (`tempfile.mkdtemp(prefix="eval-sandbox-")`) —
    create → run → collect → `shutil.rmtree` in `finally`, plus an
    orphan-reaper that kills any still-alive launched process before the
    rmtree.
3.  Env scrub — an explicit `env=` dict (never inherited `os.environ`),
    branched by `os.name` (a POSIX-only dict cannot launch python.exe or
    taskkill.exe on Windows).
4.  No-network python preamble — the driver patches `socket.socket`,
    `socket.getaddrinfo/create_connection/socketpair/fromfd`, and
    `_socket.socket` to a refuser BEFORE importing the fill. Best-effort:
    layer 0's `--unshare-net` is the real barrier when bwrap is active.
5.  Per-case timeout + whole-tree kill, cross-platform — POSIX:
    `Popen(start_new_session=True)` → `os.killpg(os.getpgid(pid), SIGKILL)`;
    Windows: `Popen(creationflags=CREATE_NEW_PROCESS_GROUP)` →
    `taskkill /T /F /PID <pid>` FIRST (while the tree is still rooted), then
    `p.kill()` only as a safety net (killpg/getpgid/SIGKILL do not exist on
    Windows).

Status scoring — PARENT compares, never the child
--------------------------------------------------
The child driver writes `json.dumps({"got": ...})` to a FILE inside the
`--bind`-ed sandbox (`emit-<case>.json`) — never a pipe/fd, because a
fd/pipe is not guaranteed to survive the bwrap namespace boundary, and a
silent empty-read-as-pass failure would only ever show up in bwrap mode
(fallback has no namespace, so it would stay green and hide the bug). The
PARENT (this script) reads that file from the HOST path AFTER the child
process exits and does the compare itself; it never imports or executes the
fill. Two mitigations close the obvious exploits:

  1. the driver binds its own references to the REAL `json.dumps`/
     `json.loads` and resolves the emit path BEFORE importing the fill, so a
     fill that reassigns `json.dumps` at import time cannot change what the
     driver actually writes;
  2. the child receives ONLY the per-case `input` value (written to a file
     already inside the sandbox) — never `expect`, and the card/config file
     is never copied or bound into the sandbox, so a fill cannot read the
     expected answer and echo it back for a forged PASS.

Honesty note: this closes the `__eq__`/`__repr__` forgery exploit (a fill
returning an object whose `__eq__` always returns True cannot fool the
comparator, because only the JSON-decoded *primitive* value is ever
compared — no python object identity or method survives the round trip). A
genuinely hostile fill could still forge its own serializer inside its own
process if it tried hard enough; the threat model here is Claude-generated
fill code, not a malicious adversary, and the final gate is a human reading
this evidence.

Comparator table — ONE canonical comparator, not
`json.dumps(a) == json.dumps(b)` (that string-compare and "100 == 100.0"
are mutually exclusive; only one rule is kept):

    | expect        | got           | result  | why                          |
    |---------------|---------------|---------|-------------------------------|
    | 100 (int)     | 100.0 (float) | EQUAL   | mathematically equal          |
    | 100 (int)     | "100" (str)   | NOT eq  | a string never equals a number|
    | -0.0          | 0.0           | EQUAL   | IEEE -0.0 == 0.0              |
    | NaN in expect | (any)         | rejected at card-load — never scored  |
    | (any)         | NaN (got)     | NOT eq  | a NaN result never passes     |
    | True (bool)   | 1 (int)       | NOT eq  | bool compares only to bool    |
    | [1, 2]        | [1, 2]        | EQUAL   | recursive list compare         |
    | {"a": 1}      | {"a": 1}      | EQUAL   | recursive dict compare (keys + values) |
    | 9007199254740993 (int) | 9007199254740992 (int) | NOT eq | int==int compares exactly, never float-coerced (float loses precision past 2**53) |

    Rule: expect/got both int -> direct `==` (exact, arbitrary precision);
    either one a float -> `float(expect) == float(got)` (the mathematical-
    equality rule above). Coercing to float unconditionally would make two
    distinct large ints compare equal once they exceed 2**53 -- this is why
    the int/int branch is kept separate from the mixed int/float branch.

Case set
--------
The card's `case_matrix` plus a mandatory edge set this script appends
itself (never declared on the card): `""`, `None`,
`"Trần Thị Ế — 東京"` (unicode + diacritics), `"{malformed"`, and a boundary
case (the case-matrix element with the longest `str(input)`, duplicated).
Edge-case "expect" is "did not crash" (an exception/timeout → FAIL-equivalent
status, still recorded); matrix-case expect is the canonical `==` against
the card's declared `expect`.

Stdlib only; paths resolve off `__file__`; never imports `harness/scripts/`
(this skill is self-contained, same discipline as `eval_scaffold.py`).
`actor` resolves via `HARNESS_USER` env, falling back to `getpass.getuser()`
— attribution, not authentication.
"""

import argparse
import getpass
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_config  # noqa: E402  (sibling import — reuse the sha256-of-file-bytes
                     # hash algorithm from eval_config.cmd_verify, and its
                     # atomic-write helper for the evidence artifact)
import sandbox_denylist  # noqa: E402  (sibling import — layer-1 static scan)


EXIT_OK = 0
EXIT_CASE_FAILURE = 1
EXIT_INPUT_ERROR = 2
EXIT_DENYLIST_REFUSE = 3
EXIT_CONTAINMENT_ERROR = 4

# Union of both platforms' env-scrub whitelists (§ layer 3) — a test on
# either platform can assert its observed env_keys is a subset of this.
ENV_WHITELIST = frozenset((
    "PATH", "HOME", "TMPDIR", "PYTHONDONTWRITEBYTECODE",
    "SystemRoot", "USERPROFILE", "TEMP", "TMP", "HARNESS_R9_NONCE",
))

_CASE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.-]")


class _InputError(Exception):
    """A malformed --fill/--config — maps to EXIT_INPUT_ERROR."""


class _ContainmentError(Exception):
    """bwrap itself failed mid-run (after preflight already passed) —
    maps to EXIT_CONTAINMENT_ERROR. This is an infra failure, never a
    per-case CRASH: the fill did not run (or its exit is not trustworthy)
    because the OS jail setup broke underneath it."""


# --------------------------------------------------------------------------
# Canonical comparator — see the module docstring table above.
# --------------------------------------------------------------------------

def canonical_equal(expect, got) -> bool:
    """Recursive structural compare with the scalar rules documented in the
    module docstring: int==float when mathematically equal, str never
    equals a number, bool only equals bool, NaN in `got` never matches."""
    if isinstance(expect, dict) or isinstance(got, dict):
        if not (isinstance(expect, dict) and isinstance(got, dict)):
            return False
        if set(expect.keys()) != set(got.keys()):
            return False
        return all(canonical_equal(expect[k], got[k]) for k in expect)
    if isinstance(expect, list) or isinstance(got, list):
        if not (isinstance(expect, list) and isinstance(got, list)):
            return False
        if len(expect) != len(got):
            return False
        return all(canonical_equal(e, g) for e, g in zip(expect, got))
    if isinstance(expect, bool) or isinstance(got, bool):
        return expect is got
    if isinstance(expect, (int, float)) and isinstance(got, (int, float)):
        if isinstance(got, float) and math.isnan(got):
            return False
        # Native comparison, never float()-coerced. CPython compares int and
        # float EXACTLY across all pairings (int/int, int/float, float/float),
        # so two distinct values past 2**53 stay distinct instead of both
        # truncating onto the same float; 100 == 100.0 still holds.
        return expect == got
    if expect is None and got is None:
        return True
    if isinstance(expect, str) and isinstance(got, str):
        return expect == got
    return False


def _contains_nan(value) -> bool:
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, dict):
        return any(_contains_nan(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_nan(v) for v in value)
    return False


# --------------------------------------------------------------------------
# Card / config loading
# --------------------------------------------------------------------------

def _load_case_matrix(config_path: Path) -> Tuple[List[dict], str]:
    """Read --config, extract case_matrix, and compute card_hash the same
    way `eval_config.cmd_verify` does — sha256 of the exact file bytes — so
    this always agrees with `eval_config.py verify` for the same file."""
    try:
        raw_bytes = config_path.read_bytes()
    except OSError as e:
        raise _InputError("cannot read --config %s: %s" % (config_path, e))

    try:
        card = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        raise _InputError("--config is not valid JSON: %s" % e)

    if not isinstance(card, dict):
        raise _InputError("--config must decode to a JSON object")

    case_matrix = card.get("case_matrix")
    if not isinstance(case_matrix, list) or not case_matrix:
        raise _InputError("--config: case_matrix must be a non-empty list")

    for i, case in enumerate(case_matrix):
        if not isinstance(case, dict) or not {"case", "input", "expect"} <= set(case):
            raise _InputError(
                "--config: case_matrix[%d] missing case/input/expect" % i)
        if _contains_nan(case["expect"]):
            raise _InputError(
                "--config: case_matrix[%d].expect contains NaN — the "
                "comparator rejects NaN in expect at card-load time" % i)

    card_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    return case_matrix, card_hash


def _digest(value) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Edge case set — code-appended, never card-declared
# --------------------------------------------------------------------------

def _boundary_input(case_matrix: List[dict]):
    longest = max(case_matrix, key=lambda c: len(str(c.get("input", ""))))
    original = longest.get("input", "")
    if isinstance(original, str):
        return original + original
    if isinstance(original, list):
        return original + original
    return str(original) + str(original)


def _edge_cases(case_matrix: List[dict]) -> List[dict]:
    return [
        {"case": "edge:empty", "input": ""},
        {"case": "edge:null", "input": None},
        {"case": "edge:unicode", "input": "Trần Thị Ế — 東京"},
        {"case": "edge:malformed", "input": "{malformed"},
        {"case": "edge:boundary", "input": _boundary_input(case_matrix)},
    ]


# --------------------------------------------------------------------------
# Layer 0 — OS containment
# --------------------------------------------------------------------------

def _resolve_python_binds(python_exe: Path) -> List[str]:
    binds = []
    for base in ("/usr", "/bin", "/lib", "/lib64"):
        if Path(base).is_dir():
            binds.append(base)
    resolved = python_exe.resolve()
    covered = any(resolved.is_relative_to(Path(b)) for b in binds)
    if not covered:
        # The interpreter lives outside /usr,/bin,/lib,/lib64 (e.g. a
        # pyenv/mise-managed install under $HOME) — bind only its own
        # install prefix, read-only, so it can execvp inside the sandbox
        # without exposing the rest of the home directory (~/.ssh stays
        # unreachable).
        binds.append(str(resolved.parent.parent))
    return binds


def _bwrap_prefix(sandbox_dir: Path, python_exe: Path, bwrap_path: str,
                   share_net: bool = False) -> List[str]:
    argv = [bwrap_path]
    for b in _resolve_python_binds(python_exe):
        argv += ["--ro-bind", b, b]
    sandbox_str = str(sandbox_dir)
    argv += [
        "--bind", sandbox_str, sandbox_str,
        "--chdir", sandbox_str,
        # Not in the phase's illustrative one-liner, but required in
        # practice (verified by hand): python's startup hash-randomization
        # needs /dev/urandom, and some stdlib paths touch /proc.
        "--dev", "/dev",
        "--proc", "/proc",
        "--unshare-all",
    ]
    if share_net:
        argv.append("--share-net")
    else:
        argv.append("--unshare-net")
    argv += [
        "--die-with-parent", "--new-session",
    ]
    return argv


def _resolve_bwrap_path() -> Optional[str]:
    """Resolve bwrap to an ABSOLUTE path ONCE, off the host PATH, before
    the env scrub. Both preflight and every real case launch use this
    exact same absolute path as argv[0] -- an execve with an absolute
    argv[0] never consults PATH, so the scrubbed per-case env's PATH can
    never disagree with what preflight already proved works (closes the
    bare-"bwrap"-argv[0] mismatch where preflight and the real per-case
    launch could resolve to two different binaries, or none at all,
    depending on which PATH each one happened to inherit)."""
    return shutil.which("bwrap")


def _bwrap_safe_base(want_bwrap: bool) -> Optional[str]:
    """bwrap's `--dev /dev` remounts /dev, which shadows a sandbox created
    under /dev/shm (a common TMPDIR on CI for speed) so bwrap can no longer
    chdir into it. When bwrap is in play, pick a temp base outside /dev;
    otherwise (None) the default TMPDIR is fine."""
    if not want_bwrap:
        return None
    default = os.path.realpath(tempfile.gettempdir())
    if default != "/dev" and not default.startswith("/dev" + os.sep):
        return None
    for cand in ("/tmp", "/var/tmp",
                 os.path.expanduser("~/.cache"), os.path.expanduser("~")):
        rp = os.path.realpath(cand)
        if (os.path.isdir(cand) and os.access(cand, os.W_OK)
                and rp != "/dev" and not rp.startswith("/dev" + os.sep)):
            return cand
    return None


def _bwrap_preflight(python_exe: Path, bwrap_path: str) -> Tuple[bool, str, bool]:
    """Launch a trivial `python -c "pass"` under the exact bind set +
    the exact ABSOLUTE bwrap path real case-subprocesses use, BEFORE any
    case runs. A failure here is unambiguous infra breakage -- the fill
    has not been touched yet, so it can never be confused with a fill
    crashing on import.

    Some CI/container kernels deny the network namespace setup that
    `--unshare-net` performs (bwrap: loopback: Failed RTM_NEWADDR:
    Operation not permitted). When that is the only failure, retry with
    a shared network namespace; filesystem/process isolation still holds,
    and the caller records the downgrade honestly."""
    probe_dir = Path(tempfile.mkdtemp(prefix="eval-sandbox-probe-", dir=_bwrap_safe_base(True)))
    try:
        argv = _bwrap_prefix(probe_dir, python_exe, bwrap_path, share_net=False) + [str(python_exe), "-c", "pass"]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, str(e), False
        if proc.returncode == 0:
            return True, "", False
        stderr = proc.stderr.strip()
        # Network-namespace denied is the only soft-failure we retry.
        if "RTM_NEWADDR" in stderr or "loopback" in stderr:
            argv = _bwrap_prefix(probe_dir, python_exe, bwrap_path, share_net=True) + [str(python_exe), "-c", "pass"]
            try:
                proc = subprocess.run(argv, capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as e:
                return False, str(e), False
            if proc.returncode == 0:
                return True, "", True
            stderr = proc.stderr.strip() or (
                "bwrap preflight exited %d" % proc.returncode)
        return False, stderr, False
    finally:
        shutil.rmtree(str(probe_dir), ignore_errors=True)


def _resolve_containment(seam: str, python_exe: Path) -> Tuple[str, str, Optional[str], bool]:
    """Returns (containment, reason, bwrap_path, share_net). bwrap_path is the ONE
    absolute path resolved for this whole run -- non-None only when
    containment == "bwrap", and is the SAME value threaded into every
    real case launch (see _resolve_bwrap_path). share_net is True when the
    kernel denied a private network namespace but bwrap still works with
    shared networking."""
    if seam not in ("bwrap", "fallback", "auto"):
        print("WARNING: unknown HARNESS_R9_CONTAINMENT=%r, treating as auto"
              % seam, file=sys.stderr)
        seam = "auto"

    if seam == "fallback":
        return "python-filter-fallback", "", None, False

    bwrap_path = _resolve_bwrap_path()
    if bwrap_path is None:
        reason = "bwrap binary not found on PATH"
        if seam == "bwrap":
            return "bwrap_failed", reason, None, False
        return "python-filter-fallback", reason, None, False

    if seam == "bwrap":
        ok, reason, share_net = _bwrap_preflight(python_exe, bwrap_path)
        return ("bwrap", "", bwrap_path, share_net) if ok else ("bwrap_failed", reason, None, False)

    # auto — never silently required, so a failure here just means the
    # honest fallback, not an error.
    ok, reason, share_net = _bwrap_preflight(python_exe, bwrap_path)
    if ok:
        return "bwrap", "", bwrap_path, share_net
    return "python-filter-fallback", reason, None, False


# --------------------------------------------------------------------------
# Layer 3 — env scrub
# --------------------------------------------------------------------------

def _build_env(sandbox_dir: Path, nonce: Optional[str] = None) -> Dict[str, str]:
    """`nonce`, when given, is threaded into the child's env as
    HARNESS_R9_NONCE -- the driver echoes it back in the emit file so the
    parent can reject an emit a fill forged itself (finding #4). Reading it
    back out is denied by layer 1 (os.environ/os.getenv and their `from os
    import ...`/alias forms are on the denylist); like every static-scan
    guarantee this is best-effort (getattr-indirection remains), so the OS
    jail + human evidence read stay the load-bearing backstop."""
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        env = {
            "SystemRoot": system_root,
            "PATH": system_root + r"\System32",
            "USERPROFILE": str(sandbox_dir),
            "TEMP": str(sandbox_dir),
            "TMP": str(sandbox_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    else:
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(sandbox_dir),
            "TMPDIR": str(sandbox_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    if nonce is not None:
        env["HARNESS_R9_NONCE"] = nonce
    return env


def _popen_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


# --------------------------------------------------------------------------
# Layer 5 — cross-platform whole-tree kill
# --------------------------------------------------------------------------

def _kill_tree(proc: "subprocess.Popen") -> None:
    if os.name == "nt":
        # taskkill /T FIRST, while the process tree is still rooted at pid —
        # p.kill() alone only TerminateProcess's the direct child, letting a
        # grandchild reparent and survive.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                        capture_output=True)
        try:
            proc.kill()
        except OSError:
            pass
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                proc.kill()
            except OSError:
                pass


def _reap(launched: List["subprocess.Popen"]) -> None:
    """Orphan-reaper: before the sandbox dir is removed, forcibly kill any
    launched process still alive."""
    for proc in launched:
        if proc.poll() is None:
            _kill_tree(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass


# --------------------------------------------------------------------------
# Driver — runs INSIDE the jailed subprocess, never imported by the parent.
# --------------------------------------------------------------------------

_DRIVER_SOURCE = '''"""R9 sandbox driver -- executed inside the jailed subprocess, never by the
parent. argv: fill_filename entry_name input_filename emit_filename mode

mode "0" -- run one case: import --fill, call --entry(case_input), write the
    raw return value to the emit file as JSON. An uncaught exception (or an
    unserializable return value) propagates naturally: nonzero exit, a
    traceback on stderr, NO emit file written -- the parent scores that as
    CRASH, never as a silent PASS.
mode "1" -- network probe (dev-only, driven by --probe-network): confirms
    the no-network preamble actually blocks socket.socket/getaddrinfo and
    _socket.socket.
mode "2" -- env probe (internal): dumps sorted(os.environ) key names to the
    emit file so the parent can pin evidence.meta.env_keys to what this
    process actually saw, not just what the parent constructed.

Binds its own references to the real json.dumps/json.loads BEFORE importing
the fill, so a fill that reassigns json.dumps afterward cannot change what
this driver writes to the emit channel (mitigation 1). The fill
never receives --config/the card or `expect` -- only the per-case `input`
value already written to a file inside this sandbox (mitigation 2).
"""
import os
import sys

import json as _json_module

_real_dumps = _json_module.dumps
_real_loads = _json_module.loads


def _refuse(*_args, **_kwargs):
    raise RuntimeError("network disabled in sandbox (R9 layer 4)")


import socket as _socket_module

_socket_module.socket = _refuse
_socket_module.getaddrinfo = _refuse
_socket_module.create_connection = _refuse
_socket_module.socketpair = _refuse
_socket_module.fromfd = _refuse

_HAVE_C_SOCKET = False
try:
    import _socket as _c_socket_module
    _c_socket_module.socket = _refuse
    _HAVE_C_SOCKET = True
except ImportError:
    _c_socket_module = None


def _network_blocked_checks():
    checks = [("socket.socket", _socket_module.socket),
              ("socket.getaddrinfo", _socket_module.getaddrinfo)]
    if _HAVE_C_SOCKET:
        checks.append(("_socket.socket", _c_socket_module.socket))
    blocked = []
    for label, fn in checks:
        try:
            fn()
        except RuntimeError as exc:
            if "network disabled" in str(exc):
                blocked.append(label)
        except Exception:
            pass
    return len(blocked) == len(checks)


def _main():
    fill_name, entry_name, input_name, emit_name, mode = sys.argv[1:6]
    # Read the nonce BEFORE importing the fill -- same discipline as
    # binding _real_dumps/_real_loads above (mitigation 1): a fill that
    # tampers with os.environ after import cannot change what this driver
    # already captured.
    _run_nonce = os.environ.get("HARNESS_R9_NONCE", "")

    if mode == "1":
        if _network_blocked_checks():
            print("PROBE_NETWORK_BLOCKED")
            sys.exit(0)
        print("PROBE_NETWORK_NOT_BLOCKED")
        sys.exit(1)

    if mode == "2":
        with open(emit_name, "w", encoding="utf-8") as fh:
            fh.write(_real_dumps({"env_keys": sorted(os.environ.keys())}))
        return

    import importlib.util

    spec = importlib.util.spec_from_file_location("fill_module", fill_name)
    fill_module = importlib.util.module_from_spec(spec)
    sys.modules["fill_module"] = fill_module
    spec.loader.exec_module(fill_module)
    entry_fn = getattr(fill_module, entry_name)

    with open(input_name, "r", encoding="utf-8") as fh:
        case_input = _real_loads(fh.read())["input"]

    got = entry_fn(case_input)

    with open(emit_name, "w", encoding="utf-8") as fh:
        fh.write(_real_dumps({"got": got, "nonce": _run_nonce}))


if __name__ == "__main__":
    _main()
'''


# --------------------------------------------------------------------------
# Sandbox lifecycle + per-case execution
# --------------------------------------------------------------------------

def _make_sandbox_dir(want_bwrap: bool = False) -> str:
    return tempfile.mkdtemp(prefix="eval-sandbox-", dir=_bwrap_safe_base(want_bwrap))


def _slug(name: str) -> str:
    return _CASE_TOKEN_RE.sub("_", name)[:80] or "case"


def _build_launch_argv(containment: str, python_exe: Path, sandbox_dir: Path,
                        argv_tail: List[str],
                        bwrap_path: Optional[str] = None,
                        share_net: bool = False) -> List[str]:
    driver = str(sandbox_dir / "driver.py")
    if containment == "bwrap":
        return _bwrap_prefix(sandbox_dir, python_exe, bwrap_path, share_net) + [str(python_exe), driver] + argv_tail
    return [str(python_exe), driver] + argv_tail


def _read_emit(path: Path, nonce: Optional[str] = None) -> Tuple[object, bool]:
    """`nonce`, when given, must match the value the driver echoed back --
    a fill that discovers its own case-input filename (os.listdir is not
    denylisted) and writes emit-<token>.json itself, then crashes, cannot
    forge the nonce (os.environ/os.getenv ARE denylisted), so its
    self-written emit is rejected here and the case still scores CRASH
    (finding #4). `nonce=None` skips the check (used only by the
    non-case env/network probes, which never score a fill's answer)."""
    if not path.is_file():
        return None, False
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return None, False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, False
    if not isinstance(parsed, dict) or "got" not in parsed:
        return None, False
    if nonce is not None and parsed.get("nonce") != nonce:
        return None, False
    return parsed["got"], True


def _tail(text: Optional[str], limit: int = 4000) -> str:
    text = text or ""
    return text[-limit:]


def _run_case(case_name: str, case_input, expect, is_edge: bool, *,
              sandbox_dir: Path, fill_name: str, entry: str, timeout: float,
              containment: str, python_exe: Path, nonce: str,
              launched: List["subprocess.Popen"],
              bwrap_path: Optional[str] = None,
              share_net: bool = False) -> dict:
    token = _slug(case_name)
    input_path = sandbox_dir / ("case-input-%s.json" % token)
    emit_path = sandbox_dir / ("emit-%s.json" % token)
    if emit_path.exists():
        emit_path.unlink()
    input_path.write_text(json.dumps({"input": case_input}, ensure_ascii=False),
                           encoding="utf-8")

    argv = _build_launch_argv(containment, python_exe, sandbox_dir,
                               [fill_name, entry, input_path.name, emit_path.name, "0"],
                               bwrap_path, share_net)
    env = _build_env(sandbox_dir, nonce)
    kwargs = _popen_kwargs()

    display_expect = expect if not is_edge else "no-crash"

    try:
        proc = subprocess.Popen(argv, cwd=str(sandbox_dir), env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, **kwargs)
    except OSError as e:
        if containment == "bwrap":
            # With an absolute, preflight-proven bwrap_path this should
            # never happen from a missing binary -- a real launch OSError
            # here is infra breaking mid-run, not the fill; the fill never
            # got to execute, so this must never read as a CRASH case.
            raise _ContainmentError("bwrap launch failed for case %r: %s" % (case_name, e))
        return {"case": case_name, "input_digest": _digest(case_input), "status": "CRASH",
                "expect": display_expect, "got": None, "stderr": "launch failed: %s" % e}

    launched.append(proc)
    timed_out = False
    stderr_text = ""
    try:
        _stdout, stderr_text = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            _stdout, stderr_text = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stderr_text = stderr_text or ""

    if (containment == "bwrap" and not timed_out and stderr_text
            and stderr_text.lstrip().startswith("bwrap:")):
        # bwrap printed its OWN setup-error message (never how a python
        # traceback from the driver/fill looks) -- the driver never even
        # started, so this is infra breaking mid-run, not a fill CRASH.
        raise _ContainmentError(
            "bwrap reported a setup failure for case %r before the driver "
            "ran: %s" % (case_name, _tail(stderr_text, 500)))

    if timed_out:
        status = "TIMEOUT"
        got = None
    else:
        got, ok = _read_emit(emit_path, nonce)
        if not ok:
            status = "CRASH"
            got = None
        elif is_edge:
            status = "PASS"
        else:
            status = "PASS" if canonical_equal(expect, got) else "FAIL"

    return {
        "case": case_name,
        "input_digest": _digest(case_input),
        "status": status,
        "expect": display_expect,
        "got": got,
        "stderr": _tail(stderr_text),
    }


def _run_probe_network(sandbox_dir: Path, containment: str, python_exe: Path,
                        launched: List["subprocess.Popen"],
                        bwrap_path: Optional[str] = None,
                        share_net: bool = False) -> bool:
    argv = _build_launch_argv(containment, python_exe, sandbox_dir,
                               ["__probe__", "__probe__", "__probe__", "__probe__", "1"],
                               bwrap_path, share_net)
    env = _build_env(sandbox_dir)
    kwargs = _popen_kwargs()
    proc = subprocess.Popen(argv, cwd=str(sandbox_dir), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, **kwargs)
    launched.append(proc)
    try:
        out, err = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        out, err = proc.communicate()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip(), file=sys.stderr)
    return "PROBE_NETWORK_BLOCKED" in out


def _probe_env(sandbox_dir: Path, containment: str, python_exe: Path,
                launched: List["subprocess.Popen"],
                bwrap_path: Optional[str] = None,
                share_net: bool = False) -> List[str]:
    """Real measurement of what the sandboxed process actually saw, not just
    what the parent constructed — proves the scrub held end to end."""
    emit_path = sandbox_dir / "emit-env-probe.json"
    argv = _build_launch_argv(containment, python_exe, sandbox_dir,
                               ["__probe__", "__probe__", "__probe__", emit_path.name, "2"],
                               bwrap_path, share_net)
    env = _build_env(sandbox_dir)
    kwargs = _popen_kwargs()
    try:
        proc = subprocess.Popen(argv, cwd=str(sandbox_dir), env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, **kwargs)
    except OSError as e:
        if containment == "bwrap":
            raise _ContainmentError("bwrap launch failed for the env probe: %s" % e)
        raise
    launched.append(proc)
    try:
        proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.communicate()
    got, ok = _read_emit(emit_path)
    if ok and isinstance(got, dict) and isinstance(got.get("env_keys"), list):
        return sorted(got["env_keys"])
    return sorted(_build_env(sandbox_dir).keys())


# --------------------------------------------------------------------------
# Evidence artifact
# --------------------------------------------------------------------------

def _base_evidence(fill_path: Path, entry: str, card_hash: str,
                    denylist_result: dict) -> dict:
    return {
        "schema_version": "1.0",
        "fill": fill_path.name,
        "entry": entry,
        "card_hash": card_hash,
        "containment": "unknown",
        "denylist": denylist_result,
        "cases": [],
        "edge_cases": [],
        "summary": {"total": 0, "pass": 0, "fail": 0},
        "meta": {"env_keys": []},
        "actor": os.environ.get("HARNESS_USER") or getpass.getuser(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _write_evidence(path: Path, evidence: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
    eval_config._atomic_write(path, body)


def _print_report(evidence: dict) -> None:
    print("sandbox evidence (hs:eval-bootstrap R9 gate) -- fill=%s entry=%s "
          "containment=%s card_hash=%s"
          % (evidence["fill"], evidence["entry"], evidence["containment"], evidence["card_hash"]))
    print("%-28s %-8s %-42s %s" % ("case", "status", "got vs expect", "stderr"))
    for c in evidence["cases"] + evidence["edge_cases"]:
        stderr_line = c["stderr"].strip().splitlines()[-1] if c["stderr"].strip() else ""
        gv = "%r vs %r" % (c["got"], c["expect"])
        print("%-28s %-8s %-42s %s" % (c["case"], c["status"], gv[:42], stderr_line[:60]))
    s = evidence["summary"]
    print("summary: total=%d pass=%d fail=%d" % (s["total"], s["pass"], s["fail"]))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _validate_extra_file_name(name: str) -> None:
    """Reject anything that could escape the sandbox_dir join: an
    absolute path, an embedded separator, or a '..' traversal segment.
    Checked at parse time, before any file is read or copied."""
    if not name:
        raise _InputError("--extra-file name must not be empty")
    if (os.path.isabs(name) or os.sep in name
            or (os.altsep and os.altsep in name)
            or name in (".", "..")
            or ".." in Path(name).parts):
        raise _InputError(
            "--extra-file name %r is invalid: must be a bare relative "
            "filename with no path separators, no '..' traversal, and "
            "no absolute path" % name)


def _parse_extra_files(values: List[str]) -> List[Tuple[str, Path]]:
    out = []
    for v in values:
        if "=" not in v:
            raise _InputError("--extra-file must be name=path, got %r" % v)
        name, path = v.split("=", 1)
        _validate_extra_file_name(name)
        out.append((name, Path(path)))
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="R9 sandbox runner -- execute a code-fill inside a "
                    "layered jail against a case matrix + mandatory edge "
                    "set, emit a JSON evidence artifact for the human gate.")
    p.add_argument("--fill", required=True, help="path to the fill file to execute")
    p.add_argument("--entry", required=True, help="entry function name inside --fill")
    p.add_argument("--config", required=True, help="path to the approved eval_config.json (card)")
    p.add_argument("--case-timeout", type=float, default=10.0)
    p.add_argument("--evidence-out", required=True)
    p.add_argument("--extra-file", action="append", default=[], metavar="name=path",
                    help="companion module the fill needs, e.g. runner=path/to/runner.py")
    # Dev-only diagnostic hook — never used in a real R9 run, only by tests
    # proving the no-network preamble actually blocks the socket layer.
    p.add_argument("--probe-network", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    fill_path = Path(args.fill)
    config_path = Path(args.config)
    evidence_path = Path(args.evidence_out)

    try:
        extra_files = _parse_extra_files(args.extra_file)
        if not fill_path.is_file():
            raise _InputError("--fill not found: %s" % fill_path)
        fill_source = fill_path.read_text(encoding="utf-8")
        case_matrix, card_hash = _load_case_matrix(config_path)
        extra_sources = []
        for name, extra_src_path in extra_files:
            if not extra_src_path.is_file():
                raise _InputError("--extra-file source not found: %s" % extra_src_path)
            extra_sources.append(
                (name, extra_src_path, extra_src_path.read_text(encoding="utf-8")))
    except _InputError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Layer 1 — denylist pre-execute. ALWAYS before any execution, and
    # ALWAYS across --fill AND every --extra-file -- a companion module is
    # just as importable by the fill as fill.py itself, so it gets the
    # exact same static scan (finding #5).
    try:
        all_findings = list(sandbox_denylist.scan_source(fill_source, lang="python"))
        for name, extra_src_path, extra_source in extra_sources:
            # Key the scan lane off the DESTINATION name (what the file becomes
            # in the sandbox and how the fill imports+runs it), NOT the source
            # suffix -- else a Python payload delivered as helper.py=x.ts routes
            # to the weak regex lane yet executes as Python.
            extra_lang = sandbox_denylist._LANG_BY_SUFFIX.get(Path(name).suffix, "python")
            for f in sandbox_denylist.scan_source(extra_source, lang=extra_lang):
                all_findings.append(sandbox_denylist.Finding(
                    f.line, f.code, "[extra-file %s] %s" % (name, f.message)))
    except SyntaxError as e:
        print("ERROR: --fill or --extra-file does not parse: %s" % e, file=sys.stderr)
        return EXIT_INPUT_ERROR

    denylist_result = {
        "clean": not all_findings,
        "findings": [{"line": f.line, "code": f.code, "message": f.message} for f in all_findings],
    }
    if all_findings:
        for f in all_findings:
            print("%s:%d: %s: %s" % (fill_path, f.line, f.code, f.message))
        evidence = _base_evidence(fill_path, args.entry, card_hash, denylist_result)
        evidence["containment"] = "n/a (refused before execution)"
        _write_evidence(evidence_path, evidence)
        return EXIT_DENYLIST_REFUSE

    python_exe = Path(os.path.realpath(sys.executable))
    seam = os.environ.get("HARNESS_R9_CONTAINMENT", "auto")
    containment, reason, bwrap_path, share_net = _resolve_containment(seam, python_exe)

    if containment == "bwrap_failed":
        print("ERROR: containment_error -- bwrap seam requested but "
              "unavailable: %s" % reason, file=sys.stderr)
        evidence = _base_evidence(fill_path, args.entry, card_hash, denylist_result)
        evidence["containment"] = "bwrap_failed"
        _write_evidence(evidence_path, evidence)
        return EXIT_CONTAINMENT_ERROR

    if containment == "bwrap" and share_net:
        print("=" * 70)
        print("WARNING: bwrap OS-level sandbox is active but network isolation")
        print("is UNAVAILABLE on this kernel (private namespace denied).")
        print("Filesystem and process isolation still hold; network is shared.")
        print("=" * 70)

    if containment == "python-filter-fallback":
        print("=" * 70)
        print("WARNING: OS-level sandbox containment (bwrap) is unavailable.")
        print("Running with a PYTHON-FILTER FALLBACK ONLY -- this is a")
        print("best-effort pre-filter, NOT a real OS jail. Network and")
        print("filesystem isolation below the python layer are NOT enforced.")
        print("=" * 70)

    # Parent-side-only secret (finding #4): reading it back is denied by the
    # layer-1 denylist (os env-reads incl. from-import/alias forms); best-effort,
    # with the OS jail + human evidence read as the load-bearing backstop.
    nonce = secrets.token_hex(16)

    sandbox_dir = Path(_make_sandbox_dir(containment == "bwrap"))
    launched: List["subprocess.Popen"] = []
    cases: List[dict] = []
    edge_cases: List[dict] = []
    env_keys: List[str] = sorted(_build_env(sandbox_dir).keys())
    try:
        # Write the ALREADY-SCANNED in-memory bytes into the sandbox rather
        # than re-reading from disk (shutil.copy2) -- so the bytes that ran the
        # denylist are exactly the bytes that execute, closing the scan->exec
        # TOCTOU window (symlink repoint / concurrent writer).
        (sandbox_dir / fill_path.name).write_text(fill_source, encoding="utf-8")
        for name, _extra_src_path, extra_source in extra_sources:
            (sandbox_dir / name).write_text(extra_source, encoding="utf-8")
        (sandbox_dir / "driver.py").write_text(_DRIVER_SOURCE, encoding="utf-8")

        if args.probe_network:
            ok = _run_probe_network(sandbox_dir, containment, python_exe, launched, bwrap_path, share_net)
            return EXIT_OK if ok else EXIT_CASE_FAILURE

        env_keys = _probe_env(sandbox_dir, containment, python_exe, launched, bwrap_path, share_net)

        for case in case_matrix:
            cases.append(_run_case(
                case["case"], case["input"], case["expect"], False,
                sandbox_dir=sandbox_dir, fill_name=fill_path.name, entry=args.entry,
                timeout=args.case_timeout, containment=containment,
                python_exe=python_exe, nonce=nonce, launched=launched,
                bwrap_path=bwrap_path, share_net=share_net))

        for edge in _edge_cases(case_matrix):
            edge_cases.append(_run_case(
                edge["case"], edge["input"], None, True,
                sandbox_dir=sandbox_dir, fill_name=fill_path.name, entry=args.entry,
                timeout=args.case_timeout, containment=containment,
                python_exe=python_exe, nonce=nonce, launched=launched,
                bwrap_path=bwrap_path, share_net=share_net))
    except _ContainmentError as e:
        print("ERROR: containment_error -- %s" % e, file=sys.stderr)
        evidence = _base_evidence(fill_path, args.entry, card_hash, denylist_result)
        evidence["containment"] = "bwrap_failed"
        _write_evidence(evidence_path, evidence)
        return EXIT_CONTAINMENT_ERROR
    finally:
        _reap(launched)
        shutil.rmtree(str(sandbox_dir), ignore_errors=True)

    total = len(cases) + len(edge_cases)
    passed = sum(1 for c in cases + edge_cases if c["status"] == "PASS")
    summary = {"total": total, "pass": passed, "fail": total - passed}

    evidence = _base_evidence(fill_path, args.entry, card_hash, denylist_result)
    evidence["containment"] = containment
    evidence["cases"] = cases
    evidence["edge_cases"] = edge_cases
    evidence["summary"] = summary
    evidence["meta"] = {"env_keys": env_keys, "bwrap_share_net": share_net}
    _write_evidence(evidence_path, evidence)
    _print_report(evidence)

    return EXIT_OK if summary["fail"] == 0 else EXIT_CASE_FAILURE


if __name__ == "__main__":
    sys.exit(main())
