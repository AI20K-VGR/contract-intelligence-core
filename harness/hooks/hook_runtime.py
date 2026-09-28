#!/usr/bin/env python3
"""hook_runtime.py — one shared runtime for all harness hooks.

Ported from product-spec hook_runtime.py (crash audit, stdin/stdout skeleton,
config cache, telemetry wrapper) and generalized for the harness:

  * 3 hook classes instead of 2 hard-coded stem sets:
      - telemetry:  default ON,  fail-open, always {"continue": true}
      - nudge:      default OFF, advisory (stderr + exit 0)
      - compliance: default ON + BLOCKING, fail-CLOSED (exit 2 + reason)
    The class is a CODE CONSTANT in each hook file (`HOOK_CLASS = "..."`),
    never config data: a broken config file must not change what a
    hook is, only whether it is enabled and which mode it runs in.
  * config = harness-hooks.yaml (human-edited config is YAML).
    PyYAML is imported lazily INSIDE the config loader so telemetry/nudge
    paths stay importable without it; the compliance wrapper turns a missing
    dep into exit 2 + the install command.
  * resolve_actor(): every hook resolves identity independently —
    session file is an optional cache, never a prerequisite.

Telemetry/nudge public functions are fail-open: they never raise back into a
hook. The compliance wrapper is the one place that fails closed by design.
"""

import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# --- shared Bash script matcher (single home for the Pre/Post:Bash pair) ------
# mark_bash_start (PreToolUse:Bash) and track_script_execution (PostToolUse:Bash)
# read ONE matcher from here so they can never drift out of lockstep. It matches
# a harness script (harness/scripts/<f>.py|sh or harness/e2e/<f>.py|sh) run in
# EXECUTION position — not merely referenced. A bare substring would count
# `grep ... scripts/check_fence.py`, `ls .../verify_install.py`, `cat ...` as
# runs and (via any read-back of these records) inflate the run signal with
# greps. Requiring a command boundary + optional interpreter is what keeps the
# signal real. group(1) = the harness-relative path (scripts/<f> | e2e/<f>).
#
# The path may carry an arbitrary leading dir prefix (`./`, an absolute path, or
# `"$CLAUDE_PROJECT_DIR"/...`): `(?:\S*/)?harness/` consumes it WITHOUT reopening
# the substring hole — it cannot bridge the space at an argument position, so a
# grep/ls/cat of the path (even an absolute one) still has no boundary in front
# and stays rejected.
#
# A bare `(` is NOT a boundary char: it opens a regex/code group as often as a
# subshell, so `python3 -c '... re.compile(r"(harness/scripts/x.py)")'` would
# false-count the capture group as a run. A genuine subshell that runs a harness
# script still presents a real boundary before the script (`(cd d && …`, `(…; …`)
# via the ; & | newline class, so dropping `(` loses no real execution signal.
SCRIPT_RE = re.compile(
    r"(?:^|[\n;|&])\s*"                                    # command boundary
    r"(?:[A-Za-z_]\w*=\S*\s+)*"                            # optional leading VAR=val env
    r"(?:(?:\S*/)?(?:python3?|bash|sh)(?:\s+-\S+)*\s+)?"   # optional interpreter (+ flags)
    r"(?:\S*/)?harness/((?:scripts|e2e)/[^\s]+\.(?:py|sh))"  # optional dir prefix (abs/$VAR/.)
)

# --- test-run recognition (the red-before-green floor) -----------------------
#
# SCRIPT_RE anchors on a `harness/scripts/...` path in EXECUTION position, which
# is exactly what a pytest invocation lacks: `python3 -m pytest <paths>` runs a
# MODULE and the paths that follow are arguments. So the one command class whose
# red/green transition carries the TDD claim was the one class the recorder could
# not see. These two helpers close that, and stay pure so a caller can pass
# records from any sink.
#
# `pytest:` prefixes the recorded target to keep it in a namespace of its own —
# a test FILE and a script PATH would otherwise collide in the same `script`
# field, and a lens counting script runs would silently absorb test runs.
_PYTEST_RE = re.compile(
    r"(?:^|[\n;|&])\s*"                          # command boundary
    r"(?:[A-Za-z_]\w*=\S*\s+)*"                  # optional leading VAR=val env
    r"(?:(?:\S*/)?python3?\s+-m\s+)?"            # optional `python3 -m`
    r"pytest\b(?P<args>[^\n;|&]*)"               # the runner, then its argv tail
)
# The repo's own runner: CLAUDE.md names it as the command CI runs, so a red/green
# pair recorded through it must count the same as a direct pytest pair.
_RUNNER_RE = re.compile(r"harness/scripts/run_local_tests\.py(?P<args>[^\n;|&]*)")


def test_run_target(command):
    """The test target this command runs, or None when it is not a test run.

    Returns a STRING, not a bool, because a bare yes/no cannot pair a red run
    with the green run OF THE SAME target — a red `test_a.py` followed by a green
    `test_b.py` would otherwise read as red->green. Falls back to the runner's own
    name when no path argument is present (a whole-suite run is still one target).
    """
    if not command:
        return None
    match = _PYTEST_RE.search(command) or _RUNNER_RE.search(command)
    if not match:
        return None
    for token in (match.group("args") or "").split():
        if token.startswith("-"):
            continue
        # a node id (`file.py::test_name`) narrows to its file: the red run often
        # names one test and the green run the whole file, and they are the same
        # target for this question.
        path = token.split("::", 1)[0]
        if path.endswith(".py") or "/" in path:
            return path
    return "run_local_tests.py" if _RUNNER_RE.search(command) else "pytest"


def had_red_before_green(records, target):
    """Did a FAILING run of `target` precede a PASSING one, in record order?

    False on an empty history by design: no evidence is not evidence of TDD. The
    caller distinguishes "did not happen" from "was not recorded" — this function
    only answers what the records show.
    """
    if not target:
        return False
    seen_red = False
    for rec in records or []:
        script = str(rec.get("script") or "")
        if not script.startswith("pytest:"):
            continue
        if target not in script[len("pytest:"):]:
            continue
        try:
            failed = int(rec.get("exit") or 0) != 0
        except (TypeError, ValueError):
            continue
        if failed:
            seen_red = True
        elif seen_red:
            return True
    return False


# --- crash audit (ported PS as-is, env names re-prefixed) --------------------

