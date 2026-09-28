#!/usr/bin/env python3
"""model_guard.py — PreToolUse(Agent|Task) gate: enforce the model-bound posture.

Historically pinned only Explore to haiku; now enforces the per-agent bound declared in
model-policy.yaml for ANY subagent-type (exact / ceiling <= / floor >= / require-explicit).
A subagent inherits the session model unless the caller passes one, which is expensive or
wrong for many roles; this gate fires when the effective model violates the agent's bound,
consults the posture, and blocks (default) / advises / stays silent, with a reasoned escape
marker for a genuine need.

Effective model:
  - an explicit tool_input.model wins;
  - a self_pinned agent (frontmatter sets its own model) trusts a bare inherit;
  - otherwise the LIVE session model, read from the transcript tail (a /model switch is
    honored) with the ANTHROPIC_MODEL env as a best-effort fallback.

Tier comparison maps THROUGH ANTHROPIC_DEFAULT_*_MODEL and FAILS OPEN on a custom/collapsed
mapping (model_policy.evaluate) — a custom model setup is never false-blocked.

HOOK_CLASS = compliance: it exits 2 to BLOCK. Deliberate, documented deviation from the
compliance contract (shared with simplify_gate): an INTERNAL ERROR
fails OPEN (exit 0) so a lỗi vặt does not wedge the whole session; only a real block
decision exits 2. The block path sits OUTSIDE the fail-open try and the except re-raises
SystemExit, so a broad except can never swallow the exit-2 and turn the gate dark (F4).

NO env knob. There is deliberately
no environment gate that would default this hook OFF and ship it dark, against the design
(default ON block). The ONLY switch is the registration toggle `model_guard.enabled`
(compliance default True).

Best-effort (Khung-1): a spawn that inherits an unclassifiable model (custom mapping) is
allowed by design; the intent-first block message + the prose docs are the real mitigation.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hook_runtime  # noqa: E402

HOOK_CLASS = "compliance"
_HOOK = "model_guard"


def _norm(agent_type) -> str:
    t = str(agent_type or "").strip().lower()
    return t.split(":", 1)[1] if ":" in t else t


def _spawn_type(data: dict) -> str:
    ti = data.get("tool_input")
    if isinstance(ti, dict):
        v = ti.get("subagent_type") or ti.get("agent_type")
        if isinstance(v, str) and v.strip():
            return v.strip()
    for k in ("subagent_type", "agent_type"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _spawn_model(data: dict) -> str:
    ti = data.get("tool_input")
    if isinstance(ti, dict):
        v = ti.get("model")
        if isinstance(v, str):
            return v.strip()
    return ""


def _last_assistant_model(path: str) -> str:
    """Read the transcript tail and return the LIVE model — the `model` of the last assistant
    message. Bounded read; any failure returns '' (the caller falls back to env)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            span = min(size, 200_000)
            fh.seek(size - span)
            tail = fh.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — no/broken transcript → env fallback
        return ""
    model = ""
    for line in tail.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:  # noqa: BLE001 — a partial first line (cut by the tail span) is skipped
            continue
        if not isinstance(o, dict):
            continue  # valid JSON, wrong shape — `[]`/`null`/a bare number has no .get
        m = o.get("message")
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("model"):
            model = str(m["model"])
    return model


def _session_model(data: dict, env) -> str:
    tp = data.get("transcript_path") if isinstance(data, dict) else None
    if isinstance(tp, str) and tp:
        m = _last_assistant_model(tp)
        if m:
            return m
    return str(env.get("ANTHROPIC_MODEL") or "").strip()  # best-effort default fallback


