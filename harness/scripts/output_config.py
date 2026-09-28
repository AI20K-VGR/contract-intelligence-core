#!/usr/bin/env python3
"""output_config.py — loader for harness/data/output.yaml (generated-prose language).

Instruction files (SKILL.md, references, rules, CLAUDE.md) are English. This
setting picks the language of the prose the harness GENERATES — reports, docs,
plan narration — and whether the humanizer rule is applied. The harness default
is Vietnamese: English instructions in, human-friendly Vietnamese reports out.
`humanize` defaults OFF (token-spend; on only when publishing externally).

`--resolved` prints resolve_all() — the terminal-voice axes + these report axes
merged, honoring both env seams. It is the ONE source a skill/agent reads the
register knobs from (never re-read the tracked file by hand), and a single-command
view of every knob (the deliberate alternative to merging the two config files).

One shared loader so every producer reads the language identically.
DELIBERATELY no env override: output.yaml is tracked config — a language change
is a git-visible diff, never a hidden in-session flip. The only load path is the
tracked file next to the repo's data dir (resolved off __file__, never CWD).
Callers that need a different file (tests) pass `path=` explicitly.
"""

from pathlib import Path


def _yaml_load(text):
    """The one shared YAML read (yaml_io.py, ruamel.yaml, C-accelerated) — see
    that module's docstring for why ruamel replaced PyYAML and hook_runtime.py
    for the parse-cost measurements.

    This module sits on a per-EVENT path, so its parse cost is paid per tool
    call / prompt, not once per CLI run. `import yaml_io` stays lazy and is a
    same-directory sibling import (harness/scripts/), so this file stays
    runnable as a standalone CLI without the hooks dir on sys.path.
    """
    import yaml_io
    return yaml_io.yaml_load(text)

_OUTPUT_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "output.yaml"

VALID_LANGUAGES = {"en", "vi"}

# Canonical write order. The writer serializes EVERY set key in this order,
# never a hardcoded subset — a field is only persisted if the writer carries it.
_CANONICAL_KEYS = ("language", "humanize", "audience", "code_style", "thinking_language")

# thinking_language (locale.thinkingLanguage): the language the model THINKS/reasons in
# (extended reasoning), separate from `language` (the prose the harness writes out). A free
# language code/name; default "en" (English), matching the upstream `null = English`.
_THINKING_DEFAULT = "en"

# audience (prose register) + code_style (generated-code verbosity) share the
# 0..5 level scale. Both default absent (None = no shaping). code_style also
# accepts the string `off` on read, folded to None.
_LEVEL_MIN, _LEVEL_MAX = 0, 5


def _validate_level(key, value, where):
    """Fold/validate a 0..5 level field. None/absent stays None. `code_style`
    accepts the literal `off` → None. Anything else out of range raises."""
    if value is None:
        return None
    # YAML 1.1 folds a bare `off`/`no` to the bool False; code_style spells its
    # "no code shaping" state that way, so accept it as None (quoted "off" too).
    if key == "code_style" and value is False:
        return None
    if isinstance(value, str):
        if key == "code_style" and value.strip().lower() == "off":
            return None
        try:
            value = int(value.strip())
        except ValueError:
            raise OutputConfigError(
                "key `%s`%s must be an int %d..%d or absent (got %r)"
                % (key, where, _LEVEL_MIN, _LEVEL_MAX, value))
    if isinstance(value, bool) or not isinstance(value, int):
        raise OutputConfigError(
            "key `%s`%s must be an int %d..%d or absent (got %r)"
            % (key, where, _LEVEL_MIN, _LEVEL_MAX, value))
    if not (_LEVEL_MIN <= value <= _LEVEL_MAX):
        raise OutputConfigError(
            "key `%s`%s must be %d..%d (got %r)"
            % (key, where, _LEVEL_MIN, _LEVEL_MAX, value))
    return value


class OutputConfigError(Exception):
    """Raised when output.yaml is missing or malformed. Message names the file
    and the offending key so the fix is a config edit, not a debug session."""


# The decoration layer. It lives beside `audience` and `code_style` because it answers
# the same question those do — what the DELIVERABLE looks like — and a second config
# door for one question is how two doors start giving different answers.
#
# Every switch defaults OFF. `antv` in particular is 874 KB, and a default-on 874 KB
# lands on pages that use none of it.
VISUAL_SWITCHES = {
    "antv": False,           # the vendored infographic bundle (harness/assets/antv/)
    "diagram_design": True,  # the vendored diagram templates (harness/assets/diagram-templates/)
    "editorial": True,       # decorative panels at all; off = plain structural output
}


