#!/usr/bin/env python3
"""Where each runtime reads, asked of the table rather than remembered.

The first writer here was measured against ONE runtime and named its directories in
module constants. That is correct until the second runtime arrives, and then every path
is right for the runtime it was written against and wrong for the one it was asked
about — silently, because a file written to the wrong place is still a file that got
written and an install that reports success.

Every answer below comes from `harness/data/runtime-targets.yaml`, and an undeclared
runtime is refused rather than defaulted: there is no sensible fallback for "where does
a runtime I have never measured read its hooks", and guessing produces exactly the
silent failure above.

Nothing here writes. It resolves, and refuses.
"""
from __future__ import annotations

import os
from pathlib import Path

_TABLE_REL = "harness/data/runtime-targets.yaml"
_cache: dict = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_targets(path=None) -> dict:
    """The declared table. Cached per path — this is read many times per install and
    the file does not change under a running install."""
    p = Path(path) if path else _repo_root() / _TABLE_REL
    key = str(p)
    if key not in _cache:
        # One reader for the whole tree: two YAML readers give one file two meanings,
        # and this file decides where an install lands.
        import yaml_io
        _cache[key] = yaml_io.yaml_load(p.read_text(encoding="utf-8"))["targets"]
    return _cache[key]


def _target(runtime: str, targets=None) -> dict:
    t = targets if targets is not None else load_targets()
    if runtime not in t:
        raise ValueError(
            "unknown runtime %r — declared runtimes are: %s. A runtime becomes "
            "installable by being measured into the table, not by being named here; "
            "there is deliberately no default." % (runtime, ", ".join(sorted(t))))
    return t[runtime]


def placement(runtime: str, targets=None) -> dict:
    return dict(_target(runtime, targets).get("placement") or {})


def hook_file(runtime: str, targets=None):
    """The relative path the runtime reads its hook config from, or None.

    None is a real answer for four measured runtimes and must stay distinguishable
    from "not declared" — which is why the table requires the key."""
    return placement(runtime, targets).get("hook_file")


def carries_gates(runtime: str, targets=None) -> bool:
    """Whether a compliance gate can exist here at all.

    A runtime with no hook surface can carry skills and instructions; it cannot carry
    an enforcement. Reporting otherwise describes a cage that is only a drawing of one.
    """
    return hook_file(runtime, targets) is not None


def is_global(runtime: str, targets=None) -> bool:
    """Writing into the user's home changes every project they own from inside one of
    them, so this is surfaced before anything is written rather than discovered after.
    """
    return placement(runtime, targets).get("scope") == "global"


def instructions_file(runtime: str, targets=None):
    return placement(runtime, targets).get("instructions_file")


def resolve_dir(runtime: str, kind: str, target_root, targets=None):
    """An absolute path for one export kind, or None if the runtime has no home for it.

    A `~`-rooted entry is a GLOBAL destination and is expanded against the user's home,
    not against the project — the two measured global runtimes would otherwise write a
    literal `~` directory inside the repo.
    """
    rel = placement(runtime, targets).get("%s_dir" % kind)
    if rel is None:
        return None
    if str(rel).startswith("~"):
        return Path(os.path.expanduser(str(rel)))
    return Path(target_root) / str(rel)


def event_name(runtime: str, event: str, targets=None) -> str:
    """The runtime's own spelling of a Claude-shaped event name.

    Two things can differ: the CASE, which most runtimes vary, and the NAME, which one
    of them does. Both come from the declaration; neither is guessed.

    Refuses an event the runtime does not declare. That refusal is the point: one
    measured runtime registers six of the eight and drops the subagent boundary, and a
    registration written there anyway never fires while reading as coverage.
    """
    import target_projection as tp
    t = _target(runtime, targets)
    declared = list(t.get("events") or [])
    # One resolver for the whole tree. The projector asks the same question to decide
    # what to drop; two spellings of the answer is how a rename reaches one and not
    # the other.
    want = tp.runtime_event_name(t, event) or tp._fallback_spelling(t, event)
    if not declared:
        raise KeyError(
            "%s declares no events — it has no hook surface, so no event name is "
            "valid there" % runtime)
    if want not in declared:
        raise KeyError(
            "%s does not register %r (as %r). Its events are: %s. Emitting it anyway "
            "produces a registration that never fires."
            % (runtime, event, want, ", ".join(declared)))
    return want


def skill_name(runtime: str, name: str, targets=None) -> str:
    """The skill's frontmatter name as this runtime can load it.

    Two measured runtimes cannot take a `:` in a skill name — the loader wants the
    frontmatter name to match a directory, and a directory cannot hold one. Emitting
    the colon form there produces a skill the runtime skips without saying so.
    """
    rule = ((_target(runtime, targets).get("skills") or {}).get("name_rewrite"))
    if rule == "colon_to_dash":
        return name.replace(":", "-")
    if rule:
        raise ValueError("%s declares an unknown skill name rewrite %r"
                         % (runtime, rule))
    return name
