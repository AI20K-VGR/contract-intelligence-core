#!/usr/bin/env python3
"""disabled_skills.py — state library for install-disabled (omitted) skills.

After the 2.0.0 plugin collapse a fresh install can OMIT a skill at the dir level
(the only disable that works for plugin skills): the dir is stashed under
harness/plugins/hs/disabled-skills/ — a TRACKED sibling of skills/ that ships with
the bundle yet the loader never scans — and recorded in install-omitted-skills.json.
The omit record stays under harness/state/ (per-install hint); the stash's presence
is the ship-with-bundle signal. This module is the single reader that turns those
raw records + stash dirs into the
questions the off-skill machinery asks:

  * effective_disabled(sources) — which skills are off, unioned across sources.
  * status(skill, sources)      — live | disabled | unknown.
  * dep_chain(skill, sources, deps_path) — the DISABLED dep-closure of a skill, in
    load (discovery) order, so hs:use can pull a whole tail of off deps before it
    reads a disabled target.
  * describe / skill_list        — the human label (from the stashed SKILL.md), with
    a stash_missing flag for a recorded-but-never-copied (install-omitted) skill.
  * stash_path                   — the abs path of the stashed dir (the read-inline
    route the router points a caller at).

Multi-source is deliberate and load-bearing: the API takes an explicit
``sources: list[Paths]`` so a later phase can append a cache source WITHOUT changing
the resolver — every query simply unions/overlays the extra source. Each Paths bundle
is one location (its live skills dir, its stash dir, its omit record). Reads are
fail-soft: an absent dir or unparseable record contributes nothing rather than raising.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import namedtuple
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import skill_frontmatter  # noqa: E402

# One source location. Three plain paths so a caller (incl. a later cache source) can
# construct one without importing the whole harness layout.
# off_list_path is optional: a dev may load a curated symlink farm instead of
# skills/, listing the skills it drops in .harness-dev/dev-off-skills.yaml. Those
# skills stay in the live skills/ tree (the repo is full) but are OFF for the
# session, so they must read as disabled from that record too.
Paths = namedtuple("Paths", ["skills_dir", "stash_dir", "record_path", "off_list_path"])
Paths.__new__.__defaults__ = (None,)

_SKILLS_REL = "harness/plugins/hs/skills"
_STASH_REL = "harness/plugins/hs/disabled-skills"
_RECORD_REL = "harness/state/install-omitted-skills.json"
_OFFLIST_REL = ".harness-dev/dev-off-skills.yaml"
_DEPS_REL = "harness/data/skill-deps.yaml"



def default_sources(root) -> list:
    """The single stock source under a target repo root (the shape install writes).
    Also carries the dev off-list path — present only on a dev symlink-farm setup, a
    no-op (empty set) everywhere else."""
    root = Path(root)
    return [Paths(
        skills_dir=root / _SKILLS_REL,
        stash_dir=root / _STASH_REL,
        record_path=root / _RECORD_REL,
        off_list_path=root / _OFFLIST_REL,
    )]


def default_deps_path(root) -> Path:
    return Path(root) / _DEPS_REL


def _recorded(record_path) -> set:
    """The `omitted` names from one record file. Missing/corrupt → empty set: a broken
    record must never silently mark everything disabled (and never raise)."""
    try:
        data = json.loads(Path(record_path).read_text(encoding="utf-8"))
        return {s for s in (data.get("omitted") or []) if isinstance(s, str)}
    except Exception:  # noqa: BLE001 — absent/unreadable/corrupt record → nothing
        return set()


def _stashed(stash_dir) -> set:
    """Skill dirs currently sitting in one stash dir. Absent dir → empty set."""
    d = Path(stash_dir)
    if not d.is_dir():
        return set()
    try:
        return {c.name for c in d.iterdir() if c.is_dir()}
    except OSError:
        return set()


def _off_listed(off_list_path) -> set:
    """Names in a dev off-list's `disabled:` block. Absent/broken file → empty set
    (a missing off-list must never mark everything disabled, and never raise)."""
    if not off_list_path:
        return set()
    p = Path(off_list_path)
    if not p.is_file():
        return set()
    try:
        import yaml_io
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
        return {s for s in (data.get("disabled") or []) if isinstance(s, str)}
    except Exception:  # noqa: BLE001 — a broken off-list disables nothing, silently
        return set()


def disabled_in(source: Paths) -> set:
    """The disabled set contributed by ONE source: recorded-omitted ∪ present-in-stash
    ∪ dev-off-listed. (A stash dir with no record, or a record with no stash, both count
    the two are independent evidence of the same off state.)"""
    return (_recorded(source.record_path) | _stashed(source.stash_dir)
            | _off_listed(source.off_list_path))


def effective_disabled(sources) -> set:
    """Union of the disabled set across every source (the cache-seam contract)."""
    out: set = set()
    for s in sources:
        out |= disabled_in(s)
    return out


def _present_live(skill, sources) -> bool:
    for s in sources:
        if (Path(s.skills_dir) / skill / "SKILL.md").is_file():
            return True
    return False


def status(skill, sources) -> str:
    """live | disabled | unknown. Disabled wins over a stray live dir so a
    recorded-but-unstashed skill still reads disabled."""
    if skill in effective_disabled(sources):
        return "disabled"
    if _present_live(skill, sources):
        return "live"
    return "unknown"


def _stash_dir_for(skill, sources):
    """Where to read a disabled skill's files from: the first source whose stash holds
    it; else — a dev-farm off skill was never moved, so its files are still in the live
    skills/ dir — the live dir if present there; else the first stash path (where it
    would live for an install-omitted skill)."""
    first = None
    for s in sources:
        p = Path(s.stash_dir) / skill
        if first is None:
            first = p
        if p.is_dir():
            return p
    for s in sources:  # dev-farm: off-listed but in place (not stashed)
        live = Path(s.skills_dir) / skill
        if (live / "SKILL.md").is_file():
            return live
    return first


def stash_path(skill, sources):
    """Absolute path of the stashed skill dir (read-inline route), or None if there is
    no source at all. May point at a not-yet-existing path for an install-omitted skill
    (no stash was ever written) — the caller pairs it with the install recovery hint."""
    p = _stash_dir_for(skill, sources)
    return p.resolve() if p is not None else None


def _read_description(skill_md: Path) -> str:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return skill_frontmatter.description(text)


def describe(skill, sources) -> dict:
    """One skill's card: {name, description, stash_missing}. description is read from
    the stashed SKILL.md; stash_missing=True for a recorded-but-unstashed skill."""
    sp = _stash_dir_for(skill, sources)
    md = (sp / "SKILL.md") if sp is not None else None
    missing = not (md is not None and md.is_file())
    return {
        "name": skill,
        "description": "" if missing else _read_description(md),
        "stash_missing": missing,
    }


def skill_list(sources, key_filter=None) -> list:
    """Cards for every disabled skill, sorted by name. key_filter (case-insensitive)
    keeps only skills whose name or description contains it."""
    out = [describe(s, sources) for s in sorted(effective_disabled(sources))]
    if key_filter:
        kf = key_filter.lower()
        out = [c for c in out
               if kf in c["name"].lower() or kf in (c["description"] or "").lower()]
    return out


def _load_deps(deps_path) -> dict:
    import skill_deps
    return skill_deps.load_deps(deps_path)["skills"]


def dep_chain(skill, sources, deps_path) -> list:
    """The DISABLED dep-closure of `skill`, in discovery (load) order, excluding
    `skill` itself. Walks declared deps depth-first preserving first-seen order; keeps
    only members that are effectively disabled. Cycle-safe via a visited set."""
    try:
        graph = _load_deps(deps_path)
    except Exception:  # noqa: BLE001 — no graph → no known chain
        return []
    off = effective_disabled(sources)
    order: list = []
    seen = {skill}

    def walk(name):
        for dep in graph.get(name, {}).get("deps", []) or []:
            if dep in seen:
                continue
            seen.add(dep)
            if dep in off:
                order.append(dep)
            walk(dep)

    walk(skill)
    return order


# --------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Query the install-disabled (omitted) skill state.")
    ap.add_argument("--root", default=".", help="target repo root (default: cwd)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="list disabled skills")
    g.add_argument("--status", metavar="SKILL", help="live|disabled|unknown for a skill")
    g.add_argument("--path", metavar="SKILL", help="abs stash path of a skill")
    g.add_argument("--chain", metavar="SKILL", help="disabled dep-closure, load order")
    ap.add_argument("--filter", metavar="KW", help="with --list: substring filter")
    args = ap.parse_args(argv)

    sources = default_sources(args.root)
    if args.list:
        for card in skill_list(sources, args.filter):
            flag = "  [stash missing — install to fetch]" if card["stash_missing"] else ""
            print("%-24s %s%s" % (card["name"], card["description"], flag))
        return 0
    if args.status:
        print(status(args.status, sources))
        return 0
    if args.path:
        p = stash_path(args.path, sources)
        print(str(p) if p is not None else "")
        return 0
    if args.chain:
        for name in dep_chain(args.chain, sources, default_deps_path(args.root)):
            print(name)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
