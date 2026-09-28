#!/usr/bin/env python3
"""catalog.py — skill catalog loader + slug↔dir normalization (PORT PS, cut
to the harness shape).

Harness skills ship as the `hs` plugin: harness/plugins/hs/skills/<dir>/SKILL.md
where the dir is the bare command suffix (`plan`) and the plugin namespace makes
the invoke name `hs:plan`. Frontmatter `name:` carries the `hs:` prefix
(`name: hs:plan`) because a plugin skill's INVOCATION follows its frontmatter
name (a bare `name: plan` would invoke bare `/plan`, not `/hs:plan`); a rare
legacy bare name is still resolved for back-compat.

`owned` is LOCATION-based: every dir holding a SKILL.md under a scanned
skills/ dir is owned, full stop — no exception by name. A skill's frontmatter
name does NOT decide ownership (that was the old, now-retired, name-prefix
model); it decides the invoke/SLUG identity (`slug_to_dir`) and — via
`_is_owned_name`/`to_dir_id` — folds a bare-vs-`hs:` name for telemetry
back-compat (`hs:plan` ↔ `plan`).

Fail-soft: a missing/unreadable skills dir yields empty structures.
"""

import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import harness_paths  # noqa: E402
import skill_frontmatter  # noqa: E402

_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
# Support dirs under skills/ that are not invocable skills.
_NON_SKILL_DIRS = {"_shared", "common"}

# Skills authored by THIS harness carry the `hs:` prefix (post-collapse, every
# skill lives in the one `hs` plugin). The legacy themed `hs-<x>:` prefixes are
# still recognized for back-compat. A skill vendored in place that kept a foreign
# name (e.g. ck:tool) is NOT owned.
_OWNED_NAME_PREFIX = "hs:"


def _is_owned_name(name) -> bool:
    """True when a RECORDED identity string looks like a legacy hs:-namespaced
    invocation (namespace before ':' is `hs`, or a legacy themed `hs-<x>`).
    NOT used for dir ownership anymore (that is location-based, see module
    docstring) — this only feeds `to_dir_id`'s back-compat tail-match so an
    old telemetry record like `hs:plan` still folds onto the `plan` dir."""
    if not name:
        return False
    ns = name.split(":", 1)[0]
    return ns == "hs" or ns.startswith("hs-")

# Compliance-tier values an owned skill may declare. The tier ties a skill to
# the governance model, so an unknown/absent tier means the field enforces
# nothing — tier_problems() flags it.
VALID_TIERS = {"workflow", "gate", "telemetry", "knowledge"}
_TIER_RE = re.compile(r"^\s*compliance-tier:\s*(.+?)\s*$", re.MULTILINE)


def skills_dir() -> Path:
    """The core `hs` plugin skill dir (primary). HARNESS_SKILLS_DIR overrides
    (tests). For the full family use skills_dirs()."""
    env = os.environ.get("HARNESS_SKILLS_DIR")
    if env:
        return Path(env)
    return harness_paths.root() / "harness" / "plugins" / "hs" / "skills"


def skills_dirs() -> list:
    """Every harness plugin's skills dir: harness/plugins/*/skills. The catalog
    spans the whole family (hs + hs-viz + future siblings), not one plugin —
    after the viz split a hs-only scan would make sibling skills invisible to
    find-skills' phantom-guard and the usage/chain lenses. HARNESS_SKILLS_DIR
    overrides to a single dir (test isolation)."""
    env = os.environ.get("HARNESS_SKILLS_DIR")
    if env:
        return [Path(env)]
    plugins = harness_paths.root() / "harness" / "plugins"
    try:
        return sorted((p / "skills") for p in plugins.iterdir()
                      if p.is_dir() and (p / "skills").is_dir())
    except OSError:
        return []


def _read_name(skill_md: Path):
    try:
        head = skill_md.read_text(encoding="utf-8")[:2000]
    except OSError:
        return None
    m = _NAME_RE.search(head)
    return m.group(1).strip() if m else None


def _scan_skill_dir(sdir: Path, dirs: set, slug_to_dir: dict, owned: set) -> None:
    """Merge one skills dir's SKILL.md entries into the accumulating catalog."""
    try:
        entries = sorted(p for p in sdir.iterdir() if p.is_dir())
    except OSError:
        return
    for d in entries:
        if d.name in _NON_SKILL_DIRS:
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        dirs.add(d.name)
        # Location-based: every dir with a SKILL.md scanned from a harness
        # plugin's skills/ dir is owned, unconditionally — name no longer gates it.
        owned.add(d.name)
        name = _read_name(skill_md)
        if name:
            slug_to_dir[name] = d.name
            slug_to_dir.setdefault(name.replace(":", "-"), d.name)
        slug_to_dir.setdefault(d.name, d.name)


