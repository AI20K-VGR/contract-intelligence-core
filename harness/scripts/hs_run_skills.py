#!/usr/bin/env python3
"""hs_run_skills.py — the `skills` domain's verb entry point for hs-run.

Answers one question: what is available, and what is the state of the name
you asked about. Two skill bodies (`use`, `find-skills`) previously carried
that question in prose; both already read the same two libraries, so this
wraps them rather than reimplementing either:

  - disabled_skills.default_sources(root) -> [Paths(...)]
  - disabled_skills.status(name, sources) -> "live" | "disabled" | "unknown"
  - disabled_skills.stash_path(name, sources) -> Path | None
  - disabled_skills.dep_chain(name, sources, deps_path) -> list[str]
  - disabled_skills.skill_list(sources) -> list[str]
  - catalog.load_catalog(sdir) -> {"dirs", "slug_to_dir", "owned"}

Signatures read from the source, not assumed: none of these take a `root=`
keyword. `default_sources(root)` is the seam that makes the root explicit —
it builds the four paths (skills dir, stash dir, record, dev off-list) under
a stated root, which is exactly what a verb needs to avoid inheriting a CWD.

ONE domain, not two. Measured before deciding: 0 of the 8 shipped domains
declare a required positional on `next`, and 7 of 8 answer a bare call. The
lone exception (`review-pr`, which exits 2 without `--poll-n`) argues the
other way once read — that flag is a loop counter the domain generates for
its OWN next invocation, not a target a person types. So `--skill` narrows
an answer the bare call already gives, which is a flag, not a second door.

`target_unknown` is deliberately NOT folded into `error`. A name nobody
recognises is a real answer about the catalog and is fixed by re-reading it;
a broken skills tree is fixed by repairing the install. One word for both
would make a typo and a corrupt tree indistinguishable at the only moment
the difference matters.

Root discipline: every library call passes the ENVELOPE's resolved root, never
the process CWD. Measured trap — `disabled_skills.status("cook")` answers
`unknown` from /tmp and `live` from inside the repo, because its `--root`
defaults to the CWD. A verb inheriting that default would report a healthy
tree as empty whenever the caller happened to be somewhere else.

No write path. This verb reads two libraries and returns; the demand signal
that `hs:use` emits on a real proxy run stays where it is, because 0 of the 8
shipped `next` verbs write to disk and because the emitter's own contract
records a skill "actually reached", which a state PROJECTION has not done.
"""
from __future__ import annotations

import sys
from pathlib import Path

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)

import catalog
import disabled_skills
import hs_run_next_command

import hs_run  # noqa: E402
from hs_run import EXIT_BROKEN, EXIT_NEEDS_MODEL  # noqa: E402


@_attrs.define(frozen=True, kw_only=True)
class CatalogSummary:
    """What the tree holds, as the bare call reports it.

    A record rather than a dict literal at the construction site: the key names
    are declared once, so a reader of `live_count` finds the same spelling every
    time and a rename is one edit. Follows `RecordedRun` in the `test` domain.
    """

    live_count: int = _attrs.field(default=0)
    disabled: list = _attrs.field(factory=list)

    def as_dict(self) -> dict:
        # NAMES, not the library's cards. Each card carries the skill's full
        # `description`, and 68 of them made this envelope 20,641 bytes — 93% of
        # it prose about skills the caller has not asked for, on a call whose own
        # next_action is "name one". The description that matters is the one the
        # NEXT call resolves, and that call already returns it.
        return {"live_count": int(self.live_count),
                "disabled_count": len(self.disabled),
                "disabled": [c["name"] if isinstance(c, dict) else str(c)
                             for c in self.disabled]}


@_attrs.define(frozen=True, kw_only=True)
class SkillTarget:
    """One named skill's state, plus what acting on it requires.

    `stash_path` and `disabled_chain` are empty for a live or unknown target
    rather than absent, so a caller never has to tell "no stash" apart from "the
    key is missing" — the same guarantee `StateRouting` makes for its own rows.
    """

    skill = _attrs.field()
    stash_path = _attrs.field(default="")
    disabled_chain: list = _attrs.field(factory=list)
    live_count: int = _attrs.field(default=0)

    def as_dict(self) -> dict:
        return {"skill": str(self.skill),
                "stash_path": str(self.stash_path or ""),
                "disabled_chain": list(self.disabled_chain),
                "live_count": int(self.live_count)}


@_attrs.frozen
class _Availability:
    """What the two libraries know about the tree, gathered once.

    A value object rather than four loose locals because every state below
    needs a different subset, and threading four returns through the branch
    ladder is how a later edit ends up reading a stale one.
    """

    live_count: int = _attrs.field()
    disabled: tuple = _attrs.field(converter=tuple)
    error: str = _attrs.field(default="")
    # The loaded catalog, carried rather than re-loaded. `to_dir_id` needs it to
    # fold `hs:cook` onto `cook`, and reading the tree a second time for that is
    # both a second chance to disagree with this one and a second directory walk.
    catalog: dict = _attrs.field(factory=dict)


def _sources(root: Path) -> list:
    """The skill-state sources under a STATED root.

    The one place the root crosses into the library. `default_sources` builds
    the skills dir, the stash dir, the record and the dev off-list beneath it;
    every call below goes through here so none of them can fall back to a CWD.
    """
    return disabled_skills.default_sources(str(root))


