#!/usr/bin/env python3
"""Deterministic eval scaffolder — stamp an `evals/` tree into a target repo.

Mechanical only: copy + `${...}` substitute + mkdir. No data pipeline, no LLM —
that judgment work belongs to the skill/model, not this script. `.py`/`.json`
templates are substituted with `string.Template.substitute` (raise-on-missing →
zero unrendered tokens); `.md`/`.yml` templates are copied verbatim (their
single-brace `{...}` markers and shell `$?` are runtime/model fills, and would
otherwise trip Template's parser).

Every judgment value (threshold, production_module, p0_rules, domain_config,
dimensions, primary_dimension, mirror_lang, judge_model/pipeline_model) is a
REQUIRED argument here — this script only VALIDATES it (deterministic: token
shape, range, sum, membership). It never supplies a default; the single
source for each value is the approved strategy card (see
references/protocol.md Phase 2).

Paths resolve off ``__file__`` (never CWD). Refuses to overwrite an existing
`evals/` tree unless ``--force``.
"""

from __future__ import annotations

import argparse
import json
import re
import string
import sys

from pathlib import Path
from typing import Optional


_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "references" / "templates"

STRATEGIES = ("contract", "ground-truth", "judge", "hybrid")

# Strategies whose stamped tree wires an LLM judge in (judge_prompt/judge_runner
# templates) — these are the only ones that REQUIRE judge_model/pipeline_model.
_JUDGE_STRATEGIES = ("judge", "hybrid")

# The two CI forges this scaffolder knows how to stamp a pipeline for. Which
# one applies is an infra-declared value (L1: no default) — same discipline
# as every other judgment field, just not part of build_context/the rendered
# scaffold-var context since no template substitutes ${forge} anywhere; it
# only routes _plan()'s CI-file choice.
_KNOWN_FORGES = ("github", "gitlab")

# Suffixes we substitute; everything else is copied verbatim.
_SUBSTITUTED = (".py", ".json")

# An identifier-ish token: what may safely reach BOTH a filesystem path segment
# AND a Python string literal in the generated code. `domain` and model ids use
# it. Anything outside is a footgun: `/`/`..` escapes the tree, a quote/newline/
# backslash breaks the stamped module's syntax, `%` corrupts a %-format prompt.
# NB: fullmatch (not match) — a trailing `$` in `re.match` also matches just
# before a final newline, so `re.match(..., "cv\n")` would wrongly pass.
_SAFE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# A module PATH additionally allows `/` (it lands only in string-literal
# docstrings / a raise message, never a path segment we write) but still no
# quote/newline/backslash/`..`.
_SAFE_MODULE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


def _validate_token(label: str, value: str) -> None:
    if not isinstance(value, str) or not _SAFE_TOKEN.fullmatch(value):
        raise ValueError(
            "invalid %s %r: use letters/digits and ._- only (no path separators, "
            "quotes, %%, backslash, or whitespace — it reaches both filesystem "
            "paths and generated code)" % (label, value))


def _judgment_error(field: str, why: str) -> ValueError:
    """A judgment-field error: names the field + points at the single source
    of truth (the approved strategy card) — never "add a default", always
    "go get the value the card already committed to"."""
    return ValueError(
        "%s: %s — this is a judgment value that must come from the approved "
        "strategy card (see references/protocol.md Phase 2), never a code "
        "default." % (field, why))


def _validate_out(out: str) -> None:
    """`out` is a RELATIVE subdir under target; reject absolute paths and any
    `..` segment so it can never write outside the target root."""
    p = Path(out)
    if p.is_absolute() or ".." in p.parts or out.strip() in ("", "."):
        raise ValueError(
            "invalid out %r: must be a relative subdir under target with no "
            "'..' segment" % (out,))


def _validate_module_path(value: str) -> None:
    if not isinstance(value, str) or not _SAFE_MODULE.fullmatch(value) or ".." in value:
        raise ValueError(
            "invalid production_module %r: a plain module path only (no quotes, "
            "newlines, backslash, or '..')" % (value,))


def _validate_p0_rules(value: str) -> None:
    # lands in a `# ${p0_rules}` comment + a docstring — a newline would break the
    # comment line and a triple-quote/backslash would corrupt the docstring.
    if not isinstance(value, str) or any(c in value for c in ("\n", "\r", "\\")) or '"""' in value:
        raise ValueError(
            "invalid p0_rules: a single line with no backslash or triple-quote")
    if not value.strip():
        raise _judgment_error("p0_rules", "must be a non-empty one-line string, no placeholder")


