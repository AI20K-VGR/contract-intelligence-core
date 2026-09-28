#!/usr/bin/env python3
"""hs_run_setup.py — the `setup` domain's verb entry point for hs-run.

`hs:setup` walks eleven configuration groups, and most of that walk is a
conversation: which archetype, which persona, which depth. None of those leave
a mark that separates "asked and answered" from "never asked" — two trees with
`voice_level: 9`, one hand-tuned and one shipped that way, are indistinguishable
on disk. Inventing a state for them would mean inventing the evidence too.

Three steps are different, and those are the ones this verb takes:

  - preflight_deps.missing_required() -> a package is installed or it is not
  - voice_prefs.legacy_output_style() -> the live voice file carries a pre-split
    key, or it does not
  - trust_store.is_trusted(root)     -> this repo is in the trust store, or not

All three go through the libraries that already own them. `voice_path()` is the
resolver `voice_prefs` itself uses ($HARNESS_TERMINAL_VOICE > dev override >
shipped), so the check reads the SAME file a later `--set` would write; a
hand-rolled grep would drift from it the first time the precedence changes.

`deps_missing` rides rung 2, not 11, and the precedent is exact rather than
analogous: `hs_run_test.py:122-132` emits this state from the IDENTICAL
predicate at EXIT_BROKEN, with the reason in the code — "a hard blocker, not a
projection". The premise that would have argued for 11 ("we want to print the
pip command, and only 11 may carry one") is false: `_next_command_violation`
constrains rungs 11 and 10 and leaves rung 2 untouched, so a rung-2 result can
name the install command in `next_action` without promising a driver may run it.

Ordering is load-bearing. Deps come first because every later check imports
something; the schema migration comes before the walk because the walk writes
through the same file and would re-save a new value on top of a schema the
reader no longer understands; trust comes before any standards rule can fire a
shell detector.
"""
from __future__ import annotations

import sys
from pathlib import Path

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)

import hs_run_next_command
import preflight_deps
import trust_store
import voice_prefs

import hs_run  # noqa: E402
from hs_run import EXIT_BROKEN, EXIT_NEEDS_MODEL  # noqa: E402

_LEGACY_KEYS = ("output_style", "detail_level", "coding_level")


@_attrs.define(frozen=True, kw_only=True)
class MissingDeps:
    """The packages preflight could not import, as this verb reports them.

    A record rather than a bare `{"missing": [...]}`: the key name is then
    declared in one place instead of at every construction site, and a caller
    reading `artifacts[0]` finds a shape it can rely on. Mirrors `RecordedRun`
    in the sibling `test` domain, which had the same reason.
    """

    missing: list = _attrs.field(factory=list)

    def as_dict(self) -> dict:
        return {"missing": list(self.missing)}


@_attrs.define(frozen=True, kw_only=True)
class LegacyKeys:
    """Pre-split keys found in the live voice file, plus the file they sit in.

    Both halves travel together because neither is actionable alone — a key name
    without its file sends the reader looking through three candidate paths, and
    a path without the key names nothing to remove.
    """

    voice_file = _attrs.field()
    keys: list = _attrs.field(factory=list)

    def as_dict(self) -> dict:
        return {"voice_file": str(self.voice_file), "legacy_keys": list(self.keys)}


@_attrs.define(frozen=True, kw_only=True)
class TrustState:
    """Whether this repo may run a standards rule's shell detector."""

    repo = _attrs.field()
    trusted: bool = _attrs.field(default=False)

    def as_dict(self) -> dict:
        return {"repo": str(self.repo), "trusted": bool(self.trusted)}


@_attrs.frozen
class _Posture:
    """What the three libraries report about this tree, gathered once.

    A value object rather than three loose locals: each state below needs a
    different subset, and the failure mode of threading them separately is a
    later edit reading one that was never refreshed.
    """

    missing_deps: tuple = _attrs.field(converter=tuple)
    legacy_keys: tuple = _attrs.field(converter=tuple)
    trusted: bool = _attrs.field()
    voice_file: str = _attrs.field(default="")
    error: str = _attrs.field(default="")


