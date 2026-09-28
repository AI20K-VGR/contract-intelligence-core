#!/usr/bin/env python3
"""scaffold.py — deterministic plan/report skeletons from harness/templates/.

hs:plan and hs:cook expect a fixed plan shape (frontmatter + phases + acceptance
+ rollback) and a fixed report shape. This helper stamps that shape out of the
template files under harness/templates/ so the boilerplate — and especially the
machine-owned provenance frontmatter (harness_version / kit_digest /
schema_version) — is never hand-typed and never stale.

Three pieces, each small and testable:
  - render(template, subs):    {{TOKEN}} substitution, pure text.
  - unfilled_tokens(text):     the {{TOKEN}}s a render left behind (drift catch).
  - scaffold_plan / scaffold_report: build the dir/file, stamp via artifact_stamp.

Containment: a plan/report lands ONLY under <root>/plans/. There is no path
argument to climb out of, and BOTH caller-supplied pieces of the leaf name are
validated before any directory is created — the slug by validate_slug() (a
lowercase kebab token) and the id by validate_ident() (YYMMDD-HHMM). They share
one path component (`plans/<id>-<slug>/`), so validating only one of them
contained nothing: `--id ../../../x` escaped the root while --root was honored.

CLI:
    scaffold.py plan   --slug S --title T [--mode hard|fast] [--no-tdd]
        [--phases a,b,c] [--id YYMMDD-HHMM] [--root .] [--force] [--print]
    scaffold.py report --slug S --type research --title T
        [--id YYMMDD-HHMM] [--root .] [--force] [--print]
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import artifact_stamp  # noqa: E402 — reuse the canonical provenance stamper (DRY)
import harness_release  # noqa: E402

# Templates ship WITH the harness and load beside this script (the engine root),
# never from the output --root: under a global install the project output-root
# carries no harness/templates/ tree ("no per-project tree copy"), so resolving
# templates from --root would raise there. Output still writes under --root.
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_TEMPLATES = ("plan-template.md", "phase-template.md", "report-template.md")
_TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
# Lowercase kebab only: a slug is a single path segment, never a route out.
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# The id shares that segment (`<id>-<slug>`), so it is held to the same
# containment. Shape is the documented YYMMDD-HHMM that _now_id() emits —
# being exact (not merely separator-free) also rejects an id with the slug
# already glued on, which otherwise silently produced `<id>-<slug>-<slug>`.
_IDENT_RE = re.compile(r"^\d{6}-\d{4}$")


def render(template: str, subs: dict) -> str:
    """Replace every ``{{KEY}}`` for which ``subs`` has KEY. Unknown tokens are
    left intact so ``unfilled_tokens`` can flag them — a render never silently
    drops a placeholder it could not fill.

    ONE pass over the template, never over its own output: a substituted value
    that itself reads ``{{OTHER}}`` stays literal. Replacing key-by-key rescans
    what earlier keys already wrote, which made the result depend on dict order
    and let a user-supplied TITLE carrying a token name splice another field's
    value into the title."""
    return _TOKEN_RE.sub(
        lambda m: str(subs[m.group(1)]) if m.group(1) in subs else m.group(0),
        template)


def unfilled_tokens(text: str) -> list:
    """The ``{{TOKEN}}`` names still present, in first-seen order, deduped."""
    seen = []
    for m in _TOKEN_RE.finditer(text):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def validate_slug(slug: str) -> str:
    """Return ``slug`` if it is a lowercase-kebab single segment, else raise.
    The single gate that keeps a write inside plans/."""
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise ValueError(
            "invalid slug %r — use lowercase letters, digits and single dashes "
            "(e.g. 'my-feature'); no slashes, spaces, dots or '..'." % (slug,))
    return slug


def validate_ident(ident: str) -> str:
    """Return ``ident`` if it is a YYMMDD-HHMM stem, else raise. The second
    half of the containment validate_slug() provides for the other half of
    the same path component."""
    if not isinstance(ident, str) or not _IDENT_RE.match(ident):
        raise ValueError(
            "invalid id %r — use YYMMDD-HHMM (e.g. '260618-2251'); the slug is "
            "appended for you, so the dir becomes <id>-<slug> — pass the "
            "timestamp alone, not the slug too." % (ident,))
    return ident


def _read_template(name: str) -> str:
    p = _TEMPLATE_DIR / name
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            "scaffold: template %s missing under %s/ — the templates ship with "
            "the harness; run verify_install." % (name, _TEMPLATE_DIR))


def _release():
    # The provenance stamp identifies the ENGINE that produced the artifact, so
    # read the release beside this script (harness_release defaults to
    # harness_paths.root() = the bin root), matching the canonical stamper
    # (artifact_stamp.read_release(harness_paths.root())). Reading it from the
    # output --root would stamp a bogus 0.0.0-dev + empty digest under a global
    # install, whose project output-root carries no harness/ tree.
    rel = harness_release.read_release()
    return rel.get("harness_version", ""), rel.get("kit_digest", "")


def _stamp(text: str) -> str:
    ver, dig = _release()
    return artifact_stamp.stamp_markdown(text, ver, dig)


# A value landing inside a DOUBLE-QUOTED YAML scalar. Every template writes
# the title as `title: "{{TITLE}}"`, and the value went in raw — so an
# ordinary title like `in "removed #<id>"` closed the scalar early and the
# frontmatter stopped parsing. Everything downstream reads that frontmatter
# (approval, the status flip, the board, the gate's active-plan resolver), so
# the author got a plan that was broken before it could be approved and the
# error surfaced far from its cause. Per-character mapping, so the backslash
# rule cannot be applied twice to an escape this function itself introduced.
_YAML_DQ_ESCAPES = {
    "\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t",
}


def _yaml_dq(value) -> str:
    """Escape `value` for interpolation into a double-quoted YAML scalar."""
    return "".join(_YAML_DQ_ESCAPES.get(ch, ch) for ch in str(value))


def _title_case(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split("-"))


def _plan_author() -> str:
    """The plan's author, stamped into frontmatter `author:` at creation so
    plan_approval._resolve_author finds it and never has to demand --author.

    Uses the same actor resolution the gates use (hook_runtime.resolve_actor —
    HARNESS_USER > git email > $USER), but strips any `/agent:` lane suffix: the
    author is the HUMAN identity, not the agent that ran scaffold. Returns "" if
    unresolved (leaves `author:` empty → plan_approval still demands --author, the
    honest fallback) — never guesses."""
    try:
        hooks = Path(__file__).resolve().parent.parent / "hooks"
        if str(hooks) not in sys.path:
            sys.path.append(str(hooks))
        import hook_runtime
        actor = (hook_runtime.resolve_actor() or "").split("/agent:", 1)[0].strip()
        return actor if actor and actor != "user:unknown" else ""
    except Exception:
        return ""


def _plan_text(root: Path, plan_id: str, slug: str, title: str, mode: str,
               tdd: bool, phases: list, branch: str, created: str,
               defer_suite: bool = False) -> str:
    """The stamped plan.md text for these inputs — shared by the writer
    (scaffold_plan) and the CLI --print path so neither drifts from the other.

    `defer_suite` gets NO `{{...}}` slot in plan-template.md on purpose: the
    key must be COMPLETELY ABSENT from frontmatter when the flag is off, not
    present as `defer_suite: false` — that absence is the back-compat
    invariant `_PINNED_FM_KEYS` depends on (a template placeholder always
    renders something). So the line is spliced in here, post-render,
    only when the flag is on."""
    phases_yaml = "\n".join(
        "  - phases/phase-%d-%s.md" % (i, name)
        for i, name in enumerate(phases, 1))
    phases_table = "\n".join(
        ["| # | Theme | Phụ thuộc | Cỡ |", "|---|---|---|---|"]
        + ["| %d | %s | TBD | TBD |" % (i, _title_case(name))
           for i, name in enumerate(phases, 1)])
    text = render(_read_template("plan-template.md"), {
        "ID": "%s-%s" % (plan_id, slug), "TITLE": _yaml_dq(title),
        "MODE": mode,
        "TDD": "true" if tdd else "false", "BRANCH": branch, "CREATED": created,
        "AUTHOR": _plan_author(),
        "PHASES_YAML": phases_yaml, "PHASES_TABLE": phases_table,
    })
    if defer_suite:
        text = text.replace("decisions: []\n", "decisions: []\ndefer_suite: true\n", 1)
    return _stamp(text)


def _report_text(root: Path, report_id: str, slug: str, rtype: str, title: str,
                 created: str) -> str:
    text = render(_read_template("report-template.md"), {
        "TITLE": _yaml_dq(title), "ID": "%s-%s" % (report_id, slug),
        "TYPE": rtype, "CREATED": created,
    })
    return _stamp(text)


def scaffold_plan(root, plan_id: str, slug: str, title: str, mode: str = "hard",
                  tdd: bool = True, phases=None, branch: str = "TBD",
                  created: str = "TBD", force: bool = False,
                  defer_suite: bool = False) -> Path:
    """Create ``<root>/plans/<plan_id>-<slug>/`` with plan.md + one phase file
    per phase. Returns the plan directory. Refuses to clobber an existing
    plan.md without ``force``."""
    validate_slug(slug)
    validate_ident(plan_id)
    phases = list(phases) if phases else ["main"]
    # Each name becomes phases/phase-N-<name>.md, so it is a path component
    # too. main() already checked these; checking here as well means the
    # library API is contained on its own rather than via its caller.
    for name in phases:
        validate_slug(name)
    root = Path(root)
    plan_dir = root / "plans" / ("%s-%s" % (plan_id, slug))
    plan_md = plan_dir / "plan.md"
    if plan_md.exists() and not force:
        raise FileExistsError(
            "scaffold: %s already exists — pass force=True to overwrite." % plan_md)

    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_md.write_text(
        _plan_text(root, plan_id, slug, title, mode, tdd, phases, branch, created,
                  defer_suite=defer_suite),
        encoding="utf-8")

    # Phase files live under phases/ (subdir), not at the plan-dir root: it keeps
    # the plan dir readable as N phases grow and matches what the gates now hash
    # (plan_approval._plan_files globs phases/phase-*.md). Both the hash glob and
    # the PHASES_YAML frontmatter above point here — keep the three in lockstep.
    phases_dir = plan_dir / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_tpl = _read_template("phase-template.md")
    for i, name in enumerate(phases, 1):
        phase_text = render(phase_tpl, {
            "NUM": str(i), "PHASE_TITLE": _yaml_dq(_title_case(name)),
            "PLAN_ID": "%s-%s" % (plan_id, slug), "CREATED": created,
        })
        (phases_dir / ("phase-%d-%s.md" % (i, name))).write_text(
            _stamp(phase_text), encoding="utf-8")
    return plan_dir


def scaffold_report(root, report_id: str, slug: str, rtype: str, title: str,
                    created: str = "TBD", force: bool = False) -> Path:
    """Create ``<root>/plans/reports/<rtype>-<report_id>-<slug>-report.md``."""
    validate_slug(slug)
    validate_slug(rtype)
    validate_ident(report_id)
    root = Path(root)
    out = (root / "plans" / "reports"
           / ("%s-%s-%s-report.md" % (rtype, report_id, slug)))
    if out.exists() and not force:
        raise FileExistsError(
            "scaffold: %s already exists — pass force=True to overwrite." % out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_report_text(root, report_id, slug, rtype, title, created),
                   encoding="utf-8")
    return out


def _now_id() -> str:
    """YYMMDD-HHMM local — the plan/report id stem. Imported lazily so the pure
    render/scaffold functions stay clock-free and deterministic for tests."""
    from datetime import datetime
    return datetime.now().strftime("%y%m%d-%H%M")


def _today() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Scaffold a plan or report skeleton under plans/.")
    sub = ap.add_subparsers(dest="kind", required=True)

    p = sub.add_parser("plan", help="scaffold a plan dir (plan.md + phases)")
    p.add_argument("--slug", required=True, metavar="KEBAB",
                   help="lowercase-kebab name, no timestamp (e.g. my-feature)")
    p.add_argument("--title", required=True)
    p.add_argument("--mode", default="hard", choices=["hard", "fast"])
    p.add_argument("--no-tdd", dest="tdd", action="store_false")
    p.add_argument("--phases", default="main",
                   help="comma-separated phase names (default: main)")
    p.add_argument("--id", dest="ident", default=None, metavar="YYMMDD-HHMM",
                   help="plan id stem, timestamp only (default: now). The dir "
                        "becomes plans/<id>-<slug>/ — do NOT append the slug.")
    p.add_argument("--branch", default="TBD")
    p.add_argument("--root", default=".")
    p.add_argument("--force", action="store_true")
    p.add_argument("--defer-suite", dest="defer_suite", action="store_true",
                   help="stamp frontmatter defer_suite: true (absent when omitted)")
    p.add_argument("--print", dest="to_stdout", action="store_true",
                   help="print plan.md, write nothing")

    r = sub.add_parser("report", help="scaffold a report file")
    r.add_argument("--slug", required=True)
    r.add_argument("--type", dest="rtype", required=True)
    r.add_argument("--title", required=True)
    r.add_argument("--id", dest="ident", default=None, metavar="YYMMDD-HHMM",
                   help="report id stem, timestamp only (default: now). The file "
                        "becomes <type>-<id>-<slug>-report.md.")
    r.add_argument("--root", default=".")
    r.add_argument("--force", action="store_true")
    r.add_argument("--print", dest="to_stdout", action="store_true")

    args = ap.parse_args(argv)
    ident = args.ident or _now_id()

    try:
        # Before any branch, including --print: the id reaches the rendered
        # ID: field as well as the path, so one check covers both.
        validate_ident(ident)
        if args.kind == "plan":
            phases = [s.strip() for s in args.phases.split(",") if s.strip()]
            for s in phases:
                validate_slug(s)
            if args.to_stdout:
                validate_slug(args.slug)
                sys.stdout.write(_plan_text(
                    Path(args.root), ident, args.slug, args.title, args.mode,
                    args.tdd, phases or ["main"], args.branch, _today(),
                    defer_suite=args.defer_suite))
                return 0
            d = scaffold_plan(
                root=args.root, plan_id=ident, slug=args.slug, title=args.title,
                mode=args.mode, tdd=args.tdd, phases=phases, branch=args.branch,
                created=_today(), force=args.force, defer_suite=args.defer_suite)
            sys.stderr.write("scaffold: wrote %s\n" % d)
            return 0

        # report
        if args.to_stdout:
            validate_slug(args.slug)
            validate_slug(args.rtype)
            sys.stdout.write(_report_text(
                Path(args.root), ident, args.slug, args.rtype, args.title,
                _today()))
            return 0
        out = scaffold_report(
            root=args.root, report_id=ident, slug=args.slug, rtype=args.rtype,
            title=args.title, created=_today(), force=args.force)
        sys.stderr.write("scaffold: wrote %s\n" % out)
        return 0
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        sys.stderr.write("scaffold: %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