def _validate_dimensions(dimensions) -> None:
    """name -> weight (positive int), non-empty, weights sum to exactly 100."""
    if not isinstance(dimensions, dict) or not dimensions:
        raise _judgment_error("dimensions", "must be a non-empty dict of name -> weight (int)")
    total = 0
    for name, weight in dimensions.items():
        _validate_token("dimensions name", name)
        if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
            raise _judgment_error(
                "dimensions", "weight for %r must be a positive int, got %r" % (name, weight))
        total += weight
    if total != 100:
        raise _judgment_error("dimensions", "weights must sum to 100, got %d" % total)


def _validate_domain_config(domain_config) -> None:
    """Exactly {"normalizers": {...}, "masks": {...}} — an explicit empty map is
    a valid (annotated) decision; `None` (absent) is refused."""
    if not isinstance(domain_config, dict) or set(domain_config) != {"normalizers", "masks"}:
        raise _judgment_error(
            "domain_config",
            "must be an explicit dict with exactly keys 'normalizers'/'masks' "
            "(empty maps are OK but must be explicit, not absent/None)")
    for section in ("normalizers", "masks"):
        mapping = domain_config[section]
        if not isinstance(mapping, dict):
            raise _judgment_error("domain_config", "%r must be a dict" % section)
        for key, value in mapping.items():
            _validate_token("domain_config.%s key" % section, key)
            _validate_token("domain_config.%s value" % section, value)


def build_context(domain: str, *, strategy: str, threshold: int, production_module: str,
                  p0_rules: str, domain_config: dict, dimensions: dict, primary_dimension: str,
                  mirror_lang: str, judge_model: Optional[str] = None,
                  pipeline_model: Optional[str] = None, ext: str = "txt",
                  forge: Optional[str] = None) -> dict:
    """Assemble the mechanical scaffold-variable context.

    Every judgment blank is a REQUIRED argument — this function only validates
    (deterministic: token shape, range, sum, membership). It never fills one in;
    the single source of truth for each value is the approved strategy card.

    Cross-module import names are flat bare modules — the stamped tree keeps the
    domain's eval modules as siblings, so `from scorer import score` resolves
    with the eval dir on sys.path.

    `forge` is accepted-and-ignored here: no template substitutes ${forge}, it
    only routes _plan()'s CI-file choice at the scaffold() level. Accepting it
    (as a no-op) lets one shared judgment-args test fixture feed both
    build_context() and scaffold() without per-call filtering.
    """
    _validate_token("domain", domain)
    # mirror_lang picks the mirror lane in _plan() and reaches a filesystem path
    # segment (mirror_contract.json emission) — same footgun as domain.
    _validate_token("mirror_lang", mirror_lang)
    # threshold lands unquoted at `THRESHOLD = ${threshold}` in scorer.py — the one
    # scaffold var in bare-expression position, so a non-int would inject live code.
    # CLI already pins it via argparse type=int; this guards the direct-call path.
    if not isinstance(threshold, int) or isinstance(threshold, bool):
        raise ValueError("threshold must be an int, got %r" % (threshold,))
    if not (0 <= threshold <= 100):
        raise ValueError("threshold must be within 0..100, got %d" % (threshold,))
    _validate_module_path(production_module)
    _validate_p0_rules(p0_rules)
    _validate_domain_config(domain_config)
    _validate_dimensions(dimensions)
    if primary_dimension not in dimensions:
        raise _judgment_error(
            "primary_dimension",
            "%r must be one of dimensions %s" % (primary_dimension, sorted(dimensions)))

    if strategy in _JUDGE_STRATEGIES and (judge_model is None or pipeline_model is None):
        raise _judgment_error(
            "judge_model/pipeline_model",
            "strategy %r requires BOTH judge_model and pipeline_model" % (strategy,))
    if judge_model is not None:
        _validate_token("judge_model", judge_model)
    if pipeline_model is not None:
        _validate_token("pipeline_model", pipeline_model)
    if judge_model is not None and pipeline_model is not None and judge_model == pipeline_model:
        raise ValueError(
            "judge_model and pipeline_model must differ (R8 self-eval guard): both %r"
            % judge_model)

    # json.dumps AFTER every value above is validated — this is the anti-injection
    # chokepoint: the literal lands in a bare-expression template slot later
    # (in scorer.py / judge_prompt.py), so an unvalidated dict here would be a
    # code-injection vector at render time.
    dimensions_json = json.dumps(dimensions, sort_keys=True)
    domain_config_json = json.dumps(domain_config, sort_keys=True)

    return {
        "domain": domain,
        "threshold": str(threshold),
        "production_module": production_module,
        "mirror_lang": mirror_lang,
        "mirror_module": "pipeline_mirror",
        "scorer_module": "scorer",
        "runner_module": "runner",
        "judge_prompt_module": "judge_prompt",
        "judge_runner_module": "judge_runner",
        "judge_model": judge_model,
        "pipeline_model": pipeline_model,
        "p0_rules": p0_rules,
        "ext": ext,
        "dimensions_json": dimensions_json,
        "primary_dimension": primary_dimension,
        "domain_config_json": domain_config_json,
    }