def _survey(root: Path, sources: list) -> _Availability:
    """Count what is loadable and what is stashed, or carry the failure.

    Fail-CLOSED on the catalog: a skills tree that cannot be listed is not
    "an empty catalog" — reporting zero skills as a normal answer would send
    a caller hunting for a skill that is sitting right there behind a
    permissions error.
    """
    try:
        loaded = catalog.load_catalog(str(sources[0].skills_dir))
    except Exception as exc:  # noqa: BLE001 — any load failure is the same answer
        return _Availability(live_count=0, disabled=(), error="%s" % exc)
    try:
        stashed = disabled_skills.skill_list(sources)
    except Exception as exc:  # noqa: BLE001
        return _Availability(live_count=0, disabled=(), error="%s" % exc)
    # LIVE = the catalog MINUS the off set, not the catalog. In a dev symlink
    # farm the skills dir holds every skill in the repo whether or not it is on,
    # so `len(dirs)` counts the disabled ones as available. Measured on this tree:
    # 122 dirs, 68 off, and all 68 are inside the 122 — the verb reported 122 live
    # when 54 were, and a caller adding the two fields got 190 for 122 dirs.
    #
    # Subtracted by NAME, the same key `--skill` resolves against, so the two
    # answers this verb gives about one skill cannot disagree.
    off = {c["name"] if isinstance(c, dict) else str(c) for c in stashed}
    dirs = loaded.get("dirs") or []
    names = {Path(d).name if not isinstance(d, dict) else d.get("name")
             for d in dirs}
    return _Availability(live_count=len(names - off),
                         disabled=tuple(stashed), catalog=loaded)


def cmd_next(argv: list, root: Path) -> dict:
    """Report skill availability — the catalog, or one name's state.

    Every path is exit 10: choosing which skill to run, or what to do with a
    disabled one, is a model turn. There is no exit-11 tier here on purpose —
    the one command that would qualify (turning a skill back on) does not take
    effect until the plugin catalog reloads at session start, so a driver
    looping on 11 would run it and find nothing changed in this session.

    `next_command` is null on every path, explicitly rather than absent.
    """
    return hs_run_next_command.finalize(_cmd_next_impl(argv, root))


def _cmd_next_impl(argv: list, root: Path) -> dict:
    # Raises VerbArgError on a mistyped flag; the dispatcher already maps that
    # to a valid EXIT_BROKEN envelope, so catching it here would only convert a
    # named error into a silent fall-through to the bare-catalog branch.
    parsed = hs_run.parse_verb_argv("hs-run skills next", argv,
                                    options=("skill",))
    wanted = (parsed.skill or "").strip()

    sources = _sources(root)
    survey = _survey(root, sources)
    if survey.error:
        return hs_run.StepResult(
            state="catalog_broken", exit_code=EXIT_BROKEN,
            next_action="STOP — the skills tree under %s could not be read "
                        "(%s); repair the install before routing to any skill"
                        % (root, survey.error),
            warnings=[survey.error],
        ).as_dict()

    if not wanted:
        return hs_run.StepResult(
            state="catalog_ready", exit_code=EXIT_NEEDS_MODEL,
            next_action="%d skills loaded, %d stashed — name one with "
                        "`hs-run skills next --skill <name>`, or read the "
                        "listing to pick"
                        % (survey.live_count, len(survey.disabled)),
            extra=CatalogSummary(live_count=survey.live_count,
                                 disabled=list(survey.disabled)).as_dict(),
        ).as_dict()

    # `hs:cook` and `cook` name one skill. Every routing doc and the plugin's own
    # invocation syntax write the prefixed form, so the model types what it read
    # and got `target_unknown` for a skill sitting right there — measured:
    # `--skill cook` -> target_live, `--skill hs:cook` -> target_unknown.
    #
    # Folded through `catalog.to_dir_id`, the library that already owns this
    # question, not by stripping the prefix here. It resolves four ways (slug map,
    # known dir, ':'->'-', tail-match) and deliberately refuses to fold a FOREIGN
    # namespace — `ck:docs` from another plugin must not become the harness's
    # `docs`. A local strip would get that wrong and answer for the wrong skill.
    wanted = catalog.to_dir_id(wanted, survey.catalog) or wanted

    state = disabled_skills.status(wanted, sources)
    if state == "live":
        return hs_run.StepResult(
            state="target_live", exit_code=EXIT_NEEDS_MODEL,
            next_action="`%s` is loaded — invoke it directly as /hs:%s; the "
                        "off-skill proxy would bounce a live target straight "
                        "back" % (wanted, wanted),
            extra=SkillTarget(skill=wanted,
                              live_count=survey.live_count).as_dict(),
        ).as_dict()

    if state == "disabled":
        stash = disabled_skills.stash_path(wanted, sources)
        chain = disabled_skills.dep_chain(
            wanted, sources, disabled_skills.default_deps_path(str(root)))
        return hs_run.StepResult(
            state="target_disabled", exit_code=EXIT_NEEDS_MODEL,
            next_action="`%s` is stashed — run it through /hs:use %s, which "
                        "loads its prose and its disabled dependencies in "
                        "order" % (wanted, wanted),
            artifacts=[str(stash)] if stash else [],
            extra=SkillTarget(skill=wanted, stash_path=stash or "",
                              disabled_chain=list(chain),
                              live_count=survey.live_count).as_dict(),
        ).as_dict()

    return hs_run.StepResult(
        state="target_unknown", exit_code=EXIT_NEEDS_MODEL,
        next_action="no skill named `%s` in the catalog under %s — re-read the "
                    "listing with a bare `hs-run skills next`, or check the "
                    "spelling" % (wanted, root),
        extra=SkillTarget(skill=wanted, live_count=survey.live_count).as_dict(),
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
        % (Path(__file__).name, 'skills'))
    raise SystemExit(EXIT_BROKEN)
