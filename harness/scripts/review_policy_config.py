#!/usr/bin/env python3
"""review_policy_config.py — read/set the shared review-policy.yaml.

review-policy.yaml names tactical review profiles (rounds + the four axes), a
per-hard-stage effort/rounds floor (ships OFF), and caps. This module is the
single reader/writer for it.

Fail-open non-breaking: an ABSENT file resolves to a default with every stage
floor disabled, so a fresh install behaves exactly as before. A PRESENT but
malformed file (non-mapping, bad enum) raises ReviewPolicyConfigError so the CLI
can point the human at the typo — but the gate that consults this policy wraps
the call in try/except and treats any raise as a no-op (the floor is a
self-discipline tier, never a real boundary).

The writer is SURGICAL and block-scoped: it rewrites ONLY the one nested line
named by a `stage_floor.<stage>.<knob>` or `profiles.<name>.<knob>` dot-key,
leaving comments and every other line byte-for-byte intact. Read path resolves
the tracked file off __file__ (never CWD); tests pass `path=` explicitly.

── DEEP MERGE (omegaconf, not mergedeep) ──────────────────────────────────────
`profiles` and `stage_floor` are TWO levels deep (block -> name -> knob), so a
block-level `dict.update()` replaces a whole `profiles.default` sub-dict when
the file overrides just one of its knobs, silently dropping the others — a real
bug this loader used to carry. The merge below fixes that AND blocks a
misspelled knob (`compunding` for `compounding`) that a plain recursive merge
would accept as a new, silently-dead key. `mergedeep` (bought the same round,
see release_orchestrator.load_config) does the first half only — no struct, so
no typo defense — which is the boundary: reach for `mergedeep` on a plain
recursive dict merge, `omegaconf` where the merge target has a fixed, typo-able
knob set worth blocking. Loading always goes ruamel (`yaml_io`) -> plain dict ->
`OmegaConf.create(dict)`; `OmegaConf.load`/`.create(<yaml text>)` are
mechanically banned (test_library_boundary_bans.py) because they re-fold
`off`/`no` to bool at OmegaConf's own coercion layer, the same trap `yaml_io`
exists to close on the read side.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

_REVIEW_POLICY_DEFAULT = (
    Path(__file__).resolve().parent.parent / "data" / "review-policy.yaml")


@dataclass
class _ProfileSchema:
    """Typo-blocking shape for one `profiles.<name>` entry — omegaconf raises on
    an unknown field when this is the merge target's struct."""
    rounds: int = 1
    compounding: bool = False
    per_aspect: bool = False
    blind_main_sub: bool = False
    refute: bool = False
    effort: str = "low"
    scope: str = "diff"
    aspects: List[str] = field(default_factory=lambda: ["correctness"])


@dataclass
class _StageFloorSchema:
    """Typo-blocking shape for one `stage_floor.<stage>` entry."""
    enabled: bool = False
    min_effort: str = "low"
    min_rounds: int = 1


