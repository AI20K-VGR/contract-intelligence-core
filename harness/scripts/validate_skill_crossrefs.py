#!/usr/bin/env python3
"""
Validate skill cross-references and workflow-chain integrity.

Scans SKILL.md bodies across all harness plugin dirs for /hs: and
/hs-<group>: references, builds a directed graph, checks expected SDLC
workflow chains, and reports orphans / hubs / broken refs.

Usage:
  python3 validate_skill_crossrefs.py <plugins-root>          # audit mode
  python3 validate_skill_crossrefs.py <plugins-root> --json   # JSON output
  python3 validate_skill_crossrefs.py --self-test             # run self-tests
"""
from __future__ import annotations

from collections.abc import Set as AbstractSet
import json
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

try:
    import yaml_io as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# Optional: UTF-8 console normalisation (degrades silently if absent)
try:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from encoding_utils import configure_utf8_console
    configure_utf8_console()
except Exception:
    pass

# ── Constants ────────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

# Match hs:<skill> and hs-<group>:<skill> — the full qualified name is captured.
# The slash-command slash is OPTIONAL: routes are written both as `/hs:cook`
# (invocation) and bare `hs:cook` (prose/backtick handoff), and the audit must
# see both. The lookbehind keeps `hs:` from matching mid-identifier.
# Examples: /hs:cook  `hs:code-review`  hs:remember
SKILL_REF_RE = re.compile(r"(?<![\w-])/?(hs(?:-[a-z0-9]+)?:[a-z0-9][\w-]*)")

# Agent references in prose use the `@name` convention (e.g. @code-reviewer) — distinct
# from skill routes (`hs:name`) and from workflow names (`hs:name` registered under a
# plugin's workflows/ dir). An @-ref resolves against the agent registry, not the skills.
# The trailing lookahead `(?![\w/-])` rejects npm scopes (`@better-auth/cli`) and mixed-case
# element tags (`@eN`); AT_KEYWORDS below filters CSS/doc at-words (`@theme`, `@generated`).
AGENT_REF_RE = re.compile(r"(?<![\w./-])@([a-z][a-z0-9-]*)(?![\w/-])")

# `@word` at-keywords that are NOT agent references (CSS at-rules, doc/codegen markers).
# An @-ref matching one of these is ignored rather than reported as a dangling agent.
AT_KEYWORDS = frozenset({
    "media", "import", "theme", "keyframes", "supports", "font-face", "charset",
    "namespace", "page", "layer", "container", "property", "scope",
    "generated", "param", "params", "returns", "throws", "deprecated", "override",
    "example", "see", "todo", "link", "type", "typedef", "default",
})

# Rule-layer references cite a `harness/rules/<name>.md` path. CS-10 (K4)
# extends this module's skill/agent graph to the rule layer: broken refs
# (cited but the file does not exist) and orphan rules (exist, cited nowhere).
RULE_REF_RE = re.compile(r"harness/rules/[a-z0-9_-]+\.md")

# Bare (no `harness/rules/` prefix) backtick-wrapped rule-name mentions, e.g.
# CLAUDE.md's routing index (`disabled-group-handling`, `primary-workflow`).
# K10 (red-team B1, PROVEN): the 3 always-load rules route through CLAUDE.md
# prose as a bare name, never a full path, so RULE_REF_RE alone misses them.
_CLAUDE_MD_BARE_NAME_RE = re.compile(r"`([a-z][a-z0-9_-]*)`")

SKIP_DIRS = frozenset({"_shared", "template-skill", "__pycache__",
                        "node_modules", ".venv"})

# Expected SDLC workflow chains.  Each consecutive pair must have an edge
# (in either direction) somewhere across the skill graph.
# Advisory only — a missing edge is reported but does not crash the tool.
EXPECTED_CHAINS = {
    "development":   ["hs:plan", "hs:cook", "hs:code-review", "hs:ship"],
    "bugfix":        ["hs:scout", "hs:debug", "hs:fix", "hs:code-review"],
    "investigation": ["hs:scout", "hs:debug", "hs:brainstorm"],
}


