#!/usr/bin/env python3
"""persona_bundle.py — load/validate the persona-bundle registry (persona-bundles.yaml).

A persona bundle is a full character profile chosen INDEPENDENTLY of voice_level:

  {id, name, characteristic, soul, form, default_voice_level}

  form                 a persona-form id from the terminal-voice catalog — the
                       surface FORM. When a bundle is active it ABSORBS the
                       standalone `persona` knob (the form comes from the bundle).
  name/characteristic  the character's identity + one-line trait.
  soul                 the character's backstory/inner motivation (maxlen-capped).
                       name/characteristic/soul are main-session-only — never
                       injected into a subagent surface (see voice_inject).
  default_voice_level  seeds voice_level at WRITE time (apply_bundle); it never
                       overrides voice_level at load.

Read path (load/resolve/valid_ids) is TOLERANT and NEVER raises — a missing file,
corrupt YAML, or a missing `bundles` key degrades to []/None (mirrors
voice_prefs.load). The validate/write path (validate/check_maxlen) DOES raise
PersonaBundleError so a malformed bundle never reaches the on-disk registry.

Leaf module by design: it imports only yaml + os + pathlib and NEVER voice_prefs.
The valid FORM set is duplicated here as a literal (VALID_FORMS); a parity test
(test_persona_bundle.test_form_catalog_in_sync) is the single place it is checked
against the voice_prefs catalog, so the two homes cannot drift silently. Keeping
the module a leaf avoids an import cycle: voice_prefs lazily imports this module
on its write path, so this module must not import back.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_REGISTRY_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "persona-bundles.yaml"
_ENV = "HARNESS_PERSONA_BUNDLES"  # test/scratch seam, mirrors HARNESS_TERMINAL_VOICE

# Required schema fields, in canonical order.
_FIELDS = ("id", "name", "characteristic", "soul", "form", "default_voice_level")
_STR_FIELDS = ("id", "name", "characteristic", "soul", "form")

# maxlen caps (chars). Central so a future change is one line. Locked at plan
# validate (the "deeper" tier). check_maxlen raises when a field exceeds its cap.
MAXLEN: Dict[str, int] = {
    "name": 40,
    "characteristic": 300,
    "soul": 800,
}

# The 13 non-`none` persona-form ids a bundle may adopt. Duplicated as a literal
# to keep this module a leaf; kept in sync with voice_prefs by a parity test.
VALID_FORMS = frozenset({
    "military", "reality-check", "git-log", "socratic",
    "bluf", "rubber-duck", "feynman", "first-principles",
    "caveman", "yoda", "pirate", "80s-hacker", "dad-joke",
})

# default_voice_level shares voice_level's 1..9 harshness range.
_VOICE_LEVEL_RANGE = range(1, 10)


class PersonaBundleError(ValueError):
    """Raised on the validate/write path when a bundle violates schema or maxlen.

    The read path (load/resolve/valid_ids) is deliberately tolerant and never
    raises — validation lives at the setter, mirroring voice_prefs."""


def _registry_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    raw = os.environ.get(_ENV)
    if raw:
        return Path(raw)
    return _REGISTRY_DEFAULT


def load(path=None) -> List[Dict[str, Any]]:
    """Return the list of bundle dicts. A missing file, corrupt YAML, a non-mapping
    top level, or a missing/non-list `bundles` key all degrade to [] — never raises."""
    import yaml_io  # lazy: keep importable without PyYAML until used
    p = _registry_path(path)
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, yaml_io.YAMLError):
        return []
    if not isinstance(raw, dict):
        return []
    bundles = raw.get("bundles")
    if not isinstance(bundles, list):
        return []
    return [b for b in bundles if isinstance(b, dict)]


def resolve(bundle_id, path=None) -> Optional[Dict[str, Any]]:
    """Return the bundle whose id == bundle_id, else None. A falsy/None/unknown id
    yields None (= "no bundle"). Never raises (read path)."""
    if not bundle_id:
        return None
    for b in load(path):
        if b.get("id") == bundle_id:
            return b
    return None


def valid_ids(path=None) -> set:
    """The set of bundle ids in the registry. Never raises → set() on any error.
    Used by the WRITE path (voice_prefs.apply_bundle / CLI) to validate an id."""
    return {b.get("id") for b in load(path) if b.get("id")}


def check_maxlen(field: str, value: Any, limit: int) -> None:
    """Raise PersonaBundleError when a string value exceeds limit chars. Shared
    helper (also imported by persona_me for RELATIONSHIP fields)."""
    if isinstance(value, str) and len(value) > limit:
        raise PersonaBundleError(
            f"persona-bundle field {field!r} is {len(value)} chars, exceeds maxlen {limit}")


def validate(bundle: Dict[str, Any]) -> None:
    """Validate one bundle: every field present + correctly typed, within maxlen,
    form ∈ catalog, default_voice_level an int 1..9. Raises PersonaBundleError on
    any violation (validate/write path)."""
    if not isinstance(bundle, dict):
        raise PersonaBundleError(f"bundle must be a mapping, got {type(bundle).__name__}")
    for f in _FIELDS:
        if f not in bundle:
            raise PersonaBundleError(f"bundle missing required field {f!r}")
    for f in _STR_FIELDS:
        if not isinstance(bundle[f], str):
            raise PersonaBundleError(f"bundle field {f!r} must be a string")
    for f, limit in MAXLEN.items():
        check_maxlen(f, bundle[f], limit)
    if bundle["form"] not in VALID_FORMS:
        raise PersonaBundleError(
            f"bundle form {bundle['form']!r} is not a known persona-form "
            f"(must be one of the 13 catalog forms)")
    lvl = bundle["default_voice_level"]
    if isinstance(lvl, bool) or not isinstance(lvl, int) or lvl not in _VOICE_LEVEL_RANGE:
        raise PersonaBundleError(
            f"bundle default_voice_level {lvl!r} must be an int 1..9")
