#!/usr/bin/env python3
"""gemini_transport.py — the transport seam behind the gemini chokepoint.

`partner_call` (gemini_companion.py) stays the ONE place that resolves the model,
scans for secrets, composes the prompt, stamps provenance, retries, and degrades.
A Transport owns only the mechanical "how the wire is driven" for a single
attempt: it drives one request/response cycle and returns a RunResult, or raises
(AcpError/AcpTimeout/OSError) so the chokepoint degrades loudly.

Pulling the ACP lifecycle out of partner_call's retry loop is what keeps ONE
chokepoint: a second engine (agy --print, P3) plugs in as another Transport behind
the same partner_call, never a parallel lane.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Optional

# The transport-neutral error contract. partner_call catches (AcpTimeout, AcpError,
# OSError) and scans the message for transient markers, so every transport raising
# these keeps the retry/degrade shell unchanged. The names keep the historical "Acp"
# prefix for now (a rename to Partner* is BACKLOG); ACP itself is retired.
class AcpError(Exception):
    """A transport failure: a non-zero engine exit, a malformed response, or a dead
    stream. Surfaced to the chokepoint — never swallowed."""


class AcpTimeout(Exception):
    """A transport call exceeded its deadline; the process has been terminated."""


@dataclass
class RunResult:
    """One transport attempt's payload. `content` is the engine's response dict
    (at least {"text": ...}); `session` is the id to resume with, or None."""
    content: Any
    session: Optional[str] = None


def _gemini_print_cmd(model, mode, session):
    """Command for `gemini -p` print mode. The prompt is appended by the transport
    (`-p <composed>` last) so a large prompt is never parsed as a flag. Mode maps to
    --approval-mode: plan = read-only, {yolo,write} = auto-approve edits (the write
    enabler, P5). Session resume uses --resume <uuid> (live-probed: a session created
    with --session-id resumes by uuid). HARNESS_GEMINI_PRINT_CMD overrides the `gemini`
    executable verbatim (fake + dogfood seam, mirrors HARNESS_AGY_CMD)."""
    override = os.environ.get("HARNESS_GEMINI_PRINT_CMD")
    base = shlex.split(override) if override else ["gemini"]
    base += ["-o", "json", "--skip-trust"]
    base += ["--approval-mode", "plan" if mode == "plan" else "yolo"]
    if model:
        base += ["-m", str(model)]
    if session:
        base += ["--resume", str(session)]
    return base


class GeminiPrintTransport:
    """Drives one `gemini -p … -o json` request. gemini runs on an API key and
    answers on stdout in one shot then EXITS — no resident ACP server, so there is
    no teardown to deadlock (the whole point of the ACP retirement). A non-zero exit
    embeds stderr in the raised AcpError so partner_call's marker scan classifies
    transient-vs-fatal; a timeout raises AcpTimeout. content keeps the raw json dict
    (response + stats + session_id) so _stats_of reads stats.models.<model>.tokens.
    Same RunResult contract as PrintTransport — callers never branch on the engine."""

    def run(self, *, composed, mode, session, cwd, timeout, model,
            engine_cfg) -> RunResult:
        cmd = _gemini_print_cmd(model, mode, session) + ["-p", composed]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                                  timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise AcpTimeout("gemini print timed out after %ss" % timeout) from e
        if proc.returncode != 0:
            raise AcpError("gemini print failed (exit=%s): %s"
                           % (proc.returncode, (proc.stderr or "").strip()))
        try:
            payload = json.loads(proc.stdout)
        except (json.JSONDecodeError, TypeError) as e:
            raise AcpError("gemini print returned non-JSON stdout: %r (%s)"
                           % ((proc.stdout or "")[:120], e)) from e
        # Valid JSON that is not an object (null / number / list / string) parses
        # cleanly, so json.loads did not raise — map it to AcpError here so
        # dict(payload) below never leaks a raw TypeError/ValueError past the
        # AcpError/AcpTimeout contract partner_call classifies on.
        if not isinstance(payload, dict):
            raise AcpError("gemini print returned non-object JSON: %r"
                           % ((proc.stdout or "")[:120],))
        content = dict(payload)
        content["text"] = payload.get("response", "")
        return RunResult(content=content, session=payload.get("session_id"))


def _agy_cmd(model, cwd=None, log_file=None):
    """Base command for `agy` print mode. The prompt is NOT included — the
    transport appends `-p <composed>` as the final tokens so a large prompt is
    never mistaken for a flag value (probed: `-p` takes the prompt as its value and
    must follow --model). HARNESS_AGY_CMD overrides the `agy` executable verbatim (a
    seam for the fake + dogfood pinning), mirroring HARNESS_GEMINI_PRINT_CMD.
    --model/--log-file are appended for the real binary; the fake tolerates them."""
    override = os.environ.get("HARNESS_AGY_CMD")
    base = shlex.split(override) if override else ["agy"]
    if model:
        base += ["--model", str(model)]
    if log_file:
        base += ["--log-file", str(log_file)]
    return base


# agy's --log-file carries a stable conversation UUID v4 (verified: 10 identical
# probes); print-mode does NOT surface it on stdout. Anchor the pattern tightly so a
# UUID elsewhere in the log can't be mistaken for it; take the first match.
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _extract_conversation_id(log_path):
    """Recover the agy conversation UUID from a --log-file, or None if the log has
    none (a format drift). None is a loud one-shot degrade upstream, never a crash."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    m = _UUID_RE.search(text)
    return m.group(0) if m else None