def _legacy_keys_present() -> tuple:
    """Pre-split keys still in the LIVE voice file, in declaration order.

    Through `voice_prefs.voice_path()` so the file inspected is the one a later
    `--set` writes. `legacy_output_style()` answers for one key only, so the
    remaining two are read from the same document rather than through a second
    resolver.
    """
    import yaml_io  # lazy, matching voice_prefs' own import style

    try:
        # `yaml_load` takes TEXT, not a path — the same call voice_prefs makes
        # (`voice_prefs.py:49-50`), so both read the file through one parser.
        raw = yaml_io.yaml_load(
            voice_prefs.voice_path().read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — a corrupt or absent file carries no key
        return ()
    if not isinstance(raw, dict):
        return ()
    return tuple(k for k in _LEGACY_KEYS if k in raw)


def _survey(root: Path) -> _Posture:
    """Read the three predicates, or carry the failure that stopped one.

    Fail-CLOSED on an unreadable policy: reporting "configured" for a tree whose
    config could not be read would send the caller into the walk with defaults
    it never chose.
    """
    try:
        missing = preflight_deps.missing_required()
    except Exception as exc:  # noqa: BLE001
        return _Posture(missing_deps=(), legacy_keys=(), trusted=False,
                        error="preflight: %s" % exc)
    try:
        legacy = _legacy_keys_present()
        voice_file = str(voice_prefs.voice_path())
    except Exception as exc:  # noqa: BLE001
        return _Posture(missing_deps=tuple(missing), legacy_keys=(),
                        trusted=False, error="voice config: %s" % exc)
    try:
        trusted = bool(trust_store.is_trusted(str(root)))
    except Exception as exc:  # noqa: BLE001
        return _Posture(missing_deps=tuple(missing), legacy_keys=tuple(legacy),
                        trusted=False, voice_file=voice_file,
                        error="trust store: %s" % exc)
    return _Posture(missing_deps=tuple(missing), legacy_keys=tuple(legacy),
                    trusted=trusted, voice_file=voice_file)


def cmd_next(argv: list, root: Path) -> dict:
    """Report the first onboarding condition that is not yet satisfied.

    `next_command` is null on every path, explicitly rather than absent. There is
    no rung-11 tier here: the one command that would qualify installs packages,
    and that is the tier the sibling `test` domain already placed at rung 2 for
    the same predicate. Guard and stage changes are env-bound and need a new
    session, so a driver looping on 11 would run them and see nothing change.
    """
    return hs_run_next_command.finalize(_cmd_next_impl(argv, root))


def _cmd_next_impl(argv: list, root: Path) -> dict:
    hs_run.parse_verb_argv("hs-run setup next", argv)
    posture = _survey(root)

    if posture.error:
        return hs_run.StepResult(
            state="policy_unreadable", exit_code=EXIT_BROKEN,
            next_action="STOP — a configuration source under %s could not be "
                        "read (%s); repair it before configuring anything else"
                        % (root, posture.error),
            warnings=[posture.error],
        ).as_dict()

    if posture.missing_deps:
        return hs_run.StepResult(
            state="deps_missing", exit_code=EXIT_BROKEN,
            next_action=preflight_deps.install_command(
                list(posture.missing_deps)),
            artifacts=[MissingDeps(missing=list(posture.missing_deps)).as_dict()],
            warnings=["%d required package(s) missing — later hooks and tests "
                      "fail with opaque ImportErrors until they are installed"
                      % len(posture.missing_deps)],
        ).as_dict()

    if posture.legacy_keys:
        return hs_run.StepResult(
            state="schema_legacy", exit_code=EXIT_NEEDS_MODEL,
            next_action="the live voice file (%s) still carries the pre-split "
                        "key(s) %s — clear them with a `voice_prefs.py --set` "
                        "re-save BEFORE the configuration walk, which writes "
                        "through the same file"
                        % (posture.voice_file, ", ".join(posture.legacy_keys)),
            artifacts=[posture.voice_file],
            extra=LegacyKeys(voice_file=posture.voice_file,
                             keys=list(posture.legacy_keys)).as_dict(),
        ).as_dict()

    if not posture.trusted:
        return hs_run.StepResult(
            state="trust_needed", exit_code=EXIT_NEEDS_MODEL,
            next_action="%s is not in the trust store, so a standards rule's "
                        "shell detector stays grep-only here — ask the user "
                        "before granting it, never grant it silently" % root,
            extra=TrustState(repo=root, trusted=False).as_dict(),
        ).as_dict()

    return hs_run.StepResult(
        state="configured", exit_code=EXIT_NEEDS_MODEL,
        next_action="deps present, no legacy keys, repo trusted — every "
                    "remaining choice (archetype, persona, depth, per-group "
                    "values) is the user's, so ask rather than assume a default",
        extra=TrustState(repo=root, trusted=True).as_dict(),
    ).as_dict()


if __name__ == "__main__":  # pragma: no cover - refusal path, asserted by subprocess
    # Not a command. On this ladder `0` is a CLAIM — "nothing left to do" — so a
    # module that runs here, does nothing and exits 0 tells an automated caller
    # the work is finished. Refuse loudly on the broken rung instead.
    import sys as _sys
    _sys.stderr.write(
        "%s is a hs-run domain module, not a command.\n"
        "Verbs are dispatched through the CLI, which resolves the project root, "
        "loads the registry and owns the exit ladder — none of which happens when "
        "this file is run on its own.\n"
        "Run it through the dispatcher instead:  hs-run %s <verb>\n"
        % (Path(__file__).name, 'setup'))
    raise SystemExit(EXIT_BROKEN)