# ── Frontmatter parsing ──────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    """Extract frontmatter dict from SKILL.md content."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}
    raw = m.group(1)
    if _HAS_YAML:
        try:
            return _yaml.safe_load(raw) or {}
        except Exception:
            return {}
    # Minimal fallback: extract name only
    nm = re.search(r"^name:\s*[\"']?(.+?)[\"']?\s*$", raw, re.M)
    return {"name": nm.group(1).strip() if nm else ""}


# ── Ref extraction ───────────────────────────────────────────────────────────

def _extract_body_refs(content: str, own_name: str) -> set[str]:
    """Extract qualified skill references from body text, excluding code fences.

    Returns a set of strings like 'hs:cook' or 'hs:brainstorm'.
    The skill's own name is excluded (no self-edges).
    """
    m = FRONTMATTER_RE.match(content)
    body = content[m.end():] if m else content
    # Strip code fences before matching to avoid false positives
    body = CODE_FENCE_RE.sub("", body)
    refs = set(SKILL_REF_RE.findall(body))
    refs.discard(own_name)
    return refs


def _extract_agent_refs(content: str) -> set[str]:
    """Extract `@agent` references from body text, excluding code fences.

    Returns bare agent names (no `@`), e.g. {'code-reviewer', 'researcher'}.
    """
    m = FRONTMATTER_RE.match(content)
    body = content[m.end():] if m else content
    body = CODE_FENCE_RE.sub("", body)
    return set(AGENT_REF_RE.findall(body))


def extract_rule_refs(skill_body: str) -> set:
    """Rule-file references (`harness/rules/<name>.md`) cited in an ALREADY
    frontmatter-stripped body, with code-fenced regions stripped first so a
    route-line inside a code example never counts as a real citation.

    Canonical owner (K11, red-team M2 PROVEN): `harness/tests/_rule_ref_util.py`
    re-exports this exact function so F3 (route-existence) and CS-10 (this
    module's rule broken/orphan check, below) share one extractor and never
    drift into two that disagree on a fenced route-line.
    """
    stripped = CODE_FENCE_RE.sub("", skill_body)
    return set(RULE_REF_RE.findall(stripped))


def _extract_body_rule_refs(content: str) -> set[str]:
    """Rule refs cited in a raw SKILL.md file's content (frontmatter stripped
    first, then delegates to `extract_rule_refs` for the fence strip)."""
    m = FRONTMATTER_RE.match(content)
    body = content[m.end():] if m else content
    return extract_rule_refs(body)


def collect_agent_names(plugins_root: Path) -> set:
    """Bare agent names from every plugin's agents/ dir (filename stem)."""
    names = set()
    for plugin_dir in plugins_root.iterdir():
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        adir = plugin_dir / "agents"
        if adir.is_dir():
            names.update(f.stem for f in adir.glob("*.md"))
    return names


def collect_workflow_names(plugins_root: Path) -> set:
    """Qualified workflow names `<plugin>:<stem>` from every plugin's workflows/ dir."""
    names = set()
    for plugin_dir in plugins_root.iterdir():
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        wdir = plugin_dir / "workflows"
        if wdir.is_dir():
            names.update(f"{plugin_dir.name}:{f.stem}" for f in wdir.glob("*.js"))
    return names


def collect_rule_names(repo_root: Path) -> set:
    """Ref-form strings (`harness/rules/<name>.md`) for every rule file that
    exists on disk — parallel to `collect_agent_names`/`collect_workflow_names`,
    the CS-10 (K4) registry of "real" rule refs a citation is checked against."""
    rules_dir = Path(repo_root) / "harness" / "rules"
    if not rules_dir.is_dir():
        return set()
    return {f"harness/rules/{f.name}" for f in rules_dir.glob("*.md")}


