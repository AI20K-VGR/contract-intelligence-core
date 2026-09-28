#!/usr/bin/env python3
"""partner_transport.py — the transport seam behind the ccs (CCS-driven) partner
lane chokepoint. Twin of gemini_transport.py's transports, but for a single
engine: ccs itself proxies to whichever provider profile (`ccs <provider> -p
...`) the caller names, so there is no engine-select branch here — `provider`
picks the destination, never a hardcoded lane.

`ccs <provider> -p ... --output-format json` prints a POLLUTED stdout (banner
ANSI art + a human table + three newline-delimited JSON stream objects), never
a single clean JSON document (verified against a live run). `json.loads(stdout)`
crashes on this shape by construction. The parser below
strips ANSI, then walks the stream with `json.JSONDecoder().raw_decode` from
every `{` to recover each top-level object, then keys off `type` to pick the
"system" record (model, session_id, permissionMode) and the "result" record
(cost, usage, text). cost lives ONLY on the "result" record — the "system"
record's cost is None at init (verified) — so the parser never reads cost from
the wrong record. A stream with no "result" record is a loud PartnerError,
never a crash.
"""
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Optional


# Honest, lane-native names — do NOT reuse gemini_transport's Acp* names here.
# The chokepoint (partner_companion.py) imports these directly from this
# module; the two lanes stay independently named even though the raise/degrade
# contract is the same shape.
class PartnerError(Exception):
    """A transport failure: non-zero ccs exit, no `type=="result"` record in
    the stream, or unparseable stdout. Surfaced to the chokepoint — never
    swallowed."""


class PartnerTimeout(Exception):
    """A transport call exceeded its deadline; the process has been
    terminated."""


@dataclass
class RunResult:
    """One transport attempt's payload. `content` carries text/model/cost/
    usage (+ permission_mode, for callers that want to assert the advisory
    flag actually reached ccs); `session` is the ccs session_id to resume
    with, or None."""
    content: Any
    session: Optional[str] = None


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

# Advisory turns pass --permission-mode plan (verified live: blocks Write both
# inside and outside cwd; it does NOT close the read-outside-cwd egress gap —
# that stays an accepted, documented risk, not something this transport
# closes). Write mode drops this flag entirely.
_ADVISORY_MODES = frozenset({"plan", "advisory"})


def _ccs_cmd(provider):
    """Base command up to and including the provider positional. HARNESS_CCS_CMD
    overrides the `ccs` executable verbatim (fake + dogfood seam, mirrors
    HARNESS_AGY_CMD) — split with shlex so a multi-token override like
    "python3 fixtures/fake_ccs.py" runs as intended. `provider` is never
    hardcoded: the caller resolves it via partner_preflight.validate_provider
    first — refuse to call ccs blind."""
    override = os.environ.get("HARNESS_CCS_CMD")
    base = shlex.split(override) if override else ["ccs"]
    return base + [str(provider)]


def _iter_json_objects(text):
    """Yield every top-level JSON object embedded in `text`, skipping anything
    between them (the banner art + table rows). This is what makes
    `json.loads(stdout)` the wrong tool for this shape — a single global parse
    chokes on the banner; scanning for `{` and decoding from there does not."""
    decoder = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        brace = text.find("{", i)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError:
            i = brace + 1
            continue
        yield obj
        i = end


def _parse_stream(stdout):
    """Strip ANSI, recover every stream object, return (system_rec, result_rec).
    Raises PartnerError when no `type=="result"` record is present — ccs
    answered but this transport cannot report a result without one (degrade
    loud, never silently return an empty/None result)."""
    clean = _ANSI_RE.sub("", stdout or "")
    system_rec = None
    result_rec = None
    for obj in _iter_json_objects(clean):
        if not isinstance(obj, dict):
            continue
        t = obj.get("type")
        if t == "system":
            system_rec = obj
        elif t == "result":
            result_rec = obj
    if result_rec is None:
        raise PartnerError(
            "ccs stream carried no type==\"result\" record (stdout=%r)" % (clean[:200],))
    return system_rec, result_rec


class CcsPrintTransport:
    """Drives one `ccs <provider> -p ... --output-format json` request. ccs
    answers on stdout in one shot then exits — no resident server, no teardown
    to deadlock. A non-zero exit embeds stderr in the raised PartnerError so
    the chokepoint's marker scan classifies transient-vs-fatal; a timeout
    raises PartnerTimeout."""

    def run(self, *, composed, mode, session, cwd, timeout, model=None,
            provider, engine_cfg=None) -> RunResult:
        # Arg order verified live: prompt BEFORE flags — flags placed before
        # the prompt collide with ccs's own injected --settings flag.
        cmd = _ccs_cmd(provider) + ["-p", composed, "--output-format", "json"]
        if mode in _ADVISORY_MODES:
            cmd += ["--permission-mode", "plan"]
        if session:
            # TODO research: ccs's session-resume flag is unconfirmed (not
            # probed live yet) — omit it rather than invent a flag name.
            # Session pin is not exercised by any test in this suite; close
            # this once the real resume flag is verified live.
            pass
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                                  timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise PartnerTimeout("ccs print timed out after %ss" % timeout) from e
        except OSError as e:
            # A missing/unrunnable binary (FileNotFoundError, PermissionError,
            # ...) must degrade through the same PartnerError contract as any
            # other transport failure — never a raw crash reaching the
            # chokepoint.
            raise PartnerError("ccs print could not run cmd=%r: %s" % (cmd, e)) from e
        if proc.returncode != 0:
            raise PartnerError("ccs print failed (exit=%s): %s"
                               % (proc.returncode, (proc.stderr or "").strip()))
        system_rec, result_rec = _parse_stream(proc.stdout)
        if "result" not in result_rec:
            # The record is present but carries no answer text — treat this
            # the same as "no result record at all" rather than silently
            # reporting an empty-but-ok answer.
            raise PartnerError(
                "ccs result record carried no \"result\" key (record=%r)"
                % (result_rec,))
        content = {
            "text": result_rec.get("result", ""),
            "model": (system_rec or {}).get("model"),
            "cost": result_rec.get("total_cost_usd"),
            "usage": result_rec.get("usage"),
            "permission_mode": (system_rec or {}).get("permissionMode"),
        }
        session_id = (system_rec or {}).get("session_id")
        return RunResult(content=content, session=session_id)
