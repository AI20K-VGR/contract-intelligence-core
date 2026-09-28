#!/usr/bin/env python3
"""Compare what a skill's OLD prose named against what its NEW prose still names.

Migrating a skill onto a CLI is supposed to delete prose — that is the point.
What it must not do is drop a REFERENT without saying so. A referent is anything
the prose pointed the model AT: another skill (`hs:foo`), an agent (`@bar`), a
script (`something.py`), a reference drawer (`references/x.md`), a rule
(`harness/rules/y.md`). Prose can be rewritten freely; a referent going missing
is a route the model will never take again, and it fails silently — cleaner
file, green tests, passing structure gate, absent constraint.

Measured on this repo, comparing the live spine skills against their rewritten
prototypes: 24 of 29 scripts and 14 of 18 skill routes absent on one pair, 31 of
34 and 18 of 20 on the other. Two of those had been caught by hand and filed as
backlog entries. Two out of thirty-two is the detection rate this replaces.

TWO MODES, and the split is the design:

  report  — print every absence with the file:line and the line's text, so the
            reviewer can judge it without re-reading the old skill.
  check   — exit non-zero while any absence lacks a written reason.

A reason is prose a human wrote and another human can disagree with. The tool
never decides whether an absence is acceptable; it only refuses to let one pass
unnoticed. A blank reason is not a reason (that would measure typing), and a
waiver naming a referent that is still present is reported as stale (a waiver
that outlives its absence pre-excuses the NEXT one).

Usage:
  skill_migration_parity.py report --old DIR --new DIR [--json]
  skill_migration_parity.py check  --old DIR --new DIR --waivers FILE.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml_io  # noqa: E402

EXIT_OK = 0
EXIT_GAPS = 1
EXIT_USAGE = 2

# What counts as a referent. Each pattern captures the referent EXACTLY as prose
# writes it, so a waiver key is copy-pasteable from the report.
#
# `script.py` is matched on its BASENAME: the same script is cited as
# `harness/scripts/x.py`, `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/x.py`, and
# bare `x.py` across the tree, and treating those as three different referents
# would report a kept script as dropped.
_PATTERNS = (
    ("skill", re.compile(r"\bhs:[a-z][a-z0-9-]*")),
    ("agent", re.compile(r"@[a-z][a-z0-9-]+")),
    ("rule", re.compile(r"harness/rules/[A-Za-z0-9._-]+\.md")),
    ("reference", re.compile(r"references/[A-Za-z0-9._-]+\.md")),
    ("script", re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_-]+\.py)\b")),
)

# Referents that are noise rather than routes. `hs-run` is the CLI this whole
# migration moves TO, so its own name showing up as a "dropped skill" would
# invert the report's meaning.
_IGNORE = frozenset({"hs:run", "hs-run"})


_AGENT_NAMES: set = set()


def load_agent_names(agents_dir) -> set:
    """The agents that exist on disk, by bare name (`tester`, `code-reviewer`).

    Needed because ONE agent is written two ways: prose says `@tester`, code says
    `subagent_type="hs:tester"`. Without this the tool reports the same agent as
    dropped while it sits in the verb's role table — measured on cook: four such
    phantom absences.

    The collapse is restricted to names that really are agents. `hs:cook` is a
    skill; if every `hs:x`/`@x` pair merged blindly, an unrelated `@cook` mention
    could silently 'cover' a genuinely dropped `hs:cook` handoff."""
    d = Path(agents_dir) if agents_dir else None
    if not d or not d.is_dir():
        return set()
    return {f.stem for f in d.glob("*.md")}


def _norm(kind: str, raw: str) -> str:
    """A referent's canonical form.

    `script` collapses to its basename (the same script is cited bare, with a
    `harness/scripts/` prefix, and with a `${HARNESS_BIN_ROOT}` prefix). An agent
    collapses across its two spellings — but only when it IS an agent on disk."""
    if kind == "script":
        return raw.rsplit("/", 1)[-1]
    bare = raw[1:] if raw.startswith("@") else raw[3:] if raw.startswith("hs:") else None
    if bare and bare in _AGENT_NAMES:
        return "@" + bare
    return raw


def _own_name(root: Path):
    """The `name:` a skill declares for itself, e.g. `hs:plan`.

    A skill naming ITSELF is not a route — it is the file's own label, and the
    rename that a migration performs (`hs:plan` -> `hs:plan-ng`) would otherwise
    report the skill's own name as a dropped referent on every single run. That
    one guaranteed false positive at the top of every report is exactly the kind
    of noise that teaches a reviewer to skim.

    Note this drops ONLY the skill's own name. A SIBLING's name (`hs:cook` cited
    from `hs:plan`) stays in scope: that is a real handoff route, and it going
    missing is a real finding."""
    skill = root / "SKILL.md"
    if not skill.is_file():
        return None
    for line in skill.read_text(encoding="utf-8").splitlines()[:20]:
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None


def harvest(root: Path, drop_self: bool = True) -> dict:
    """{referent: {"kind","file","line","context"}} for one skill directory.

    First sighting wins: the report needs ONE place to point the reviewer at,
    and the first mention is where the prose introduces the route."""
    found = {}
    own = _own_name(root) if drop_self else None
    for f in sorted(root.rglob("*.md")):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for kind, pat in _PATTERNS:
                for m in pat.finditer(line):
                    raw = m.group(1) if pat.groups else m.group(0)
                    ref = _norm(kind, raw)
                    if ref in _IGNORE or ref in found or ref == own:
                        continue
                    found[ref] = {"kind": kind, "file": str(f), "line": n,
                                  "context": line.strip()}
    return found


def emitted(paths) -> set:
    """Every referent the CLI modules themselves name.

    This is the second half of parity, and without it the tool argues against
    the migration it exists to check. When a skill stops naming `hs:tester` in
    prose because `hs-run cook next` now hands that role over at the right
    moment, the route did not disappear — it moved from something the model must
    remember into something a verb states. A prose-vs-prose diff cannot tell
    those apart and calls both a loss.

    Measured: `hs_run_cook.py` emits `hs:code-reviewer`, `hs:tester`,
    `hs:docs-manager` and `hs:git-manager` (its `_ROLES` table plus the
    `next_action` sentences). A prose-only run reported all four as dropped —
    a false alarm about the most safety-relevant part of the handoff.

    The whole module source is scanned, not just a role table: a referent named
    in a `next_action` string reaches the model just as surely as one in a dict."""
    out = set()
    for p in paths or ():
        src = Path(p).read_text(encoding="utf-8")
        for kind, pat in _PATTERNS:
            for m in pat.finditer(src):
                out.add(_norm(kind, m.group(1) if pat.groups else m.group(0)))
    return out


def absences(old_dir: Path, new_dir: Path, emits=None) -> list:
    old, new = harvest(old_dir), harvest(new_dir)
    covered = set(new) | emitted(emits)
    out = []
    for ref, meta in sorted(old.items()):
        if ref not in covered:
            out.append({"referent": ref, **meta})
    return out


def _reason_of(value) -> str:
    """A waiver entry is either the reason itself or a record holding it.

    Both spellings stay legal because they answer different needs. A one-off
    `--waivers` file passed on a command line wants the short form; the shipped
    ledger wants `covered_by:` beside the reason, since a paragraph asserting the
    CLI handles a case is the shape of every claim that turned out wrong when
    someone finally ran it."""
    if isinstance(value, dict):
        return str(value.get("reason") or "")
    return "" if value is None else str(value)


def load_waiver_records(path: Path):
    """[(skill, referent, {reason, covered_by}), ...] from a per-skill ledger.

    The shipped ledger nests entries under a skill key; `_load_waivers` reads a
    top-level `waived:`. Measured on the shipped file, that mismatch made the
    loader return ZERO waivers — so the one absence the ledger documents would
    have been reported UNEXPLAINED by the exact tool it exists to satisfy. Both
    shapes load now, and this is the accessor that keeps the skill scope."""
    data = yaml_io.yaml_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for skill, block in data.items():
        if skill == "waived" or not isinstance(block, dict):
            continue
        for referent, value in (block.get("waived") or {}).items():
            rec = dict(value) if isinstance(value, dict) else {"reason": str(value or "")}
            rec.setdefault("reason", "")
            rec.setdefault("covered_by", "")
            out.append((str(skill), str(referent), rec))
    return out


def _load_waivers(path: Path, skill: Optional[str] = None) -> dict:
    """{referent: reason}. A top-level `waived:` is the flat form; anything else is
    read as per-skill sections, narrowed by `skill` when one is named."""
    data = yaml_io.yaml_load(path.read_text(encoding="utf-8")) or {}
    if "waived" in data:
        w = data.get("waived") or {}
        if not isinstance(w, dict):
            raise SystemExit("%s: `waived:` must be a mapping of referent -> reason" % path)
        return {str(k): _reason_of(v) for k, v in w.items()}
    return {ref: rec["reason"] for sk, ref, rec in load_waiver_records(path)
            if skill is None or sk == skill}


def _report(args) -> int:
    gaps = absences(Path(args.old), Path(args.new), args.emits)
    if args.json:
        print(json.dumps({"absent": gaps}, indent=1, ensure_ascii=False))
        return EXIT_OK
    if not gaps:
        print("parity: no referent dropped")
        return EXIT_OK
    print("parity: %d referent(s) named by the old prose and not by the new one\n" % len(gaps))
    for kind in ("skill", "agent", "script", "reference", "rule"):
        rows = [g for g in gaps if g["kind"] == kind]
        if not rows:
            continue
        print("  %s (%d)" % (kind, len(rows)))
        for g in rows:
            print("    %-42s %s:%d" % (g["referent"], g["file"], g["line"]))
            print("        %s" % g["context"][:150])
        print()
    return EXIT_OK


def _check(args) -> int:
    gaps = absences(Path(args.old), Path(args.new), args.emits)
    waived = _load_waivers(Path(args.waivers))
    gap_names = {g["referent"] for g in gaps}

    unexplained = [g for g in gaps if not waived.get(g["referent"], "").strip()]
    stale = sorted(set(waived) - gap_names)

    for g in unexplained:
        print("UNEXPLAINED  %-40s %s:%d" % (g["referent"], g["file"], g["line"]))
        print("             %s" % g["context"][:150])
    for s in stale:
        print("STALE WAIVER %-40s (still present in the new prose — a waiver that "
              "outlives its absence pre-excuses the next one)" % s)

    if unexplained or stale:
        print("\nparity check FAILED: %d unexplained, %d stale"
              % (len(unexplained), len(stale)))
        return EXIT_GAPS
    print("parity check OK: %d absence(s), every one with a written reason" % len(gaps))
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("report", "check"):
        s = sub.add_parser(name)
        s.add_argument("--old", required=True)
        s.add_argument("--new", required=True)
        s.add_argument("--agents", metavar="DIR",
                       help="the agents/ directory. Lets `@x` and `hs:x` collapse "
                            "to one referent when x is really an agent — prose "
                            "writes the first form, code the second.")
        s.add_argument("--emits", action="append", metavar="FILE",
                       help="a CLI module whose own source names referents the "
                            "prose no longer has to (repeatable). A referent it "
                            "emits has MOVED into the tool, not vanished.")
        if name == "report":
            s.add_argument("--json", action="store_true")
        else:
            s.add_argument("--waivers", required=True)
    args = ap.parse_args(argv)
    # Populated before any harvest: _norm() consults it while scanning.
    global _AGENT_NAMES
    _AGENT_NAMES = load_agent_names(getattr(args, "agents", None))
    for d in (args.old, args.new):
        if not Path(d).is_dir():
            print("not a directory: %s" % d, file=sys.stderr)
            return EXIT_USAGE
    return _report(args) if args.cmd == "report" else _check(args)


if __name__ == "__main__":
    sys.exit(main())