def collect_claude_md_rule_refs(repo_root: Path) -> set:
    """Ref-form strings for rule names mentioned bare (backtick-wrapped, no
    `harness/rules/` prefix) in the repo-root CLAUDE.md.

    K10 (red-team B1, PROVEN): a rule is "routed" (not orphan) when it is
    cited in a SKILL.md body **or** named here — the 3 always-load rules
    (`disabled-group-handling`/`primary-workflow`/`skill-routing`) route
    through CLAUDE.md's routing-index prose as a bare name and have zero
    SKILL.md-body citations."""
    claude_md = Path(repo_root) / "CLAUDE.md"
    if not claude_md.is_file():
        return set()
    try:
        content = claude_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    content = CODE_FENCE_RE.sub("", content)
    stems = set(_CLAUDE_MD_BARE_NAME_RE.findall(content))
    return {f"harness/rules/{s}.md" for s in stems}


# ── Scanning ─────────────────────────────────────────────────────────────────

def scan_all_skills(plugins_root: Path) -> dict[str, dict]:
    """Walk all plugin dirs under plugins_root and collect skill metadata.

    Returns a dict keyed by the skill's qualified name (from the name: field),
    e.g. ``{"hs:cook": {"name": "hs:cook", "body_refs": {...}, ...}}``.

    Plugin layout expected:
        <plugins_root>/<plugin>/skills/<skill-dir>/SKILL.md
    """
    skills: dict[str, dict] = {}

    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        skills_dir = plugin_dir / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if skill_dir.name in SKIP_DIRS or skill_dir.name.startswith("."):
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _parse_frontmatter(content)
            name = (fm.get("name") or "").strip()
            if not name:
                # Fall back to plugin:dir-name form
                name = f"{plugin_dir.name}:{skill_dir.name}"
            body_refs = _extract_body_refs(content, name)
            agent_refs = _extract_agent_refs(content)
            rule_refs = _extract_body_rule_refs(content)
            requires = fm.get("requires") or []
            related = fm.get("related") or []
            if isinstance(requires, str):
                requires = [requires]
            if isinstance(related, str):
                related = [related]
            skills[name] = {
                "name": name,
                "body_refs": body_refs,
                "agent_refs": agent_refs,
                "rule_refs": rule_refs,
                "requires": requires,
                "related": related,
                "path": str(skill_file),
            }

    return skills


# ── Graph analysis ───────────────────────────────────────────────────────────

def build_reference_graph(skills: dict[str, dict],
                          known_agents: AbstractSet = frozenset(),
                          known_workflows: AbstractSet = frozenset()) -> dict:
    """Build directed graph from skill cross-references.

    `known_agents` (bare names) validate `@agent` refs; `known_workflows`
    (`plugin:stem`) whitelist workflow-name `hs:` refs so a legitimate
    Workflow({name:"hs:base-..."}) call is not reported as a broken skill ref.

    Returns a dict with keys:
        edges      — {src_name: [dst_name, ...]}
        orphans    — [name, ...] (no inbound AND no outbound edges)
        hubs       — [(name, in_degree), ...] sorted descending
        broken     — [(src_name, ref), ...] ref is not a known skill name
        in_degree  — {name: count}
        out_degree — {name: count}
    """
    all_names = set(skills.keys())
    edges: dict[str, set] = defaultdict(set)
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)

    for name, data in skills.items():
        for ref in data["body_refs"]:
            if ref in all_names and ref != name:
                edges[name].add(ref)
                out_degree[name] += 1
                in_degree[ref] += 1

    # Orphans: no inbound AND no outbound
    orphans = [n for n in all_names if in_degree[n] == 0 and out_degree[n] == 0]

    # Hubs: in_degree >= 3
    hubs = [(n, in_degree[n]) for n in all_names if in_degree[n] >= 3]
    hubs.sort(key=lambda x: -x[1])

    # Broken: references that point to an unknown skill name
    broken = []
    for name, data in skills.items():
        for ref in data["body_refs"]:
            if ref not in all_names and ref not in known_workflows:
                broken.append((name, ref))
        for agent in data.get("agent_refs", ()):
            if agent not in known_agents and agent not in AT_KEYWORDS:
                broken.append((name, "@" + agent))

    return {
        "edges": {k: sorted(v) for k, v in edges.items()},
        "orphans": sorted(orphans),
        "hubs": hubs,
        "broken": broken,
        "in_degree": dict(in_degree),
        "out_degree": dict(out_degree),
    }


