#!/usr/bin/env python3
"""Measure the SessionStart catalog token cost.

The host loads every live skill's `name`+`description` into the system prompt at
SessionStart; an omitted skill costs nothing. Summing `description:` bytes across
live vs off skills (bytes/4 ≈ tokens) is the same proxy the context-diet plan used,
and re-runs cheaply after any off-list edit.

Off-list sources: --off-list reads either a dev farm off-list YAML (`disabled:`
key) or the ship `skill-defaults.yaml` (`default_off:` key) — both top-level list
keys are accepted. Floor-disjoint and partition invariants are asserted elsewhere
(test_skill_defaults / test_dev_skill_farm); this tool only measures.

Scope of the estimate: only `description:` bytes are summed — the skill `name` and
other frontmatter the host also loads are excluded, so est_tokens_* is a consistent
lower-bound proxy (the diet plan's chosen proxy), sound for deltas, not an absolute.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

try:
    import yaml_io
except ImportError:  # measurement degrades to single-line regex parse
    yaml_io = None

if str(pathlib.Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import skill_frontmatter  # noqa: E402
from token_estimate import est_tokens  # noqa: E402


def _description(skill_md: pathlib.Path) -> str:
    return skill_frontmatter.description(skill_md.read_text(encoding="utf-8"))


def measure(skills_root, off_names=None) -> dict:
    off = set(off_names or [])
    root = pathlib.Path(skills_root)
    # Accumulate the payloads, not just their sizes: the token estimate is
    # corrected by the share of non-ASCII bytes, which a size cannot carry.
    live_buf, off_buf = bytearray(), bytearray()
    live_ct = off_ct = 0
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        sk = d / "SKILL.md"
        if not sk.is_file():
            continue
        payload = _description(sk).encode("utf-8")
        if d.name in off:
            off_buf += payload
            off_ct += 1
        else:
            live_buf += payload
            live_ct += 1
    return {
        "skills_root": str(root),
        "live_count": live_ct,
        "off_count": off_ct,
        "live_desc_bytes": len(live_buf),
        "off_desc_bytes": len(off_buf),
        "total_desc_bytes": len(live_buf) + len(off_buf),
        "est_tokens_live": est_tokens(bytes(live_buf)),
        "est_tokens_saved": est_tokens(bytes(off_buf)),
    }


def _load_off_list(path) -> list:
    if not path or yaml_io is None:
        return []
    data = yaml_io.safe_load(pathlib.Path(path).read_text(encoding="utf-8")) or {}
    names = data.get("disabled")
    if names is None:
        names = data.get("default_off")
    return list(names or [])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure catalog description token cost")
    ap.add_argument("--skills-root", default="harness/plugins/hs/skills")
    ap.add_argument("--off-list", default=None,
                    help="YAML with a `disabled:` (or `default_off:`) list")
    ap.add_argument("--off", action="append", default=None,
                    help="explicit off skill name (repeatable)")
    a = ap.parse_args(argv)
    off = list(a.off or []) + _load_off_list(a.off_list)
    print(json.dumps(measure(a.skills_root, off), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
