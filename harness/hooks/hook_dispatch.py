#!/usr/bin/env python3
"""hook_dispatch.py — ONE command per (event, matcher) group.

Claude Code spawns one process per registered hook per tool call. A busy
PreToolUse:Bash fires 8 separate Python interpreters; across all events that is
~61k spawns a day. This dispatcher replaces the N per-group commands with ONE:
it reads stdin once, loads the group's registry, and runs each hook's `core(data)`
IN-PROCESS under its correct HOOK_CLASS posture — no re-spawn, no stdin re-read.

Posture is preserved exactly (the whole point — a mixed fail-open/fail-closed loop
is the F3 hole). The contract (plan Validation Log VL-1, hardened through VL-4/VL-5):

  * Run order: telemetry + nudge cores FIRST (isolated, fail-open, timed) so their
    JSONL/trace side-effects are never dropped by a later block; compliance cores
    AFTER, in registry order.
  * Timeout: each core runs in a daemon worker thread observed with join(timeout)
    (hook_runtime.run_core_isolated — portable, no SIGALRM). telemetry/nudge timeout
    → skip (fail-open); compliance timeout → exit 2 (fail-closed). The main thread
    never injects into the worker, so a gate's own `except Exception` cannot swallow
    the timeout (C1).
  * Short-circuit: the first compliance core that returns a reason AND is in
    `blocking` mode stops the group, remaining cores skip. HOW it stops depends on
    _Block.kind: a VERDICT ("policy says no") denies through the PreToolUse JSON
    `permissionDecision:"deny"` shape at exit 0, so the model sees only the reason;
    a FAILURE (crash/timeout/unloadable module/unreadable registry/stdin error) keeps
    stderr `[name] BLOCKED: reason` + exit 2, which needs nothing from a process whose
    ability to emit valid stdout is exactly what is in doubt. Both block equally hard
    (s1-hook-contract C3 vs C11); only exit 2 leaks this dispatcher's command line into
    the model transcript. A verdict on any non-PreToolUse event falls back to exit 2 —
    CC reads permissionDecision there and nowhere else.
    A reason in `advisory` mode (e.g. simplify_gate shipped-ON) → `[advisory]` stderr
    + CONTINUE, no early stop (OVERTURN-1).
  * stdin: a genuine READ failure with any compliance core in the group → exit 2
    (fail-closed); an empty/unparseable payload → {} → continue (the anti-DoS
    fail-open contract, C4).
  * stdout merge on continue: ONE JSON — {continue:true} plus a joined systemMessage
    (drained per-core) plus a joined additionalContext, the latter ONLY for
    UserPromptSubmit / SessionStart (CC honors the field only there; Stop uses
    decision:block+reason). Queue drained per-core so a crashing core never leaks its
    partial systemMessage into a later core's blob (C8).
  * enabled:false in-loop → skip; a disabled compliance core still records a
    skip-trace once per session (inherits Phase 3).

Fail-open on the dispatcher's own telemetry side, fail-closed on any error while a
compliance core is still pending.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import hook_runtime  # noqa: E402

HOOK_CLASS = "compliance"  # the dispatcher inherits the strictest posture in its group
NAME = "hook_dispatch"

_REGISTRY_NAME = "hook-dispatch.yaml"
_ADDITIONAL_CONTEXT_EVENTS = ("UserPromptSubmit", "SessionStart")

# nudge-channels.yaml deliberately ships with NO file-global `default:` so an
# unlisted hook keeps its own CODE default (hook_runtime.emit_nudge's
# `default_channel` param) — e.g. a security advisory stays both/systemMessage
# rather than collapsing to the generic stderr fallback. That code default
# lives in the hook's OWN main()/standalone entry (`run_nudge_hook(...,
# default_channel=...)`), which the dispatcher never calls — it invokes the
# core function directly and passes emit_nudge no default_channel at all, so
# it silently falls back to emit_nudge's OWN hardcoded "stderr". Mirror each
# hook's non-default code default here so the dispatcher path carries the same
# visibility promise as the standalone path. Keep in sync with any nudge core
# whose main() passes a non-default `default_channel` to run_nudge_hook().
_NUDGE_DEFAULT_CHANNEL = {
    "methodology_review_gate": "systemMessage",
}


def _core_timeout_s() -> float:
    """Per-core timeout budget (seconds). Env-overridable so tests can shrink it;
    a bad value degrades to the 5s default."""
    try:
        return float(os.environ.get("HARNESS_DISPATCH_TIMEOUT", "5.0"))
    except (TypeError, ValueError):
        return 5.0


# --- registry -----------------------------------------------------------------

def _registry_path() -> Path:
    raw = os.environ.get("HARNESS_HOOK_DISPATCH_CONFIG")
    return Path(raw) if raw else Path(__file__).resolve().parent.parent / "data" / _REGISTRY_NAME


def _registration_path() -> Path:
    """hooks-registration.yaml — the installer's INPUT, hence the source of truth
    for which (event, matcher) pairs are supposed to exist at all.

    Read ONLY when a group lookup misses (see run()). Do not move this onto the
    hit path: that would add a YAML parse to every tool call, and the miss path
    does not execute at all in a healthy tree."""
    raw = os.environ.get("HARNESS_HOOK_REGISTRATION")
    return (Path(raw) if raw
            else Path(__file__).resolve().parent.parent / "install"
            / "hooks-registration.yaml")


def _is_registered(event: str, matcher: str):
    """Is (event, matcher) declared in hooks-registration.yaml?

    Returns True / False, or None when the registration cannot be read — and the
    None is load-bearing, not laziness. The caller uses this to decide whether a
    missing group means "a gate was lost" (block) or "the group was retired and
    settings.json is merely stale" (continue). "Retired" is a CLAIM; without a
    readable registration there is no evidence for it, so None must not collapse
    into either answer at this level."""
    p = _registration_path()
    if not p.is_file():
        return None
    try:
        raw = hook_runtime.yaml_load(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — unreadable is "unknown", not "absent"
        return None
    entries = raw.get("hooks") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return None
    for e in entries:
        if not isinstance(e, dict) or not e.get("event"):
            continue
        # Matchers compare verbatim: Claude Code matches tool names exactly, so
        # a case or spelling difference is a genuinely different wire.
        if str(e["event"]) == event and (e.get("matcher") or "*") == matcher:
            return True
    return False


class RegistryError(ValueError):
    """This registry cannot be trusted to say which hooks run.

    Distinct from "the file is missing/unparseable" only in provenance, not in
    consequence: run() funnels both into the same fail-closed exit 2, because a
    row the parser cannot make sense of is a hook whose very CLASS is unknown —
    there is no way to fail closed for compliance alone when the compliance
    marker is the thing that failed to parse."""


# The complete core-spec schema. Anything outside this set is a typo, and a typo
# on a key is invisible at runtime: the field silently reverts to its default,
# which for `class` is telemetry and for `fail_open` is False.
_SPEC_KEYS = frozenset(
    ("name", "module", "entry", "class", "kind", "fail_open", "timeout"))
_CLASSES = frozenset(("telemetry", "nudge", "compliance"))
_KINDS = frozenset(("additionalContext",))


def _core_spec(group_key: str, idx: int, c) -> dict:
    """Validate ONE registry row into a core-spec, or raise RegistryError.

    ── WHY THIS REJECTS INSTEAD OF SKIPPING (do not "restore" the skip) ────────
    This loop used to be `if not isinstance(c, dict) or not c.get("module"):
    continue`. Measured against the live tree on 2026-07-29, ship env: writing
    `modul:` for `module:` on the floor_bash_guard row turned `echo x >
    harness/hooks/evil.py` from BLOCK into ALLOW at exit 0, with EMPTY stderr and
    stdout byte-identical to a legitimate pass. The group still had other rows,
    so it was never empty, so the `dispatch_empty_group` warning below never
    fired and no audit trace was written. One mistyped character deleted a
    blocking gate with nothing left behind to notice it by.

    Every field is checked, not just the two that were measured, because each one
    degrades silently in its own way — see this module's own field comments and
    test_hook_dispatch_registry_strict.py for the enumeration. Messages name the
    group, the row index and the key so an operator can go straight to the line.
    """
    where = "hook-dispatch.yaml group %r row %d" % (group_key, idx)
    if not isinstance(c, dict):
        raise RegistryError(
            "%s is %s, expected a mapping like "
            "{name: …, module: …, entry: core, class: compliance}"
            % (where, "null" if c is None else "a %s" % type(c).__name__))
    unknown = sorted(set(map(str, c)) - _SPEC_KEYS)
    if unknown:
        raise RegistryError("%s has unknown key(s) %s — valid keys are %s"
                            % (where, ", ".join(repr(k) for k in unknown),
                               ", ".join(sorted(_SPEC_KEYS))))
    module = c.get("module")
    if not isinstance(module, str) or not module.strip():
        raise RegistryError("%s has no usable `module` (got %r)" % (where, module))

    cls = c.get("class", "telemetry")
    # Compared case-SENSITIVELY on purpose: `Compliance` is not `compliance`, and
    # accepting it here would only paper over a registry that lies about itself.
    # Downstream, hook_runtime._CLASS_DEFAULTS keys on the exact string.
    if cls not in _CLASSES:
        raise RegistryError("%s has class %r — must be one of %s"
                            % (where, cls, ", ".join(sorted(_CLASSES))))

    kind = c.get("kind")
    # kind is consumed by an equality test further down (`== "additionalContext"`),
    # so a near-miss spelling does not error — it just means the core's context
    # output is computed and then dropped on the floor.
    if kind is not None and kind not in _KINDS:
        raise RegistryError("%s has kind %r — must be omitted or one of %s"
                            % (where, kind, ", ".join(sorted(_KINDS))))

    # fail_open: a compliance hook whose crash/timeout is fail-open BY DESIGN
    # (e.g. simplify_gate — a heuristic advisory whose own main() never blocks
    # on an internal error). Only the crash/timeout path is affected; a
    # returned BLOCK reason still respects hook_mode. Default False = a crash
    # fails closed, the safe default for a real gate.
    #
    # Demand a REAL bool: this value used to go through bool(), under which every
    # non-empty string is true. `fail_open: "no"` therefore read as YES and
    # inverted the field's whole meaning, turning a fail-closed gate fail-open.
    fail_open = c.get("fail_open", False)
    if not isinstance(fail_open, bool):
        raise RegistryError(
            "%s has fail_open %r — must be true or false (an unquoted YAML bool; "
            "a quoted string is truthy and would silently open the gate)"
            % (where, fail_open))

    # per-hook timeout override (seconds): a core making a slow external call
    # (e.g. a partner-model spawn) needs longer than the default budget; None
    # → the group default. The hook's inherent latency is not the dispatcher's
    # to cap below what the standalone would wait. Validated here rather than at
    # use so the failure names the file instead of surfacing mid-dispatch.
    timeout = c.get("timeout")
    if timeout is not None and (isinstance(timeout, bool)
                                or not isinstance(timeout, (int, float))
                                or timeout <= 0):
        raise RegistryError("%s has timeout %r — must be omitted or a positive "
                            "number of seconds" % (where, timeout))

    return {"name": str(c.get("name") or module), "module": str(module),
            "entry": str(c.get("entry") or "core"), "class": str(cls),
            "kind": kind, "fail_open": fail_open, "timeout": timeout}


def load_registry(path=None) -> dict:
    """Parse the dispatch registry into {(event, matcher): [core-spec, ...]}.

    A core-spec is {name, module, entry, class, kind, fail_open, timeout}. Raises
    on a missing or unparseable file, and on any row that cannot be validated
    (see _core_spec) — the caller decides whether that is fail-closed (a wired
    group with a broken registry) vs a benign empty group. Group keys are
    'event:matcher'.

    A parsed-but-EMPTY group is still a legitimate no-op and is NOT an error here;
    that distinction lives at the call site. This function's contract is narrower:
    every row that exists must be meaningful."""
    p = Path(path) if path is not None else _registry_path()
    raw = hook_runtime.yaml_load(p.read_text(encoding="utf-8")) or {}
    out = {}
    for key, cores in (raw.get("groups") or {}).items():
        event, _, matcher = str(key).partition(":")
        specs = [_core_spec(str(key), i, c) for i, c in enumerate(cores or [])]
        out[(event, matcher or "*")] = specs
    return out


def _resolve_core(spec):
    """Import the spec's module and return (callable, hook_class). The module's own
    HOOK_CLASS constant wins over the registry's `class` (config cannot reclassify a
    hook — mirrors hook_enabled). Returns (None, class) if the entry is missing."""
    mod = __import__(spec["module"])
    fn = getattr(mod, spec["entry"], None)
    cls = getattr(mod, "HOOK_CLASS", None) or spec["class"]
    return fn, cls


# --- per-core execution -------------------------------------------------------

class _Block(Exception):
    """A compliance stop. `kind` picks WHICH door the process leaves by — the two are
    not interchangeable:

      "verdict" — a gate ran fine and said no. Denies through the PreToolUse JSON
                  `permissionDecision:"deny"` shape at exit 0, so the model receives
                  only `permissionDecisionReason`. Exit 2 would instead hand it CC's
                  `hook error: [<the dispatcher's whole command line>]` wrapper.
      "failure" — the gate never reached a verdict (crash, timeout, unloadable module,
                  unreadable registry, stdin read error). Keeps exit 2: the JSON door
                  requires this process to still emit well-formed stdout, which is the
                  very thing a failure puts in doubt.

    Defaults to "failure" — an un-annotated raise must land on the door that needs
    nothing from a process already suspect.
    """
    def __init__(self, reason, kind="failure"):
        super().__init__(reason)
        self.reason = reason
        self.kind = kind


def resolve_run_id(session, state_dir=None):
    """The `run_id` of the most recent `hs-run` invocation in `session`, or None.

    Resolved HERE, once per dispatch, beside `session_id` — not by each hook that
    wants it. Two hooks in one group each working out "the current run" for
    themselves will disagree, and the disagreement is silent. That already
    happened on this exact group: `spawn_provenance.count_in_window` carries an
    `exclude_tool_use_id` parameter that exists only because two hooks recorded
    the SAME spawn and then read each other's record as prior history, turning a
    budget of N into N-1. Central resolution is that fix applied at the source.

    LAST MATCHING LINE WINS, by append order rather than by `ts`. Two runs inside
    one clock tick tie on `ts`, and a stepped clock can invert it; append order is
    the only ordering an append-only store actually guarantees.

    None means NOT PROVABLE — never a guess. Falling back to the newest row of
    any session would credit a spawn in this session to a CLI call made in
    another one, which is a false PASS in the one direction that matters.

    Fail-open throughout: this runs before every hook in the group, and an
    exception would take down hooks that never asked about run_id — including a
    compliance gate whose job is to block."""
    if not session:
        return None
    try:
        import json as _json
        # Same lazy sibling-import shape this module already uses further down —
        # harness/ carries no __init__.py, so scripts/ is reachable only once it
        # is on the path, and doing it lazily keeps a hook dispatch that never
        # needs hs_run from paying the import.
        _scripts = str(Path(__file__).resolve().parent.parent / "scripts")
        if _scripts not in sys.path:
            sys.path.append(_scripts)
        import hs_run
        # `hs_run` owns the ledger format — including the torn-line tolerance
        # this block used to re-implement. A third parser of one on-disk format
        # is a third chance for it to drift.
        return hs_run.latest_run_id(session=session, state_dir=state_dir)
    except Exception:
        return None


def _run_group(event, matcher, data, specs):
    """Run every core in `specs` per the contract. Returns a continue-blob dict, or
    raises _Block(reason) for a fail-closed stop. `data` is the parsed stdin payload."""
    session = data.get("session_id") if isinstance(data, dict) else None
    # Resolved once and offered to every core through the payload, the same way
    # `session` already is. A hook that does not care simply never reads the key.
    if isinstance(data, dict) and "hs_run_id" not in data:
        data["hs_run_id"] = resolve_run_id(session)
    # telemetry + nudge FIRST (in registry order), compliance AFTER (registry order).
    ordered = ([s for s in specs if s["class"] != "compliance"] +
               [s for s in specs if s["class"] == "compliance"])

    sys_msgs = []
    addl_ctx = []
    for spec in ordered:
        name = spec["name"]
        reg_cls = spec["class"]
        # Cheap enabled-check BEFORE importing the module — a disabled hook must not
        # pay the per-dispatch import tax, and a disabled compliance hook with a
        # broken import must not fail the group closed. Uses the registry class
        # (import-free); a disabled hook does not run regardless of its true
        # HOOK_CLASS, so deciding to SKIP off the registry class cannot change a gate
        # outcome (the module HOOK_CLASS still governs every RUNNING core below).
        if not hook_runtime.hook_enabled(name, reg_cls):
            if reg_cls == "compliance":
                _skip_trace_once(name, session)
            continue

        # Enabled -> import + resolve. HOOK_CLASS constant is authoritative; fall back
        # to the registry class if the module cannot be imported cleanly (compliance =
        # safest assumption).
        try:
            core, cls = _resolve_core(spec)
        except Exception as e:  # noqa: BLE001
            if reg_cls == "compliance":
                hook_runtime.log_hook_error(name, e)
                raise _Block("dispatch: cannot load %s (%s)" % (name, e))
            hook_runtime.log_hook_error(name, e)
            continue
        if core is None:
            if cls == "compliance":
                raise _Block("dispatch: %s.%s missing" % (spec["module"], spec["entry"]))
            continue

        hook_runtime._reset_pending_system_messages()  # per-core clean slate (C8)
        _t0 = time.monotonic()
        _timeout = spec.get("timeout")
        _timeout = float(_timeout) if _timeout else _core_timeout_s()
        res = hook_runtime.run_core_isolated(core, data, timeout=_timeout)
        _emit_timing(event, matcher, name, cls, (time.monotonic() - _t0) * 1000.0,
                     res.get("status"))
        status = res.get("status")

        if status == "timeout":
            hook_runtime._reset_pending_system_messages()  # discard partial queue
            if cls == "compliance" and not spec.get("fail_open"):
                raise _Block("%s timed out (>%.1fs) — fail-closed" % (name, _core_timeout_s()))
            # fail-open-by-design compliance (e.g. simplify_gate) OR telemetry/nudge
            hook_runtime.log_hook_error(name, TimeoutError("%s core timeout" % name))
            continue

        if status == "error":
            hook_runtime._reset_pending_system_messages()  # discard partial queue
            err = res.get("error")
            hook_runtime.log_hook_error(name, err)
            if cls == "compliance" and not spec.get("fail_open"):
                raise _Block("%s crashed (%s) — fail-closed" % (name, type(err).__name__))
            continue

        value = res.get("value")
        if cls == "compliance":
            if value:  # a block reason
                if hook_runtime.hook_mode(name, "compliance") == "blocking":
                    hook_runtime._reset_pending_system_messages()
                    raise _Block("%s: %s" % (name, value), kind="verdict")
                # advisory reason: warn, do NOT stop (OVERTURN-1)
                sys.stderr.write("[advisory] %s: %s\n" % (name, value))
                hook_runtime._reset_pending_system_messages()
                continue
            # no reason — a soft compliance core may have queued a systemMessage
            q = hook_runtime._drain_system_messages()
            if q:
                sys_msgs.append(q)
            continue

        # telemetry / nudge core
        # kind wins over class: a hook may be nudge/telemetry-class for its FAILURE
        # posture yet produce a model-channel additionalContext (e.g. a Stop reinject or
        # a post-compaction resurface) rather than a routed nudge advisory.
        if spec.get("kind") == "additionalContext" and value:
            addl_ctx.append(value if isinstance(value, str) else str(value))
        elif cls == "nudge" and value:
            hook_runtime.emit_nudge(
                name, value, session=session,
                default_channel=_NUDGE_DEFAULT_CHANNEL.get(name, "stderr"))
        q = hook_runtime._drain_system_messages()
        if q:
            sys_msgs.append(q)

    return _assemble_blob(event, addl_ctx, sys_msgs)


# CC event name -> context_surface_config SSOT key (the injector chokepoint events).
# For these, the model channel + the OPTIONAL human systemMessage mirror (and Stop's
# decision:block/reason model channel) are owned by context_surface_config so every
# injector — and now the dispatcher — mirrors identically. Emitting additionalContext
# raw here would DROP the human mirror that the standalone hooks carry.
_CHOKEPOINT_EVENT_KEY = {
    "UserPromptSubmit": "user_prompt_submit",
    "SessionStart": "session_start",
    "SubagentStart": "subagent_start",
    "Stop": "stop",
}


def _assemble_blob(event, addl_ctx, sys_msgs):
    """Build the ONE terminal continue-blob. additionalContext for a chokepoint event
    routes through context_surface_config.build_payload so the human systemMessage
    mirror + Stop decision:block model channel match the standalone injectors exactly;
    other events emit additionalContext raw (only UPS/SessionStart honor the field)."""
    joined_ctx = "\n".join(addl_ctx) if addl_ctx else ""
    blob = None
    if joined_ctx and event in _CHOKEPOINT_EVENT_KEY:
        try:
            sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
            import context_surface_config as _cs
            blob = _cs.build_payload(_CHOKEPOINT_EVENT_KEY[event], joined_ctx)
        except Exception as e:  # noqa: BLE001 — fall back to a raw additionalContext emit
            hook_runtime.log_hook_error(NAME, e)
            blob = None
    if blob is None:
        blob = {"continue": True}
        if joined_ctx and event in _ADDITIONAL_CONTEXT_EVENTS:
            blob["hookSpecificOutput"] = {"hookEventName": event,
                                          "additionalContext": joined_ctx}
    # fold the dispatcher's own queued systemMessages under any mirror build_payload set
    if sys_msgs:
        existing = blob.get("systemMessage")
        blob["systemMessage"] = ((existing + "\n") if existing else "") + "\n".join(sys_msgs)
    # continue:true is the non-blocking marker for every shape EXCEPT Stop's
    # decision:block (which re-invokes and must not also say continue).
    if "decision" not in blob:
        blob.setdefault("continue", True)
    return blob


def _emit_timing(event, matcher, hook, cls, elapsed_ms, status) -> None:
    """Record a per-core elapsed_ms to the diag stream (always-on INFO — every machine
    gets its own hook-cost profile, the perf dashboard's input). Fail-open: a diag
    hiccup never affects the dispatch. HARNESS_DEBUG adds the verbose per-core line."""
    try:
        import hlog
        # NB: the diag record's own key is `event` (="core_timing"); the CC hook event
        # is carried as `hook_event` to avoid colliding with hlog.info's `event` param.
        hlog.info("core_timing", **{
            "hook_event": event, "matcher": matcher, "hook": hook, "class": cls,
            "elapsed_ms": round(elapsed_ms, 3), "status": status})
        if os.environ.get("HARNESS_DEBUG"):
            hlog.debug("core_detail", hook=hook, hook_event=event, matcher=matcher,
                       elapsed_ms=round(elapsed_ms, 3), status=status)
    except Exception:  # noqa: BLE001 — self-timing is telemetry, never blocks
        pass


def _skip_trace_once(name, session):
    """Record a disabled-compliance skip once per (session, hook) — inherits the
    Phase 3 marker so a wide always-off gate does not spam the trace. Fail-open."""
    try:
        if not hook_runtime._skip_already_traced(session, name):
            import trace_log
            trace_log.append_event(hook=name, event="%s_skip" % name, session=session,
                                   note="disabled (dispatch)")
            hook_runtime._mark_skip_traced(session, name)
    except Exception as e:  # noqa: BLE001 — the skip trace is telemetry, never blocks
        hook_runtime.log_hook_error(name, e)


# --- entry --------------------------------------------------------------------

def _group_has_compliance(specs) -> bool:
    """True if the group carries a compliance gate. Defense-in-depth (M1): trusts the
    registry `class`, BUT if a spec is labelled non-compliance it best-effort resolves
    the module's own HOOK_CLASS — a mislabelled gate must not hide behind a wrong
    registry class and fail open. An unresolvable module is assumed compliance (safe)."""
    for s in specs:
        if s["class"] == "compliance":
            return True
        try:
            _, cls = _resolve_core(s)
            if cls == "compliance":
                return True
        except Exception:  # noqa: BLE001 — cannot tell → assume the gate side
            return True
    return False


def run(argv=None, stdin_text=None) -> int:
    """Testable entry. Resolves (event, matcher) from argv, reads stdin, runs the
    group, writes the terminal JSON to stdout (or a block reason to stderr). Returns
    the process exit code (0 continue / 2 block). Never raises."""
    argv = list(sys.argv[1:] if argv is None else argv)
    # `--runtime <id>` is present ONLY on a second runtime whose envelope differs
    # from the one every gate reads. Stripped before the positionals so the home
    # runtime's argv — the 61k-spawns-a-day path — is byte-identical to before and
    # pays nothing for a translation it does not need.
    runtime = None
    if "--runtime" in argv:
        i = argv.index("--runtime")
        runtime = argv[i + 1] if len(argv) > i + 1 else None
        del argv[i:i + 2]
    event = argv[0] if len(argv) >= 1 else ""
    matcher = argv[1] if len(argv) >= 2 else "*"

    # Load the registry. A wired group whose registry is broken must fail closed IF
    # it could carry a compliance gate; but we cannot know the class before parsing,
    # so an unparseable/missing registry → fail-closed exit 2 (the safe default for a
    # command that stands in for real gates).
    try:
        registry = load_registry()
    except Exception as e:  # noqa: BLE001
        hook_runtime.log_hook_error(NAME, e)
        # Two provenances, one door. A RegistryError already names the file, the
        # group and the key, so it is emitted as-is; anything else (missing file,
        # YAML syntax, unreadable bytes) gets the "unreadable" framing. Keep them
        # distinct in the WORDING — telling an operator a file with a one-letter
        # typo is "unreadable" sends them looking for the wrong problem.
        sys.stderr.write(
            "[%s] BLOCKED: %s. Fail-closed.\n"
            % (NAME, e if isinstance(e, RegistryError)
               else "registry unreadable (%s)" % e))
        return 2

    specs = registry.get((event, matcher))
    if specs is None:
        specs = registry.get((event, "*"), [])
    # ── THE MISS PATH ─────────────────────────────────────────────────────────
    # This used to warn and continue unconditionally. That was a NEGATIVE
    # predicate — "nothing is here" — and it cannot tell "nothing is supposed to
    # be here" from "the thing that was supposed to be here is gone". Three
    # measured registry edits produced exactly this state while leaving the file
    # parseable and non-empty, so nothing else caught them either: every group
    # emptied out, a group key with the wrong case, and a matcher that drifted
    # away from the wired one. Each one silently skipped that key's gates.
    #
    # The positive predicate asks hooks-registration.yaml — the installer's input,
    # i.e. which pairs are SUPPOSED to exist. Deliberately read here and nowhere
    # else: in a healthy tree this branch never executes, so the hit path pays
    # nothing, whereas consulting it up front would add a YAML parse to every
    # single tool call.
    #
    # A retired group is the one case that must still pass. Removing a group from
    # both files is supported; until the operator re-runs the installer their
    # settings.json keeps firing the old wire. Blocking there would brick every
    # affected tool call as punishment for a correct removal — so an unregistered
    # pair continues, with a line saying what to do about it.
    if not specs:
        registered = _is_registered(event, matcher) if event else False
        try:
            import hlog
            hlog.warn("dispatch_empty_group", hook_event=event, matcher=matcher,
                      registered=registered,
                      note="no registry group for a wired key" if registered
                           else "no registry group — retired or unregistered key")
        except Exception:  # noqa: BLE001
            pass
        if registered is not False:
            # True  -> the pair IS registered, so its group was lost: a gate is
            #          missing and this is drift. Fail closed.
            # None  -> the registration could not be read, so "retired" cannot be
            #          proven. An unprovable claim does not earn a pass.
            sys.stderr.write(
                "[%s] BLOCKED: %s:%s is wired but hook-dispatch.yaml has no group "
                "for it%s — any gates on this key would be skipped. Check the "
                "group key (compared exactly, including case) and the matcher "
                "spelling. Fail-closed.\n"
                % (NAME, event, matcher,
                   "" if registered else " (and hooks-registration.yaml could not "
                   "be read to confirm the key was retired)"))
            return 2
        if event:
            sys.stderr.write(
                "[%s] no dispatch group for %s:%s, and it is not in "
                "hooks-registration.yaml either — a retired group whose wiring is "
                "still in place. Re-run the installer to drop the stale wire.\n"
                % (NAME, event, matcher))
        _write_continue({"continue": True})
        return 0

    has_compliance = _group_has_compliance(specs)

    # Read stdin ONCE. A genuine read FAILURE with a compliance core pending is
    # fail-closed; an empty/unparseable payload degrades to {} → continue (C4).
    if stdin_text is None:
        try:
            stdin_text = sys.stdin.read()
        except Exception as e:  # noqa: BLE001
            hook_runtime.log_hook_error(NAME, e)
            if has_compliance:
                sys.stderr.write("[%s] BLOCKED: stdin read failed (%s). Fail-closed.\n" % (NAME, e))
                return 2
            _write_continue({"continue": True})
            return 0
    data = hook_runtime._parse(stdin_text)
    if runtime:
        # Add the aliases the gates read. A union, never a rename, and fail-open by
        # construction: an unreadable table returns the payload untouched, which is
        # exactly what a gate would see with no translation at all.
        try:
            import payload_dialect
            data = payload_dialect.normalise(data, runtime)
        except Exception as e:  # noqa: BLE001
            hook_runtime.log_hook_error(NAME, e)

    try:
        blob = _run_group(event, matcher, data, specs)
    except _Block as b:
        if b.kind == "verdict" and runtime and _write_runtime_deny(runtime, event,
                                                                   b.reason):
            # This runtime reads a decision object on stdout where the home one reads
            # permissionDecision. The exit code stays 2, as the upstream shim's own
            # relay does — the object carries the reason, the code carries the block.
            sys.stderr.write("[%s] BLOCKED: %s\n" % (NAME, b.reason))
            return 2
        if b.kind == "verdict" and _json_deny_supported(event) and _write_deny(b.reason):
            # Denied through the JSON door. The stderr line stays as a local debug trace
            # (exit-0 stderr reaches neither model nor human) so the block is still
            # greppable in a hook log.
            sys.stderr.write("[%s] BLOCKED: %s\n" % (NAME, b.reason))
            return 0
        sys.stderr.write("[%s] BLOCKED: %s\n" % (NAME, b.reason))
        return 2
    except Exception as e:  # noqa: BLE001 — any unexpected error with compliance pending is fail-closed
        hook_runtime.log_hook_error(NAME, e)
        if has_compliance:
            sys.stderr.write("[%s] BLOCKED: dispatch crashed (%s). Fail-closed.\n" % (NAME, e))
            return 2
        _write_continue({"continue": True})
        return 0

    _write_continue(blob)
    return 0


def _write_continue(blob) -> None:
    try:
        sys.stdout.write(json.dumps(blob, ensure_ascii=False))
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 — fail-open on the write itself
        pass


# CC reads `hookSpecificOutput.permissionDecision` on PreToolUse only (s1-hook-contract
# C11, re-probed on 2.1.220 across every tool this harness gates: Write, Edit, Bash,
# Read, Agent, Skill, Workflow — each denied with the reason and no wrapper). Every compliance
# core ships on PreToolUse today; this predicate is the standing guard for the day one
# is wired elsewhere, where a JSON deny would be read as no decision at all — i.e. an
# allow. Any other event falls through to the exit-2 door.
_JSON_DENY_EVENTS = ("PreToolUse",)


def _json_deny_supported(event) -> bool:
    return event in _JSON_DENY_EVENTS


def _write_runtime_deny(runtime, event, reason) -> bool:
    """Write the denial object THIS runtime reads, if it declares one for this event.

    False means "not applicable or not written", and the caller falls through to the
    doors that were already there. A denial in the wrong shape is a denial that does
    not happen, so this never swallows its own write failure.
    """
    try:
        import payload_dialect
        if event not in payload_dialect.deny_events(runtime):
            return False
        blob = payload_dialect.deny_payload(runtime, str(reason))
        if not blob:
            return False
        _write_continue_impl(blob)
        return True
    except Exception:  # noqa: BLE001 — fail CLOSED: caller keeps the exit-2 door
        return False


def _write_deny(reason) -> bool:
    """Emit the PreToolUse JSON deny as this process's ONE terminal stdout write.

    Returns True only when the payload is actually out and flushed. False means the
    caller must fall back to exit 2 — a swallowed write failure here would turn a block
    into a silent allow, since the JSON door's exit code is 0.
    """
    try:
        _write_continue_impl({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": str(reason),
            }
        })
        return True
    except Exception:  # noqa: BLE001 — fail CLOSED: the caller re-raises the exit-2 door
        return False


def _write_continue_impl(blob) -> None:
    """The raw stdout write, WITHOUT _write_continue's fail-open swallow. Only the deny
    path uses it, because only the deny path must know that the write failed."""
    sys.stdout.write(json.dumps(blob, ensure_ascii=False))
    sys.stdout.flush()


def main(argv=None) -> None:
    sys.exit(run(argv=argv))


if __name__ == "__main__":
    main()