def collect_registry_routed_rules(repo_root: Path) -> set:
    """Ref-form strings for rules the CLI hands a skill at a step.

    The third routing channel, and the SSOT one: `rules:` lists under
    `step_routing.<domain>.always` and `.states.*` in hs-run-registry.d/*.yaml.
    A rule routed only there carries no SKILL.md citation and no CLAUDE.md
    mention, so a reachability check blind to this channel calls it an orphan —
    which is what happened to all seven of them, silently, at exit 0.
    """
    import glob as _glob
    out: set = set()
    try:
        from yaml_io import yaml_load
    except ImportError:
        return out
    pattern = str(Path(repo_root) / "harness/data/hs-run-registry.d/*.yaml")
    for path in sorted(_glob.glob(pattern)):
        try:
            doc = yaml_load(Path(path)) or {}
        except Exception:  # noqa: BLE001 — a bad fragment must not blind the rest
            continue
        for blk in (doc.get("step_routing") or {}).values():
            if not isinstance(blk, dict):
                continue
            entries = [blk.get("always") or {}]
            entries += list((blk.get("states") or {}).values())
            for entry in entries:
                if isinstance(entry, dict):
                    for stem in entry.get("rules") or ():
                        out.add("harness/rules/%s.md" % stem)
    return out


def check_rule_references(skills: dict, known_rules: set,
                          claude_md_routed: AbstractSet = frozenset(),
                          registry_routed: AbstractSet = frozenset()) -> dict:
    """Rule-layer referential integrity (CS-10, K4): broken `harness/rules/*.md`
    refs cited from any SKILL.md body, and rules that exist on disk but nothing
    routes to. "Routed" = cited in a SKILL.md body, named bare in CLAUDE.md
    (K10), **or** handed over at a step by the CLI — see
    `collect_claude_md_rule_refs` and `collect_registry_routed_rules`.

    Returns a dict with keys:
        broken_rules — [(skill_name, ref), ...] ref not in known_rules
        orphan_rules — [ref, ...] a known rule cited by nobody
        cited_rules  — {ref: [citing skill names]}
    """
    cited: dict[str, set] = defaultdict(set)
    broken = []
    for name, data in skills.items():
        for ref in data.get("rule_refs", ()):
            cited[ref].add(name)
            if ref not in known_rules:
                broken.append((name, ref))
    routed = set(cited.keys()) | set(claude_md_routed) | set(registry_routed)
    orphan_rules = sorted(r for r in known_rules if r not in routed)
    return {
        "broken_rules": broken,
        "orphan_rules": orphan_rules,
        "cited_rules": {k: sorted(v) for k, v in cited.items()},
    }


def check_expected_workflows(graph: dict) -> list[dict]:
    """Check SDLC workflow chains for missing consecutive edges.

    An edge is considered present if either direction (a->b or b->a) exists.
    Returns a list of missing-edge dicts: {"chain": ..., "from": ..., "to": ...}.
    Advisory only — callers decide how to surface the result.
    """
    edges = graph["edges"]
    missing = []
    for chain_name, chain in EXPECTED_CHAINS.items():
        for i in range(len(chain) - 1):
            src, dst = chain[i], chain[i + 1]
            fwd = dst in edges.get(src, set())
            rev = src in edges.get(dst, set())
            if not fwd and not rev:
                missing.append({"chain": chain_name, "from": src, "to": dst})
    return missing


# ── Output ───────────────────────────────────────────────────────────────────

