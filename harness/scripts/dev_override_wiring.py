#!/usr/bin/env python3
"""dev_override_wiring — detector for a `.harness-dev/<name>.yaml` override that
NO `HARNESS_*` env points to, so the loader silently falls back to the shipped
default and the override does nothing.

This is the "I made a dev override but forgot to wire its env" failure mode:
most localized configs resolve `explicit --config > $HARNESS_XXX > shipped`, so
the dev file is inert until an explicit `HARNESS_XXX` env in
`.claude/settings.local.json` points at it (a restart then applies it). Auto-
discovery is deliberately NOT done for the caged/security-relevant seams (an
agent could widen its own cage via a writeable-zone file), so the wiring is
manual — and therefore forgettable. This detector catches the gap; it owns no
side effects and never writes anything.

Dev-only by construction: it returns None (silent) when `.harness-dev/` is
absent, so a shipped install never trips it.
"""
import json
import os
from pathlib import Path
from typing import Optional

# Dev override files consumed WITHOUT a HARNESS_* env — absence of an env is
# correct for these, not a wiring bug:
#   dev-off-skills.yaml — read directly by dev_skill_farm.py (the farm off-list)
#   terminal-voice.yaml — voice_prefs.py AUTO-DISCOVERS it at the repo-root path
#                         (cosmetic config, safe to auto-load; the caged seams
#                         are the ones that must stay env-explicit)
_NO_ENV_NEEDED = frozenset({"dev-off-skills.yaml", "terminal-voice.yaml"})

_DEV_DIRNAME = ".harness-dev"


def _env_sources(project: Path):
    """The env maps to scan for HARNESS_* wiring, most-authoritative first:
    settings.local.json (the per-machine tier, and the one that wins when both
    declare a key), then settings.json (the committed tier — where a checkout
    that must work at first launch declares its wiring, since a fresh session
    binds env at startup and cannot be restarted), then the live process env.

    Both settings files are read because `env` is valid in either; a detector
    that knew only the local tier would call a committed wiring unwired."""
    sources = []
    for name in ("settings.local.json", "settings.json"):
        try:
            data = json.loads(
                (project / ".claude" / name).read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("env"), dict):
                sources.append(data["env"])
        except (OSError, ValueError):
            pass
    sources.append(dict(os.environ))
    return sources


def _wiring(project: Path, dev: Path):
    """Two facts about the HARNESS_* envs aimed into `.harness-dev/`:
    `(wired_basenames, {env_key: raw_value})` where the second holds the DEAD
    wirings — an env whose target does not exist.

    A dead wiring is deliberately NOT counted as wired. Every one of these
    loaders fails open, so an env pointing at nothing degrades to the shipped
    default in exactly the same silence as no env at all — while *looking*
    configured. That is what a settings.local.json carrying another checkout's
    absolute paths produces, so it needs its own name and its own fix (repoint
    the env) rather than hiding inside the wired set.

    First writer wins per key, matching `_env_sources` precedence.
    """
    wired, dead, seen = set(), {}, set()
    for env in _env_sources(project):
        for key, val in env.items():
            if not (isinstance(key, str) and key.startswith("HARNESS_")
                    and isinstance(val, str) and val):
                continue
            if key in seen:
                continue
            try:
                p = Path(val)
                p = p.resolve() if p.is_absolute() else (project / p).resolve()
            except (OSError, RuntimeError, ValueError):
                continue
            seen.add(key)
            if p.suffix != ".yaml":
                continue  # this detector governs the .yaml override tier only;
                # HARNESS_PERSONA_ME's persona-me.json is absent by design until
                # authored, and its loader degrades to None — not a wiring fault
            if p.parent == dev:
                if p.is_file():
                    wired.add(p.name)
                else:
                    dead[key] = val  # report as WRITTEN — the string to go fix
            elif p.parent.name == _DEV_DIRNAME and not p.is_file():
                # names a .harness-dev/ override, but under a prefix that does not
                # exist here — a settings file carried over from another checkout.
                # Calling this "unwired" would send the reader hunting for a
                # missing env line that is sitting right in front of them.
                dead[key] = val
            # anything else is aimed outside .harness-dev — another owner's business
    return wired, dead


def collect(project_dir: Optional[str] = None) -> Optional[dict]:
    """Return `{"unwired": [<name>.yaml, ...]}` for dev overrides present but
    wired to no HARNESS_* env, else None. Fail-soft: any error or a non-dev
    tree returns None (the nudge stays silent) rather than raising."""
    try:
        project = Path(project_dir).resolve() if project_dir else Path.cwd()
        dev = project / ".harness-dev"
        if not dev.is_dir():
            return None
        present = {f.name for f in dev.glob("*.yaml")}
        wired, dead = _wiring(project, dev)
        # A file already reported dead is not ALSO unwired: one root cause earns
        # one line. Listing both doubles a 12-file advisory and implies two fixes.
        claimed = {Path(v).name for v in dead.values()}
        unwired = sorted(present - wired - claimed - _NO_ENV_NEEDED)
        out = {}
        if unwired:
            out["unwired"] = unwired
        if dead:
            out["dead"] = sorted("%s=%s" % kv for kv in dead.items())
        return out or None
    except (OSError, RuntimeError):
        return None