def _deep_merge_block(default_block: dict, raw_block: dict, *, schema, block_name, source) -> dict:
    """Merge `raw_block` (one `profiles`/`stage_floor` sub-mapping keyed by
    name/stage) over `default_block`, per-entry, via `OmegaConf.merge` against
    `schema` — deep (knob-level) instead of the old block-level `dict.update`,
    and struct-typed so a misspelled knob raises instead of landing as a dead
    key. A name absent from `raw_block` is untouched (union, not intersection)."""
    from omegaconf import OmegaConf
    from omegaconf.errors import OmegaConfBaseException

    merged = {name: dict(spec) for name, spec in default_block.items()}
    for name, override in raw_block.items():
        if not isinstance(override, dict):
            raise ReviewPolicyConfigError(
                "%s.%s in %s must be a mapping (got %s)"
                % (block_name, name, source, type(override).__name__))
        base_cfg = OmegaConf.structured(schema(**merged.get(name, {})))
        try:
            result = OmegaConf.merge(base_cfg, OmegaConf.create(override))
            # resolve=False is load-bearing, not a default being restated.
            #
            # With resolution ON, every string in this block becomes an interpolation
            # site, and OmegaConf ships an `${oc.env:VAR}` resolver. Measured: one edited
            # line in review-policy.yaml — `aspects: ["${oc.env:GITHUB_TOKEN}"]` — made
            # the documented inspection command print the real token to stdout, into the
            # terminal, the transcript, and any CI log capturing it. `_validate_policy`
            # does not close it; that check only inspects `effort` and `scope`, while
            # `aspects` is a free-form List[str].
            #
            # Turned off outright rather than filtered by resolver name: nothing in this
            # repo uses interpolation (the decision that bought omegaconf recorded zero
            # sites), and a denylist is the wrong shape for a feature with no users —
            # `${oc.decode:'${oc.env:X}'}` already reaches the same value by another name.
            #
            # Inside the try because resolution can itself raise: with it outside, an
            # interpolation failure escaped as a raw OmegaConf exception and broke this
            # module's own contract that a malformed file yields ReviewPolicyConfigError.
            merged[name] = OmegaConf.to_container(result, resolve=False)
        except OmegaConfBaseException as e:
            raise ReviewPolicyConfigError(
                "%s.%s in %s: %s" % (block_name, name, source, e)) from e
    return merged

_VALID_EFFORT = {"low", "medium", "high", "xhigh", "max"}
_VALID_SCOPE = {"diff", "project"}
_STAGES = ("pr", "merge", "ship", "deploy")

# knob -> coercion type for the surgical writer / loader validation.
_PROFILE_KNOBS = {
    "rounds": "int", "compounding": "bool", "per_aspect": "bool",
    "blind_main_sub": "bool", "refute": "bool", "effort": "effort",
    "scope": "scope",
}
_FLOOR_KNOBS = {"enabled": "bool", "min_effort": "effort", "min_rounds": "int"}


class ReviewPolicyConfigError(Exception):
    """Raised when review-policy.yaml is malformed or a write is rejected; the
    message names the file/key so the fix is a config edit, not a debug session."""


def _default_policy() -> dict:
    """The all-floors-OFF default returned when the file is absent. A fresh dict
    each call so callers can never mutate a shared default."""
    def _floor():
        return {"enabled": False, "min_effort": "low", "min_rounds": 1}
    return {
        "profiles": {
            "default": {"rounds": 1, "compounding": False, "per_aspect": False,
                        "blind_main_sub": False, "refute": False,
                        "effort": "low", "scope": "diff",
                        "aspects": ["correctness"]},
            "thorough": {"rounds": 3, "compounding": True, "per_aspect": True,
                         "blind_main_sub": False, "refute": True,
                         "effort": "high", "scope": "diff",
                         "aspects": ["security", "dry", "correctness",
                                     "consistency"]},
            "ship-grade": {"rounds": 3, "compounding": True, "per_aspect": True,
                           "blind_main_sub": True, "refute": True,
                           "effort": "max", "scope": "project",
                           "aspects": ["security", "dry", "correctness",
                                       "consistency"]},
        },
        "stage_floor": {s: _floor() for s in _STAGES},
        "caps": {"max_rounds": 5, "max_lenses_per_round": 8},
    }


def _validate_profiles_block(profiles: dict, source) -> None:
    """Reject an out-of-enum effort/scope inside `profiles`. Split out of
    `_validate_policy` so `stage_floor`-only callers (`load_stage_floor`) can
    validate their one block without also requiring `profiles` to parse — a
    typo in `profiles.default.effort` must never block a `stage_floor` read,
    and vice versa (the two blocks are independently useful)."""
    for name, prof in (profiles or {}).items():
        if not isinstance(prof, dict):
            continue
        eff = prof.get("effort")
        if eff is not None and eff not in _VALID_EFFORT:
            raise ReviewPolicyConfigError(
                "profile %r in %s: effort must be one of %s (got %r)"
                % (name, source, sorted(_VALID_EFFORT), eff))
        scope = prof.get("scope")
        if scope is not None and scope not in _VALID_SCOPE:
            raise ReviewPolicyConfigError(
                "profile %r in %s: scope must be one of %s (got %r)"
                % (name, source, sorted(_VALID_SCOPE), scope))