def render_text(text: str, context: dict) -> str:
    """Substitute ${...} tokens. Raises KeyError on any unmapped token."""
    return string.Template(text).substitute(context)


def _ci_entry(forge: str, ci: str) -> tuple:
    """The (template_name, dest_relpath) for the ONE CI file this forge
    stamps — mutually exclusive, never both (a repo has exactly one CI
    provider wired in)."""
    if forge == "github":
        return ("github-actions.yml.tmpl", "%s/production-evals.yml" % ci)
    return ("gitlab-ci.yml.tmpl", "%s/.gitlab-ci-evals.yml" % ci)


def _plan(strategy: str, domain: str, out: str, mirror_lang: str, forge: str) -> list:
    """Return a list of (template_name, dest_relpath) for the strategy.

    `mirror_lang` only affects the ground_truth/judge/hybrid lanes (a
    "contract" tree has no mirror at all, in either lang): `"python"` stamps
    the same pipeline_mirror.py + test_mirror_parity.py as always (regression
    lock — this is the pre-existing behavior, unchanged); any other lang
    stamps `mirror-implementation-guide.md` + `test_mirror_contract.py` in
    their place instead (contract tests run on the FILLED mirror, not
    the skeleton, so they are mutually exclusive with test_mirror_parity.py:
    exactly one of the two is ever stamped per lane). Scoring infra
    (scorer/runner/config_integrity/conformance) stays Python either way —
    only the mirror itself is lang-variable, and writing a non-python
    mirror is a judgment fill (R9), never something this mechanical script
    generates.

    `forge` picks the ONE CI file stamped (github -> production-evals.yml,
    gitlab -> .gitlab-ci-evals.yml) — mutually exclusive, same reasoning as
    mirror_lang: a repo has exactly one CI provider, never both.
    """
    ed = "%s/eval_types/%s" % (out, domain)
    scripts = "%s/scripts" % out
    tests = "%s/tests" % ed
    fixtures = "%s/production_fixtures" % tests
    docs = "%s/docs" % out
    ci = "%s/ci" % out

    contract = [
        ("scorer.py.tmpl", "%s/scorer.py" % ed),
        ("config_integrity.py.tmpl", "%s/config_integrity.py" % ed),
        ("test_scorer.py.tmpl", "%s/test_scorer.py" % tests),
        # every strategy has a scorer -> every strategy gets the conformance
        # guard: scorer's dims/threshold vs the verified card, shape-only.
        ("test_config_conformance.py.tmpl", "%s/test_config_conformance.py" % tests),
        ("ground_truth.json.tmpl", "%s/ground_truth.json" % fixtures),
    ]
    if mirror_lang == "python":
        mirror_entries = [
            ("pipeline_mirror.py.tmpl", "%s/pipeline_mirror.py" % ed),
            ("test_mirror_parity.py.tmpl", "%s/test_mirror_parity.py" % tests),
        ]
    else:
        mirror_entries = [
            ("mirror-implementation-guide.md.tmpl", "%s/mirror-implementation-guide.md" % ed),
            ("test_mirror_contract.py.tmpl", "%s/test_mirror_contract.py" % tests),
        ]
    ground_truth = contract + mirror_entries + [
        ("runner.py.tmpl", "%s/runner.py" % ed),
        ("run_production_evals.py.tmpl", "%s/run_production_evals.py" % scripts),
        ("extract_data_text.py.tmpl", "%s/extract_data_text.py" % scripts),
        ("production-eval-setup.md.tmpl", "%s/production-eval-setup.md" % docs),
        _ci_entry(forge, ci),
    ]
    judge = ground_truth + [
        ("comparison.py.tmpl", "%s/comparison.py" % ed),
        ("thresholds.py.tmpl", "%s/thresholds.py" % ed),
        ("judge_prompt.py.tmpl", "%s/judge_prompt.py" % ed),
        ("judge_runner.py.tmpl", "%s/judge_runner.py" % ed),
        ("judge_rubric.md.tmpl", "%s/judge_rubric.md" % ed),
        ("quality_report.md.tmpl", "%s/quality_report_template.md" % docs),
    ]
    return {"contract": contract, "ground-truth": ground_truth,
            "judge": judge, "hybrid": judge}[strategy]