_LOG_NAME = "hook-crashes.log"
_LOG_MAX_BYTES = 256 * 1024  # coarse cap; over this we rotate to .1 then truncate


def yaml_load(text):
    """The one shared YAML read, delegated to yaml_io.yaml_load (ruamel.yaml,
    C-accelerated via ruamel.yaml.clib).

    ── WHY THIS DELEGATES INSTEAD OF PARSING HERE ────────────────────────────────
    Ruling (docs decisions, 2026-07-29, re-affirmed 2026-08-02): replace PyYAML
    with ruamel.yaml everywhere — a partial swap ("hooks stay on PyYAML, the rest
    moves") recreates the exact thing the ruling forbids, two YAML readers with
    two meanings for one file. yaml_io.py (harness/scripts/) is the SINGLE place
    that imports ruamel.yaml; this function is a thin call-through so every
    caller of hook_runtime.yaml_load keeps working unchanged.

    ── WHY THIS WAS PyYAML+CSafeLoader BEFORE, AND WHAT CHANGED ─────────────────
    The prior version resolved `getattr(yaml, "CSafeLoader", yaml.SafeLoader)`
    once and cached the LOADER CLASS. ruamel resolves its C parser
    (`ruamel.yaml.clib`) on the YAML() INSTANCE instead (`pure=False`, the
    default) — yaml_io._loader() caches that instance the same way this module
    used to cache the class. The one behavior change worth knowing: ruamel's
    safe loader raises DuplicateKeyError on a repeated mapping key where PyYAML
    silently kept the last value (see test_yaml_io.py).

    `import yaml_io` stays LAZY (module import happens on first call), matching
    this module's convention that telemetry/nudge paths must not explode if a
    dependency is missing; the compliance wrapper is what turns that into exit 2.

    Callers still catch yaml.YAMLError / ruamel's YAMLError — same exception
    family shape as before, pinned by test_yaml_fast_loader.py.
    """
    try:
        import yaml_io
    except ImportError:
        sys.path.append(str(_hooks_dir().parent / "scripts"))
        import yaml_io
    return yaml_io.yaml_load(text)


def _hooks_dir() -> Path:
    return Path(__file__).resolve().parent


def _log_dir() -> Path:
    # HARNESS_HOOK_LOG_DIR lets tests redirect the crash log to a tmp dir.
    raw = os.environ.get("HARNESS_HOOK_LOG_DIR")
    return Path(raw) if raw else _hooks_dir() / ".logs"


def _audit_disabled() -> bool:
    # Always-on by default; off via env, and silent under pytest so test runs
    # never write the real crash log.
    return bool(
        os.environ.get("HARNESS_HOOK_AUDIT_DISABLED")
        or os.environ.get("PYTEST_CURRENT_TEST")
    )


def log_hook_error(hook_name, exc) -> None:
    """Append ONE line (UTC ts, hook, exc type, message, traceback tail) to
    hook-crashes.log. Itself fail-open: any IO error is swallowed. Logs
    exception metadata ONLY, never the stdin payload (no PII leak)."""
    if _audit_disabled():
        return
    try:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        tb_tail = tb.strip().splitlines()[-1] if tb.strip() else ""
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "hook": str(hook_name),
                "type": type(exc).__name__,
                "msg": str(exc)[:500],
                "tb": tb_tail[:500],
            },
            ensure_ascii=False,
        )
        d = _log_dir()
        d.mkdir(parents=True, exist_ok=True)
        p = d / _LOG_NAME
        try:
            if p.stat().st_size > _LOG_MAX_BYTES:
                p.replace(d / (_LOG_NAME + ".1"))
        except OSError:
            pass  # no file yet, or unstattable — nothing to rotate
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # fail-open: a crash logger must never crash a hook


# --- stdin / stdout skeleton (ported PS as-is) --------------------------------

