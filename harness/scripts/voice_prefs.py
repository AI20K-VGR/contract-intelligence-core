#!/usr/bin/env python3
"""voice_prefs.py — resolve the terminal-voice knobs from terminal-voice.yaml.

The terminal voice is the harness's CONVERSATIONAL register in the terminal —
how the assistant talks to the user while working — NOT the language or candor
of any written artifact. Knobs:

  terminal_voice_level   0..5   explanation depth/format of terminal answers (5 = full)
  persona        none + 13 catalog ids   the surface FORM of terminal prose
                       (the full catalog of ids; `none` is the default)
  voice_level    1..9   harshness/bluntness register on the terminal (5 = blunt,
                       no profanity; 6-9 escalate). The universal-harm floor and
                       the scope-fence are enforced in harness/rules/terminal-voice.md,
                       NOT here — this module stores closed-enum values, judges nothing.
  no_markdown    bool   drop markdown formatting from terminal answers

SCOPE-FENCE: these knobs shape terminal SURFACE prose only. They never alter
code, generated docs/reports, commits, evidence, or any gate decision; and they
do NOT control an artifact's own designed voice (the journal-writer's brutal
candor, the hs:critique neutral tone). See harness/rules/terminal-voice.md.

Tolerance ported from product-spec preferences.py: a missing file, missing key,
out-of-range enum, wrong-typed value, or corrupt YAML all resolve to the default
and load() NEVER raises. The write path (save) validates the closed enums and
raises VoicePrefsError so the on-disk file stays canonical for the next read.

Loader idiom mirrors guard_policy: resolve off __file__, honor an env override
HARNESS_TERMINAL_VOICE so tests/ephemeral runs point at a scratch file; the
committed default lives next to the data dir.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


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

_VOICE_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "terminal-voice.yaml"


class VoicePrefsError(ValueError):
    """Raised by save() when a value violates a closed enum (write-path only).

    The read path is deliberately tolerant — load() never raises — but the write
    path validates so the on-disk file stays canonical for the next read."""


# The single authoritative home for the terminal-voice defaults. Adding a knob
# here (with its default) is the ONLY place a new knob is registered.
DEFAULTS: Dict[str, Any] = {
    "terminal_voice_level": 5,
    "persona": "none",
    "voice_level": 5,
    "no_markdown": False,
    # Interview-rigor knobs (ported from product-spec preferences.py). LLM-side
    # guidance, not script gates: surfaced in the SessionStart additionalContext
    # and read by hs:plan / hs:discover / hs:brainstorm. Neutral default
    # `standard` so a fresh project is neither under- nor over-questioned.
    "interview_rigor": "standard",   # depth of challenge / gap-probing (NOT verbosity)
    "action_prompting": "standard",  # density of suggested next-actions at turn ends
    # persona_bundle: the id of an active persona bundle (a full character profile
    # in persona-bundles.yaml) or None (OFF, the default). It is NOT a closed enum
    # here — the ids are dynamic (registry-resolved), so it rides the tolerant read
    # path (pass-through) and the verbatim write path (save persists it, never
    # validates). Validation lives at the SETTER (apply_bundle + CLI) so a stale
    # on-disk id can never brick another voice write. When set, the bundle ABSORBS
    # the `persona` knob (its form wins); its default_voice_level SEEDS voice_level
    # at write time only (apply_bundle), never overriding voice_level at load.
    "persona_bundle": None,
    # voice_surface: whether the CONVERSATIONAL half of the register block is
    # injected at all — the harshness ladder, the persona line, the universal-harm
    # floor, and the authority pointer. `off` skips emitting them; it deletes
    # nothing, so `on` restores the block byte for byte and every knob above keeps
    # its meaning for /hs:voice and the rule file.
    #
    # Why a deployment turns it off: those lines only change how the assistant
    # TALKS, and a project that has settled on a neutral voice gets no behaviour
    # from any of them — measured at 1213 of 2850 characters, paid on every
    # SessionStart and every spawn. What they do NOT cover is what gets WRITTEN
    # (audience / code_style / language) or the scope-fence that keeps those off an
    # evidence token; those survive `off` because they are not voice.
    "voice_surface": "on",
    # NOTE: `detail_level` (interview/turn verbosity) was merged into
    # `terminal_voice_level` — one 0..5 scale now sizes both answer depth and
    # interview verbosity. A legacy `detail_level` key is shimmed in load().
    # NOTE: the audience-adaptation level (formerly `output_style`) now lives in
    # output.yaml as `code_style`, owned by output_config — it shapes generated
    # CODE, a deliverable concern, not the scope-fenced terminal voice. Only the
    # level→profile DATA + resolver remain here (CODE_STYLE_NAMES / code_style_profile).
}

# The persona catalog ids. The id strings live here (the enum's source); the
# one-line style descriptions + groups live in harness/rules/terminal-voice.md
# and the /hs:voice menu — a parity test keeps the three homes from drifting.
# work-group personas are default-eligible; fun-group are opt-in only. persona
# sets the surface FORM of terminal prose; voice_level sets the harshness inside.
WORK_PERSONAS = (
    "military", "reality-check", "git-log", "socratic",
    "bluf", "rubber-duck", "feynman", "first-principles",
)
FUN_PERSONAS = ("caveman", "yoda", "pirate", "80s-hacker", "dad-joke")
PERSONAS = ("none",) + WORK_PERSONAS + FUN_PERSONAS

# Closed enums per scalar key. A value outside its set is treated as absent
# (read path: fall back to default; write path: VoicePrefsError).
ENUMS: Dict[str, frozenset] = {
    "terminal_voice_level": frozenset(range(0, 6)),   # 0..5
    "persona": frozenset(PERSONAS),           # none + 13 catalog ids
    "voice_level": frozenset(range(1, 10)),   # 1..9
    "interview_rigor": frozenset({"light", "standard", "deep"}),
    "action_prompting": frozenset({"minimal", "standard", "proactive"}),
    "voice_surface": frozenset({"on", "off"}),
}

# code_style audience profiles (ported, renamed from output_style). The full
# directives live in harness/data/output-styles/code-style-level-<n>.md; the
# short ESSENCE below is the always-injected steer, with the file available on
# demand for the full MANDATORY rules. NAMES is the single source for the
# level<->name mapping. The knob VALUE lives in output.yaml (output_config); only
# this level→profile data + the resolver below stay here.
CODE_STYLE_NAMES: Dict[int, str] = {
    0: "eli5", 1: "junior", 2: "mid", 3: "senior", 4: "lead", 5: "god",
}
CODE_STYLE_ESSENCE: Dict[int, str] = {
    0: "reader is an absolute beginner — real-world analogies, define every term, "
       "comment every line, 5-10 line code blocks, show expected output, end with a check-in",
    1: "reader is a junior (0-2y) — explain the why before the how, name the patterns, "
       "moderate comments, link to docs, encourage",
    2: "reader is mid-level (3-5y) — system thinking and trade-offs, professional patterns, "
       "less hand-holding, brief rationale",
    3: "reader is senior (5-8y) — concise; lead with trade-offs, edge cases, operational "
       "concerns; skip the basics",
    4: "reader is a lead (8-15y) — strategic framing, risk assessment, business alignment, brevity",
    5: "reader is an expert (15y+) — terse, code-first, zero explanation unless asked; "
       "challenge a flawed approach as a peer",
}


def code_style_profile(level):
    """Resolve a code_style level to its profile, or None when off.

    Returns {"level", "name", "essence", "file"} for 0..5; None for None/unknown.
    `file` points at the full profile doc under harness/data/output-styles/.
    """
    if level is None or level not in CODE_STYLE_NAMES:
        return None
    name = CODE_STYLE_NAMES[level]
    f = Path(__file__).resolve().parent.parent / "data" / "output-styles" / (
        "code-style-level-%d.md" % level)
    return {"level": level, "name": name, "essence": CODE_STYLE_ESSENCE[level], "file": str(f)}


# Audience prose register — names map jargon-tolerance level to a behaviour-based
# label (no job-title labels). Level 0 = plain/accessible, 5 = peer/dense.
AUDIENCE_NAMES: Dict[int, str] = {
    0: "plain", 1: "guided", 2: "informed", 3: "practitioner", 4: "expert", 5: "peer",
}
# Prose-only one-liner per level — the always-injected steer for CHAT + report
# register. The full MANDATORY directives live in audience-level-N.md; this is
# the short essence. Evidence tokens (file:line/IDs/SHAs/numbers/quotes) are
# invariant at EVERY level — these phrasings never license altering them.
AUDIENCE_ESSENCE: Dict[int, str] = {
    0: "write for a non-technical reader — open with a plain-language so-what, "
       "define every term inline, close with a short glossary",
    1: "write for a guided reader — explain jargon on first use, keep a gentle "
       "so-what framing, avoid unexplained acronyms",
    2: "write for an informed reader — assume basic domain literacy, define only "
       "specialist terms",
    3: "write for a practitioner — normal domain vocabulary, no hand-holding, "
       "context only where non-obvious",
    4: "write for an expert — dense domain vocabulary, skip background, lead with "
       "the load-bearing point",
    5: "write for a peer — maximal density, terse, assume full shared context",
}


def audience_profile(level):
    """Resolve an audience level to its prose profile, or None when absent/off.

    Returns {"level", "name", "essence", "file"} for 0..5; None for None/out-of-range.
    `file` points at the audience-level-N.md profile under harness/data/output-styles/.
    The `audience` knob lives in output.yaml (output_config); only the resolver
    and the level→name/essence mapping stay here.
    """
    if level is None or level not in AUDIENCE_NAMES:
        return None
    name = AUDIENCE_NAMES[level]
    f = Path(__file__).resolve().parent.parent / "data" / "output-styles" / (
        "audience-level-%d.md" % level)
    return {"level": level, "name": name, "essence": AUDIENCE_ESSENCE[level], "file": str(f)}

# Keys whose canonical type is bool: validated by TYPE, not membership. Kept
# out of ENUMS because `True == 1` / `False == 0` in Python would let a bool
# satisfy an int enum (and an int satisfy a bool), so bool is handled apart.
_BOOL_KEYS: frozenset = frozenset({"no_markdown"})


# Dev-only override discovery — TERMINAL VOICE ONLY. A gitignored
# .harness-dev/terminal-voice.yaml at the repo root lets a dev run a different
# CONVERSATIONAL posture without editing the committed default (which must ship
# safe) and without an env var or session restart — the file is read live on
# every load(). Resolved AFTER the env seam and BEFORE the shipped default.
#
# Deliberately limited to the terminal voice, which is scope-fenced and never
# changes a gate verdict. Gate-AFFECTING config (guard_policy, artifact_check
# stage policy) is NOT file-discovered: it stays env-bound so the pre-push hook's
# HARNESS_* env scrub can neutralize a local override and the real-push gate
# always reads the tracked file (see test_pre_push_env_scrub.py).
_DEV_OVERRIDE = (".harness-dev", "terminal-voice.yaml")


def _repo_root() -> Path:
    """Repo root for locating the dev override. Honors HARNESS_ROOT (the same
    test / odd-layout seam harness_paths uses), else derives from this file's
    location (harness/scripts/ -> repo root)."""
    raw = os.environ.get("HARNESS_ROOT")
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[2]


def _dev_override_path() -> Optional[Path]:
    """The gitignored repo-root dev override if present, else None."""
    cand = _repo_root().joinpath(*_DEV_OVERRIDE)
    return cand if cand.is_file() else None


def _voice_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    raw = os.environ.get("HARNESS_TERMINAL_VOICE")
    if raw:
        return Path(raw)
    dev = _dev_override_path()
    if dev is not None:
        return dev
    return _VOICE_DEFAULT


def voice_path(path=None) -> Path:
    """The resolved config path (explicit arg > HARNESS_TERMINAL_VOICE > shipped
    default). Public so the quick-switch skill writes the same file load reads."""
    return _voice_path(path)


def load(path=None) -> Dict[str, Any]:
    """Return the resolved terminal-voice knobs: every key present, defaults
    filled. A missing file, missing key, out-of-range enum, wrong-typed value,
    or unparseable YAML all degrade to defaults — this function never raises."""
    import yaml_io  # lazy: keep importable without ruamel until actually used

    resolved = dict(DEFAULTS)
    p = _voice_path(path)
    try:
        raw = _yaml_load(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, yaml_io.YAMLError):
        return resolved
    if not isinstance(raw, dict):
        # A scalar / list top-level (corrupt or hand-mangled) is not a mapping;
        # ignore it wholesale rather than guess.
        return resolved

    for key in DEFAULTS:
        if key not in raw:
            continue
        value = raw[key]
        if key in _BOOL_KEYS:
            # Accept only a real bool; a hand-edited non-bool is ignored.
            if isinstance(value, bool):
                resolved[key] = value
        elif key in ENUMS:
            # Reject bool explicitly: True/False would otherwise match an int
            # enum's 1/0. A level is an int, never a bool.
            if not isinstance(value, bool) and value in ENUMS[key]:
                resolved[key] = value
            # else: leave the default (defensive against a hand-edited typo)
        else:
            resolved[key] = value

    # Legacy shim: `detail_level` was merged into `terminal_voice_level`. An old
    # config carrying detail_level with no explicit terminal_voice_level maps the
    # old verbosity onto the 0..5 scale; an explicit terminal_voice_level wins.
    if "detail_level" in raw and "terminal_voice_level" not in raw:
        mapped = {"concise": 2, "standard": 3, "verbose": 5}.get(raw.get("detail_level"))
        if mapped is not None:
            resolved["terminal_voice_level"] = mapped
            resolved.setdefault("_diag", []).append(
                "deprecated: `detail_level` is merged into `terminal_voice_level` "
                "(concise->2, standard->3, verbose->5); migrate it")
    return resolved


def legacy_output_style(path=None):
    """Read a pre-migration `output_style` level straight from terminal-voice.yaml.

    The knob was renamed `code_style` and moved to output.yaml; `load()` no longer
    surfaces it. This probe lets the resolver shim an OLD install (terminal-voice
    still carries the value) until the project migrates. Returns 0..5, else None.
    Never raises — a corrupt/absent file just yields None."""
    import yaml_io  # lazy
    try:
        raw = _yaml_load(_voice_path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, yaml_io.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    val = raw.get("output_style")
    if isinstance(val, bool) or not isinstance(val, int):
        return None
    return val if 0 <= val <= 5 else None


def _preserved_header(p) -> str:
    """Keep terminal-voice.yaml's documentation header across a --set rewrite,
    mirroring the sibling config CLIs (output/guard/team via
    config_io.leading_comment_block) — the header is the only in-file record of
    the knob ranges, so a rewrite must not destroy it. Missing file → a minimal
    header."""
    import config_io
    return config_io.leading_comment_block(
        p, "# terminal-voice.yaml — conversational register for TERMINAL prose "
           "only (scope-fenced; never code/gates/evidence).\n")


def save(prefs: Dict[str, Any], path=None) -> Path:
    """Validate + write terminal-voice.yaml.

    Only known keys are persisted (unknown keys are dropped — the schema is
    closed). A value outside its closed enum, or a non-bool for a bool key,
    raises VoicePrefsError before any write. The leading comment header is
    preserved across the rewrite (matching the sibling config CLIs)."""
    import yaml_io

    out: Dict[str, Any] = {}
    for key, value in prefs.items():
        if key not in DEFAULTS:
            continue  # drop unknown keys — schema is closed
        if key in _BOOL_KEYS:
            if not isinstance(value, bool):
                raise VoicePrefsError(
                    f"terminal-voice {key!r}={value!r} must be true or false")
        elif key in ENUMS:
            if isinstance(value, bool) or value not in ENUMS[key]:
                raise VoicePrefsError(
                    f"terminal-voice {key!r}={value!r} is not one of "
                    f"{sorted(ENUMS[key], key=lambda v: (v is not None, v))}")
        out[key] = value

    p = _voice_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = _preserved_header(p)  # read BEFORE opening 'w' truncates the file
    body = yaml_io.safe_dump(out, sort_keys=True, allow_unicode=True,
                             default_flow_style=False)
    # newline='' keeps the file byte-stable (LF) across platforms.
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(header + body)
    return p


def apply_bundle(bundle_id, tv_path=None) -> Path:
    """Apply a persona bundle: the WRITE-TIME SEED writer (mirrors a preset apply).

    Validates bundle_id ∈ valid_ids() ∪ {None} at the SETTER — an unknown id raises
    VoicePrefsError BEFORE any write (validation-at-setter; save() itself never
    validates, so a rolled-back id never bricks other voice writes). On a known id
    it sets persona_bundle and SEEDS voice_level from the bundle's
    default_voice_level (last-writer-wins — it never re-seeds on load).
    apply_bundle(None) clears the active bundle.

    persona_bundle is imported lazily to keep the load/save hot path free of the
    registry and to avoid an import cycle (the registry module is a leaf)."""
    import persona_bundle  # lazy: hot read/write path stays registry-free

    if bundle_id is not None and bundle_id not in persona_bundle.valid_ids():
        raise VoicePrefsError(
            f"persona_bundle {bundle_id!r} is not a known bundle id")

    current = load(tv_path)
    current["persona_bundle"] = bundle_id
    if bundle_id is not None:
        bundle = persona_bundle.resolve(bundle_id)
        if bundle is not None:
            lvl = bundle.get("default_voice_level")
            if lvl in ENUMS["voice_level"]:
                current["voice_level"] = lvl
    return save(current, path=tv_path)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="read/write the terminal-voice knobs (terminal-voice.yaml)")
    ap.add_argument(
        "--set",
        dest="sets",
        action="append",
        metavar="KEY=VALUE",
        help="write a known knob (repeatable). load->merge->save: every other "
             "committed knob is preserved. An unknown key OR a value outside the "
             "key's closed enum exits non-zero, writing nothing. Digit strings "
             "coerce to int for level keys; true/false to bool for no_markdown.",
    )
    args = ap.parse_args()

    if not args.sets:
        print(json.dumps(load(), indent=2, ensure_ascii=False))
        return 0

    prefs = load()
    for pair in args.sets:
        if "=" not in pair:
            print(f"--set: expected KEY=VALUE, got {pair!r}", file=sys.stderr)
            return 2
        key, value = pair.split("=", 1)  # split on FIRST '=' only
        if key not in DEFAULTS:
            # save() silently drops unknown keys; reject here so a typo is a
            # loud non-zero exit, not a "saved" no-op the user would trust.
            print(f"--set: unknown knob {key!r}", file=sys.stderr)
            return 2
        if key in _BOOL_KEYS:
            low = value.strip().lower()
            if low in ("true", "yes", "on", "1"):
                value = True
            elif low in ("false", "no", "off", "0"):
                value = False
            else:
                print(f"--set: knob {key!r} must be true/false; got {value!r}",
                      file=sys.stderr)
                return 2
        elif key == "persona_bundle":
            # off-able + registry-validated at the setter (never a closed enum).
            low = value.strip().lower()
            if low in ("off", "none", "null", ""):
                value = None
            else:
                import persona_bundle
                if value not in persona_bundle.valid_ids():
                    print(f"--set: unknown persona_bundle id {value!r}",
                          file=sys.stderr)
                    return 2
        elif None in ENUMS.get(key, frozenset()):
            # off-able knob (None in its enum): off/none -> None, digits -> int
            low = value.strip().lower()
            if low in ("off", "none", "null", ""):
                value = None
            elif (low[:1] == "-" and low[1:].isdigit()) or low.isdigit():
                value = int(value)
        elif isinstance(DEFAULTS[key], int) and (
            (value[:1] == "-" and value[1:].isdigit()) or value.isdigit()
        ):
            value = int(value)
        prefs[key] = value

    try:
        p = save(prefs)
    except VoicePrefsError as exc:
        print(f"VoicePrefsError: {exc}", file=sys.stderr)
        return 1
    print(f"saved terminal-voice → {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