def print_report(skills: dict, graph: dict, missing: list[dict],
                 rule_check: dict | None = None) -> None:
    """Print human-readable audit report to stdout."""
    print(f"\n=== Skill Cross-Reference Audit ===")
    print(f"Total skills scanned: {len(skills)}")
    print(f"Skills with outward refs: {len(graph['edges'])}")
    print(f"Orphaned skills: {len(graph['orphans'])}")
    print(f"Hub skills: {len(graph['hubs'])}")
    print(f"Broken references: {len(graph['broken'])}")
    print(f"Missing workflow edges: {len(missing)}")
    if rule_check is not None:
        print(f"Broken rule references: {len(rule_check['broken_rules'])}")
        print(f"Orphan rules: {len(rule_check['orphan_rules'])}")

    if graph["hubs"]:
        print("\n--- Hub Skills (in_degree >= 3) ---")
        for name, count in graph["hubs"]:
            print(f"  {name}: {count} inbound refs")

    if missing:
        print("\n--- Missing Workflow Edges ---")
        for m in missing:
            print(f"  [{m['chain']}] {m['from']} -> {m['to']}")

    if graph["broken"]:
        print("\n--- Broken References ---")
        for src, ref in graph["broken"]:
            print(f"  {src} -> /{ref} (not found)")

    if graph["orphans"]:
        print(f"\n--- Orphaned Skills ({len(graph['orphans'])}) ---")
        for name in graph["orphans"]:
            print(f"  {name}")

    if rule_check is not None and rule_check["broken_rules"]:
        print(f"\n--- Broken Rule References ---")
        for src, ref in rule_check["broken_rules"]:
            print(f"  {src} -> {ref} (not found)")

    if rule_check is not None and rule_check["orphan_rules"]:
        print(f"\n--- Orphan Rules ({len(rule_check['orphan_rules'])}) ---")
        for ref in rule_check["orphan_rules"]:
            print(f"  {ref}")


# ── Self-tests ───────────────────────────────────────────────────────────────

