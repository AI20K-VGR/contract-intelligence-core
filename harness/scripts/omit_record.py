"""omit_record.py — the install-time omitted-skills record (single source of truth).

Per-skill install selection omits deselected skill dirs at copy (the dir-omit
disable for the collapsed single-hs plugin). This module is the ONE place that
knows the record's path, its JSON envelope, and the skill-dir path prefix. It is
read/written by install (copy + write), verify_install (the omit seam), hs-cli
(enable/disable), and the disabled-skill nudge — keeping the path / envelope /
prefix from drifting across those sites.
"""
import json
from pathlib import Path

_REL = "harness/state/install-omitted-skills.json"
_SKILLS_REL = "harness/plugins/hs/skills"


def record_path(root) -> Path:
    """Path to the omit record under `root` (a target repo root)."""
    return Path(root) / _REL


def read_omitted(root) -> set:
    """The recorded omitted-skill names. Missing/invalid record -> empty set
    (nothing omitted) so a broken record never silently hides a real drift."""
    try:
        data = json.loads(record_path(root).read_text(encoding="utf-8"))
        return {s for s in (data.get("omitted") or []) if isinstance(s, str)}
    except Exception:  # noqa: BLE001 — absent/unreadable record -> nothing omitted
        return set()


def write_omitted(root, skills) -> None:
    """Write the omit record (machine-written JSON, sorted)."""
    p = record_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"omitted": sorted(skills)}, indent=2) + "\n",
                 encoding="utf-8")


def skill_dir_prefixes(skills) -> tuple:
    """Repo-relative path prefixes for the given skill dirs (omit-filter helper):
    ``harness/plugins/hs/skills/<skill>/`` for each, in a tuple ready for
    ``str.startswith``."""
    return tuple("%s/%s/" % (_SKILLS_REL, s) for s in skills if s)
