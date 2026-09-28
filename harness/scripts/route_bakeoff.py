#!/usr/bin/env python3
"""route_bakeoff.py — probe-set structural validator for hs:* skill routing.

The hs:* skill ``description`` strings are the router contract: the text the
UserPromptSubmit / SessionStart surface and ``hs:find-skills``
match a user's intent against. Nothing tests them today — ``check_skill_structure``
only lints shape. This turns them into a cheap regression surface.

HONEST framing (the $0 pass does NOT measure routing): ``score_structural`` fires no
router and scores no over/under-trigger. It parses every ``description`` into a
catalog and checks a human-edited probe-set is internally consistent against it —
every probe targets a skill that exists (or the ``__none__`` sentinel), every
``none`` probe is shaped as one, and no distractor doubles as a probe target. Its CI
value is catching a probe YAML that went stale (target renamed/removed) or
self-contradicts — NOT proving routing works. A green CI check must not be read as
"routing tested".

Real routing rates require firing the router prompt and only run under ``--run-llm``
(opt-in, needs a runner — outside CI). The three axes are reported SEPARATELY so
over-trigger (``none_clean_rate``) is never folded into under-trigger
(``indirect_rate`` / ``context_only_rate``).

Contract (mirrors check_report_language / check_skill_structure):
  - Advisory by default: exits 0, prints a JSON verdict, never mutates.
  - ``--strict`` exits non-zero on a FAIL verdict (a structural config contradiction,
    or — under ``--run-llm`` — a measured rate below its threshold).
  - ``--run-llm`` fires the router to score the 3 rates; without a runner it skips
    clean (exit 0, named), mirroring check_report_language's degrade path.
  - No probe-set at the resolved path => skip clean (exit 0, named).

CLI:
    route_bakeoff.py <skills-root> [--probes PATH] [--strict] [--run-llm]
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from frontmatter_parser import parse_file

# The valid trigger conditions a probe may carry. ``none`` is the over-trigger guard
# (no skill should fire); ``indirect`` / ``context-only`` are under-trigger checks.
_CONDITIONS = {"indirect", "context-only", "none"}
# Sentinel target for a ``none`` probe — no skill in the catalog should win it.
_NONE = "__none__"

# Routing-rate thresholds for --strict under --run-llm. Below these a measured axis
# fails. Tunable knobs; kept here as the single place.
INDIRECT_MIN = 0.70
CONTEXT_ONLY_MIN = 0.70
NONE_CLEAN_MIN = 0.80

# The default probe-set lives next to the other human-edited data, resolved from the
# script location so the CI invocation finds it regardless of cwd.
_DEFAULT_PROBES = Path(__file__).resolve().parent.parent / "data" / "route-probes.yaml"

# Router prompt fired under --run-llm, verbatim discipline from the source bake-off:
# the router auto-activates ONLY on a clear match and must not force one — this is
# what makes the none-clean (over-trigger) axis meaningful.
ROUTER_PROMPT = (
    "You are a skill router. Given the skill catalog (name -> description) and a user "
    "message, return the single skill name that clearly matches, or __none__. A skill "
    "auto-activates ONLY if it clearly matches the user's intent. Do not force a match."
)

# A runner fires the router for one message. It receives the verbatim prompt, the
# message, and the catalog, and returns the chosen skill name or __none__/None. It is
# injected (tests, or a dev wiring a real LLM); there is no built-in LLM client, so a
# real --run-llm without a runner skips clean.
Runner = Callable[[str, str, Dict[str, str]], Optional[str]]


def build_catalog(root) -> Dict[str, str]:
    """Map skill name -> description for every SKILL.md under ``root``.

    Keyed on the frontmatter ``name`` (e.g. ``hs:plan``), falling back to the dir
    name when absent. Parsing goes through frontmatter_parser so a malformed SKILL.md
    is skipped (fail-soft) rather than crashing the sweep.
    """
    root = Path(root)
    catalog: Dict[str, str] = {}
    skill_mds: List[Path] = []
    if (root / "SKILL.md").is_file():
        skill_mds = [root / "SKILL.md"]
    else:
        skill_mds = sorted(root.glob("*/SKILL.md"))
        if not skill_mds:
            # plugins-parent layout: <plugin>/skills/<skill>/SKILL.md — lets one sweep
            # cover every plugin's catalog at once (spine + themed siblings).
            skill_mds = sorted(root.glob("*/skills/*/SKILL.md"))
    for skill_md in skill_mds:
        parsed = parse_file(skill_md)
        fm = parsed.get("frontmatter") or {}
        if not isinstance(fm, dict):
            continue
        name = fm.get("name") or skill_md.parent.name
        catalog[str(name)] = str(fm.get("description") or "")
    return catalog


def load_probes(path) -> Optional[Dict[str, Any]]:
    """Load the human-edited probe-set, or None when the file is absent.

    A None return drives the caller to skip clean — the probe-set is optional and a
    fresh clone may not carry one yet.
    """
    import yaml_io
    p = Path(path)
    if not p.is_file():
        return None
    with open(p, encoding="utf-8") as f:
        data = yaml_io.safe_load(f) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("probes", [])
    data.setdefault("distractors", [])
    return data


def _empty_rates() -> Dict[str, Any]:
    return {"indirect_rate": None, "context_only_rate": None, "none_clean_rate": None}


def _by_condition(probes: List[dict]) -> Dict[str, int]:
    counts = {c: 0 for c in _CONDITIONS}
    for pr in probes:
        cond = str(pr.get("condition", ""))
        if cond in counts:
            counts[cond] += 1
    return counts


def score_structural(catalog: Dict[str, str], probes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate the probe-set against the catalog WITHOUT firing the router.

    Findings (all ``severity: hard`` config contradictions):
      - ``unknown-condition``     — condition not in {indirect, context-only, none}
      - ``probe-target-unknown``  — a non-none probe targets a skill not in the catalog
      - ``none-probe-malformed``  — condition/target disagree on whether it is a none probe
      - ``distractor-is-target``  — a probe target is also listed as a distractor
    """
    probes = probes or {"probes": [], "distractors": []}
    probe_list: List[dict] = probes.get("probes") or []
    distractors = set(probes.get("distractors") or [])
    findings: List[dict] = []

    for i, pr in enumerate(probe_list):
        target = str(pr.get("target", ""))
        cond = str(pr.get("condition", ""))
        where = "probe[%d] (target=%r)" % (i, target)

        if cond not in _CONDITIONS:
            findings.append({"rule": "unknown-condition", "severity": "hard",
                             "detail": "%s has condition %r (want one of %s)"
                                       % (where, cond, sorted(_CONDITIONS))})
            continue

        is_none_target = target == _NONE
        if (cond == "none") != is_none_target:
            findings.append({"rule": "none-probe-malformed", "severity": "hard",
                             "detail": "%s: condition 'none' must pair with target '__none__'"
                                       % where})
            continue

        if not is_none_target:
            if target not in catalog:
                findings.append({"rule": "probe-target-unknown", "severity": "hard",
                                 "detail": "%s targets a skill not in the catalog" % where})
            if target in distractors:
                findings.append({"rule": "distractor-is-target", "severity": "hard",
                                 "detail": "%s targets %r which is also a distractor"
                                           % (where, target)})

    verdict = "FAIL" if findings else "PASS"
    result = {
        "tool": "route_bakeoff",
        "mode": "structural",
        "verdict": verdict,
        "catalog_size": len(catalog),
        "probe_count": len(probe_list),
        "by_condition": _by_condition(probe_list),
        "config_findings": findings,
    }
    result.update(_empty_rates())
    return result


