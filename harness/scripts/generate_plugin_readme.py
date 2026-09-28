#!/usr/bin/env python3
"""generate_plugin_readme.py — scripted per-plugin index README.

Each plugin dir gets a README that INDEXES its skills (invoke name + one-line purpose),
states the default on/off posture, and shows how to enable the group. This is new
navigation info, not a per-skill README restating SKILL.md frontmatter (that would be
DRY-violating boilerplate). Idempotent; never clobbers a hand-written README (one without
the generated MARKER).

Usage:
  python3 harness/scripts/generate_plugin_readme.py            # write all plugin READMEs
  python3 harness/scripts/generate_plugin_readme.py --check    # report missing/ stale, write nothing
"""
import argparse
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import diff_render  # noqa: E402
import skill_frontmatter  # noqa: E402

MARKER = "<!-- generated: plugin-readme -->"
# the always-on spine plugin; every other plugin is opt-in at install time
_SPINE = "hs"


def _plugins_root():
    return Path(__file__).resolve().parent.parent / "plugins"


def _frontmatter(skill_md):
    return skill_frontmatter.frontmatter(skill_md.read_text(encoding="utf-8"))


def _first_sentence(text, limit=140):
    text = " ".join(str(text).split())
    # cut at the first sentence boundary, then hard-cap
    cut = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return (cut[: limit - 1] + "…") if len(cut) > limit else cut


def _skills(plug_dir, plugin_name):
    """[(invoke_name, purpose)] sorted by invoke name.

    The invoke name is `<plugin>:<dir>` (location-based, matching catalog.py's
    ownership model) — NOT the frontmatter `name:`, which is bare post the S1
    name-prefix-strip and carries no plugin namespace of its own."""
    out = []
    for sk in sorted((plug_dir / "skills").rglob("SKILL.md")) if (plug_dir / "skills").is_dir() else []:
        fm = _frontmatter(sk)
        invoke = "%s:%s" % (plugin_name, sk.parent.name)
        out.append((invoke, _first_sentence(fm.get("description", ""))))
    return sorted(out, key=lambda t: t[0])


def render_plugin_readme(plug_dir) -> str:
    meta = json.loads((plug_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    name = meta.get("name", plug_dir.name)
    desc = meta.get("description", "").strip()
    version = meta.get("version", "")
    skills = _skills(plug_dir, name)

    if name == _SPINE:
        posture = "**Default:** always-on (the SDLC spine — installed and enabled on every harness)."
    else:
        group = name[3:] if name.startswith("hs-") else name
        posture = ("**Default:** opt-in. Enable with `hs-cli components --enable %s` "
                   "(or choose it at install time)." % group)

    lines = [MARKER, "", "# %s" % name, ""]
    if desc:
        lines += [desc, ""]
    lines += [posture]
    if version:
        lines += ["**Version:** %s" % version]
    if name == _SPINE:
        lines += ["", "## Packaging notes"]
        lines += [
            "",
            "This plugin is **repo-embedded by design**, not marketplace-cache portable: "
            "its skills/agents assume the full harness tree at `harness/` (scripts, data, "
            "rules) under the project root, and its 17 fail-closed gate hooks are wired "
            "per-project in `.claude/settings.json` rather than in a plugin-level "
            "`hooks/hooks.json` — a deliberate two-zone choice that keeps "
            "gate policy out of a user-scope manifest an agent could otherwise widen via a "
            "project-local write (the F3 hole). It still installs cleanly in global mode "
            "(one shared `$HARNESS_BIN_ROOT` binary, many projects); it just is not "
            "copy-into-`~/.claude/plugins/cache/` portable today. See "
            "`plans/260709-1514-cc-docs-standardization/artifacts/investigation/"
            "INV-2-plugin-self-containment.md` for the full trade-off.",
            "",
            "`workflows/*.js` (`ping`, `base-fanout-consolidate`, `base-pipeline-verify`) uses "
            "Claude Code's plugin-bundled workflow loading (`<plugin>/workflows/*.js` namespaced "
            "`hs:`). This loading path is not yet listed in CC's official file-locations table "
            "(https://code.claude.com/docs/en/workflows) — treat it as an undocumented-but-"
            "observed convention. The `scriptPath` fallback documented in "
            "`harness/rules/orchestration-protocol.md` stays mandatory as the hedge if the "
            "convention ever changes.",
        ]
    lines += ["", "## Skills (%d)" % len(skills), "", "| Invoke | Purpose |", "|---|---|"]
    for inv, purpose in skills:
        lines.append("| `/%s` | %s |" % (inv, purpose or "—"))
    lines += [
        "",
        "Each skill's full contract lives in its `SKILL.md`; load-on-demand detail lives under "
        "the skill's `references/`. This index is generated — regenerate with "
        "`harness/scripts/generate_plugin_readme.py`.",
        "",
    ]
    return "\n".join(lines)


def write_plugin_readme(plug_dir) -> bool:
    """Write the plugin README. Returns True if written, False if a hand-written
    README (no MARKER) was preserved."""
    readme = plug_dir / "README.md"
    if readme.is_file() and MARKER not in readme.read_text(encoding="utf-8"):
        return False  # hand-written -> never clobber
    readme.write_text(render_plugin_readme(plug_dir), encoding="utf-8")
    return True


def _iter_plugins(root):
    for plug in sorted(root.iterdir()):
        if (plug / ".claude-plugin" / "plugin.json").is_file():
            yield plug


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)
    root = _plugins_root()
    written, skipped, stale = [], [], []
    for plug in _iter_plugins(root):
        if args.check:
            r = plug / "README.md"
            if not r.is_file():
                stale.append(plug.name)
            else:
                txt = r.read_text(encoding="utf-8")
                rendered = render_plugin_readme(plug)
                if MARKER in txt and txt != rendered:
                    stale.append(plug.name)
                    sys.stderr.write(diff_render.render_check_diff(rendered, txt, str(r)))
            continue
        (written if write_plugin_readme(plug) else skipped).append(plug.name)
    if args.check:
        print(json.dumps({"stale_or_missing": stale, "count": len(stale)}, indent=2))
        return 1 if stale else 0
    print(json.dumps({"written": written, "skipped_handwritten": skipped}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