def load_catalog(sdir=None) -> dict:
    """{'dirs': set, 'slug_to_dir': dict, 'owned': set}.

    dirs = dir name of every dir holding a SKILL.md; slug_to_dir = each
    `name:` slug (and its ':'→'-' variant, and the dir itself) → dir; owned =
    dirs in the harness plugin family (hs / hs-viz / ...). With no `sdir` the
    scan spans EVERY plugin (harness/plugins/*/skills); an explicit `sdir`
    scans just that one dir (test isolation / single-plugin queries)."""
    sources = [Path(sdir)] if sdir is not None else skills_dirs()
    dirs, slug_to_dir, owned = set(), {}, set()
    for src in sources:
        _scan_skill_dir(src, dirs, slug_to_dir, owned)
    return {"dirs": dirs, "slug_to_dir": slug_to_dir, "owned": owned}


def to_dir_id(skill: str, catalog: dict) -> str:
    """Normalize a recorded invocation identity to its canonical dir slug.

    Resolution: exact slug→dir map → known dir → ':'-stripped variants → flat
    fallback (':' → '-'). An unknown skill is still returned (counted), never
    dropped — surfaced honestly under its flat slug."""
    if not skill:
        return ""
    s2d = catalog.get("slug_to_dir", {})
    dirs = catalog.get("dirs", set())
    if skill in s2d:
        return s2d[skill]
    if skill in dirs:
        return skill
    hyphen = skill.replace(":", "-")
    if hyphen in dirs:
        return hyphen
    # Tail-match ONLY within the harness's own namespace: hs:plan -> plan. A foreign
    # namespaced skill (e.g. ck:docs from another plugin) must NOT fold into a bare hs
    # dir that happens to share the tail, or a usage/chain lens over-counts the hs
    # skill with the other plugin's invocations.
    tail = skill.split(":")[-1]
    if _is_owned_name(skill) and tail in dirs:
        return tail
    return hyphen