def _validate_stage_floor_block(stage_floor: dict, source) -> None:
    """Reject an out-of-enum `min_effort` inside `stage_floor`. See
    `_validate_profiles_block` for why this is split out on its own."""
    for stage, floor in (stage_floor or {}).items():
        if not isinstance(floor, dict):
            continue
        me = floor.get("min_effort")
        if me is not None and me not in _VALID_EFFORT:
            raise ReviewPolicyConfigError(
                "stage_floor.%s in %s: min_effort must be one of %s (got %r)"
                % (stage, source, sorted(_VALID_EFFORT), me))


def _validate_policy(policy: dict, source) -> None:
    """Reject out-of-enum effort/scope so a bad file fails loudly at load."""
    _validate_profiles_block(policy.get("profiles") or {}, source)
    _validate_stage_floor_block(policy.get("stage_floor") or {}, source)


def stage_floor_peek(stage, path=None):
    """(enabled: bool, error: str|None) — the cheap raw-YAML peek at
    `stage_floor.<stage>.enabled`, ruamel only, no omegaconf, no default-fill,
    no schema validation.

    `error` is the thing `stage_floor_enabled()` (below) used to throw away: an
    ABSENT file cleanly resolves to (False, None) — that is the intentional
    fail-soft default, matching `load_review_policy`'s own direction, and stays
    silent. A PRESENT-but-unreadable file (malformed YAML, a non-mapping
    document, or `stage_floor.<stage>` itself not a mapping) instead resolves
    to (False, "<what went wrong>") — a caller that only reads the bool still
    gets the historic False, but a caller that needs to tell "cleanly off" from
    "could not tell" (`artifact_check._check_stage_floor`, so it can trace the
    failure instead of silently no-op'ing it) now can.
    """
    import yaml_io  # lazy

    p = Path(path) if path else _REVIEW_POLICY_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, None
    except Exception as e:  # noqa: BLE001 — named, not swallowed
        return False, "%s: %s" % (type(e).__name__, e)
    if raw is None:
        return False, None
    if not isinstance(raw, dict):
        return False, "review policy %s is not a YAML mapping" % p
    floor = (raw.get("stage_floor") or {}).get(stage)
    if floor is not None and not isinstance(floor, dict):
        return False, "stage_floor.%s in %s is not a mapping" % (stage, p)
    if not isinstance(floor, dict):
        return False, None
    enabled_raw = floor.get("enabled")
    verdict = _reads_as_true(enabled_raw)
    if verdict is None:
        # `None`, not `False`. The caller has to tell two different unknowns apart:
        # "the whole document is unreadable, so I cannot know whether a floor was even
        # intended" (fail-SOFT is right — nobody demonstrably opted in), versus "a
        # stage_floor block for this stage plainly exists and its enabled value is
        # gibberish" (fail-CLOSED is right — somebody opted in and the opt-in is broken).
        # Returning False for the second collapsed it into the first and switched the
        # floor off in silence.
        # UNRECOGNISED is not the same answer as OFF, and collapsing the two is how a
        # narrower fix reopened a wider hole: returning (False, None) lands the caller in
        # its "cleanly off — silent, no trace noise" branch, so `enabled: y` or
        # `enabled: 2` — which the typed loader coerces to TRUE — switched the floor off
        # without a single line of output. Before that collapse the gate blocked and said
        # why. An opt-in nobody can read is not an opt-out; it is a broken opt-in.
        return None, (
            "stage_floor.%s.enabled in %s reads %r, which is neither a boolean nor one "
            "of %s / %s — write it as `true` or `false`"
            % (stage, p, enabled_raw,
               "/".join(sorted(_TRUE_WORDS)), "/".join(sorted(_FALSE_WORDS))))
    return verdict, None