def _run_self_tests() -> bool:
    """Run inline self-tests with temporary SKILL.md fixtures.

    Returns True if all tests pass.
    """
    passed = 0
    failed = 0

    def _assert(cond: bool, label: str) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [OK] {label}")
        else:
            failed += 1
            print(f"  [X]  {label}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        def _write(plugin: str, skill_dir: str, name: str, body: str) -> None:
            d = base / plugin / "skills" / skill_dir
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: test\nuser-invocable: true\n---\n\n{body}",
                encoding="utf-8",
            )

        _write("hs", "plan", "hs:plan",
               "After deciding, run /hs:cook to implement.\n")
        _write("hs", "cook", "hs:cook",
               "Call /hs:brainstorm for ideas then /hs:code-review.\n")
        _write("hs-think", "brainstorm", "hs:brainstorm",
               "Ideation only.\n```\n/hs:plan should not match\n```\n")
        _write("hs", "orphan", "hs:orphan",
               "Standalone skill.\n")
        _write("hs", "broken", "hs:broken",
               "See /hs-x:ghost for help.\nAlso /hs:cook is good.\n")
        _write("hs", "agentuser", "hs:agentuser",
               "Delegate to @code-reviewer, but @ghost-agent does not exist.\n"
               "Run Workflow({name:'hs:base-fanout-consolidate'}).\n")
        # agent + workflow registry fixtures
        (base / "hs" / "agents").mkdir(parents=True, exist_ok=True)
        (base / "hs" / "agents" / "code-reviewer.md").write_text(
            "---\nname: code-reviewer\n---\n", encoding="utf-8")
        (base / "hs" / "workflows").mkdir(parents=True, exist_ok=True)
        (base / "hs" / "workflows" / "base-fanout-consolidate.js").write_text(
            "// workflow\n", encoding="utf-8")

        skills = scan_all_skills(base)
        known_agents = collect_agent_names(base)
        known_workflows = collect_workflow_names(base)
        graph = build_reference_graph(skills, known_agents, known_workflows)

        print("Self-tests:")

        # T1: Spine ref /hs:cook detected in plan body
        plan_refs = skills.get("hs:plan", {}).get("body_refs", set())
        _assert("hs:cook" in plan_refs, "T1: /hs:cook ref detected in plan body")

        # T2: Namespaced ref /hs:brainstorm detected in cook body
        cook_refs = skills.get("hs:cook", {}).get("body_refs", set())
        _assert("hs:brainstorm" in cook_refs,
                "T2: /hs:brainstorm ref detected in cook body")

        # T3: Orphan has no in/out edges
        _assert("hs:orphan" in graph["orphans"], "T3: Orphan detection")

        # T4: hs:cook is referenced by plan and broken -> in_degree >= 2
        cook_in = graph["in_degree"].get("hs:cook", 0)
        _assert(cook_in >= 2, f"T4: Hub-like (hs:cook in_degree={cook_in})")

        # T5: Missing chain edges exist (development chain incomplete)
        missing = check_expected_workflows(graph)
        _assert(len(missing) > 0, "T5: Missing chain edges detected")

        # T6: Broken reference /hs-x:ghost detected
        broken_refs = [ref for _, ref in graph["broken"]]
        _assert("hs-x:ghost" in broken_refs, "T6: Broken ref /hs-x:ghost detected")

        # T7: Self-reference excluded (brainstorm has no self-edge)
        bt_refs = skills.get("hs:brainstorm", {}).get("body_refs", set())
        _assert("hs:brainstorm" not in bt_refs,
                "T7: Self-reference excluded")

        # T8: Code-fence ref in brainstorm body excluded
        _assert("hs:plan" not in bt_refs,
                "T8: Code-fence ref excluded")

        # T9: Unknown @agent ref is broken
        _assert("@ghost-agent" in broken_refs, "T9: Unknown @ghost-agent detected as broken")

        # T10: Known @agent ref (registry) is NOT broken
        _assert("@code-reviewer" not in broken_refs,
                "T10: Known @code-reviewer not broken")

        # T11: Workflow-name hs: ref is whitelisted (not broken)
        _assert("hs:base-fanout-consolidate" not in broken_refs,
                "T11: Workflow ref hs:base-fanout-consolidate not broken")

        n_tests = 11
        print(f"\nResults: {passed}/{n_tests} passed, {failed}/{n_tests} failed")
        return failed == 0


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if "--self-test" in sys.argv:
        ok = _run_self_tests()
        sys.exit(0 if ok else 1)

    if len(sys.argv) < 2:
        print("Usage: validate_skill_crossrefs.py <plugins-root> [--json]",
              file=sys.stderr)
        sys.exit(2)

    plugins_root = Path(sys.argv[1])
    if not plugins_root.is_dir():
        print(f"Error: {plugins_root} is not a directory", file=sys.stderr)
        sys.exit(2)

    use_json = "--json" in sys.argv

    skills = scan_all_skills(plugins_root)
    known_agents = collect_agent_names(plugins_root)
    known_workflows = collect_workflow_names(plugins_root)
    graph = build_reference_graph(skills, known_agents, known_workflows)
    missing = check_expected_workflows(graph)

    # CS-10 (K4): rule-layer referential integrity, only when plugins_root sits
    # at the expected `<repo>/harness/plugins` layout (else skip — best-effort,
    # never guess a repo root and report a false orphan/broken set).
    rule_check = None
    resolved = plugins_root.resolve()
    if resolved.name == "plugins" and resolved.parent.name == "harness":
        repo_root = resolved.parent.parent
        known_rules = collect_rule_names(repo_root)
        claude_md_routed = collect_claude_md_rule_refs(repo_root)
        registry_routed = collect_registry_routed_rules(repo_root)
        rule_check = check_rule_references(skills, known_rules, claude_md_routed,
                                           registry_routed)

    if use_json:
        result = {
            "total_skills": len(skills),
            "edges": graph["edges"],
            "orphans": graph["orphans"],
            "hubs": [{"name": n, "in_degree": c} for n, c in graph["hubs"]],
            "broken": [{"from": s, "ref": r} for s, r in graph["broken"]],
            "missing_workflow_edges": missing,
        }
        if rule_check is not None:
            result["broken_rules"] = [
                {"from": s, "ref": r} for s, r in rule_check["broken_rules"]]
            result["orphan_rules"] = rule_check["orphan_rules"]
        print(json.dumps(result, indent=2))
    else:
        print_report(skills, graph, missing, rule_check)

    # Non-zero exit only when workflow chains have gaps (advisory signal)
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