def _block_reason(agent: str, verdict: dict, resolved: dict, session_model: str) -> str:
    kind = verdict.get("kind")
    eff = verdict.get("effective") or session_model or "inherit"
    # The escape is a genuine option, NOT a fallback of last resort — so it names the exact
    # command with NO `<id>` placeholder (model_override.py auto-resolves the session).
    # `--count` is named here because this message is the ONE text a blocked caller is
    # guaranteed to read, and the grant defaults to a SINGLE use. Measured: every caller
    # copied this line verbatim, got one use, and was blocked again on the next spawn of
    # the same fan-out. The expiry is named for the same reason — 3 of 3 historical
    # markers died on the clock still holding 11, 7 and 9 unused counts.
    escape = ("record a reason: `model_override.py --grant --reason \"...\"` "
              "(auto-resolves the session), then re-spawn — but do NOT swap to a different "
              "agent-type just to dodge the bound. Spawning N agents? pass `--count N`: a "
              "grant covers ONE spawn by default and expires on a timer, so a long fan-out "
              "may need re-granting.")
    # Every branch opens by making the model REASON about the task's real need first, so it does
    # not reflexively downgrade (or upgrade) to satisfy the bound. Two balanced exits: fit the
    # bound, OR justify crossing it.
    lead = ("FIRST decide what THIS task actually needs — do not reflexively change the model "
            "to clear the gate. ")
    # Appended to EVERY block reason: the spawn param must be subagent_type spelled exactly. A
    # mistyped key (e.g. subject_type) is silently ignored, so the spawn silently falls back to
    # the general-purpose agent — frequently the real reason an unexpected model bound trips here.
    call_hint = (" Also confirm the spawn used subagent_type=\"<agent-type>\" spelled exactly: a "
                 "mistyped key (e.g. subject_type) is silently dropped and the spawn falls back to "
                 "the general-purpose agent, which is often what actually tripped this bound.")
    if kind == "explicit":
        msg = ("%sThe catch-all '%s' agent inherits the session model ('%s'). If a specialized "
               "agent-type fits the task, prefer it (its bound is intentional); if you must use "
               "'%s', re-spawn with an explicit model:'<model>' chosen for the task. If the "
               "inherited model is genuinely right, %s" % (lead, agent, eff, agent, escape))
    elif kind == "ceiling":
        cap = resolved.get("max_model")
        gp = _norm(agent) == "general-purpose"
        msg = ("%s%s is capped at model <= '%s' but the effective model is '%s'. Two paths, pick "
               "by the task — NOT by whichever clears the gate fastest: (a) if the task genuinely "
               "fits a lighter model, re-spawn with model:'%s' (or lower)%s; (b) if it genuinely "
               "needs a stronger model than the cap, this %sagent is likely the wrong tool — "
               "prefer a specialized agent-type whose bound allows it; only if it truly must be "
               "this agent on the stronger model, %s"
               % (lead, agent, cap, eff, cap,
                  (" or pick a specialized agent-type" if gp else ""),
                  ("catch-all " if gp else ""), escape))
    elif kind == "floor":
        flr = resolved.get("min_model")
        msg = ("%s%s should run model >= '%s' but the effective model is '%s'. Pick by the task: "
               "if it truly needs that floor, re-spawn with model:'%s' (or higher); if the task "
               "is genuinely lighter, a lower-bound agent-type fits it better. If the floor is "
               "wrong for this task, %s" % (lead, agent, flr, eff, flr, escape))
    else:
        req = resolved.get("required_model")
        msg = ("%s%s is pinned to model '%s' but the effective model is '%s'. Re-spawn with "
               "model:'%s' if the task fits it; if the pin is wrong for this task, %s"
               % (lead, agent, req, eff, req, escape))
    return msg + call_hint


def core(data: dict):
    """Return a BLOCK reason string for a deliberate model-bound violation, else None.

    Stdout-free (no emit/exit) so the in-process dispatcher can call it. Advisory-mode
    and escape-marker-consumed paths write their `[advisory]`/marker line to stderr and
    return None (allow). The caller (standalone main or dispatcher) owns the terminal
    write; the block reason is returned, not printed. Every internal path here is
    fail-open BY DESIGN — the caller wraps it so a crash never wedges a spawn (F4)."""
    agent = _spawn_type(data)
    if not agent:
        return None  # not an Agent/Task spawn — free
    import model_policy
    resolved = model_policy.resolve(agent)
    mode = resolved.get("mode", "off")
    has_bound = any((
        resolved.get("required_model"), resolved.get("max_model"),
        resolved.get("min_model"), resolved.get("require_explicit"),
    ))
    if mode == "off" or not has_bound:
        return None  # posture disabled / this agent carries no bound
    spawn_model = _spawn_model(data)
    session_model = _session_model(data, os.environ)
    verdict = model_policy.evaluate(spawn_model, session_model, resolved)
    if verdict.get("ok"):
        return None  # within bound
    reason = _block_reason(agent, verdict, resolved, session_model)
    # Advisory posture never blocks and never spends the escape marker — it only nudges.
    if mode == "advisory":
        sys.stderr.write("[advisory] %s: %s\n" % (_HOOK, reason))
        return None
    # mode == block: a reasoned, session-scoped override marker allows + logs. Empty
    # session => consume_marker returns False => no escape (F5).
    import model_override
    session = data.get("session_id") or ""
    if model_override.consume_marker(session):
        sys.stderr.write("[%s] escape marker consumed — allowing %s@%s\n"
                         % (_HOOK, agent, spawn_model or "inherit"))
        return None
    return reason  # the ONLY block


def main() -> None:
    # 1. Registration toggle is the ONLY switch. A broken enabled read fails OPEN.
    try:
        if not hook_runtime.hook_enabled(_HOOK, HOOK_CLASS):
            hook_runtime.emit_continue()
            sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — a broken enabled read must not wedge a spawn
        hook_runtime.log_hook_error(_HOOK, e)
        hook_runtime.emit_continue()
        sys.exit(0)

    # Every internal error from here fails OPEN (documented deviation, F4).
    try:
        reason = core(hook_runtime.read_stdin_json())  # {} on empty/malformed
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — FAIL-OPEN: a gate crash never wedges a spawn
        hook_runtime.log_hook_error(_HOOK, e)
        reason = None
    if reason:
        # The only exit-2 path — deliberate block, kept outside the fail-open try (F4).
        sys.stderr.write("[%s] BLOCKED: %s\n" % (_HOOK, reason))
        sys.exit(2)
    hook_runtime.emit_continue()
    sys.exit(0)


if __name__ == "__main__":
    main()