# `bool()` is the wrong test here, and wrong in the dangerous direction.
#
# The shared reader deliberately keeps a bare `off`/`no` a STRING — that is the whole
# reason it exists — and `bool("off")` is True, as is `bool("false")`. So the peek read
# every spelling this repo's own YAML rule RECOMMENDS for "I mean the word" as the floor
# being ON. The gate survived it only because a later disagreement branch treats
# peek-on/loader-off as off; the public `stage_floor_enabled()` still answered the
# question wrong.
#
# Matching the word set to what the typed loader coerces, rather than inventing a third
# vocabulary: anything not recognised is NOT enabled, because a floor is an opt-in and an
# unreadable opt-in has not been given.
_TRUE_WORDS = frozenset(["true", "yes", "on", "1"])
_FALSE_WORDS = frozenset(["false", "no", "off", "0"])


def _reads_as_true(value):
    """True / False / None, where None means "this is not a yes-or-no answer".

    The three-way return is the point. A two-way one has to guess for `y`, `2`, `maybe`,
    `1.0` — every guess is wrong in one direction, and guessing OFF is the dangerous one
    because the caller reads OFF as "the operator did not opt in" and stays silent.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
        return None
    if isinstance(value, int):
        return True if value == 1 else (False if value == 0 else None)
    if value is None:
        return False          # key absent entirely: a floor nobody turned on
    return None


def stage_floor_enabled(stage, path=None) -> bool:
    """Bool-only convenience wrapper over `stage_floor_peek` — every existing
    caller that only needs "is the floor on" keeps working unchanged (an
    unreadable file still collapses to False here). See `stage_floor_peek`'s
    docstring for the case this drops: prefer that function when the caller
    must react differently to a present-but-broken policy than to a cleanly
    absent one."""
    enabled, _error = stage_floor_peek(stage, path=path)
    return enabled


def load_review_policy(path=None) -> dict:
    """Parse review-policy.yaml. Missing file -> the all-floors-OFF default (no
    raise). A non-mapping document or an out-of-enum value raises
    ReviewPolicyConfigError. Present-but-partial documents are filled from the
    default per top-level block so resolve_profile always finds `default`."""
    import yaml_io  # lazy

    p = Path(path) if path else _REVIEW_POLICY_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _default_policy()
    if raw is None:
        return _default_policy()
    if not isinstance(raw, dict):
        raise ReviewPolicyConfigError(
            "review policy %s is malformed — expected a YAML mapping" % p)
    _validate_policy(raw, p)
    merged = _default_policy()
    if isinstance(raw.get("profiles"), dict):
        merged["profiles"] = _deep_merge_block(
            merged["profiles"], raw["profiles"],
            schema=_ProfileSchema, block_name="profiles", source=p)
    if isinstance(raw.get("stage_floor"), dict):
        merged["stage_floor"] = _deep_merge_block(
            merged["stage_floor"], raw["stage_floor"],
            schema=_StageFloorSchema, block_name="stage_floor", source=p)
    if isinstance(raw.get("caps"), dict):
        merged["caps"].update(raw["caps"])  # flat 2-key block, no nested knobs
    return merged


def load_stage_floor(path=None, *, stage=None) -> dict:
    """Parse + validate ONLY the `stage_floor` block, independent of
    `profiles`/`caps`.

    Why this exists alongside `load_review_policy`: that function loads and
    validates BOTH blocks in one pass, so a typo anywhere in `profiles` (an
    unrelated block `_check_stage_floor` never reads) raises before
    `stage_floor` is ever merged — a misspelled `profiles.default.compunding`
    then silently disables a `stage_floor` a team explicitly turned ON, because
    the caller's only recourse (today) is to catch the raise and no-op. This
    function reads and validates `stage_floor` on its own, so the ONE thing
    `_check_stage_floor` depends on can succeed or fail on its own merits.

    Same absence/raise contract as `load_review_policy`, scoped narrower: an
    ABSENT file (or one with no `stage_floor` key) resolves to the built-in
    all-off default; a malformed document (unreadable YAML, non-mapping, or a
    real typo inside `stage_floor` itself) raises `ReviewPolicyConfigError`
    naming it.
    """
    import yaml_io  # lazy

    p = Path(path) if path else _REVIEW_POLICY_DEFAULT
    default = _default_policy()["stage_floor"]
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    if raw is None:
        return default
    if not isinstance(raw, dict):
        raise ReviewPolicyConfigError(
            "review policy %s is malformed — expected a YAML mapping" % p)
    stage_floor_raw = raw.get("stage_floor")
    if not isinstance(stage_floor_raw, dict):
        return default
    if stage is not None:
        # Narrow to the stage the caller actually asked about. Splitting `stage_floor`
        # away from `profiles` fixed the cross-BLOCK version of this and left the
        # cross-STAGE one: a misspelled knob under `stage_floor.deploy` still raised
        # while checking `ship`, and the caller's fail-closed branch then blocked ship
        # for a typo in a stage it never reads. A floor is per-stage; so is its blast
        # radius. Stages the caller did not ask about keep their built-in defaults.
        stage_floor_raw = {k: v for k, v in stage_floor_raw.items() if k == stage}
    _validate_stage_floor_block(stage_floor_raw, p)
    return _deep_merge_block(
        default, stage_floor_raw,
        schema=_StageFloorSchema, block_name="stage_floor", source=p)


def resolve_profile(name, policy) -> dict:
    """Return the named profile, falling back to `default` (never crashing) for
    an unknown name + a stderr warning."""
    import sys
    profiles = policy.get("profiles") or {}
    if name in profiles:
        return profiles[name]
    sys.stderr.write(
        "review-policy: unknown profile %r — falling back to `default`\n" % name)
    return profiles.get("default", _default_policy()["profiles"]["default"])


def _coerce(knob, kind, value):
    """Coerce a raw (CLI string or Python) value to the knob's type, validating
    enums. Raises ReviewPolicyConfigError on a bad value."""
    if kind == "bool":
        if isinstance(value, bool):
            return value
        low = str(value).strip().lower()
        if low in ("true", "1", "yes", "on"):
            return True
        if low in ("false", "0", "no", "off"):
            return False
        raise ReviewPolicyConfigError("knob %r expects a boolean (got %r)"
                                      % (knob, value))
    if kind == "int":
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            raise ReviewPolicyConfigError("knob %r expects an integer (got %r)"
                                          % (knob, value))
    if kind == "effort":
        v = str(value).strip()
        if v not in _VALID_EFFORT:
            raise ReviewPolicyConfigError(
                "knob %r must be one of %s (got %r)"
                % (knob, sorted(_VALID_EFFORT), value))
        return v
    if kind == "scope":
        v = str(value).strip()
        if v not in _VALID_SCOPE:
            raise ReviewPolicyConfigError(
                "knob %r must be one of %s (got %r)"
                % (knob, sorted(_VALID_SCOPE), value))
        return v
    raise ReviewPolicyConfigError("unknown coercion kind %r" % kind)  # pragma: no cover


def _parse_dot_key(dot_key):
    """Resolve a `<block>.<sub>.<knob>` dot-key to (block, sub, knob, kind).
    Unknown shape/block/knob raises ReviewPolicyConfigError before any write."""
    parts = dot_key.split(".")
    if len(parts) != 3:
        raise ReviewPolicyConfigError(
            "unknown review-policy key %r — expected "
            "stage_floor.<stage>.<knob> or profiles.<name>.<knob>" % dot_key)
    block, sub, knob = parts
    if block == "stage_floor":
        if sub not in _STAGES:
            raise ReviewPolicyConfigError(
                "unknown stage %r — expected one of %s" % (sub, list(_STAGES)))
        if knob not in _FLOOR_KNOBS:
            raise ReviewPolicyConfigError(
                "unknown stage_floor knob %r — expected one of %s"
                % (knob, sorted(_FLOOR_KNOBS)))
        return block, sub, knob, _FLOOR_KNOBS[knob]
    if block == "profiles":
        if knob not in _PROFILE_KNOBS:
            raise ReviewPolicyConfigError(
                "unknown profile knob %r — expected one of %s"
                % (knob, sorted(_PROFILE_KNOBS)))
        return block, sub, knob, _PROFILE_KNOBS[knob]
    raise ReviewPolicyConfigError(
        "unknown review-policy block %r — expected stage_floor or profiles"
        % block)


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _rewrite_nested_line(lines, block, sub, knob, formatted):
    """Block-scoped surgical rewrite: find `^block:`, then the `sub:` line under
    it (by indent), then the `knob:` line in that sub-block, and rewrite only its
    value — preserving the key's leading whitespace. Returns True on success."""
    block_re = re.compile(r"^(\s*)%s\s*:\s*$" % re.escape(block))
    i = 0
    n = len(lines)
    # locate block
    while i < n and not block_re.match(lines[i]):
        i += 1
    if i >= n:
        return False
    block_indent = len(block_re.match(lines[i]).group(1))
    i += 1
    # locate sub-block under block
    sub_re = re.compile(r"^(\s+)%s\s*:\s*$" % re.escape(sub))
    sub_indent = None
    while i < n:
        line = lines[i]
        if line.strip() and not line.lstrip().startswith("#"):
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent <= block_indent:
                return False  # left the block without finding sub
        m = sub_re.match(line)
        if m and (len(m.group(1)) > block_indent):
            sub_indent = len(m.group(1))
            i += 1
            break
        i += 1
    if sub_indent is None:
        return False
    # locate knob line within sub-block
    knob_re = re.compile(r"^(\s+)%s\s*:\s*(.*)$" % re.escape(knob))
    while i < n:
        line = lines[i]
        if line.strip() and not line.lstrip().startswith("#"):
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent <= sub_indent:
                return False  # left the sub-block without finding knob
        m = knob_re.match(line)
        if m and len(m.group(1)) > sub_indent:
            lines[i] = "%s%s: %s\n" % (m.group(1), knob, formatted)
            return True
        i += 1
    return False