def _parse(raw) -> dict:
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_stdin_json() -> dict:
    """Read stdin and parse it as a JSON object. Empty/malformed → {} (fail-open)."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    return _parse(raw)


def bash_command(data: dict) -> str:
    """The Bash tool's command string from a PreToolUse payload, coerced to
    str ("" when the payload shape is unexpected or the command is absent or
    non-string). Centralizes the boundary guard every PreToolUse(Bash) gate runs
    before stage detection, so the "what is a non-string command" answer lives
    in one place."""
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return command if isinstance(command, str) else ""


def emit_continue() -> None:
    """Emit the non-blocking contract: {"continue": true} on stdout."""
    try:
        sys.stdout.write(json.dumps({"continue": True}))
        sys.stdout.flush()
    except Exception:
        pass  # fail-open


def emit_system_message(text: str) -> None:
    """Emit the CC-spec-guaranteed user-visible field (`SyncHookJSONOutput.
    systemMessage`, docs/product/_refs/claude-agent-sdk/CATALOG.md sec.3) alongside
    `continue: true`. A HIGH-priority / security-and-ops nudge whose stderr-on-
    exit-0 advisory is otherwise invisible to a human uses this instead of
    `sys.stderr.write` (H2-resolved, INV-3 F-2). Fail-open like emit_continue.

    A hook's stdout is ONE JSON blob -- this writes it, so the CALLER must not
    also call emit_continue() in the same invocation (see each hook's own
    single-stdout-write guard, e.g. a per-module `_STDOUT_WRITTEN` flag)."""
    try:
        sys.stdout.write(json.dumps({"continue": True, "systemMessage": text}))
        sys.stdout.flush()
    except Exception:
        pass  # fail-open


# Opt-in queue: a COMPLIANCE hook's core() may want a soft/advisory line to reach
# the spec-guaranteed systemMessage field, but core() must never write stdout
# itself -- run_compliance_hook owns the hook's ONE terminal JSON write (the
# fail-closed contract lives there). queue_system_message() lets core() mark that
# line; the wrapper drains it into the SAME stdout write it would have made
# anyway (no double-write, no change to any OTHER compliance hook that never
# calls this -- the queue is empty for them, so _drain_system_messages() is a
# silent no-op and behavior is byte-identical to before).
_pending_system_messages = []


def queue_system_message(text: str) -> None:
    """Opt-in: a compliance core() calls this (instead of stderr) to mark an
    advisory that should reach the human via systemMessage once the wrapper's
    single terminal stdout write happens. Never writes stdout itself."""
    _pending_system_messages.append(str(text))


def _drain_system_messages() -> str:
    """Pop + join every queued message (newline-joined), clearing the queue so a
    later invocation in the same process never sees a stale leftover."""
    global _pending_system_messages
    msgs = _pending_system_messages
    _pending_system_messages = []
    return "\n".join(msgs) if msgs else ""


def _reset_pending_system_messages() -> None:
    """Test seam: drop any queued-but-undrained message (mirrors
    _reset_config_cache). Guards against a prior test's core() queuing a
    message then hitting an exception path that skips the drain."""
    global _pending_system_messages
    _pending_system_messages = []


# --- nudge visibility router (3 sinks, config-driven — INV-3 F-2) -------------
#
# HOOK_CLASS picks the FAILURE posture (fail-open vs fail-closed); it does NOT
# say who an advisory reaches. That is a separate, configurable axis: visibility
# is THREE INDEPENDENT booleans, not one sink enum --
#   model   -> record a `<name>_observation`; nudge_context_inject re-surfaces it
#              to the MODEL as additionalContext next turn.
#   user    -> shown to the HUMAN this turn (emit/queue_system_message).
#   stderr  -> `[advisory] ...` on stderr; exit-0 stderr reaches NOBODY (debug log
#              only), but a fail-closed hook's exit-2 stderr IS the block reason.
# The four legacy sink names survive only as back-compat sugar over those flags:
#   off = {model:false,user:false} · stderr = +{stderr:true} · relay = model-only
#   · systemMessage = model+user. No shipped config uses them.
#
# The map lives in harness/data/nudge-channels.yaml (human-edited); a repo owner
# MAY point HARNESS_NUDGE_CHANNELS at an override file (e.g. .harness-dev/ with
# `default: systemMessage` so a dev sees every nudge). Precedence, load-bearing:
#   per-name file entry > file-global `default:` (only when the file sets one)
#   > the caller's code-level default_channel > "stderr".
# Ship OMITS `default:`, so an unlisted security nudge keeps its code default
# (systemMessage) instead of being silenced. A broken/absent file fails OPEN to
# the caller default -- a visibility router must never crash or block a hook.

_NUDGE_CHANNELS_NAME = "nudge-channels.yaml"
_VALID_CHANNELS = ("relay", "systemMessage", "stderr", "off")
_nudge_channels_cache = None  # None = not yet loaded

# THREE independent output flags, not one tangled sink enum. A nudge can reach the
# model, the human-always, and/or the human-on-error — independently:
#   model -> record a `<name>_observation` (resurfaced to the MODEL as
#            additionalContext next UserPromptSubmit / folded into the /goal reinject).
#   user  -> queue a `systemMessage` the HUMAN sees THIS turn (unconditional).
#   stderr-> write an `[advisory]` line to stderr. Silent on exit 0 (a fail-open
#            nudge), BUT on exit 2 (a fail-closed hook that blocks) CC surfaces it to
#            the user AND feeds it to the model as the block reason. So stderr =
#            ERROR-ONLY visibility — DISTINCT from `off` (never visible). Do not
#            conflate the two: off drops the advisory entirely; stderr keeps it as the
#            block message a compliance hook shows only when it actually stops the op.
# The legacy 1-D sink NAMES are accepted as sugar and mapped here — a `systemMessage`
# that (post fix) ALSO reached the model is exactly the ambiguity this split removes.
#   relay = model-only · systemMessage = both · stderr = error-only · off = never
_AXES_FROM_CHANNEL = {
    "relay":         {"model": True,  "user": False, "stderr": False},
    "systemMessage": {"model": True,  "user": True,  "stderr": False},
    "stderr":        {"model": False, "user": False, "stderr": True},
    "off":           {"model": False, "user": False, "stderr": False},
}


def _axes_to_channel(ax) -> str:
    """Collapse resolved axes back to the closest legacy sink name (compat shim for
    nudge_channel / tests): both -> systemMessage, model-only -> relay, debug-only ->
    stderr, else off."""
    if ax.get("user") and ax.get("model"):
        return "systemMessage"
    if ax.get("model"):
        return "relay"
    if ax.get("stderr"):
        return "stderr"
    return "off"


def _norm_entry(v):
    """A YAML value → resolved axes {model,user,stderr}, or None to drop.
    Accepts BOTH the new 2-axis mapping `{model: bool, user: bool[, stderr: bool]}`
    AND a legacy sink string / bare `off` (YAML 1.1 folds a bare `off` → False)."""
    if v is False:  # bare `off`
        return dict(_AXES_FROM_CHANNEL["off"])
    if isinstance(v, str) and v in _AXES_FROM_CHANNEL:
        return dict(_AXES_FROM_CHANNEL[v])
    if isinstance(v, dict) and ("model" in v or "user" in v or "stderr" in v):
        return {"model": bool(v.get("model", False)),
                "user": bool(v.get("user", False)),
                "stderr": bool(v.get("stderr", False))}
    return None


def _norm_channel(v):
    """Back-compat shim: a YAML value → the legacy sink STRING (or None to drop),
    derived from the resolved axes. Retained for any caller still thinking in sinks."""
    ax = _norm_entry(v)
    return _axes_to_channel(ax) if ax is not None else None


def _nudge_channels_path() -> Path:
    override = os.environ.get("HARNESS_NUDGE_CHANNELS")
    if override:
        return Path(override)
    return _hooks_dir().parent / "data" / _NUDGE_CHANNELS_NAME


def _load_nudge_channels() -> dict:
    """Parse the channel map once per process. Malformed/unreadable/missing-PyYAML
    or a bogus env path ⇒ {default:None, channels:{}} (every nudge then falls to
    its caller default) + a crash-log line. Never raises."""
    global _nudge_channels_cache
    if _nudge_channels_cache is not None:
        return _nudge_channels_cache
    cfg = {"default": None, "channels": {}}
    try:
        p = _nudge_channels_path()
        # env override that points at a missing/unreadable file → fall back to the
        # tracked ship file, so a stale HARNESS_NUDGE_CHANNELS never blanks the map.
        if os.environ.get("HARNESS_NUDGE_CHANNELS") and not p.is_file():
            p = _hooks_dir().parent / "data" / _NUDGE_CHANNELS_NAME
        if p.is_file():
            raw = yaml_load(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                d = _norm_entry(raw.get("default"))
                if d is not None:
                    cfg["default"] = d
                ch = raw.get("channels")
                if isinstance(ch, dict):
                    cfg["channels"] = {
                        str(k): _norm_entry(v) for k, v in ch.items()
                        if _norm_entry(v) is not None
                    }
    except Exception as e:  # noqa: BLE001 — a visibility router must not crash a hook
        log_hook_error("hook_runtime", e)
        cfg = {"default": None, "channels": {}}
    _nudge_channels_cache = cfg
    return cfg


def _reset_nudge_channels_cache() -> None:
    """Test seam: force a re-read of the channel map (mirrors _reset_config_cache)."""
    global _nudge_channels_cache
    _nudge_channels_cache = None


def nudge_axes(name, default_channel="stderr") -> dict:
    """Resolve the {model,user,stderr} axes for nudge `name`. Precedence: a per-name
    entry > the file-global `default:` (only when the file sets one) > the caller's
    code-level default_channel (a legacy sink name) > stderr. Fail-open to the caller
    default — a visibility resolver never crashes a hook."""
    try:
        cfg = _load_nudge_channels()
        ax = cfg["channels"].get(name)
        if isinstance(ax, dict):
            return ax
        d = cfg.get("default")
        if isinstance(d, dict):
            return d
    except Exception as e:  # noqa: BLE001 — fail-open to the caller default
        log_hook_error("hook_runtime", e)
    return dict(_AXES_FROM_CHANNEL.get(default_channel, _AXES_FROM_CHANNEL["stderr"]))


def nudge_channel(name, default_channel="stderr") -> str:
    """Back-compat shim: the legacy sink STRING for `name`, derived from its resolved
    axes. Prefer nudge_axes() in new code — the sink name loses the model/user split."""
    return _axes_to_channel(nudge_axes(name, default_channel))


def nudge_relay_names() -> list:
    """Names that reach the model but NOT the human (model-only: the legacy `relay`
    sink, now axes model=True & user=False). Per-name entries only, NOT a file-global
    default — a global would name every hook, including ones that record no observation."""
    try:
        cfg = _load_nudge_channels()
        return [n for n, ax in cfg.get("channels", {}).items()
                if isinstance(ax, dict) and ax.get("model") and not ax.get("user")]
    except Exception as e:  # noqa: BLE001 — fail-open
        log_hook_error("hook_runtime", e)
        return []


def nudge_observation_names() -> list:
    """Names whose model axis is on (they record a `<name>_observation` — the MODEL
    bus): the legacy `relay` AND `systemMessage` sinks both qualify (systemMessage is
    an additive human layer over the model bus, not a replacement). The generic
    resurface pass uses THIS (not nudge_relay_names) so a both-axes nudge still reaches
    the model, not just the human. Per-name entries only, not a file-global default."""
    try:
        cfg = _load_nudge_channels()
        return [n for n, ax in cfg.get("channels", {}).items()
                if isinstance(ax, dict) and ax.get("model")]
    except Exception as e:  # noqa: BLE001 — fail-open
        log_hook_error("hook_runtime", e)
        return []


def _record_nudge_observation(name, text, *, session, actor=None) -> None:
    """Append a `<name>_observation` for the relay sink (read by
    nudge_context_inject). Best-effort; append_event swallows its own errors."""
    import trace_log
    trace_log.append_event(hook=name, event="%s_observation" % name,
                           actor=actor, session=session,
                           status="observed", note=str(text))


def emit_nudge_and_continue(name, text, data=None, *,
                            default_channel="stderr") -> None:
    """For a hand-rolled nudge main() that owns its own stdout write: route `text`
    to its configured sink, then emit the hook's SINGLE terminal blob (a
    systemMessage if the sink queued one, else a plain continue). Drop-in for the
    old `sys.stderr.write(text); emit_continue()` pair. `data` supplies session_id
    for the relay sink."""
    session = data.get("session_id") if isinstance(data, dict) else None
    emit_nudge(name, text, session=session, default_channel=default_channel)
    queued = _drain_system_messages()
    if queued:
        emit_system_message(queued)
    else:
        emit_continue()


def route_relay_nudge(name, text, record_obs, *, default_channel="relay") -> None:
    """Router for a nudge that records its OWN bespoke `<family>_observation` (the
    caller passes `record_obs`). Dispatches on the resolved {model,user} axes WITHOUT
    writing terminal stdout:
      model -> call record_obs() (the observation is the model's channel — resurfaced
               at the next UserPromptSubmit OR folded into the /goal reinject reason);
      user  -> queue the advisory as a systemMessage (the hook's main() drains it).
    The two are INDEPENDENT: both on (legacy `systemMessage`) reaches both; model-only
    (legacy `relay`) reaches the model quietly; user-only reaches only the human; a
    bare `stderr`/neither writes a debug `[advisory]` line that reaches nobody on
    exit 0. Fail-open: any error is logged and swallowed."""
    if not text:
        return
    try:
        ax = nudge_axes(name, default_channel)
        if ax.get("model"):
            record_obs()
        if ax.get("user"):
            # leading newline: content drops below CC's "<Event> says:" label line
            queue_system_message("\n" + text)
        # legacy debug echo (relay/stderr sinks) — only when nothing reached the human.
        if not ax.get("user") and (ax.get("model") or ax.get("stderr")):
            sys.stderr.write("[advisory] %s\n" % text)
    except Exception as e:  # noqa: BLE001 — advisory routing must never raise
        log_hook_error(name, e)


def drain_or_continue() -> None:
    """Terminal write for a hand-rolled nudge main(): emit a queued systemMessage
    (from route_relay_nudge / emit_nudge) if any, else a plain continue. Replaces a
    bare emit_continue() in mains that now route through the systemMessage queue."""
    queued = _drain_system_messages()
    if queued:
        emit_system_message(queued)
    else:
        emit_continue()


def emit_nudge(name, text, *, kind=None, session=None, actor=None,
               default_channel="stderr") -> None:
    """Route a nudge advisory `text` on its resolved {model,user} axes WITHOUT writing
    the hook's terminal stdout blob:
      model -> record the `<name>_observation` (the model's channel; needs a `session`
               to record on — an anonymous model-only nudge degrades to a stderr line
               so it isn't silently lost);
      user  -> queue a systemMessage for the human.
    Both are independent (legacy `systemMessage` = both, `relay` = model-only,
    `stderr`/neither = a debug line reaching nobody on exit 0). The observation is the
    ONLY way a nudge reaches the model — a systemMessage never enters model context —
    so it fires whenever the model axis is on. Fail-open: errors are logged, swallowed."""
    if not text:
        return
    try:
        ax = nudge_axes(name, default_channel)
        if ax.get("model") and session:
            _record_nudge_observation(name, text, session=session, actor=actor)
        if ax.get("user"):
            # leading newline: content drops below CC's "<Event> says:" label line
            queue_system_message("\n" + text)
        # stderr leg: the legacy `stderr` sink, OR a model nudge with no session to
        # record on (degrade). Never when the human already saw it via systemMessage.
        if not ax.get("user") and (ax.get("stderr") or (ax.get("model") and not session)):
            sys.stderr.write("[advisory] %s\n" % text)
    except Exception as e:  # noqa: BLE001 — advisory routing must never raise
        log_hook_error(name, e)


# --- per-hook config (YAML, enabled/mode overrides ONLY) ----------------------

_CONFIG_NAME = "harness-hooks.yaml"

# Per-class defaults. The compliance row is the deliberate inversion of the
# source corpus: a gate that ships asleep protects nothing.
_CLASS_DEFAULTS = {
    "telemetry": {"enabled": True, "mode": "advisory"},
    "nudge": {"enabled": False, "mode": "advisory"},
    "compliance": {"enabled": True, "mode": "blocking"},
}

_config_cache = None  # module-level; None = not yet loaded


def _config_path() -> Path:
    # The BASE layer. HARNESS_HOOK_CONFIG (tests, dev tree) replaces it outright —
    # deliberately a replacement, because that is what a test seam is for; the
    # per-project layer below is the one that merges. Otherwise the shipped default
    # lives in harness/data/ (the config home, alongside stage-policy/guard-policy/…),
    # resolved off __file__ (durable, not CWD/env).
    raw = os.environ.get("HARNESS_HOOK_CONFIG")
    return Path(raw) if raw else _hooks_dir().parent / "data" / _CONFIG_NAME


def _overlay_path() -> Path:
    """The per-project layer: one file in THIS project's writeable data home.

    Under a shared-bin install the base is read-only and shared, so a project that
    wants one nudge on would otherwise have to edit the file every other project
    reads. This path is per-project by construction — `data_root()` is the project
    zone — and it is a LAYER, never a replacement (see `hook_config_document`).
    """
    raw = os.environ.get("HARNESS_HOOK_OVERLAY")
    if raw:
        return Path(raw)
    try:
        scripts = str(_hooks_dir().parent / "scripts")
        if scripts not in sys.path:
            sys.path.append(scripts)
        import harness_paths
        return harness_paths.data_root() / _CONFIG_NAME
    except Exception:  # noqa: BLE001 — an unresolvable project home means no layer
        return _hooks_dir().parent / "data" / ".no-project-overlay"


def _read_doc(path: Path) -> dict:
    """One YAML document, or {} for anything unreadable. Never raises."""
    try:
        if not path.is_file():
            return {}
        raw = yaml_load(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as e:  # noqa: BLE001 — malformed config must never crash a hook
        log_hook_error("hook_runtime", e)
        return {}


def _merge_docs(base: dict, over: dict) -> dict:
    """Layer `over` onto `base`: top-level keys replace, `hooks:` merges per NAME,
    and each named entry merges per KEY.

    Replacing instead of merging is the measured defect this function exists for —
    a bound override naming 12 hooks silently took nine shipped-enabled hooks off,
    because a name it did not mention fell through to its class default. A project
    saying "this one nudge, off" must not be read as "and nothing else applies".
    """
    merged = dict(base)
    for key, val in over.items():
        if key != "hooks":
            merged[key] = val
    over_hooks = over.get("hooks")
    if not isinstance(over_hooks, dict):
        return merged
    hooks = {}
    base_hooks = base.get("hooks")
    if isinstance(base_hooks, dict):
        hooks = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base_hooks.items()}
    for name, entry in over_hooks.items():
        cur = hooks.get(name)
        if isinstance(cur, dict) and isinstance(entry, dict):
            cur.update(entry)
        else:
            hooks[name] = dict(entry) if isinstance(entry, dict) else entry
    merged["hooks"] = hooks
    return merged


def hook_config_document() -> dict:
    """The WHOLE resolved config — `hooks:` plus the top-level knobs — after the
    per-project layer is applied. Read this rather than the file: a caller that
    opens `_config_path()` itself sees the shipped answer and misses the project's.
    """
    doc, _ = _resolve_config()
    return doc


def hook_config_overlay_names() -> list:
    """The hook names the project layer changed, sorted. An override nobody can see
    is how the measured defect stayed invisible; this is what lets a report say why
    a hook did not run instead of leaving the reader to guess."""
    _, names = _resolve_config()
    return names


def _resolve_config():
    """(merged document, overlay names) — parsed once per process."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    base = _read_doc(_config_path())
    over = _read_doc(_overlay_path())
    names = sorted(over["hooks"]) if isinstance(over.get("hooks"), dict) else []
    _config_cache = (_merge_docs(base, over), names)
    return _config_cache


def _load_config() -> dict:
    """The `hooks:` block of the resolved document. Malformed/unreadable/missing-PyYAML
    ⇒ {} (every hook then falls to its per-class default) + a crash-log line.
    The lazy yaml import keeps telemetry/nudge importable without PyYAML."""
    hooks = _resolve_config()[0].get("hooks")
    return hooks if isinstance(hooks, dict) else {}


def _reset_config_cache() -> None:
    """Test seam: drop the per-process config cache so a fresh file is re-read."""
    global _config_cache
    _config_cache = None


def _telemetry_globally_disabled() -> bool:
    return bool(os.environ.get("HARNESS_TELEMETRY_DISABLED"))


def _hook_entry(name: str) -> dict:
    entry = _load_config().get(name)
    return entry if isinstance(entry, dict) else {}


def _guard_policy_mode(name: str):
    """The unified posture for a REGISTERED guard ('off'|'warn'|'block'), or
    None if `name` is not a registered guard or the posture engine is
    unavailable. Lazy + defensive: guard_policy lives in ../scripts and imports
    trace_log (which imports this module), so importing it at call time avoids a
    cycle, and any failure degrades to None so the caller falls to its class
    default -- the posture bridge must never break a hook."""
    try:
        import guard_policy  # lazy: avoid an import cycle
    except Exception:  # noqa: BLE001
        try:
            sys.path.append(str(_hooks_dir().parent / "scripts"))
            import guard_policy
        except Exception:  # noqa: BLE001
            return None
    if name not in guard_policy.GUARD_REGISTRY:
        return None
    try:
        return guard_policy.resolve_mode(name)
    except Exception:  # noqa: BLE001 -- malformed policy must not crash a hook
        return None


def _class_defaults(hook_class: str, name: str = "?") -> dict:
    """The defaults for ``hook_class``, or raise on a class that is not one of
    the three.

    ── WHY THIS RAISES (this used to be a .get(..., _CLASS_DEFAULTS["nudge"])) ──
    An unrecognised class fell back to `nudge`, and nudge defaults to DISABLED.
    So a class name that was merely MISSPELT in the dispatch registry switched
    the hook off -- and because hook_dispatch skips a disabled hook by its
    REGISTRY class, the compliance-only `_skip_trace_once` audit line did not run
    either. The gate vanished with no verdict, no stderr and no trace.

    Measured on the live tree (2026-07-29, ship config, 15 compliance cores):
    a mistyped class disabled exactly 3 of them and left 12 standing. The
    survivors were not luckier -- each is named in guard-policy.yaml's
    GUARD_REGISTRY or in harness-hooks.yaml, so a second config plane answered
    the enabled question before the class default was ever consulted. The three
    that leant on the class default alone were disabled_skill_router,
    floor_bash_guard and protected_ref_guard: the skill cage, the Bash-write
    floor and the protected-branch fence.

    A caller passing a class this module does not know is a BUG in that caller,
    not a state to degrade through. Every hook passes its own HOOK_CLASS literal;
    the only config-derived callers (hook_dispatch, hs_cli) both funnel an
    exception into a fail-closed exit, and hook_dispatch.load_registry now
    rejects a bad class before it can reach here at all -- this is the backstop
    for the standalone path, not the primary check.
    """
    try:
        return _CLASS_DEFAULTS[hook_class]
    except (KeyError, TypeError):
        raise ValueError(
            "unknown hook class %r for hook %s -- must be one of %s. A misspelt "
            "class used to disable the hook silently; it now fails loudly."
            % (hook_class, name, ", ".join(sorted(_CLASS_DEFAULTS)))) from None


def hook_enabled(name: str, hook_class: str) -> bool:
    """Is hook ``name`` of ``hook_class`` enabled?

    Precedence: an explicit bool `enabled` in config wins (back-compat); else
    the unified guard policy when `name` is a registered guard (off => off);
    else the class default. The HARNESS_TELEMETRY_DISABLED kill-switch forces
    telemetry OFF and has no effect on nudge/compliance. `hook_class` comes from
    the hook's own HOOK_CLASS constant -- config cannot reclassify a hook.

    Raises ValueError on a class outside {telemetry, nudge, compliance}; see
    _class_defaults for why that is not degraded to a default.
    """
    defaults = _class_defaults(hook_class, name)
    if hook_class == "telemetry" and _telemetry_globally_disabled():
        return False
    val = _hook_entry(name).get("enabled")
    if isinstance(val, bool):
        return val
    gmode = _guard_policy_mode(name)
    if gmode is not None:
        return gmode != "off"
    return defaults["enabled"]


def hook_mode(name: str, hook_class: str) -> str:
    """Enforcement mode for an ENABLED hook: 'blocking' | 'advisory'.

    telemetry/nudge: always advisory; config cannot escalate them to blocking.
    compliance precedence: an explicit `mode` of 'advisory'/'blocking' in config
    wins (back-compat); else the unified guard policy when `name` is registered
    (warn => advisory, block => blocking); else blocking -- the safe default for
    a gate is to gate.

    Raises ValueError on an unknown class, for the same reason hook_enabled does
    (see _class_defaults). The shape here was the sibling of that bug: the test
    below is `!= "compliance"`, so EVERY unrecognised class -- including a
    misspelt "compliance" -- was answered 'advisory', i.e. a gate that no longer
    gates. Validating first is what makes the two answers agree about which
    classes exist.
    """
    _class_defaults(hook_class, name)
    if hook_class != "compliance":
        return "advisory"
    explicit = _hook_entry(name).get("mode")
    if explicit in ("advisory", "blocking"):
        return explicit
    gmode = _guard_policy_mode(name)
    if gmode is not None:
        return "advisory" if gmode == "warn" else "blocking"
    return "blocking"


# --- actor resolution -------------------------------------------

# Sentinel rather than "" so an EMPTY answer counts as answered: "git has no email
# configured" is a real result, and re-spawning git on every call to rediscover it
# is most of the cost this removes (1.9-6.2 ms per spawn against 0.148 ms warm).
_IDENTITY_UNSET = object()
_git_email_cache = _IDENTITY_UNSET


def _reset_identity_cache() -> None:
    """Drop the memoised git identity. For tests — a hook process is short-lived
    and has no reason to call this."""
    global _git_email_cache
    _git_email_cache = _IDENTITY_UNSET


def _git_user_email() -> str:
    """The git-configured email, memoised for the life of the process.

    Only THIS lookup is cached, never the assembled actor string: the CI markers,
    HARNESS_USER, the per-session cache and the HARNESS_AGENT suffix are all
    re-read by resolve_actor on every call, and freezing the whole string would
    pin a value a caller is entitled to change mid-process (an agent suffix being
    the obvious one)."""
    global _git_email_cache
    if _git_email_cache is not _IDENTITY_UNSET:
        return _git_email_cache
    try:
        out = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=5,
        )
        value = out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        value = ""
    _git_email_cache = value
    return value


def _state_dir() -> Path:
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    # Global install (HARNESS_BIN_ROOT set, bin != project): per-project runtime
    # state belongs in the PROJECT's .harness/, never the shared binary. Delegate
    # to harness_paths (data_root()/state) so trace/telemetry/session-cache/mutation
    # snapshots isolate per project. Self-host (HARNESS_BIN_ROOT unset) keeps the
    # legacy state next to this module (harness/state) — dogfood + the suite depend
    # on that path. Fail-open: any resolution failure or an unresolved project root
    # falls through to the legacy dir rather than crashing the hook.
    if os.environ.get("HARNESS_BIN_ROOT"):
        try:
            scripts = str(_hooks_dir().parent / "scripts")
            if scripts not in sys.path:
                sys.path.append(scripts)
            import harness_paths
            sd = harness_paths.state_dir()
            if not harness_paths.data_root_unresolved(sd.parent):
                return sd
        except Exception:
            pass
    # Self-host legacy (harness/state). In a linked worktree this state must go
    # to the HOST, not fragment per worktree (F2). Anchor off _hooks_dir() — the
    # hook flavour NEVER keys off CLAUDE_PROJECT_DIR (R4) — and map the legacy
    # suffix (harness/state) onto the host. Fail-open: any failure -> legacy dir.
    try:
        scripts = str(_hooks_dir().parent / "scripts")
        if scripts not in sys.path:
            sys.path.append(scripts)
        import harness_paths
        host = harness_paths.worktree_host_root(_hooks_dir())
        if host is not None:
            return host / "harness" / "state"
    except Exception:
        pass
    return _hooks_dir().parent / "state"


def _safe_session_id(session_id: str) -> str:
    """Sanitize a session id for use as a single path component. A session id is
    normally a UUID from the host, but it is never trusted into a path: any char
    outside [A-Za-z0-9_-] is collapsed to '_' so it cannot traverse directories."""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in (session_id or "_"))



