#!/usr/bin/env python3
"""Decomposition migrate engine — relocate non-spine skills + rewrite every reference.

The harness now ships COLLAPSED to one `hs` plugin, produced by this
engine's `--reverse`. The FORWARD direction documented below splits a single `hs`
plugin into a spine (13 always-on
SDLC skills, kept in `hs`) plus six themed sibling plugins. This tool moves each
non-spine skill dir into its themed plugin and rewrites EVERY reference to it across
the repo, in all four forms:

  1. slash invocation   /hs:<s>            -> /hs-<g>:<s>
  2. bare invocation     hs:<s>            ->  hs-<g>:<s>      (the dominant form)
  3. frontmatter name    name: hs:<s>      ->  name: hs-<g>:<s>   (a bare-form case)
  4. path                hs/skills/<s>     ->  hs-<g>/skills/<s>

Spine skills (group "hs") and already-prefixed refs (hs-viz:, hs-devops:, …) are never
touched. The generated manifest and the entire plans/ tree are out of scope — manifest
is rebuilt by build_manifest, and plans/ is frozen history plus the drift-sensitive
active plan (rewriting it would change a plan_hash and trip the drift gate).

Idempotent: a second run is a no-op (already-moved dirs are skipped; already-prefixed
refs no longer match). `--check` independently scans for any surviving old-form ref.

This engine is the core of `hs-cli migrate` (wrapped in a later phase).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml_io
except ImportError:  # pragma: no cover - ruamel.yaml is a harness dep
    yaml_io = None

_SCRIPT = Path(__file__).resolve()
_DEFAULT_ROOT = _SCRIPT.parents[2]

# Top-level paths never content-rewritten. plans/ is frozen+drift; manifest is
# regenerated; state/git/caches are not source.
_EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache"}
_EXCLUDE_REL = {
    "harness/manifest.json",
    "harness/data/decomposition-rename-map.json",  # generated; intentionally keeps old names
    "docs/harness/decomposition-migration.md",  # user-facing old->new table; old column must survive
    "GOAL.md",  # program tracker; records the old->new transition, old names are intentional
    "CHANGELOG.md",  # release history; documents old->new renames, both names are intentional
    "harness/state",
    "plans",
    ".claude/plugins",
}
# Reverse-only exclusions, unioned with _EXCLUDE_REL when collapsing back to the spine.
# These files intentionally hold themed hs-<g>: literals that must survive the reverse
# (cross-ref catalogs/tests that assert the split topology, history docs, backlog).
_REVERSE_EXCLUDE_REL = {
    "docs/STANDARDIZE.md",
    "docs/decisions.md",
    "BACKLOG.md",
    "harness/tests/test_catalog.py",
    "harness/tests/test_validate_skill_crossrefs.py",
}
# A per-line opt-out: any line carrying this literal is never rewritten (forward or
# reverse), so a deliberately-kept themed literal can sit inside an otherwise-rewritten
# file.
_KEEP_MARKER = "# migrate:keep"
# Only these extensions are treated as rewritable text; everything else is left alone.
_TEXT_SUFFIXES = {
    ".md", ".py", ".yaml", ".yml", ".json", ".txt", ".sh", ".toml", ".cfg",
    ".ini", ".gitkeep", "",
    # JS/TS family — ported skills ship these and they can carry route references
    ".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs",
}


# --------------------------------------------------------------------------- map

def load_map(path: Path) -> dict[str, str]:
    """skill -> group ("hs" for spine). Reads decomposition-map.yaml."""
    if yaml_io is None:
        raise RuntimeError("ruamel.yaml required")
    data = yaml_io.safe_load(Path(path).read_text()) or {}
    skills = data.get("skills", {})
    if not isinstance(skills, dict) or not skills:
        raise ValueError(f"no skills declared in {path}")
    return {str(k): str(v) for k, v in skills.items()}


def spine_skills(m: dict[str, str]) -> list[str]:
    return [s for s, g in m.items() if g == "hs"]


def non_spine_skills(m: dict[str, str]) -> dict[str, str]:
    """{skill: group} for every skill that moves out of the spine."""
    return {s: g for s, g in m.items() if g != "hs"}


def _invert_non_spine(root: Path | str) -> dict[str, str]:
    """{skill: group} sourced from the FILESYSTEM, not the map.

    The authoritative truth for a reverse migration is where the skill dirs actually
    live: every dir under harness/plugins/hs-<g>/skills/<skill> is a non-spine skill
    whose group is the '<g>' in its sibling-plugin name. The spine plugin 'hs' is
    excluded (its 'hs-' would-be group is empty). This yields all 84 non-spine skills
    including the ck-ports (excalidraw->viz, deploy->devops) that the original
    6-group map region never listed.
    """
    root = Path(root)
    out: dict[str, str] = {}
    for skill_dir in (root / "harness/plugins").glob("hs-*/skills/*"):
        if not skill_dir.is_dir():
            continue
        # plugin dir name is 'hs-<g>'; the group is everything after the 'hs-' prefix.
        plugin = skill_dir.parents[1].name  # .../hs-<g>/skills/<skill> -> hs-<g>
        if not plugin.startswith("hs-"):
            continue
        group = plugin[len("hs-"):]
        if not group:  # defensive: a bare 'hs-' is not a themed group
            continue
        out[skill_dir.name] = group
    return out


# ----------------------------------------------------------------- text rewrite

def _alt(names) -> str:
    # longest-first so the alternation never prefers a shorter prefix of a longer name
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


def _invoke_re(non_spine: dict[str, str]) -> re.Pattern:
    # (?<![\w-/]) rejects a word-char, '-' or '/' before hs (so hs-viz:, xhs: and
    # the `//hs:` inside a URL like https://hs:skill never match). A real slash-
    # command `/hs:s` or bare `hs:s` is preceded by start/space, so it still fires.
    # optional leading '/' is preserved. trailing (?![\w-]) is the name boundary
    # (so hs:zzfoo does not fire inside hs:zzfoobar).
    return re.compile(rf"(?<![\w\-/])(/?)hs:({_alt(non_spine)})(?![\w-])")


def _path_re(non_spine: dict[str, str]) -> re.Pattern:
    return re.compile(rf"(?<![\w-])hs/skills/({_alt(non_spine)})(?![\w-])")


def rewrite_text(text: str, non_spine: dict[str, str]) -> str:
    """Apply all four reference rewrites. Frontmatter `name:` is a bare-form case."""
    if not non_spine:
        return text
    inv = _invoke_re(non_spine)
    pth = _path_re(non_spine)
    text = inv.sub(lambda m: f"{m.group(1)}hs-{non_spine[m.group(2)]}:{m.group(2)}", text)
    text = pth.sub(lambda m: f"hs-{non_spine[m.group(1)]}/skills/{m.group(1)}", text)
    return text


def _check_res(non_spine: dict[str, str]) -> tuple[re.Pattern, re.Pattern]:
    # Independently constructed alternation detectors (NOT the rewrite Pattern objects),
    # so a rewrite-regex bug cannot blind the checker — but combined into one scan each
    # for speed (per-name finditer over the whole tree was minutes-slow).
    alt = _alt(non_spine)
    inv = re.compile(rf"(?<![\w\-/])/?hs:({alt})(?![\w-])")
    pth = re.compile(rf"(?<![\w-])hs/skills/({alt})(?![\w-])")
    return inv, pth


def find_dangling(text: str, non_spine: dict[str, str]) -> list[tuple[str, str, str]]:
    """Independent old-form detector (NOT the rewrite regex) — (kind, skill, match)."""
    if not non_spine:
        return []
    inv, pth = _check_res(non_spine)
    hits: list[tuple[str, str, str]] = []
    for m in inv.finditer(text):
        hits.append(("invoke", m.group(1), m.group(0)))
    for m in pth.finditer(text):
        hits.append(("path", m.group(1), m.group(0)))
    return hits


# ----------------------------------------------------------- reverse text rewrite

def _group_names(non_spine: dict[str, str]) -> list[str]:
    """The distinct themed-group names ('flow', 'think', …, 'viz')."""
    return sorted(set(non_spine.values()))


def _invoke_re_reverse(non_spine: dict[str, str]) -> re.Pattern:
    # Mirror of _invoke_re for the collapse direction: match hs-<g>:<skill> where <g>
    # is one of the themed group names and <skill> is one of the known skills. Same
    # boundary discipline as forward — (?<![\w\-/]) rejects a word-char/'-'/'/' before
    # 'hs' (so xhs-viz: and a URL '//hs-viz:' never match), an optional leading '/' is
    # preserved, and the trailing (?![\w-]) is the skill-name boundary. Group/skill
    # membership (the wrong-group filter) is enforced in the substitution, not here.
    return re.compile(
        rf"(?<![\w\-/])(/?)hs-({_alt(_group_names(non_spine))}):({_alt(non_spine)})(?![\w-])"
    )


def _path_re_reverse(non_spine: dict[str, str]) -> re.Pattern:
    return re.compile(
        rf"(?<![\w-])hs-({_alt(_group_names(non_spine))})/skills/({_alt(non_spine)})(?![\w-])"
    )


_REVERSE_RES_CACHE: dict[tuple, tuple[re.Pattern, re.Pattern]] = {}


def _reverse_res(non_spine: dict[str, str]) -> tuple[re.Pattern, re.Pattern]:
    """Compiled (invoke, path) reverse patterns, memoized by the non-spine signature.

    rewrite_text_reverse is applied once per LINE (keep-marker awareness), so without
    this cache the 84-skill alternation recompiled on every line of every file —
    minutes-slow over the full tree. Keyed by the sorted items so equal maps share
    one compile and the per-line cost drops to a dict lookup."""
    key = tuple(sorted(non_spine.items()))
    res = _REVERSE_RES_CACHE.get(key)
    if res is None:
        res = (_invoke_re_reverse(non_spine), _path_re_reverse(non_spine))
        _REVERSE_RES_CACHE[key] = res
    return res


def rewrite_text_reverse(text: str, non_spine: dict[str, str]) -> str:
    """Collapse themed refs back to the spine: hs-<g>:<s> -> hs:<s>, path likewise.

    A ref is only rewritten when its declared <g> matches the skill's real group, so a
    wrong-group ref (hs-flow:bakeoff, where bakeoff is a think skill) and an unknown
    skill (hs-think:notaskill) are both left untouched — exactly inverting the forward
    rewrite, which only ever produces correct-group refs.
    """
    if not non_spine:
        return text
    inv, pth = _reverse_res(non_spine)

    def _sub_invoke(m: re.Match) -> str:
        lead, group, skill = m.group(1), m.group(2), m.group(3)
        if non_spine.get(skill) != group:
            return m.group(0)  # wrong-group / unknown -> leave verbatim
        return f"{lead}hs:{skill}"

    def _sub_path(m: re.Match) -> str:
        group, skill = m.group(1), m.group(2)
        if non_spine.get(skill) != group:
            return m.group(0)
        return f"hs/skills/{skill}"

    text = inv.sub(_sub_invoke, text)
    text = pth.sub(_sub_path, text)
    return text


def _check_res_reverse(non_spine: dict[str, str]) -> tuple[re.Pattern, re.Pattern]:
    # Independently constructed reverse detectors (NOT the rewrite Pattern objects), so
    # a rewrite-regex bug cannot blind the checker. Deliberately broader than the
    # rewrite match: it flags ANY hs-<g>:<known-skill> where <g> is a real group name,
    # regardless of whether <skill> actually belongs to <g>. That way a wrong-group ref
    # (hs-flow:bakeoff) is caught too — after a reverse migration NO themed ref of any
    # kind should survive, correct-group or not.
    groups = _alt(_group_names(non_spine))
    skills = _alt(non_spine)
    inv = re.compile(rf"(?<![\w\-/])/?hs-({groups}):({skills})(?![\w-])")
    pth = re.compile(rf"(?<![\w-])hs-({groups})/skills/({skills})(?![\w-])")
    return inv, pth


def find_dangling_reverse(text: str, non_spine: dict[str, str]) -> list[tuple[str, str, str]]:
    """Independent themed-form detector (NOT the rewrite regex) — (kind, ref, match)."""
    if not non_spine:
        return []
    inv, pth = _check_res_reverse(non_spine)
    hits: list[tuple[str, str, str]] = []
    for m in inv.finditer(text):
        hits.append(("invoke", f"hs-{m.group(1)}:{m.group(2)}", m.group(0)))
    for m in pth.finditer(text):
        hits.append(("path", f"hs-{m.group(1)}/skills/{m.group(2)}", m.group(0)))
    return hits


# ----------------------------------------------------------------- scope / walk

def _excluded(rel: Path, root: Path, reverse: bool = False) -> bool:
    parts = rel.parts
    if any(p in _EXCLUDE_DIRS for p in parts):
        return True
    rel_str = rel.as_posix()
    # Reverse mode adds the reverse-only exclusions on top of the shared forward set.
    excludes = _EXCLUDE_REL | _REVERSE_EXCLUDE_REL if reverse else _EXCLUDE_REL
    for ex in excludes:
        if rel_str == ex or rel_str.startswith(ex + "/"):
            return True
    return False


def iter_text_files(root: Path, reverse: bool = False):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _excluded(rel, root, reverse):
            continue
        if p.suffix not in _TEXT_SUFFIXES:
            continue
        yield p


def _rewrite_keep_aware(text: str, fn) -> str:
    """Apply rewrite `fn`, skipping any line carrying the keep marker.

    Fast path: a marker-free file is rewritten in ONE pass over the whole text — the
    per-line split exists only to spare marked lines, and a ref never spans a newline
    (a leading '\\n' satisfies the same negative lookbehind as start-of-line), so the
    whole-text pass is identical to the per-line one for unmarked text. This is the
    difference between one regex scan per file and one per line (minutes vs seconds
    over the full tree)."""
    if _KEEP_MARKER not in text:
        return fn(text)
    out = []
    for line in text.splitlines(keepends=True):
        out.append(line if _KEEP_MARKER in line else fn(line))
    return "".join(out)


# --------------------------------------------------------------------- dir move

def plan_moves(root: Path, non_spine: dict[str, str]) -> list[tuple[Path, Path]]:
    moves = []
    for skill, group in non_spine.items():
        src = root / "harness/plugins/hs/skills" / skill
        dst = root / f"harness/plugins/hs-{group}/skills" / skill
        if src.is_dir() and not dst.exists():
            moves.append((src, dst))
    return moves


def move_skill_dirs(root: Path, non_spine: dict[str, str]) -> list[tuple[Path, Path]]:
    done = []
    for src, dst in plan_moves(root, non_spine):
        # Re-check at move time: plan_moves snapshots the source set, so a source
        # that disappeared since (e.g. another migrate run already moved it) is
        # skipped rather than crashing the run.
        if not src.is_dir() or dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        done.append((src, dst))
    return done


def plan_moves_reverse(root: Path, non_spine: dict[str, str]) -> list[tuple[Path, Path]]:
    """Inverse of plan_moves: src under the themed plugin, dst back in the spine."""
    moves = []
    for skill, group in non_spine.items():
        src = root / f"harness/plugins/hs-{group}/skills" / skill
        dst = root / "harness/plugins/hs/skills" / skill
        if src.is_dir() and not dst.exists():
            moves.append((src, dst))
    return moves


def move_skill_dirs_reverse(root: Path, non_spine: dict[str, str]) -> list[tuple[Path, Path]]:
    done = []
    for src, dst in plan_moves_reverse(root, non_spine):
        # Same disappeared-source guard as the forward mover.
        if not src.is_dir() or dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        done.append((src, dst))
    return done


# ------------------------------------------------------------------ rename map

def build_rename_map(m: dict[str, str]) -> dict:
    ns = non_spine_skills(m)
    moved = {
        s: {
            "group": g,
            "old_invoke": f"hs:{s}",
            "new_invoke": f"hs-{g}:{s}",
            "old_dir": f"harness/plugins/hs/skills/{s}",
            "new_dir": f"harness/plugins/hs-{g}/skills/{s}",
        }
        for s, g in ns.items()
    }
    return {
        "generated_by": "migrate_decomposition.py",
        "spine": sorted(spine_skills(m)),
        "moved": moved,
    }


def build_rename_map_reverse(non_spine: dict[str, str]) -> dict:
    """Inverse rename map: old = themed (the migration's destination), new = spine."""
    moved = {
        s: {
            "group": g,
            "old_invoke": f"hs-{g}:{s}",
            "new_invoke": f"hs:{s}",
            "old_dir": f"harness/plugins/hs-{g}/skills/{s}",
            "new_dir": f"harness/plugins/hs/skills/{s}",
        }
        for s, g in non_spine.items()
    }
    return {
        "generated_by": "migrate_decomposition.py (reverse)",
        "moved": moved,
    }


# ------------------------------------------------------------------------- run

def run_migrate(
    root: Path | str = _DEFAULT_ROOT,
    *,
    dry_run: bool = False,
    do_check: bool = False,
    map_path: Path | None = None,
    write_rename_map: bool = True,
    reverse: bool = False,
) -> int:
    root = Path(root)
    if reverse:
        return _run_reverse(
            root, dry_run=dry_run, do_check=do_check, write_rename_map=write_rename_map
        )

    map_path = Path(map_path) if map_path else root / "harness/data/decomposition-map.yaml"
    m = load_map(map_path)
    ns = non_spine_skills(m)

    if do_check:
        inv_re, pth_re = _check_res(ns) if ns else (None, None)
        dangling: list[str] = []
        for p in iter_text_files(root):
            try:
                txt = p.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if inv_re is None:
                continue
            for m in inv_re.finditer(txt):
                dangling.append(f"{p.relative_to(root)}: invoke {m.group(0)}")
            for m in pth_re.finditer(txt):
                dangling.append(f"{p.relative_to(root)}: path {m.group(0)}")
        if dangling:
            print(f"DANGLING ({len(dangling)}) old-form refs:", file=sys.stderr)
            for d in dangling[:50]:
                print(f"  {d}", file=sys.stderr)
            return 1
        print("check: 0 dangling old-form refs")
        return 0

    if dry_run:
        moves = plan_moves(root, ns)
        changed = 0
        for p in iter_text_files(root):
            try:
                txt = p.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if rewrite_text(txt, ns) != txt:
                changed += 1
        print(f"dry-run: {len(moves)} dir moves, {changed} files would be rewritten")
        for src, dst in moves:
            print(f"  move {src.relative_to(root)} -> {dst.relative_to(root)}")
        return 0

    # real run: move dirs first so moved SKILL.md files are rewritten in place
    move_skill_dirs(root, ns)
    for p in iter_text_files(root):
        try:
            txt = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        new = rewrite_text(txt, ns)
        if new != txt:
            p.write_text(new)

    if write_rename_map:
        out = root / "harness/data/decomposition-rename-map.json"
        out.write_text(json.dumps(build_rename_map(m), indent=2, sort_keys=True) + "\n")
    return 0


def _run_reverse(
    root: Path,
    *,
    dry_run: bool = False,
    do_check: bool = False,
    write_rename_map: bool = True,
) -> int:
    """Collapse every themed sibling plugin back into the spine — inverse of forward.

    The non-spine set is sourced from the FILESYSTEM (the authoritative truth for the
    collapse), so this works the same on the live tree or a temp-dir fixture without a
    map. Walks honor the wider reverse exempt set and the per-line keep marker.
    """
    ns = _invert_non_spine(root)

    if do_check:
        inv_re, pth_re = _check_res_reverse(ns) if ns else (None, None)
        dangling: list[str] = []
        for p in iter_text_files(root, reverse=True):
            try:
                txt = p.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if inv_re is None:
                continue
            for line in txt.splitlines():
                if _KEEP_MARKER in line:
                    continue  # an intentionally-kept themed literal is not dangling
                for mm in inv_re.finditer(line):
                    dangling.append(f"{p.relative_to(root)}: invoke {mm.group(0)}")
                for mm in pth_re.finditer(line):
                    dangling.append(f"{p.relative_to(root)}: path {mm.group(0)}")
        if dangling:
            print(f"DANGLING ({len(dangling)}) themed-form refs:", file=sys.stderr)
            for d in dangling[:50]:
                print(f"  {d}", file=sys.stderr)
            return 1
        print("check: 0 dangling themed-form refs")
        return 0

    if dry_run:
        moves = plan_moves_reverse(root, ns)
        changed = 0
        for p in iter_text_files(root, reverse=True):
            try:
                txt = p.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if _rewrite_keep_aware(txt, lambda t: rewrite_text_reverse(t, ns)) != txt:
                changed += 1
        print(f"dry-run (reverse): {len(moves)} dir moves, {changed} files would be rewritten")
        for src, dst in moves:
            print(f"  move {src.relative_to(root)} -> {dst.relative_to(root)}")
        return 0

    # real run: move dirs back first so collapsed SKILL.md files are rewritten in place
    move_skill_dirs_reverse(root, ns)
    for p in iter_text_files(root, reverse=True):
        try:
            txt = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        new = _rewrite_keep_aware(txt, lambda t: rewrite_text_reverse(t, ns))
        if new != txt:
            p.write_text(new)

    if write_rename_map:
        out = root / "harness/data/decomposition-rename-map.json"
        out.write_text(json.dumps(build_rename_map_reverse(ns), indent=2, sort_keys=True) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="decomposition migrate engine")
    ap.add_argument("--root", default=str(_DEFAULT_ROOT))
    ap.add_argument("--map", dest="map_path", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="scan for surviving old-form refs; exit!=0 if any")
    ap.add_argument("--reverse", action="store_true",
                    help="collapse themed siblings back into the spine (inverse of forward)")
    ap.add_argument("--no-rename-map", action="store_true")
    a = ap.parse_args(argv)
    return run_migrate(
        root=a.root,
        dry_run=a.dry_run,
        do_check=a.check,
        map_path=a.map_path,
        write_rename_map=not a.no_rename_map,
        reverse=a.reverse,
    )


if __name__ == "__main__":
    raise SystemExit(main())
