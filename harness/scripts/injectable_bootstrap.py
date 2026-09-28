#!/usr/bin/env python3
"""injectable_bootstrap.py — propose + apply the `injectable` frontmatter field.

`injectable` marks whether a skill's methodology may be injected into the gemini
partner lane (a second engine following the skill's role + process). The proposal
is mechanical: a skill listed in `spine_false` (injectable-classifier.yaml) is
harness machinery (gate/write/deploy/config/autonomous-commit) and proposed
`false`; every other skill is advisory / read-comprehension-safe and proposed
`true`. A human ratifies the WHOLE table once — `--propose` prints it and writes
NOTHING; only `--apply <confirmed.yaml>` (or `--apply-proposal` after review)
mutates frontmatter, idempotently.

Path discipline: config + catalog resolve off __file__, never CWD (this runs from
an installed tree too).
"""
import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_HARNESS = _HERE.parents[1]                      # scripts→harness
for _p in (_HARNESS / "scripts",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import skill_frontmatter  # noqa: E402

_CLASSIFIER = _HARNESS / "data" / "injectable-classifier.yaml"
_NON_SKILL = {"_shared", "common", "_docslib"}


def _load_classifier():
    import yaml_io
    data = yaml_io.safe_load(_CLASSIFIER.read_text(encoding="utf-8")) or {}
    return data


def _spine_false() -> set:
    return set(_load_classifier().get("spine_false") or [])


def classify(name: str) -> bool:
    """True (injectable) unless the skill is harness machinery in spine_false."""
    return name not in _spine_false()


def _reason(name: str, injectable: bool) -> str:
    if not injectable:
        return "harness machinery (gate/write/deploy/config/autonomous) — spine_false"
    return "advisory / read-comprehension-safe methodology — injectable"


def _iter_skill_dirs(root: Path):
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.name in _NON_SKILL or not d.is_dir():
            continue
        if (d / "SKILL.md").is_file():
            out.append(d)
    return out


def _skills_root(skills_root=None) -> Path:
    if skills_root:
        return Path(skills_root)
    return _HARNESS / "plugins" / "hs" / "skills"


def propose(skills_root=None) -> dict:
    """{skill_name: {'injectable': bool, 'reason': str}} over the live skills dir
    AND its sibling disabled-skills/ (an off skill still needs the field)."""
    root = _skills_root(skills_root)
    dirs = list(_iter_skill_dirs(root))
    sibling = root.parent / "disabled-skills"
    dirs += _iter_skill_dirs(sibling)
    table = {}
    for d in dirs:
        val = classify(d.name)
        table[d.name] = {"injectable": val, "reason": _reason(d.name, val)}
    return dict(sorted(table.items()))


def apply_field(skill_md, value: bool) -> bool:
    """Insert (or update) `injectable: <value>` in the SKILL.md frontmatter, right
    after the `name:` line (or at the top of the block if none). Idempotent: a
    re-apply updates the value in place, never a duplicate. Returns True only when the
    file changed (a no-op re-apply returns False)."""
    p = Path(skill_md)
    text = p.read_text(encoding="utf-8")
    block, _ = skill_frontmatter.split(text)
    if block is None:           # no leading fence or no close — nothing to edit
        return False
    end = 3 + len(block)        # index of the closing fence within `text`
    head = block[1:] if block.startswith("\n") else block  # drop the leading newline
    rest = text[end:]           # from the closing fence onward
    lines = head.split("\n")
    val = "true" if value else "false"

    out, replaced = [], False
    for ln in lines:
        if ln.lstrip().startswith("injectable:"):
            indent = ln[:len(ln) - len(ln.lstrip())]
            out.append("%sinjectable: %s" % (indent, val))
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        # insert after the first `name:` line, else at the top
        idx = next((i for i, ln in enumerate(out)
                    if ln.lstrip().startswith("name:")), -1)
        out.insert(idx + 1, "injectable: %s" % val)
    new = "---\n" + "\n".join(out) + rest
    if new != text:
        p.write_text(new, encoding="utf-8")
        return True
    return False


def _apply_table(table: dict, skills_root=None) -> int:
    """Write every field in a {name: bool|{'injectable': bool}} table. Returns the
    count applied. Resolves each name to its live-or-stashed SKILL.md."""
    root = _skills_root(skills_root)
    lookup = {d.name: d for d in _iter_skill_dirs(root)}
    lookup.update({d.name: d for d in _iter_skill_dirs(root.parent / "disabled-skills")})
    n = 0
    for name, spec in table.items():
        val = spec["injectable"] if isinstance(spec, dict) else bool(spec)
        d = lookup.get(name)
        if d and apply_field(str(d / "SKILL.md"), val):
            n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="propose/apply the injectable field")
    ap.add_argument("--propose", action="store_true",
                    help="print the proposed table (writes nothing)")
    ap.add_argument("--apply", metavar="CONFIRMED_YAML",
                    help="apply a ratified {name: bool} table")
    ap.add_argument("--apply-proposal", action="store_true",
                    help="apply the mechanical proposal directly (use after review)")
    ap.add_argument("--skills-root", default=None)
    args = ap.parse_args(argv)

    if args.propose:
        import yaml_io
        table = propose(args.skills_root)
        t = sum(1 for v in table.values() if v["injectable"])
        sys.stderr.write("injectable proposal: %d skills — %d true, %d false\n"
                         % (len(table), t, len(table) - t))
        sys.stdout.write(yaml_io.safe_dump(
            {k: v["injectable"] for k, v in table.items()}, sort_keys=False))
        return 0

    if args.apply:
        import yaml_io
        table = yaml_io.safe_load(Path(args.apply).read_text(encoding="utf-8")) or {}
        n = _apply_table({k: bool(v) for k, v in table.items()}, args.skills_root)
        sys.stderr.write("injectable: applied %d field(s)\n" % n)
        return 0

    if args.apply_proposal:
        n = _apply_table(propose(args.skills_root), args.skills_root)
        sys.stderr.write("injectable: applied %d field(s) from the proposal\n" % n)
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