def _validate_visual(value, where) -> dict:
    """Booleans only, and an unknown key is an error rather than a no-op.

    Coercion is the silent failure here: `antv: "false"` is a non-empty string, which
    every truthiness test in Python reads as ON — so a switch the user set to off stays
    on with nothing to notice. An unknown key is refused for the same reason a typo'd
    switch is worse than a missing one: it reads as configured.
    """
    out = dict(VISUAL_SWITCHES)
    if value is None:
        return out
    if not isinstance(value, dict):
        raise OutputConfigError(
            "key `visual`%s must be a mapping of switches %s (got %r)"
            % (where, sorted(VISUAL_SWITCHES), value))
    for k, v in value.items():
        if k not in VISUAL_SWITCHES:
            raise OutputConfigError(
                "unknown switch `visual.%s`%s — known switches are %s"
                % (k, where, sorted(VISUAL_SWITCHES)))
        if not isinstance(v, bool):
            raise OutputConfigError(
                "switch `visual.%s`%s must be true or false (got %r) — a quoted "
                "\"false\" reads as ON" % (k, where, v))
        out[k] = v
    return out


def load_output(path=None, *, _lenient_thinking_language=False) -> dict:
    """Parse output.yaml → {language, humanize}.

    Missing file / non-mapping document / out-of-enum language raise
    OutputConfigError naming file + key. A missing `humanize` defaults to False
    (the humanizer is token-spend; it is OFF unless a human turns it on for an
    externally-published report).

    `_lenient_thinking_language` is a private seam for save_output()'s repair
    path only: a broken on-disk `thinking_language` (e.g. an unquoted `no`/`off`
    a prior write let YAML 1.1 fold to a bool) degrades to the default instead
    of raising, so a write that fixes a DIFFERENT knob — or fixes this one — is
    never blocked by the very corruption it could repair. Every other caller
    keeps the strict, fail-CLOSED contract.
    """
    p = Path(path) if path else _OUTPUT_DEFAULT
    try:
        raw = _yaml_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise OutputConfigError(
            "output config missing at %s — create it with at least:\n"
            "  language: vi" % p
        )
    if not isinstance(raw, dict):
        raise OutputConfigError(
            "output config %s is malformed — expected a YAML mapping (keys: "
            "`language` required; `humanize`, `audience`, `code_style` optional)" % p
        )

    lang = raw.get("language", "vi")
    if lang not in VALID_LANGUAGES:
        raise OutputConfigError(
            "key `language` in %s must be one of %s (got %r)"
            % (p, sorted(VALID_LANGUAGES), lang)
        )

    humanize = raw.get("humanize", False)
    if not isinstance(humanize, bool):
        raise OutputConfigError(
            "key `humanize` in %s must be true or false (got %r)" % (p, humanize)
        )

    where = " in %s" % p
    audience = _validate_level("audience", raw.get("audience"), where)
    code_style = _validate_level("code_style", raw.get("code_style"), where)

    tlang = raw.get("thinking_language", _THINKING_DEFAULT)
    if not isinstance(tlang, str) or not tlang.strip():
        if _lenient_thinking_language:
            tlang = _THINKING_DEFAULT
        else:
            raise OutputConfigError(
                "key `thinking_language` in %s must be a non-empty language code/name "
                "(got %r); default is %r" % (p, tlang, _THINKING_DEFAULT)
            )

    visual = _validate_visual(raw.get("visual"), where)

    return {
        "language": lang,
        "humanize": humanize,
        "audience": audience,
        "code_style": code_style,
        "thinking_language": tlang.strip(),
        "visual": visual,
    }


def language(path=None) -> str:
    """Convenience: the configured output language (en|vi)."""
    return load_output(path=path)["language"]


_DEFAULTS = {"language": "vi", "humanize": False, "audience": None, "code_style": None,
             "thinking_language": _THINKING_DEFAULT,
             "visual": dict(VISUAL_SWITCHES)}