def _templates_dir(stack: str) -> Path:
    """Resolve a template stack under _TEMPLATES_ROOT.

    `stack` picks WHICH vetted template set to stamp from — it must never let a
    caller read templates from outside the shipped tree (an absolute or `..`
    stack would replace/climb the root and stamp arbitrary, possibly executable
    content into the target). Reject anything that resolves outside the root.
    """
    if Path(stack).is_absolute() or ".." in Path(stack).parts:
        raise ValueError("invalid stack %r: must be a template set name, not a path" % (stack,))
    resolved = (_TEMPLATES_ROOT / stack).resolve()
    root = _TEMPLATES_ROOT.resolve()
    # must name a set STRICTLY under the root — an empty/'.' stack resolves to the
    # root itself and would read <root>/scorer.py.tmpl (an opaque FileNotFound).
    if root not in resolved.parents:
        raise ValueError("invalid stack %r: must name a template set under %s" % (stack, root))
    return _TEMPLATES_ROOT / stack


def _render_all(plan: list, stack: str, context: dict) -> dict:
    """Render every planned template to its final text (in memory, atomic).

    A substituted template with an unmapped ${...} raises here, before any file
    is touched — so a bad template never leaves a half-written tree.
    """
    tdir = _templates_dir(stack)
    rendered = {}
    for tmpl_name, dest in plan:
        src = (tdir / tmpl_name).read_text(encoding="utf-8")
        dest_suffix = Path(dest).suffix
        rendered[dest] = render_text(src, context) if dest_suffix in _SUBSTITUTED else src
    return rendered


def _is_within(path: Path, root: Path) -> bool:
    """True if `path` is `root` itself or nested under it (both resolved)."""
    return path == root or root in path.parents


def _host_repo_root() -> Optional[Path]:
    """The root of the harness host repo that ships this skill, derived from
    __file__ (…/<root>/harness/plugins/hs/skills/eval-bootstrap/scripts/…).
    Require the FULL authoritative sub-path, not a bare `harness/` child — a
    look-alike empty `harness/` dir must not spoof the host-root detection."""
    for anc in Path(__file__).resolve().parents:
        if (anc / "harness" / "plugins" / "hs" / "skills").is_dir():
            return anc
    return None


def is_self_target(target: str) -> bool:
    """True if `target` is (or is inside) the harness/orchestrator repo that
    HOSTS this skill.

    This skill builds evals for OTHER repos; scaffolding into its own host is a
    footgun (a self-grading eval). The fence lives in code, not just prose — the
    scaffolder is the mechanical actor that writes, so the guard belongs here.
    A SUB-FOLDER target (…/orchestrator, …/harness/data) must trip it too, so
    the host-root check is at-or-under, not an exact-root presence gate.
    """
    tp = Path(target).resolve()
    host = _host_repo_root()
    if host is not None and _is_within(tp, host):
        return True
    # A look-alike repo (its own harness tree or orchestrator scorer at the
    # root) is itself a self-grading-eval footgun. Require the FULL
    # authoritative sub-path (mirrors _host_repo_root's own check) — a bare
    # dir named "harness" is a common name in an ordinary user repo and must
    # not false-positive the fence.
    if (tp / "orchestrator" / "critic" / "score.py").exists():
        return True
    if (tp / "harness" / "plugins" / "hs" / "skills").is_dir():
        return True
    return False


