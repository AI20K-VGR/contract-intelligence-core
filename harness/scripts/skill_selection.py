"""skill_selection.py — install-time per-skill selection for the single hs plugin.

After the collapse every skill lives under harness/plugins/hs/skills and the only
plugin is `hs` (always on), so a per-plugin toggle no longer selects skills. An
install instead picks skills at the dir level:

  - a GROUP expands to its skills (components.yaml `skills:` list),
  - a manually-picked skill AUTO-TICKS its declared deps (skill-deps.yaml),
  - the 16-skill spine floor is ALWAYS present (never omittable),
  - deselected skills are OMITTED at copy.

Dir-omission is the only disable that works for plugin skills on this CC version
(the `disable-model-invocation` frontmatter is unsupported for plugin
skills — see the probe). The omit list drives the verify_install seam and
the hs-cli re-enable path.
"""
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import skill_deps  # noqa: E402
import component_config as cc  # noqa: E402

_SKILLS_REL = "harness/plugins/hs/skills"
_DEFAULTS_REL = "harness/data/skill-defaults.yaml"


class SelectionError(Exception):
    """An install-time skill selection that cannot be honored (e.g. unknown group)."""


def load_defaults(source_root) -> set | None:
    """The shipped default-OFF skill set (skill-defaults.yaml `default_off`).

    Returns None when the catalog is missing or unreadable so the caller can fall
    back to ship-all rather than brick the installer. Stale names (present in the
    catalog but not a real skill) are dropped, never enabled/omitted by accident.
    """
    p = Path(source_root) / _DEFAULTS_REL
    try:
        import yaml_io
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
        off = data.get("default_off")
        if not isinstance(off, list):
            return None
        return set(off) & all_skills(source_root)
    except Exception:  # noqa: BLE001 — a broken catalog must not stop an install
        return None


def all_skills(source_root) -> set:
    """Every skill dir (carrying SKILL.md) under the collapsed hs plugin."""
    base = Path(source_root) / _SKILLS_REL
    if not base.is_dir():
        return set()
    return {d.name for d in base.iterdir() if (d / "SKILL.md").is_file()}


def _components(source_root) -> dict:
    return cc.load_components(
        Path(source_root) / "harness" / "data" / "components.yaml")


def group_skills(group, source_root) -> list:
    """The skills a group label carries (components.yaml). Unknown group -> error."""
    comps = _components(source_root)
    if group not in comps:
        raise SelectionError(
            "unknown group %r — known: %s" % (group, ", ".join(sorted(comps))))
    return list(comps[group].get("skills") or [])


def resolve_enabled(*, source_root, skills=None, groups=None, add_skills=None) -> set:
    """The enabled-skill set for an install.

    skills=None AND groups=None AND add_skills=None -> the default: ship-all MINUS
    the default-off catalog (skill-defaults.yaml). A missing/broken catalog falls
    back to ship-all with a WARN so a bad file never bricks the installer.

    add_skills=<names> (the interactive 'recommended + clusters' path) -> the
    recommended default baseline UNCHANGED (never re-dep-closed — the recommended
    set deliberately leaves its own deps stashed, off-as-dep is valid) PLUS the
    transitive closure of ONLY the opt-in names. add_skills=[] therefore resolves
    identically to the plain default; picking a cluster adds that cluster and its
    own deps, and nothing else.

    Otherwise (explicit --skills/--skill-groups): the named skills + each named
    group's skills, the transitive dep auto-tick closure of THAT user seed, then the
    16-skill floor unioned in WITHOUT expanding its own closure (the floor must not
    drag its dep tree back in, or a spine-only install silently resurrects opt-in
    clusters). A name with no skill dir is dropped (a typo ghost-enables nothing).
    """
    deps_path = Path(source_root) / "harness" / "data" / "skill-deps.yaml"
    floor = set(skill_deps.core_immutable(deps_path))

    def _default_base():
        """(recommended set, catalog_ok). ship-all minus default-off, floor bare."""
        base = all_skills(source_root)
        off = load_defaults(source_root)
        if off is None:
            sys.stderr.write("[skill_selection] WARN: skill-defaults.yaml missing or "
                             "unreadable — shipping all skills\n")
            return base, False
        return (base - off) | floor, True  # floor is off-disjoint; union is belt-and-braces

    if skills is None and groups is None and add_skills is None:
        return _default_base()[0]
    if add_skills is not None:
        base, ok = _default_base()
        if not ok:
            return base  # broken catalog already degraded to ship-all
        # close ONLY the opt-in seed; the recommended baseline stays as-is.
        extra = skill_deps.resolve(set(add_skills), deps_path)
        return (base | extra | floor) & all_skills(source_root)
    seed = set(skills or [])
    for g in (groups or []):
        seed.update(group_skills(g, source_root))
    enabled = skill_deps.resolve(seed, deps_path)  # auto-tick the USER seed's deps only
    enabled |= floor                                # floor: unioned bare, never expanded
    return enabled & all_skills(source_root)


def omitted(source_root, enabled) -> set:
    """Skills to OMIT at copy = the full universe minus the enabled set. The spine
    core is in `enabled` by construction, so it can never appear here."""
    return all_skills(source_root) - set(enabled)