def _frontmatter(skill_md: Path) -> str:
    """The YAML frontmatter block text, or "" when there is no valid closing fence.
    Body prose after the fence is excluded, so a tier value in prose can't false-match
    (delegates fence detection to skill_frontmatter — both '---' and '...' close)."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return ""
    block, _ = skill_frontmatter.split(text)
    return block or ""


def _tier_problems_one(sdir: Path) -> list:
    problems = []
    try:
        entries = sorted(p for p in sdir.iterdir() if p.is_dir())
    except OSError:
        return problems
    for d in entries:
        if d.name in _NON_SKILL_DIRS:
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        # Location-based: every dir scanned here is owned (see module docstring),
        # so tier enforcement no longer filters by frontmatter name.
        m = _TIER_RE.search(_frontmatter(skill_md))
        if not m:
            problems.append("%s: missing compliance-tier" % d.name)
        elif m.group(1) not in VALID_TIERS:
            problems.append("%s: invalid compliance-tier %r" % (d.name, m.group(1)))
    return problems


def tier_problems(sdir=None) -> list:
    """'dir: reason' for every scanned skill (location-based owned — see module
    docstring) whose frontmatter compliance-tier is missing or outside
    VALID_TIERS. No `sdir` scans the whole plugin family; an explicit `sdir`
    scans just that one dir."""
    sources = [Path(sdir)] if sdir is not None else skills_dirs()
    problems = []
    for src in sources:
        problems += _tier_problems_one(src)
    return problems


# --- confusable-pair detection (cross-skill, advisory) ------------------------
# Two skills whose descriptions read near-identically are hard for the model to
# route between. This is inherently cross-skill (needs every description at
# once), so it lives in the catalog loader, not the per-skill lint. Advisory
# only — callers surface it as a warning; it never gates.
#
# This USED to be a second, independent hand-rolled Jaccard implementation (its
# own token set from findings_store.canon(), threshold 0.85 "mirroring"
# findings_store's — a comment admitting a conscious copy, not an accident).
# score_skill_description.py had a THIRD independent copy (own tokenizer,
# threshold 0.80). Measured on the real catalog (124 SKILL.md descriptions,
# 7,626 pairs), the hand-rolled token-Jaccard scorer topped out at 0.578 — below
# EITHER of its own two thresholds — so neither copy could ever fire; a real
# near-duplicate pair (hs:plan / hs:plan-ng, 0.9273 by the measure below) walked
# through undetected. That pair is HISTORY — `hs:plan-ng` was a prototype and has
# since been retired — but it is what the merge was measured against, so removing
# it would leave the 0.578-vs-0.9273 comparison with nothing to compare. The
# detector's live positive control is now a synthetic pair (test_catalog.py).
# Both copies asked the exact same question ("do these two
# descriptions read alike enough to misroute a caller"), so they are merged onto
# ONE measurement (`pairwise_confusable`, rapidfuzz.fuzz.token_set_ratio) and ONE
# threshold below. findings_store.py's own Jaccard is NOT part of this merge —
# it answers a different question (is this new finding-text the same recurring
# belief as an existing one, over arbitrary critique prose, not skill
# descriptions) and keeps its own 0.85 for that domain.

CONFUSABLE_THRESHOLD = 0.80  # calibrated on the real catalog — see module docstring above
_EXEMPTIONS_FILE = "skill-confusable-exemptions.yaml"


def _skill_descriptions(sdir: Path) -> list:
    """[(invoke-name, description)] for every skill under one dir, blank
    descriptions dropped (nothing to compare)."""
    out = []
    try:
        entries = sorted(p for p in sdir.iterdir() if p.is_dir())
    except OSError:
        return out
    for d in entries:
        if d.name in _NON_SKILL_DIRS:
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        name = skill_frontmatter.frontmatter(text).get("name") or d.name
        desc = skill_frontmatter.description(text).strip()
        if desc:
            out.append((str(name), desc))
    return out


def pairwise_confusable(entries: list, threshold: float = CONFUSABLE_THRESHOLD) -> list:
    """The ONE measurement, pure and disk-free: rapidfuzz.fuzz.token_set_ratio
    (0-100 scale) over the raw description text, normalized to 0-1. `entries` is
    [(name, description), ...] with blanks already dropped by the caller.
    Returns [(name_a, name_b, score), ...] with a < b, sorted by descending
    score then name. Exists so catalog.confusable_pairs() and
    score_skill_description.check_confusable_pairs() call the SAME function
    instead of drifting onto separate scales again."""
    from rapidfuzz import fuzz  # lazy: keep catalog's hot-path import cheap

    hits = []
    for i in range(len(entries)):
        na, da = entries[i]
        for j in range(i + 1, len(entries)):
            nb, db = entries[j]
            if na == nb:
                continue
            score = fuzz.token_set_ratio(da, db) / 100.0
            if score >= threshold:
                a, b = sorted((na, nb))
                hits.append((a, b, round(score, 4)))
    hits.sort(key=lambda h: (-h[2], h[0], h[1]))
    return hits


def load_confusable_exemptions(path=None) -> set:
    """{frozenset({a, b})} pairs a human has reviewed and accepted as an
    intentional near-duplicate (harness/data/skill-confusable-exemptions.yaml).
    Fail-soft: a missing file, a parse error, or an entry missing a non-empty
    `reason` is never an exemption — the safe failure direction is to keep
    FLAGGING, not to silently stop. `path` overrides the file for tests."""
    import yaml_io

    p = Path(path) if path is not None else (harness_paths.root() / "harness" / "data" / _EXEMPTIONS_FILE)
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml_io.YAMLError):
        return set()
    out = set()
    for entry in (data.get("exemptions") or []):
        if not isinstance(entry, dict):
            continue
        a, b, reason = entry.get("a"), entry.get("b"), entry.get("reason")
        if a and b and reason and str(reason).strip():
            out.add(frozenset((a, b)))
    return out


def confusable_pairs(sdir=None, threshold=CONFUSABLE_THRESHOLD, *, exemptions_path=None) -> list:
    """Skill pairs whose descriptions are confusable — an advisory signal that
    two skills read alike and may misroute. No `sdir` scans the whole plugin
    family; an explicit `sdir` scans just that one dir. A pair a human has
    reviewed and recorded as an intentional sibling
    (harness/data/skill-confusable-exemptions.yaml) is filtered out. Each hit is
    {"a", "b", "score"} with a < b; the list is sorted by descending score then
    name. Fail-soft: a missing dir yields []."""
    sources = [Path(sdir)] if sdir is not None else skills_dirs()
    entries = []
    for src in sources:
        entries += _skill_descriptions(src)
    hits = pairwise_confusable(entries, threshold=threshold)
    exempt = load_confusable_exemptions(exemptions_path)
    return [{"a": a, "b": b, "score": s} for a, b, s in hits
            if frozenset((a, b)) not in exempt]
