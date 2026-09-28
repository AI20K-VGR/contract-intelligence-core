#!/usr/bin/env python3
"""gemini_skill_inject.py — mechanical, deterministic skill passthrough for gemini.

`resolve_skill(name)` reads a live SKILL.md and inlines VERBATIM the
`harness/rules/*.md` + `references/*.md` files that skill cites — no LLM, no scrub,
no trim (user decision: the harness methodology is AGPL-open, not a secret; a real
secret in task context is the scrub module's job). The point of a passthrough is
that Claude never re-reads this bulk; the relayer carries it to gemini untouched.

Containment (F-A, HARD): the read is regex+open, so an unclamped cite like
`references/../../../.ssh/id_rsa` would egress an arbitrary file to Google (the old
LLM-scrub never *followed* a traversal — a file reader does). Every resolved path
is realpath-clamped: the references arm must stay inside the skill dir, the rule
arm inside `harness/rules/`. Anything with `..` or landing out-of-zone is refused
(WARN + skip), never read. Resolution is depth-1 and deduped — bounded, no
recursion into the cited files' own citations.
"""
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_HARNESS = _HERE.parents[3]                     # scripts→hs→plugins→harness
for _p in (_HARNESS / "scripts", _HARNESS / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Soft threshold: verbatim depth-1 can balloon (e.g. critique pulls ~379 rule
# lines). Over this we WARN "prompt large" — never block; the token-frugal
# philosophy must not silently contradict itself.
SIZE_WARN_LINES = 800

# Mechanical path extractors. references/ allows '.' and '/' ON PURPOSE so a
# traversal cite is MATCHED here and then rejected by containment below — a
# stricter regex would silently ignore the attack instead of refusing it loudly.
_RULE_RE = re.compile(r"harness/rules/[\w.-]+\.md")
# NOT anchored to .md ON PURPOSE: a traversal cite (references/../../.ssh/id_rsa)
# has no .md, so an .md-only regex would silently ignore the F-A attack instead of
# matching it and refusing it loudly. Containment clamps every match.
_REF_RE = re.compile(r"references/[\w./-]+")


class SkillNotFound(Exception):
    """`--skill <name>` names a skill that has no SKILL.md."""


def _warn(msg):
    sys.stderr.write("gemini-skill-inject: WARNING — %s\n" % msg)


def _find_skill_dir(name, skills_dir):
    """Locate <name>'s directory (the one holding SKILL.md). Tries the dir name
    directly under skills_dir, then the catalog slug→dir map."""
    if skills_dir is not None:
        cand = Path(skills_dir) / name
        if (cand / "SKILL.md").is_file():
            return cand
    try:
        import catalog
        cat = catalog.load_catalog(str(skills_dir) if skills_dir else None)
        dir_name = cat["slug_to_dir"].get(name) or cat["slug_to_dir"].get(
            name.replace(":", "-"))
        if dir_name:
            for src in ([Path(skills_dir)] if skills_dir else catalog.skills_dirs()):
                cand = src / dir_name
                if (cand / "SKILL.md").is_file():
                    return cand
    except Exception:
        pass
    return None


def _contained(target: Path, zone: Path) -> bool:
    """True iff target's realpath is inside zone's realpath. Refuses traversal by
    construction — a `..` that climbs out fails the prefix check."""
    try:
        rt = os.path.realpath(str(target))
        rz = os.path.realpath(str(zone))
    except OSError:
        return False
    return rt == rz or rt.startswith(rz + os.sep)


def _inline(raw_cite, base_dir, zone, arm, seen, out_refs, parts):
    """Clamp one cited path and, if contained + present, append its content
    verbatim. `raw_cite` is the literal string as it appeared in SKILL.md."""
    if ".." in raw_cite.split("/"):
        _warn("refusing traversal cite %r (%s arm) — not read" % (raw_cite, arm))
        return
    target = (base_dir / raw_cite).resolve() if arm == "reference" else \
        (zone / Path(raw_cite).name)
    key = os.path.realpath(str(target))
    if key in seen:
        return
    if not _contained(target, zone):
        _warn("refusing out-of-zone cite %r (%s arm) — not read" % (raw_cite, arm))
        return
    seen.add(key)
    try:
        text = Path(target).read_text(encoding="utf-8")
    except OSError:
        _warn("cited %s %r not found — skipped (fail-open)" % (arm, raw_cite))
        return
    out_refs.append(str(target))
    parts.append("\n\n--- %s: %s ---\n%s" % (arm, raw_cite, text))


def resolve_skill(name, *, skills_dir=None, harness_root=None):
    """Return (composed_text, resolved_refs).

    composed_text = SKILL.md VERBATIM + each cited rule/reference inlined verbatim
    (deduped, depth-1, containment-clamped). resolved_refs = the realpaths inlined.
    Raises SkillNotFound if the skill has no SKILL.md.
    """
    hroot = Path(harness_root) if harness_root else _HARNESS.parent
    rules_zone = hroot / "harness" / "rules"

    sdir = _find_skill_dir(name, skills_dir)
    if sdir is None:
        raise SkillNotFound("no SKILL.md for skill %r" % name)

    skill_body = (sdir / "SKILL.md").read_text(encoding="utf-8")
    parts = [skill_body]
    seen, refs = set(), []

    # depth-1: scan SKILL.md only, not the inlined files' own citations
    for cite in dict.fromkeys(_RULE_RE.findall(skill_body)):
        _inline(cite, sdir, rules_zone, "rule", seen, refs, parts)
    for cite in dict.fromkeys(_REF_RE.findall(skill_body)):
        _inline(cite, sdir, sdir, "reference", seen, refs, parts)

    composed = "".join(parts)
    if composed.count("\n") + 1 > SIZE_WARN_LINES:
        _warn("composed skill prompt is large (%d lines) — token cost is real"
              % (composed.count("\n") + 1))
    return composed, refs


if __name__ == "__main__":  # pragma: no cover - manual inspection aid
    _name = sys.argv[1] if len(sys.argv) > 1 else "research"
    _text, _refs = resolve_skill(_name)
    sys.stdout.write(_text)
    sys.stderr.write("\n[resolved refs: %s]\n" % ", ".join(_refs))
