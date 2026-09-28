#!/usr/bin/env python3
"""Build a curated symlink farm of the hs plugin that exposes every repo skill
EXCEPT a personal dev off-list, so a session loading this plugin from a directory
marketplace sees fewer skills (token diet) while the repo stays full (109 skills →
pack/test/ship unaffected).

The off-list SSOT is `.harness-dev/dev-off-skills.yaml` (`disabled:` list, gitignored,
dev-local, DIFFERENT from the shipped ship-default in harness/data/skill-defaults.yaml).
The farm is a tree of SYMLINKS back into the repo, so it never drifts from repo edits;
resource dirs (common/_shared/_docslib) and everything but skills/ are symlinked whole.

Usage:
  dev_skill_farm.py --build [--root R] [--farm D]   # (re)build the farm
  dev_skill_farm.py --check [--root R] [--farm D]    # exit 1 on drift (exposed != all-off)

The floor (13 spine + use/find-skills/cleanup) can never be off-listed; --build refuses.
No off-list file → no-op (nothing to curate).
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_deps  # noqa: E402

try:
    import yaml_io
except ImportError:  # pragma: no cover - ruamel.yaml is a harness dep
    yaml_io = None

_OFFLIST_REL = ".harness-dev/dev-off-skills.yaml"
_DEFAULT_FARM_REL = ".harness-dev/hs-plugins"
_PLUGINS_REL = "harness/plugins"


def load_off_list(root: Path):
    """The dev off-list set, or None when the file is absent (no curation). Raises
    on a malformed file rather than silently shipping the wrong catalog."""
    p = Path(root) / _OFFLIST_REL
    if not p.is_file():
        return None
    if yaml_io is None:
        raise RuntimeError("ruamel.yaml required to read %s" % _OFFLIST_REL)
    data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
    return set(data.get("disabled") or [])


def _floor(root: Path) -> set:
    return set(skill_deps.core_immutable(Path(root) / "harness" / "data" / "skill-deps.yaml"))


def all_skills(root: Path) -> set:
    skills = Path(root) / _PLUGINS_REL / "hs" / "skills"
    return {p.name for p in skills.iterdir() if (p / "SKILL.md").is_file()}


def validate_off(root: Path, names) -> list:
    """Reasons a name cannot be off-listed (unknown skill / floor). Empty = all OK."""
    allsk = all_skills(root)
    floor = _floor(root)
    bad = []
    for n in names:
        if n in floor:
            bad.append("%s is a floor skill (never disablable)" % n)
        elif n not in allsk:
            bad.append("%s is not a skill" % n)
    return bad


def toggle_record(root: Path, add=(), remove=()) -> set:
    """Add/remove names in .harness-dev/dev-off-skills.yaml TEXTUALLY so the file's
    header + per-cluster comments survive (yaml.dump would strip them). Returns the
    new disabled set. Creates the file if absent. Caller validates first."""
    root = Path(root)
    p = root / _OFFLIST_REL
    cur = set(load_off_list(root) or set())
    add, remove = [n for n in add if n not in cur], set(remove)
    lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else ["disabled:"]
    if remove:
        pat = re.compile(r"^\s*-\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*(#.*)?$")
        kept = []
        for ln in lines:
            m = pat.match(ln)
            if m and m.group(1) in remove:
                continue
            kept.append(ln)
        lines = kept
    if add:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("  # toggled on via hs-cli skills --off")
        lines.extend("  - %s" % n for n in add)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (cur | set(add)) - remove


def _symlink(link: Path, target: Path):
    """Point `link` at `target` RELATIVE to the link's own directory.

    Both ends live in the same repo, so a relative link is position-independent:
    the farm keeps working after the checkout is moved, cloned, or opened at a
    different prefix. An absolute target pinned it to one machine's path, and the
    failure was silent — the directory still lists and the entries still appear,
    the skills just never load."""
    link.symlink_to(os.path.relpath(target.resolve(), link.parent.resolve()))


def build_farm(root: Path, farm: Path, off: set) -> dict:
    """(Re)materialize the farm. Returns {'exposed': N, 'off': N}. Refuses a floor
    skill in the off-list (would break the always-on contract)."""
    root, farm = Path(root), Path(farm)
    off = set(off or ())
    bad = off & _floor(root)
    if bad:
        raise ValueError("off-list contains floor skills (never disablable): %s"
                         % ", ".join(sorted(bad)))
    src_plugins = root / _PLUGINS_REL
    if farm.exists() or farm.is_symlink():
        shutil.rmtree(farm, ignore_errors=True)
    farm.mkdir(parents=True)
    # plugins/ level: symlink every entry except the hs plugin dir (curated below)
    for entry in src_plugins.iterdir():
        if entry.name == "hs":
            continue
        _symlink(farm / entry.name, entry)
    # hs/ level: real dir, symlink every entry except skills/
    farm_hs = farm / "hs"
    farm_hs.mkdir()
    for entry in (src_plugins / "hs").iterdir():
        if entry.name == "skills":
            continue
        _symlink(farm_hs / entry.name, entry)
    # skills/ level: real dir; symlink each ON skill + every resource dir; drop off skills
    farm_skills = farm_hs / "skills"
    farm_skills.mkdir()
    exposed = 0
    for entry in (src_plugins / "hs" / "skills").iterdir():
        is_skill = (entry / "SKILL.md").is_file()
        if is_skill and entry.name in off:
            continue
        _symlink(farm_skills / entry.name, entry)
        if is_skill:
            exposed += 1
    return {"exposed": exposed, "off": len(off)}


def exposed_skills(farm: Path) -> set:
    """Skill names the farm actually exposes (a symlinked dir resolving to a SKILL.md)."""
    skills = Path(farm) / "hs" / "skills"
    if not skills.is_dir():
        return set()
    return {p.name for p in skills.iterdir() if (p / "SKILL.md").is_file()}


def bin_root_pointer(root: Path) -> str:
    """The absolute path ANOTHER project sets as its $HARNESS_BIN_ROOT to consume
    THIS dogfood repo as its shared binary (Goal 2: dev auto-consumes latest, no
    snapshot copy). The value is this repo's own root.

    Deliberately NOT set in this repo's own env: the dogfood repo must keep
    HARNESS_BIN_ROOT UNSET so the two-zone guards stay in the self-host collapse
    (bin==project) and dev edits to harness/ are not caught by the whole-bin
    read-only zone. This pointer is for the OTHER project's settings.local.json."""
    return str(Path(root).resolve())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build/check the curated dev skill farm.")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--farm", default=None, help="farm dir (default: .harness-dev/hs-plugins)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--bin-root", dest="bin_root", action="store_true",
                   help="print the $HARNESS_BIN_ROOT value another project sets to "
                        "consume THIS repo as its shared binary (Goal 2). Does NOT "
                        "set it here — the dogfood repo stays self-host.")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.bin_root:
        print("HARNESS_BIN_ROOT=%s" % bin_root_pointer(root))
        sys.stderr.write(
            "# set this in the OTHER project's .claude/settings.local.json env; "
            "leave THIS repo's HARNESS_BIN_ROOT unset (self-host collapse).\n")
        return 0
    farm = Path(args.farm) if args.farm else root / _DEFAULT_FARM_REL
    off = load_off_list(root)
    if off is None:
        sys.stderr.write("no %s — nothing to curate (repo ships full catalog)\n" % _OFFLIST_REL)
        return 0
    if args.build:
        res = build_farm(root, farm, off)
        print("built farm at %s: %d exposed, %d off" % (farm, res["exposed"], res["off"]))
        return 0
    # --check: farm exposure must equal all_skills - off
    want = all_skills(root) - off
    have = exposed_skills(farm)
    if want != have:
        miss, extra = sorted(want - have), sorted(have - want)
        sys.stderr.write("farm drift: missing=%s extra=%s\n" % (miss, extra))
        return 1
    print("farm OK: %d exposed matches off-list" % len(have))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