def score_llm(catalog: Dict[str, str], probes: Dict[str, Any], runner: Runner) -> Dict[str, Any]:
    """Fire the router for every probe and score the 3 rates separately.

    Structural validation runs first; a structurally broken probe-set still reports
    its config findings here. Rates are computed only over well-formed probes.
    """
    result = score_structural(catalog, probes)
    result["mode"] = "llm"
    probe_list: List[dict] = (probes or {}).get("probes") or []

    tallies = {"indirect": [0, 0], "context-only": [0, 0], "none": [0, 0]}  # [hit, total]
    for pr in probe_list:
        cond = str(pr.get("condition", ""))
        if cond not in tallies:
            continue
        target = str(pr.get("target", ""))
        message = str(pr.get("message", ""))
        chosen = runner(ROUTER_PROMPT, message, catalog)
        chosen = None if chosen in (None, "", _NONE) else str(chosen)
        tallies[cond][1] += 1
        if cond == "none":
            # Clean when NO real skill fired (over-trigger guard).
            if chosen is None:
                tallies[cond][0] += 1
        else:
            if chosen == target:
                tallies[cond][0] += 1

    def rate(axis):
        hit, tot = tallies[axis]
        return (hit / tot) if tot else None

    result["indirect_rate"] = rate("indirect")
    result["context_only_rate"] = rate("context-only")
    result["none_clean_rate"] = rate("none")

    # A measured axis below its floor turns the verdict FAIL (in addition to any
    # structural finding). Axes with no probes (rate None) are not judged.
    below = []
    for axis, key, floor in (
        ("indirect", "indirect_rate", INDIRECT_MIN),
        ("context-only", "context_only_rate", CONTEXT_ONLY_MIN),
        ("none", "none_clean_rate", NONE_CLEAN_MIN),
    ):
        r = result[key]
        if r is not None and r < floor:
            below.append({"rule": "rate-below-threshold", "severity": "hard",
                          "detail": "%s rate %.2f < %.2f" % (axis, r, floor)})
    if below:
        result["config_findings"] = result["config_findings"] + below
        result["verdict"] = "FAIL"
    return result


