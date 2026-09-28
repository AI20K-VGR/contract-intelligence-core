#!/usr/bin/env python3
"""payload_dialect.py — translate one runtime's hook envelope into the one the
gates read, and its denial back into the one the runtime reads.

Every gate in this harness reads `tool_name`, `tool_input` and `hook_event_name`,
because that is what the home runtime sends. A second runtime measured here sends
camelCase keys, snake_case event values and its own tool vocabulary. Handed that
envelope a gate finds nothing, returns nothing and blocks nothing — while the
install reports it as carried and the hooks file names it. That is the failure the
projection module exists to refuse, one layer below where it was being checked.

The upstream tool answers this with a per-runtime Node shim wrapping every hook
process. This does the same work in the dispatcher, which already reads stdin once
for the whole group: one pass, no extra process, and the mapping is DECLARED in the
capability table rather than written into code per runtime.

Fail open by construction. Anything unexpected — an unreadable table, a payload
that is not an object, a runtime with no dialect — returns the payload untouched,
which is exactly what the gates would see with no translation at all. A translation
layer must never be stricter than its own absence.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TABLE_REL = "harness/data/runtime-targets.yaml"

_CACHE: dict = {}


def _dialect(runtime) -> dict:
    """The runtime's declared dialect, or {} — read once per process."""
    if not runtime:
        return {}
    if runtime in _CACHE:
        return _CACHE[runtime]
    out: dict = {}
    try:
        sys.path.insert(0, str(_ROOT / "harness" / "scripts"))
        from yaml_io import yaml_load  # noqa: PLC0415 — cost only where declared
        blob = yaml_load((_ROOT / _TABLE_REL).read_text(encoding="utf-8")) or {}
        targets = blob.get("targets", blob)
        out = ((targets.get(runtime) or {}).get("payload_dialect")) or {}
    except Exception:  # noqa: BLE001 — see the module docstring: fail open
        out = {}
    _CACHE[runtime] = out
    return out


def _pascal(value):
    if not isinstance(value, str) or not value:
        return value
    parts = value.split("_")
    if not all(p and p.isalnum() and p.islower() or p.isdigit() for p in parts):
        return value
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _tool(value, dialect: dict):
    if not isinstance(value, str):
        return value
    names = dialect.get("tool_names") or {}
    if value in names:
        return names[value]
    if dialect.get("mcp_prefix_restore") and "__" in value \
            and not value.startswith("mcp__"):
        return "mcp__%s" % value
    return value


def normalise(payload, runtime):
    """Add the aliases the gates read. A union, never a rename.

    Renaming would break anything reading the runtime's own spelling, and an alias
    is never written over a key that is already present — a payload that already
    carries `tool_name` is telling us something this table cannot improve on.
    """
    dialect = _dialect(runtime)
    if not dialect or not isinstance(payload, dict):
        return payload
    transforms = {}
    if (dialect.get("event_value_case") or "") == "snake_to_pascal":
        transforms["hook_event_name"] = _pascal
    for src, dest in (dialect.get("field_map") or {}).items():
        if src not in payload or dest in payload:
            continue
        value = payload[src]
        if dest == "tool_name":
            value = _tool(value, dialect)
        elif dest in transforms:
            value = transforms[dest](value)
        payload[dest] = value
    return payload


def deny_payload(runtime, reason: str):
    """The denial object THIS runtime reads on stdout, or None for the home one.

    The home runtime reads `permissionDecision` inside a PreToolUse-specific
    envelope; the one measured here reads a decision object. The dispatcher writes
    whichever the runtime it was registered on understands.
    """
    decl = (_dialect(runtime).get("deny") or {})
    if not decl.get("stdout_key"):
        return None
    return {decl["stdout_key"]: decl.get("stdout_value") or "deny",
            decl.get("reason_key") or "reason": reason}


def deny_events(runtime) -> list:
    """The events whose denial travels through that object."""
    return list((_dialect(runtime).get("deny") or {}).get("events") or [])