# SSH_* leaking into agy's env breaks its file-token auth (probed: an SSH session's
# vars route agy into a token-storage path that fails). Stripped for the agy transport
# only — gemini runs on an API key and keeps its env intact (R3).
_SSH_ENV = ("SSH_CLIENT", "SSH_TTY", "SSH_CONNECTION", "SSH_AUTH_SOCK", "SSH_AGENT_PID")


class PrintTransport:
    """Drives one `agy -p` (print-mode) request. agy runs on Google OAuth (no API key)
    and answers on stdout in one shot; a non-zero exit is a failure whose stderr is
    embedded in the raised error so partner_call's marker scan classifies transient-vs-
    fatal (D17). Token stats are n/a (agy reports none) → _stats_of returns {}. Same
    RunResult contract as GeminiPrintTransport so callers never branch on the engine.

    Write path: a write turn (mode yolo/write) adds --dangerously-skip-permissions and
    strips SSH_* from the env. agy ignores cwd, so the WRITE-TARGET is delivered as an
    absolute path inside the prompt (the sandbox path injects it); the worktree jail +
    escape-scan still bound the blast, and the empty-diff guard catches a write that
    landed in agy's scratch OUTSIDE the repo. NOT an OS sandbox (F3 unchanged)."""

    def run(self, *, composed, mode, session, cwd, timeout, model,
            engine_cfg) -> RunResult:
        # Per-call log file so concurrent calls never cross conversation ids
        # (race-free by construction); unlinked in finally (no tmp litter).
        fd, log_path = tempfile.mkstemp(prefix="agy-log-", suffix=".log")
        os.close(fd)
        try:
            cmd = _agy_cmd(model, cwd=cwd, log_file=log_path)
            if mode in ("yolo", "write"):
                cmd += ["--dangerously-skip-permissions"]
            if session:
                # Resume the caller's conversation. A rejected/invalid id makes agy
                # exit non-zero → we RAISE below (loud), never a silent fresh call:
                # running fresh when the caller expected recall is amnesia (a broken
                # conversation), which is worse than a loud failure.
                cmd += ["--conversation", session]
            cmd += ["-p", composed]
            # Strip SSH_* so agy's file-token auth survives inside an SSH session.
            env = os.environ.copy()
            for _k in _SSH_ENV:
                env.pop(_k, None)
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                                      timeout=timeout, env=env)
            except subprocess.TimeoutExpired as e:
                raise AcpTimeout("agy print timed out after %ss" % timeout) from e
            if proc.returncode != 0:
                # Embed stderr so partner_call._is_transient can scan it for the
                # configured markers; a down/expired agy degrades loudly.
                raise AcpError("agy print failed (exit=%s): %s"
                               % (proc.returncode, (proc.stderr or "").strip()))
            text = (proc.stdout or "").strip()
            if session:
                # Do NOT trust the exit code alone (review I-1). If agy silently
                # forked a fresh thread for an unknown/expired id (a clean exit,
                # common CLI behavior), its log carries a DIFFERENT id — that is the
                # silent amnesia the loop must never do. Raise LOUD on a definite
                # mismatch; a log with no id can't confirm the resume, so warn but
                # proceed (raising there would break a valid resume on an agy build
                # that doesn't re-log the id).
                resumed = _extract_conversation_id(log_path)
                if resumed is not None and resumed != session:
                    raise AcpError(
                        "agy did not resume conversation %s (started %s instead) — "
                        "refusing to pass fresh content off as a continuation "
                        "(anti-amnesia)" % (session, resumed))
                if resumed is None:
                    sys.stderr.write(
                        "gemini-partner: WARNING — could not confirm agy resumed "
                        "conversation %s (no id in log); proceeding on the exit "
                        "code\n" % session)
                new_session = session
            else:
                # Round 1: recover the conversation id for the next round. A miss is
                # a LOUD one-shot degrade — this round still answered, but the caller
                # must know recall is unavailable (no silent amnesia next round).
                new_session = _extract_conversation_id(log_path)
                if new_session is None:
                    sys.stderr.write(
                        "gemini-partner: WARNING — could not recover an agy "
                        "conversation id from the log; this round runs as an "
                        "independent one-shot (no recall next round)\n")
            return RunResult(content={"text": text}, session=new_session)
        finally:
            try:
                os.unlink(log_path)
            except OSError:
                pass