def save_review_policy(updates: dict, path=None) -> Path:
    """Surgically set one or more nested knobs. Every key/value is validated
    BEFORE any write; an unknown key or bad value raises ReviewPolicyConfigError
    and the file is left untouched. Comments and untouched lines are preserved."""
    p = Path(path) if path else _REVIEW_POLICY_DEFAULT
    if not updates:
        return p
    # validate everything first (no partial writes)
    resolved = []
    for dot_key, value in updates.items():
        block, sub, knob, kind = _parse_dot_key(dot_key)
        coerced = _coerce(knob, kind, value)
        resolved.append((block, sub, knob, _format_value(coerced)))

    text = p.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for block, sub, knob, formatted in resolved:
        if not _rewrite_nested_line(lines, block, sub, knob, formatted):
            raise ReviewPolicyConfigError(
                "could not locate %s.%s.%s in %s — key path not present in file"
                % (block, sub, knob, p))
    from register_store import atomic_write
    atomic_write(p, "".join(lines))
    return p


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(
        description="read/set the shared review-policy.yaml (profiles + "
                    "stage_floor + caps)")
    ap.add_argument("--file", default=None,
                    help="explicit review-policy.yaml path (default: shipped file)")
    ap.add_argument("--set", dest="sets", action="append", metavar="KEY=VALUE",
                    help="surgically set stage_floor.<stage>.<knob> or "
                         "profiles.<name>.<knob>")
    args = ap.parse_args(argv)
    path = args.file
    if not args.sets:
        import json
        print(json.dumps(load_review_policy(path=path), indent=2,
                         ensure_ascii=False))
        return 0
    updates = {}
    for pair in args.sets:
        if "=" not in pair:
            sys.stderr.write("--set expects KEY=VALUE, got %r\n" % pair)
            return 2
        key, value = pair.split("=", 1)
        updates[key] = value.strip()
    try:
        out = save_review_policy(updates, path=path)
    except ReviewPolicyConfigError as e:
        sys.stderr.write("ReviewPolicyConfigError: %s\n" % e)
        return 1
    print("saved review-policy → %s" % out)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