safe_session_id = _safe_session_id  # public name for the shared sanitizer


def shard_discriminator(session) -> "str | None":
    """A per-session filename discriminator, or None when there is no real
    session. SSOT for the trace/telemetry shard name: N worktrees pointed at one
    host state store (P1) shard their writes by session so concurrent sessions
    stop contending on a single daily file. NO pid fallback (R2) — a sessionless
    writer keeps the shared legacy file, which is safe because a single JSONL
    line is < PIPE_BUF (4096B) so O_APPEND stays atomic; a pid shard would sprawl
    and starve rotation. Sanitized to [A-Za-z0-9_-], capped at 12 chars."""
    if not session:
        return None
    disc = _safe_session_id(session)[:12]
    # _safe_session_id collapses a garbage id to all-'_'; an all-'_' disc is not
    # a real session — keep it on the shared legacy file rather than a junk shard.
    if not disc.strip("_"):
        return None
    return disc


def project_dir(stdin_cwd=None):
    """Resolve the project root the hooks scan. CLAUDE_PROJECT_DIR (set by the
    host) wins; the Stop/PostToolUse stdin `cwd` is the fallback. Returns None
    when neither is usable (empty string is treated as absent)."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or stdin_cwd or None

def resolve_actor(session_id=None) -> str:
    """Resolve the acting identity. Attribution, NOT authentication —
    env-derived, spoofable, never an authz signal.

    Order: CI marker → session file cache (optional — a hook must work when
    session_init never ran) → HARNESS_USER → git config user.email →
    $USER. Agent suffix from HARNESS_AGENT. Format: user:<u>[/agent:<a>] | ci.
    """
    if os.environ.get("CI") or os.environ.get("GITLAB_CI") or os.environ.get("GITHUB_ACTIONS"):
        return "ci"

    if session_id:
        try:
            p = _state_dir() / "sessions" / ("%s.json" % _safe_session_id(session_id))
            if p.is_file():
                cached = json.loads(p.read_text(encoding="utf-8")).get("actor")
                if cached:
                    return str(cached)
        except Exception:
            pass  # cache miss/corrupt → fall through to env chain

    user = (
        os.environ.get("HARNESS_USER")
        or _git_user_email()
        or os.environ.get("USER", "unknown")
    )
    actor = "user:%s" % user
    agent = os.environ.get("HARNESS_AGENT")
    if agent:
        actor += "/agent:%s" % agent
    return actor


# --- telemetry convenience wrapper (ported PS) ---------------------------------

_DEFAULT_CORE_TIMEOUT_S = 5.0


def run_core_isolated(core, data, timeout=None) -> dict:
    """Run ``core(data)`` in a daemon worker thread, observed from the main thread
    with ``join(timeout)``. Thin, posture-blind (the CALLER maps the outcome to a
    fail-open skip or a fail-closed block by the core's HOOK_CLASS). Returns:

      {"status": "ok", "value": <core return>}   core returned within the budget
      {"status": "error", "error": <exception>}  core raised
      {"status": "timeout"}                       core still running past the budget

    Portable by construction — a daemon thread + join, NOT signal.setitimer (which
    is Unix-only and would break the declared Windows target). Critically, a timeout
    does NOT inject an exception into the worker: the main thread simply observes the
    worker still alive, so a gate whose own body carries `except Exception: return
    None` cannot swallow the timeout signal (the F3 hole — VL-4/C1). The worker is a
    daemon, so a hung core dies with the process; its result box is per-call, never a
    shared global (VL-1 §9 — no cross-core leak). Never raises."""
    import threading
    box = {}

    def _work():
        try:
            box["value"] = core(data)
            box["status"] = "ok"
        except Exception as e:  # noqa: BLE001 — surfaced to the caller as status=error
            box["error"] = e
            box["status"] = "error"

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(_DEFAULT_CORE_TIMEOUT_S if timeout is None else timeout)
    if t.is_alive():
        return {"status": "timeout"}
    return box if box.get("status") else {"status": "error",
                                          "error": RuntimeError("core produced no result")}


def run_telemetry_hook(name, core, raw=None) -> None:
    """Skeleton for telemetry hooks: read stdin JSON (or ``raw``), check
    enabled; if disabled, emit continue WITHOUT running core. Core runs inside
    a fail-open guard routing exceptions to the crash log. ALWAYS continues."""
    data = read_stdin_json() if raw is None else _parse(raw)
    try:
        if hook_enabled(name, "telemetry"):
            core(data)
    except Exception as e:  # noqa: BLE001 — telemetry must never break the op
        log_hook_error(name, e)
    emit_continue()


# --- nudge wrapper -------------------------------------------------------------

def run_nudge_hook(name, core, raw=None, default_channel="stderr") -> None:
    """Skeleton for nudge hooks (default OFF): core(data) may return a message
    string → routed to its configured sink (relay/systemMessage/stderr/off) via
    emit_nudge, NOT hard-wired to stderr any more (INV-3 F-2). Always exits 0 /
    continues. The systemMessage sink queues its line; the terminal write drains
    it into the hook's single stdout blob (no double-write)."""
    data = read_stdin_json() if raw is None else _parse(raw)
    try:
        if hook_enabled(name, "nudge"):
            msg = core(data)
            if msg:
                session = data.get("session_id") if isinstance(data, dict) else None
                emit_nudge(name, msg, session=session, default_channel=default_channel)
    except Exception as e:  # noqa: BLE001 — a nudge must never break the op
        log_hook_error(name, e)
    queued = _drain_system_messages()
    if queued:
        emit_system_message(queued)
    else:
        emit_continue()


# --- compliance wrapper — fail-CLOSED, its own top-level guard ----------

def run_compliance_hook(name, core, raw=None, data=None) -> None:
    """Top-level wrapper for compliance hooks. NOT built on the telemetry
    skeleton: that one is fail-open by contract, a gate must be fail-closed.

    core(data) contract: return None ⇒ pass; return a string ⇒ block reason.
    EVERY exception raised by core — including ImportError from a machine
    that skipped preflight and config trouble — lands in the except arm and
    blocks with exit 2 + an actionable reason. In `mode: advisory` (explicit
    opt-in) the reason is warned to stderr and the op continues. Disabled
    (explicit `enabled: false`) ⇒ skip core, exit 0.

    Deliberate fail-open edge: empty or unparseable STDIN becomes {} (see
    read_stdin_json), so core sees no command and passes. Blocking every
    Bash call whenever the transport hiccups would be a denial-of-service on
    the whole session; a payload that cannot be parsed also yields no
    command to gate. The gate therefore fails closed on ITS OWN errors, and
    open on absent input.

    This function never raises and never exits 0 on a broken enabled gate.
    """
    try:
        if data is None:
            data = read_stdin_json() if raw is None else _parse(raw)

        if not hook_enabled(name, "compliance"):
            emit_continue()
            sys.exit(0)

        reason = core(data)
        if reason:
            if hook_mode(name, "compliance") == "advisory":
                sys.stderr.write("[advisory] %s: %s\n" % (name, reason))
                emit_continue()
                sys.exit(0)
            sys.stderr.write("[%s] BLOCKED: %s\n" % (name, reason))
            sys.exit(2)

        # A soft/advisory core() may have QUEUED a systemMessage line (e.g.
        # gate_stage's soft-stage / receipt-gap advisories, H2-resolved) instead
        # of writing stderr directly -- drain it into this SAME terminal write so
        # the hook's stdout stays one JSON blob. Every other compliance hook
        # never calls queue_system_message(), so the queue is always empty for
        # them and this is byte-identical to the old plain emit_continue().
        queued = _drain_system_messages()
        if queued:
            emit_system_message(queued)
        else:
            emit_continue()
        sys.exit(0)
    except SystemExit:
        raise
    except ImportError as e:
        # Missing dependency — point at the fix, then fail closed.
        log_hook_error(name, e)
        sys.stderr.write(
            "[%s] BLOCKED: dependency missing (%s).\n"
            "Run: python3 harness/scripts/preflight_deps.py\n"
            "or:  pip install 'ruamel.yaml' 'ruamel.yaml.clib' pytest\n" % (name, e)
        )
        sys.exit(2)
    except Exception as e:  # noqa: BLE001 — fail CLOSED, with audit trail
        log_hook_error(name, e)
        sys.stderr.write(
            "[%s] BLOCKED: gate crashed (%s: %s). Fail-closed by policy; "
            "see hook-crashes.log. To bypass IN AN EMERGENCY set "
            "`enabled: false` for this hook in harness/data/harness-hooks.yaml — the "
            "change is tracked in git and traced.\n" % (name, type(e).__name__, e)
        )
        sys.exit(2)


def _skip_marker_path(session_id, name) -> Path:
    """Per-(session, hook) marker recording that this session already traced a skip
    for this gate."""
    return _state_dir() / "skip-marks" / ("%s.%s" % (_safe_session_id(session_id), name))


def _skip_already_traced(session_id, name) -> bool:
    """True if this (session, hook) already recorded a skip this session. Fail-open:
    no session id, or any stat error, yields False — degrade to recording again (per
    call) rather than suppressing the audit entirely, and never raise."""
    if not session_id:
        return False
    try:
        return _skip_marker_path(session_id, name).is_file()
    except OSError:
        return False


def _mark_skip_traced(session_id, name) -> None:
    """Record that this (session, hook) traced its skip. Best-effort; an error just
    means the next call re-records (degrade to per-call, never a raise)."""
    if not session_id:
        return
    try:
        p = _skip_marker_path(session_id, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    except OSError:
        pass


def compliance_skip_or_run(name, core, *, skip_event, skip_note=None) -> None:
    """Compliance entry shared by the enforcement guards: read stdin once, and if
    the gate is disabled record a VISIBLE `<skip_event>` trace (run_compliance_hook
    exits silently on disabled, but a skipped gate DECISION must be auditable) then
    continue; otherwise delegate to run_compliance_hook with the already-parsed
    payload (no parse->serialize->parse round-trip).

    The skip trace is written ONCE per (session, hook): a marker keyed by the session
    id and gate name suppresses the repeat lines a wide always-disabled matcher would
    otherwise emit on every tool call. One line per session (plus the config git diff)
    still proves the skip decision. The trace write and the marker are both fail-open —
    a broken trace or an unwritable marker degrades to re-recording, never blocks the
    skip, and posture is unchanged (continue + exit 0)."""
    raw = read_stdin_json()
    if not hook_enabled(name, "compliance"):
        sid = raw.get("session_id")
        if not _skip_already_traced(sid, name):
            try:
                import trace_log
                trace_log.append_event(
                    hook=name, event=skip_event, session=sid,
                    note=skip_note if skip_note is not None
                    else "disabled via %s" % _config_path())
            except Exception as e:  # noqa: BLE001 — trace is telemetry, never blocks
                log_hook_error(name, e)
            _mark_skip_traced(sid, name)
        emit_continue()
        sys.exit(0)
    run_compliance_hook(name, core, data=raw)