def load(path=None) -> dict:
    """Fail-OPEN sibling of load_output for the HOOK / SKILL path.

    Never raises: a missing / malformed file or a single bad field degrades to
    the safe default and records the reason under `_diag`, so a fail-open hook
    (SessionStart / UserPromptSubmit) is never killed by a corrupt output.yaml.
    The gate path MUST keep using load_output (fail-CLOSED) — these two fail
    modes are deliberately NOT merged (LESSONS: a fail-open path must never be
    mistaken for a fail-closed one).

    Test/ephemeral seam: when `path` is None, HARNESS_OUTPUT env var can point at
    a scratch file — the same seam pattern HARNESS_TERMINAL_VOICE uses. The gate
    path (load_output) DOES NOT honour this env var by design (tracked config only).
    """
    import os

    if path is not None:
        p = Path(path)
    else:
        raw_env = os.environ.get("HARNESS_OUTPUT")
        p = Path(raw_env) if raw_env else _OUTPUT_DEFAULT
    out = dict(_DEFAULTS)
    diag = []
    try:
        raw = _yaml_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        diag.append("output config missing at %s — using defaults" % p)
        out["_diag"] = diag
        return out
    except Exception as e:  # unreadable / unparseable YAML — degrade, do not raise
        diag.append("output config unreadable at %s: %s" % (p, e))
        out["_diag"] = diag
        return out
    if not isinstance(raw, dict):
        diag.append("output config %s is not a mapping — using defaults" % p)
        out["_diag"] = diag
        return out

    lang = raw.get("language", "vi")
    if lang in VALID_LANGUAGES:
        out["language"] = lang
    else:
        diag.append("bad language %r — default vi" % lang)
    hz = raw.get("humanize", False)
    if isinstance(hz, bool):
        out["humanize"] = hz
    else:
        diag.append("bad humanize %r — default false" % hz)
    for key in ("audience", "code_style"):
        try:
            out[key] = _validate_level(key, raw.get(key), "")
        except OutputConfigError as e:
            diag.append(str(e))  # leaves the safe default in place
    tlang = raw.get("thinking_language", _THINKING_DEFAULT)
    if isinstance(tlang, str) and tlang.strip():
        out["thinking_language"] = tlang.strip()
    else:
        diag.append("bad thinking_language %r — default %r" % (tlang, _THINKING_DEFAULT))
    # Fail-OPEN, and the safe default here means OFF for the expensive switch and ON
    # for the cheap ones — a corrupt file must not silently turn 874 KB on.
    try:
        out["visual"] = _validate_visual(raw.get("visual"), "")
    except OutputConfigError as e:
        diag.append(str(e))
    if diag:
        out["_diag"] = diag
    return out


def resolve_all(voice_path=None, output_path=None) -> dict:
    """Compose the terminal-voice axes (voice_prefs.load, fail-open) and the
    report/docs axes (output_config.load, fail-open) into ONE flat dict for a
    caller that wants every knob (e.g. `hs:setup show`, skill runtime). The two
    files own disjoint domains so the flat merge cannot collide. Never raises —
    both halves are fail-open by construction, and the terminal-voice keys are
    always present (seeded from DEFAULTS) even if voice_prefs.load itself raises
    (e.g. PyYAML missing), so a consumer can index them without a KeyError."""
    import voice_prefs  # same scripts dir

    # Seed the voice axes from DEFAULTS first: voice_prefs.load is fail-open, but a
    # pre-try failure (the lazy `import yaml` raising ImportError) would otherwise
    # leave the voice keys absent and make a hard-indexing caller raise.
    merged = dict(voice_prefs.DEFAULTS)
    try:
        merged.update(voice_prefs.load(path=voice_path))
    except Exception as e:  # voice_prefs.load is fail-open, but stay defensive
        merged["_voice_diag"] = str(e)
    merged.update(load(path=output_path))

    # Legacy shim: a pre-migration install still carries `output_style` in
    # terminal-voice.yaml. output.yaml's `code_style` is canonical and wins; only
    # when it is unset do we fall back to the old value (and flag it deprecated).
    if merged.get("code_style") is None:
        try:
            legacy = voice_prefs.legacy_output_style(path=voice_path)
        except Exception:
            legacy = None
        if legacy is not None:
            merged["code_style"] = legacy
            merged.setdefault("_diag", []).append(
                "deprecated: `output_style` in terminal-voice.yaml is read as "
                "`code_style`; migrate it to output.yaml")
    return merged


def _preserved_header(path: Path) -> str:
    """Leading comment/blank header kept across a CLI write (shared extractor in
    config_io). Missing file → a minimal header."""
    import config_io
    return config_io.leading_comment_block(
        path, "# output.yaml — language + humanize for GENERATED prose.\n")