def scaffold(target: str, domain: str, strategy: str, forge: str, stack: str = "python",
             out: str = "evals", dry_run: bool = False, print_only: bool = False,
             force: bool = False, **ctx_kwargs) -> list:
    """Stamp the eval tree. Returns the list of destination paths (written or planned)."""
    if strategy not in STRATEGIES:
        raise ValueError("unknown strategy %r (choose from %s)" % (strategy, ", ".join(STRATEGIES)))
    if forge not in _KNOWN_FORGES:
        raise ValueError("unknown forge %r (choose from %s)" % (forge, ", ".join(_KNOWN_FORGES)))
    tdir = _templates_dir(stack)
    if not tdir.is_dir():
        raise ValueError("unknown stack %r: no templates at %s" % (stack, tdir))

    if is_self_target(target):
        raise ValueError(
            "self-target fence: %r is the harness/orchestrator repo that hosts this "
            "skill — refusing to scaffold evals into it. This skill builds evals for "
            "OTHER repos." % target)

    _validate_out(out)
    target_path = Path(target)
    context = build_context(domain, strategy=strategy, **ctx_kwargs)  # validates domain + every judgment field
    out_root = target_path / out
    if out_root.exists() and not force and not (dry_run or print_only):
        raise FileExistsError(
            "refusing to overwrite existing %s (pass force=True / --force to replace)" % out_root)

    plan = _plan(strategy, domain, out, context["mirror_lang"], forge)
    rendered = _render_all(plan, stack, context)

    # Path-escape fence (airtight belt): every dest MUST resolve inside target
    # AND never inside the host repo. is_self_target only inspects `target`, so a
    # high target (e.g. "/") with an --out that descends into the host would slip
    # past it — this per-dest check on the RESOLVED path closes that. Both run
    # before ANY write happens.
    target_resolved = target_path.resolve()
    host = _host_repo_root()
    for dest_rel in rendered:
        dest_resolved = (target_path / dest_rel).resolve()
        if not _is_within(dest_resolved, target_resolved):
            raise ValueError(
                "path-escape fence: %s resolves outside target %s"
                % (dest_rel, target_resolved))
        if host is not None and _is_within(dest_resolved, host):
            raise ValueError(
                "self-target fence: %s lands inside the host repo %s"
                % (dest_rel, host))

    # Write phase is best-effort: a mid-loop I/O failure (disk full, permission,
    # name collision) can leave a partial tree. The render + fence checks above are
    # all-or-nothing; recover a partial write by deleting the out dir and re-running
    # with --force.
    written = []
    for dest_rel, text in rendered.items():
        dest = target_path / dest_rel
        if print_only:
            print("# ---- %s ----" % dest_rel)
            print(text)
            continue
        if dry_run:
            written.append(str(dest))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        written.append(str(dest))
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stamp an evals/ tree into a target repo")
    parser.add_argument("--target", required=True, help="Target repo root")
    parser.add_argument("--domain", required=True, help="Eval domain name (e.g., cv_extraction)")
    parser.add_argument("--strategy", required=True, choices=STRATEGIES)
    parser.add_argument("--forge", required=True, choices=_KNOWN_FORGES,
                        help="CI provider to stamp a pipeline for — a judgment value "
                             "from the approved strategy card, no default")
    parser.add_argument("--stack", default="python", help="Template stack (default: python)")
    # No --out knob: the card reader (eval_config), emit-mirror-contract, and the
    # tier-1 memory dir all resolve the tree at <target>/evals, so a non-default
    # output dir would stamp a scaffold whose own card can never be found. The
    # internal scaffold(out=...) fence stays for programmatic callers.
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--production-module", required=True)
    parser.add_argument("--mirror-lang", required=True,
                        help="Mirror implementation language (e.g. python/node/go) — a "
                             "judgment value from the approved strategy card, no default")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--pipeline-model", default=None)
    parser.add_argument("--p0-rules", required=True)
    parser.add_argument("--dimensions", required=True,
                        help='JSON string: {"name": weight, ...} (weights must sum to 100)')
    parser.add_argument("--primary-dimension", required=True)
    parser.add_argument("--domain-config", required=True,
                        help='JSON string: {"normalizers": {...}, "masks": {...}}')
    parser.add_argument("--dry-run", action="store_true", help="Plan without writing")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="Print rendered files to stdout without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing evals/ tree")
    args = parser.parse_args(argv)

    try:
        dimensions = json.loads(args.dimensions)
    except json.JSONDecodeError as e:
        print("ERROR: invalid --dimensions JSON: %s" % e, file=sys.stderr)
        return 2
    try:
        domain_config = json.loads(args.domain_config)
    except json.JSONDecodeError as e:
        print("ERROR: invalid --domain-config JSON: %s" % e, file=sys.stderr)
        return 2

    try:
        written = scaffold(
            target=args.target, domain=args.domain, strategy=args.strategy, forge=args.forge,
            stack=args.stack, dry_run=args.dry_run, print_only=args.print_only,
            force=args.force, threshold=args.threshold, production_module=args.production_module,
            judge_model=args.judge_model, pipeline_model=args.pipeline_model,
            p0_rules=args.p0_rules, dimensions=dimensions, primary_dimension=args.primary_dimension,
            domain_config=domain_config, mirror_lang=args.mirror_lang)
    except (ValueError, OSError, KeyError) as e:  # OSError incl. FileExistsError; KeyError = unmapped ${token}
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    if not args.print_only:
        verb = "would write" if args.dry_run else "wrote"
        print("%s %d files under %s/evals" % (verb, len(written), args.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
