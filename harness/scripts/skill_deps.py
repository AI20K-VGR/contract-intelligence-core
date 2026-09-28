"""Loader and resolver for the skill dependency graph.

The installer's skill picker uses this graph: when a user ticks a skill, its
declared dependencies are auto-ticked transitively, and a fixed core-immutable
spine can never be unticked. The graph lives in `harness/data/skill-deps.yaml`.

Shape of the data file::

    core_immutable: [plan, cook, test, ...]   # the 13 spine skills
    skills:
      cook: { deps: [plan, test] }
      scout: { deps: [] }
      ...

Every skill listed under `skills:` is one of the project's skills, and every
name appearing in any `deps:` list must itself be a declared skill key. The
loader enforces both invariants and raises ValueError naming the offender.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Set

import yaml_io

# Default location of the graph relative to the repo root (this file lives in
# harness/scripts/, so the data dir is one level up under harness/data/).
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "skill-deps.yaml"


def load_deps(path: Path | str | None = None) -> Dict:
    """Parse the dependency graph and validate it.

    Returns the parsed mapping with a top-level ``skills`` dict (each value a
    dict carrying a ``deps`` list) and a ``core_immutable`` list.

    Raises ValueError if:
      - the file is malformed (missing ``skills`` mapping), or
      - any dep references a name that is not a declared skill key (the
        offending ``skill -> dep`` pair is named in the message).
    """
    path = Path(path) if path is not None else DEFAULT_PATH
    data = yaml_io.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict) or not isinstance(data.get("skills"), dict):
        raise ValueError(f"{path}: expected a top-level 'skills' mapping")

    skills = data["skills"]
    known: Set[str] = set(skills)

    # Normalise: ensure every entry exposes a deps list (default empty) and
    # validate every dep points at a known skill key.
    for skill, body in skills.items():
        if body is None:
            body = {}
            skills[skill] = body
        if not isinstance(body, dict):
            raise ValueError(f"{path}: skill {skill!r} entry must be a mapping")
        deps = body.get("deps", [])
        if deps is None:
            deps = []
        if not isinstance(deps, list):
            raise ValueError(f"{path}: skill {skill!r} deps must be a list")
        for dep in deps:
            if dep not in known:
                raise ValueError(
                    f"{path}: skill {skill!r} declares unknown dep {dep!r} "
                    f"(not one of the declared skills)"
                )
        body["deps"] = deps

    core = data.get("core_immutable", [])
    if not isinstance(core, list):
        raise ValueError(f"{path}: core_immutable must be a list")
    for name in core:
        if name not in known:
            raise ValueError(
                f"{path}: core_immutable lists unknown skill {name!r}"
            )
    data["core_immutable"] = core

    return data


def core_immutable(path: Path | str | None = None) -> List[str]:
    """Return the core-immutable spine skills (the ones that cannot be unticked)."""
    return list(load_deps(path)["core_immutable"])


def resolve(selected: Iterable[str], path: Path | str | None = None) -> Set[str]:
    """Return the transitive auto-tick closure of ``selected``.

    Starting from the selected skills, follow declared deps breadth-first,
    adding each newly reached skill. A visited set guarantees termination even
    when the graph contains cycles (e.g. plan <-> cook). The result always
    contains the original selections.
    """
    skills = load_deps(path)["skills"]

    resolved: Set[str] = set()
    frontier = list(selected)
    while frontier:
        skill = frontier.pop()
        if skill in resolved:
            continue
        resolved.add(skill)
        # Unknown selections (not in the graph) simply contribute themselves;
        # the installer never feeds names outside the graph, but stay robust.
        for dep in skills.get(skill, {}).get("deps", []):
            if dep not in resolved:
                frontier.append(dep)
    return resolved