def save_output(updates: dict, path=None) -> Path:
    """Validate + write output.yaml, merging ``updates`` over the current values
    (every unspecified key is preserved). Raises OutputConfigError on an unknown
    key / bad language / non-bool humanize BEFORE any write, so the file stays
    canonical. The header comment block is preserved."""
    p = Path(path) if path else _OUTPUT_DEFAULT
    # Lenient on thinking_language: a prior unquoted write may have let YAML 1.1
    # fold it to a bool, and that must not block THIS write from repairing it
    # (or any other knob) — see load_output()'s docstring for the seam.
    current = load_output(path=p, _lenient_thinking_language=True)
    for key in updates:
        if key not in _CANONICAL_KEYS:
            raise OutputConfigError(
                "unknown output knob %r — valid: %s"
                % (key, ", ".join(_CANONICAL_KEYS)))
    merged = dict(current)
    merged.update(updates)
    if merged["language"] not in VALID_LANGUAGES:
        raise OutputConfigError(
            "key `language` must be one of %s (got %r)"
            % (sorted(VALID_LANGUAGES), merged["language"]))
    if not isinstance(merged["humanize"], bool):
        raise OutputConfigError(
            "key `humanize` must be true or false (got %r)" % merged["humanize"])
    merged["audience"] = _validate_level("audience", merged.get("audience"), "")
    merged["code_style"] = _validate_level("code_style", merged.get("code_style"), "")
    tlang = merged.get("thinking_language")
    if not isinstance(tlang, str) or not tlang.strip():
        raise OutputConfigError(
            "key `thinking_language` must be a non-empty language code/name "
            "(got %r); default is %r" % (tlang, _THINKING_DEFAULT))
    merged["thinking_language"] = tlang.strip()

    # Field-agnostic serialize: emit every canonical key that is set, in order,
    # skipping None/absent. A new field is persisted the moment it appears here —
    # never dropped by a later single-key write (the drop-on-write corruption).
    lines = []
    for key in _CANONICAL_KEYS:
        val = merged.get(key)
        if val is None:
            continue
        if key == "humanize":
            lines.append("%s: %s" % (key, "true" if val else "false"))
        elif key == "thinking_language":
            # A bare word like `no`/`off`/`true` is a legitimate free-string
            # value (e.g. "no" == Norwegian) that YAML 1.1 would otherwise fold
            # to a bool on the next read. yaml_io.safe_dump quotes it only when
            # the scalar is actually ambiguous, so a plain value stays unquoted
            # (same behavior as PyYAML's safe_dump — see test_yaml_io.py).
            import yaml_io
            lines.append(yaml_io.safe_dump({key: val}, default_flow_style=False).strip())
        else:
            lines.append("%s: %s" % (key, val))
    body = "\n".join(lines) + "\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    from register_store import atomic_write
    atomic_write(p, _preserved_header(p) + body)
    return p


def _coerce(key: str, value: str):
    if key == "humanize":
        low = value.strip().lower()
        if low in ("true", "yes", "on", "1"):
            return True
        if low in ("false", "no", "off", "0"):
            return False
        raise OutputConfigError("humanize must be true/false (got %r)" % value)
    if key in ("audience", "code_style"):
        # _validate_level folds `off`→None and range-checks; let it own the rules.
        return _validate_level(key, value, "")
    return value


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(
        description="read/write output.yaml (generated-prose language)")
    ap.add_argument("--file", default=None,
                    help="explicit output.yaml path (default: shipped tracked file)")
    ap.add_argument("--set", dest="sets", action="append", metavar="KEY=VALUE",
                    help="write a knob (language|humanize|audience|code_style); repeatable")
    ap.add_argument("--resolved", action="store_true",
                    help="print resolve_all() (terminal-voice + output axes merged, "
                         "honoring HARNESS_OUTPUT + HARNESS_TERMINAL_VOICE) — the source "
                         "skills/agents read; fail-open, NOT a gate path")
    args = ap.parse_args(argv)
    path = args.file
    if args.resolved:
        import json
        # resolve_all is fail-open and honors both env seams; --file (if given)
        # pins the output side, else the env/shipped file is used.
        print(json.dumps(resolve_all(output_path=path), indent=2, ensure_ascii=False))
        return 0
    if not args.sets:
        import json
        print(json.dumps(load_output(path=path), indent=2, ensure_ascii=False))
        return 0
    updates = {}
    for pair in args.sets:
        if "=" not in pair:
            sys.stderr.write("--set expects KEY=VALUE, got %r\n" % pair)
            return 2
        key, value = pair.split("=", 1)
        try:
            updates[key] = _coerce(key, value)
        except OutputConfigError as e:
            sys.stderr.write("%s\n" % e)
            return 2
    try:
        p = save_output(updates, path=path)
    except OutputConfigError as e:
        sys.stderr.write("OutputConfigError: %s\n" % e)
        return 1
    print("saved output → %s" % p)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