def _default_runner() -> Optional[Runner]:
    """No built-in LLM client ships with the harness. A real --run-llm run needs a
    runner wired here (or injected via main(runner=...)); absent one, return None so
    the caller skips clean rather than pretending to measure routing."""
    return None


def main(argv=None, runner: Optional[Runner] = None) -> int:
    ap = argparse.ArgumentParser(description="Probe-set structural validator for skill routing.")
    ap.add_argument("path", help="skills root (a dir holding skill dirs, or one skill dir)")
    ap.add_argument("--probes", default=None,
                    help="probe-set YAML (default: harness/data/route-probes.yaml)")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on a FAIL verdict (config contradiction or low rate)")
    ap.add_argument("--run-llm", action="store_true",
                    help="fire the router to measure the 3 rates (opt-in, needs a runner)")
    args = ap.parse_args(argv)

    probes_path = Path(args.probes) if args.probes else _DEFAULT_PROBES
    probes = load_probes(probes_path)
    if probes is None:
        print(json.dumps({"tool": "route_bakeoff", "verdict": "SKIP",
                          "skipped": "no probe-set at %s — skip" % probes_path},
                         ensure_ascii=False, indent=2))
        # Benign SKIP on the default structural path: no probe-set is configured,
        # so there is nothing to validate -> exit 0. This differs INTENTIONALLY
        # from the --run-llm SKIP below (exit 2): that path was explicitly opted
        # into by the caller and must not be misread as a PASS.
        return 0

    catalog = build_catalog(args.path)

    if args.run_llm:
        run = runner or _default_runner()
        if run is None:
            print(json.dumps({"tool": "route_bakeoff", "verdict": "SKIP",
                              "skipped": "no LLM runner configured — routing rates not measured"},
                             ensure_ascii=False, indent=2))
            return 2  # SKIP != PASS; exit non-zero so CI exit-code checks don't misread
        result = score_llm(catalog, probes, run)
    else:
        result = score_structural(catalog, probes)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if (args.strict and result.get("verdict") == "FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
