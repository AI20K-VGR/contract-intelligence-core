"""check_skill_structure.py — structural + content lint for hs:* skills.

Enforces the thin-core discipline the harness documents for skills: a SKILL.md stays
small so the always-loaded core is cheap, and detail is pushed one level deep into
references/ that themselves stay bounded. Three existing validators cover other
concerns (catalog.tier_problems for compliance-tier; the dot-claude tree for
frontmatter/cross-refs) — this one owns the size + description-shape gap none of them
check, plus the WRITE-time content integrity the skill_quality_gate hook enforces.

Size is measured in CHARS, not lines — line-count is a bad proxy that rewards narrow
wrapping and lets a wide-wrapped file smuggle 2-3x the content past the same cap.

Findings by severity:
  - HARD: an over-budget SKILL.md body / reference / agent (skill-md-too-large /
    reference-too-large / agent-too-large), a run-on line past the per-line cap
    (overlong-line), a dangling local reference the body points at
    (broken-reference-link), and a machine birth-marker leaking into prose
    (birth-marker-leak).
  - ADVISORY: description shape, an orphan reference NOTHING reaches — neither a body
    link nor an hs-run routing row (orphan-reference) — and tight email / US-SSN PII
    shapes (pii-possible).

Contract (mirrors check_report_language):
  - Advisory by default: exits 0, emits a per-skill verdict on stdout, never mutates.
  - With --strict any HARD finding exits non-zero. CI runs --strict only on skills
    CHANGED vs main, so existing skills are grandfathered until they are next touched.
  - write_gate_reason() is the compliance-core for the PostToolUse skill_quality_gate
    hook: it blocks ONLY on the HARD content rules (dangling reference / birth-marker),
    leaving size to CI and shape/PII advisory.

Input is a skill directory (one with a SKILL.md) or a root that holds skill dirs;
a root is swept. A path with no SKILL.md is inert (skipped, exit 0).
"""
import argparse
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import skill_frontmatter  # noqa: E402


def load_routed_reference_names() -> "dict[str, set[str]]":
    """Every skill's routed reference basenames, keyed by skill dir name.

    The second inbound channel a reference can have. Read through `hs_run`'s own
    loader rather than a local YAML parse: the registry is a root file plus
    per-domain fragments, and a second reader that missed the fragment merge would
    silently see zero routed refs -- failing in the direction that looks like a
    clean tree (every routed ref reported as an orphan), which is the exact defect
    this channel exists to close.

    FAIL-OPEN, deliberately. `write_gate_reason()` feeds a compliance-class hook
    that blocks a tool call, and orphan-reference is ADVISORY -- a registry that is
    missing, unreadable, or mid-edit must degrade to prose-only judgment, never take
    the gate down. The cost of the degraded answer is a false advisory line; the
    cost of raising here is a blocked edit on an unrelated file.

    Returns the WHOLE map in one read because the caller is a per-skill sweep:
    measured at ~13 ms per registry load, a per-skill call cost ~630 ms across the
    47-skill tree for 47 copies of the same answer."""
    try:
        import hs_run
        routing = hs_run.load_step_routing() or {}
    except Exception:
        return {}

    out: "dict[str, set[str]]" = {}
    for block in routing.values():
        if not isinstance(block, dict):
            continue
        names = out.setdefault(str(block.get("skill") or ""), set())
        names.update(Path(r).name for r in ((block.get("always") or {}).get("refs") or []))
        for row in (block.get("states") or {}).values():
            names.update(Path(r).name for r in (row.get("refs") or []))
            for cond in (row.get("when_flag") or {}).values():
                names.update(Path(r).name for r in (cond.get("refs") or []))
    return out

# Thin-core thresholds, measured in CHARS — the real token/context cost, independent of
# how the prose is wrapped. A line-count cap is a bad proxy for size: it rewards narrow
# wrapping and lets a wide-wrapped file smuggle 2-3x the content past the same cap
# (measured p50 wrap width across skills spans 25-89 chars/line — a 3.5x spread at the
# same 200-line ceiling). These char budgets are ~4 chars/token: skill/ref ~3,750 tok,
# agent ~3,000 tok. Both live here as the single knob.
MAX_SKILL_CHARS = 15000   # SKILL.md BODY (frontmatter excluded)
MAX_REF_CHARS = 15000     # each references/*.md (whole file)
MAX_AGENT_CHARS = 12000   # each agents/*.md (whole file)
# Per-line char cap (HARD): a readability/diff guard, not an anti-evasion tool — the
# char size cap already bounds total content, so a long line smuggles nothing. It keeps
# every line reviewable. p99 of real lines is ~130-275 chars, so a line past this is an
# unambiguous run-on. Prefer MERGING short lines over COMPRESSING a rule — only split
# when a line is genuinely too long to read.
MAX_LINE_CHARS = 400

# Durable per-skill body-cap override (chars). A handful of skills — the spine
# orchestrators cook + plan — carry an always-read directive set that legitimately
# exceeds MAX_SKILL_CHARS; their override lives in data/thin-core-caps.yaml and HOLDS
# under --strict (it is an accepted budget, NOT the grandfather ledger's temporary debt).
# The exemption is bounded, never a blank cheque: EXEMPTION_HARD_CEILING clamps every
# override so a bad data-file entry cannot grant unlimited budget ("no blind ballooning").
EXEMPTION_HARD_CEILING = 25000
_CAPS_PATH = Path(__file__).resolve().parents[1] / "data" / "thin-core-caps.yaml"

# A named skill may be granted a HIGHER, still-bounded ceiling than the general
# EXEMPTION_HARD_CEILING — a deliberate, code-level exception, NOT a data-file value a
# fat-finger could grant. It is two-key: the skill must ALSO carry a reasoned entry in
# thin-core-caps.yaml (data), so both the code allowlist and the data override must agree.
# The general ceiling is 25k for every other skill; only these names may exceed it, and
# only up to their own bounded ceiling.
_UNCLAMPED_EXEMPTIONS = {
    # Verbatim reasoning-protocol port: the body is ONE cohesive always-read unit (the
    # five moves cross-reference each other and the Floor/Constraint-Loop gates), so
    # splitting it into references would break the protocol rather than thin it.
    "fable-thinking": 26000,
}


def exemption_ceiling(name: str) -> int:
    """The absolute override ceiling for a skill: the named higher ceiling for a reviewed
    clamp-exemption, else the general EXEMPTION_HARD_CEILING that bounds every other skill."""
    return _UNCLAMPED_EXEMPTIONS.get(name, EXEMPTION_HARD_CEILING)


def load_skill_cap_overrides() -> dict:
    """The per-skill body-cap overrides as {skill_dir_name: {body_max, reason}}.
    Fail-open: a missing/unparseable file yields {} (no override, general cap holds)."""
    try:
        import yaml_io
        data = yaml_io.safe_load(_CAPS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    out = {}
    if isinstance(data, dict):
        for name, spec in data.items():
            if isinstance(spec, dict) and isinstance(spec.get("body_max"), int):
                out[str(name)] = {"body_max": spec["body_max"],
                                  "reason": str(spec.get("reason") or "")}
    return out


# Cached once at import (matches the _GATE_CALL_RE/_SKILL_SCHEMA/_GRANDFATHER idiom in this
# module): skill_body_cap runs per-skill in a repo-wide sweep, so re-parsing the YAML on
# every call was ~50-90 redundant reads. A test needing a fresh read calls
# load_skill_cap_overrides() directly.
_CAP_OVERRIDES = load_skill_cap_overrides()

# Same idiom, same reason: the orphan pass runs per-skill in a repo-wide sweep, and
# the registry read is ~13 ms. A test needing a fresh read calls
# load_routed_reference_names() directly.
_ROUTED_REFS = load_routed_reference_names()


def _clamp_body_max(body_max: int, name: str) -> int:
    """Bound an override at the skill's ceiling — a named clamp-exemption gets its higher
    bound, every other skill the general EXEMPTION_HARD_CEILING. The exemption grants MORE
    budget, never UNLIMITED, even if the data file names an absurd value. On the production
    path (skill_body_cap) so it is the single, tested clamp — not a parallel dead one."""
    return min(int(body_max), exemption_ceiling(name))


def skill_body_cap(name: str) -> int:
    """The body char cap for a skill by dir name: the ceiling-clamped override when the
    skill is a documented exemption, else the general MAX_SKILL_CHARS. The clamp uses the
    skill's own ceiling (a named clamp-exemption gets its higher bound; every other skill
    the general EXEMPTION_HARD_CEILING). Single source of truth so every consumer (checker
    + tests) resolves the same cap."""
    spec = _CAP_OVERRIDES.get(name)
    if not spec:
        return MAX_SKILL_CHARS
    return _clamp_body_max(spec["body_max"], name)


# Description-shape advisory bounds.
DESC_MIN = 30
DESC_MAX = 512
_TRIGGER_RE = re.compile(r"\bUse (?:when|for|to)\b", re.I)


# A bare local reference the body points at: references/scripts/assets + a filename.
# The negative-lookbehind skips an absolute-path mention (harness/.../references/x.md
# is preceded by `/`), so only a repo-local relative ref is resolved against the skill
# dir — exactly what a reader would click. The file part is case-blind (A-Za-z): a
# capitalized name or uppercase extension (references/Detail.md, references/x.MD) is the
# same dead link to a reader, so it must not slip past on case alone.
# ONE directory level is allowed after the dir, because that is what the tree has:
# across 104 skills with a `references/` dir, three keep files in a subdirectory
# (`code-review` 3, `deploy` 15, `payment-integration` 36). A flat-only pattern made a
# dead link in any of them invisible to this HARD gate.
_LOCAL_REF_RE = re.compile(
    r"(?<![/\w])(references|scripts|assets)/((?:[A-Za-z0-9_-]+/)?[A-Za-z0-9_-]+\.[A-Za-z]+)")

# Birth-marker leak — deliberately tightened to ONLY machine-generated provenance SHAPES. It is
# deliberately NOT `success rate` or a bare `\d+ episode`: those match legitimate
# documentation prose (a belief-store SKILL.md reads "reinforced from 3 episodes"),
# which would make the very phases that document the belief store self-trip this gate.
# "generated from N episodes/runs/samples" requires the literal "generated from", so
# "reinforced from 3 episodes" does not match.
_BIRTH_MARKER_RE = re.compile(
    r"auto-drafted|generated_on|generated_by|generated from \d+ (?:episodes?|runs?|samples?)",
    re.IGNORECASE)

# Tight PII shapes (advisory): an email and a US SSN. Phone is deliberately
# dropped — its loose shape false-matched timestamp slugs / SVG viewBox / ISO dates.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# The WRITE-time gate (skill_quality_gate hook) blocks ONLY these HARD content rules.
# Size stays a CI lint (a mid-edit oversize is not a write-time integrity failure) and
# shape/PII stay advisory.
_WRITE_GATE_RULES = ("broken-reference-link", "birth-marker-leak",
                     "injectable-gate-conflict")

# injectable-gate-conflict tripwire: a skill declaring `injectable: true` whose BODY
# CALLS a gate (python3 harness/{hooks,scripts}/<gate>.py) — a narrow reverse-mistake
# net, NOT an executor detector (an executor kicks its gate through a tool-use hook,
# not a prose call). The gate basenames are a CLOSED enum loaded from the classifier
# SSOT; a bare prose mention or a non-gate script call never matches.
_CLASSIFIER_PATH = Path(__file__).resolve().parents[1] / "data" / "injectable-classifier.yaml"


def _load_gate_markers() -> list:
    try:
        import yaml_io
        data = yaml_io.safe_load(_CLASSIFIER_PATH.read_text(encoding="utf-8")) or {}
        return [str(m) for m in (data.get("gate_call_markers") or [])]
    except Exception:
        return []


def _gate_call_re():
    markers = _load_gate_markers()
    if not markers:
        return None
    alt = "|".join(re.escape(m) for m in markers)
    # a CALL shape: `python3 harness/hooks/<gate>.py` or `.../scripts/<gate>.py`.
    # The `python3 harness/…` prefix is what separates a call from a prose mention.
    return re.compile(r"python3?\s+harness/(?:hooks|scripts)/(?:%s)\.py" % alt)


_GATE_CALL_RE = _gate_call_re()


def is_injectable(skill_dir) -> bool:
    """Fail-closed: a skill is injectable ONLY when its frontmatter says so
    explicitly. An ABSENT field is NOT injectable — a skill missing the flag is
    never routed to the partner lane."""
    fm = _frontmatter(Path(skill_dir) / "SKILL.md")
    return bool(fm and fm.get("injectable") is True)

# Frontmatter contract (skill-schema.json). Loaded once; absence/parse-failure degrades
# to "no schema check" (fail-open) so a missing schema never blocks a write.
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "skill-schema.json"
_JSON_TO_PY = {"string": str, "boolean": bool, "array": list,
               "object": dict, "number": (int, float), "integer": int}


def _load_skill_schema() -> dict:
    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


_SKILL_SCHEMA = _load_skill_schema()

# Grandfather ledger: (component, rule) pairs whose HARD finding is pre-existing debt from
# the line-count -> char-count standard migration. In the default (repo-wide sweep) mode
# such a finding is downgraded to advisory so the standard could land without a mass
# rewrite; --strict (CI on CHANGED files) bypasses this so each entry re-teeths the moment
# its file is next touched. Fail-open: a missing/unparseable ledger means no grandfathering.
_GRANDFATHER_PATH = Path(__file__).resolve().parents[1] / "data" / "thin-core-grandfather.yaml"


def _load_grandfather() -> set:
    try:
        import yaml_io
        data = yaml_io.safe_load(_GRANDFATHER_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    out = set()
    for rule, names in data.items():
        for n in (names or []):
            out.add((str(n), str(rule)))
    return out


_GRANDFATHER = _load_grandfather()


def _apply_grandfather(name: str, findings: list, honor: bool) -> None:
    """Downgrade a grandfathered HARD finding to advisory in place (keeping a
    `grandfathered` marker for traceability). No-op under strict mode."""
    if not honor:
        return
    for f in findings:
        if f["severity"] == "hard" and (name, f["rule"]) in _GRANDFATHER:
            f["severity"] = "advisory"
            f["grandfathered"] = True


def _frontmatter(skill_md: Path) -> dict:
    """The SKILL.md frontmatter as a dict; {} when absent/unparseable (fail-soft).

    `errors="replace"` matches the sibling readers (`_body`/`_description`/
    `check_agent`): a SKILL.md with a stray non-UTF-8 byte (written via Bash/import,
    not the always-UTF-8 Write tool) must degrade, never crash the repo-wide lint
    with a raw UnicodeDecodeError that only OSError would have caught."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return skill_frontmatter.frontmatter(text)


def _type_ok(value, schema_type) -> bool:
    """True if value matches a JSON-Schema type (string, or list-of-types union)."""
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    for t in types:
        py = _JSON_TO_PY.get(t)
        if py is None:
            return True  # unknown type keyword -> do not penalize
        # bool is a subclass of int: keep them distinct so a boolean field is not
        # silently accepted as a number and vice-versa.
        if py is bool and isinstance(value, bool):
            return True
        if py is not bool and isinstance(value, py) and not isinstance(value, bool):
            return True
        if py is bool:
            continue
    return False


def _schema_findings(skill_md: Path, fm: dict = None) -> list:
    """Advisory findings from the frontmatter contract: required-present + known-field
    types. A MISSING OPTIONAL field is never a finding — that is rollout coverage, not a
    structural error — so the existing tree stays clean until the rollout fills it.

    `fm` may be passed by a caller that already parsed the frontmatter, to avoid a
    second read+parse of the same SKILL.md; it defaults to reading it here."""
    if not _SKILL_SCHEMA:
        return []
    if fm is None:
        fm = _frontmatter(skill_md)
    if not fm:
        return []
    out = []
    for req in _SKILL_SCHEMA.get("required", []):
        val = fm.get(req)
        if val is None or (isinstance(val, str) and not val.strip()):
            out.append({"rule": "frontmatter-missing-required", "severity": "advisory",
                        "detail": "frontmatter is missing required field %r" % req})
    props = _SKILL_SCHEMA.get("properties", {})
    for key, spec in props.items():
        if key in fm and fm[key] is not None and "type" in spec:
            if not _type_ok(fm[key], spec["type"]):
                out.append({"rule": "frontmatter-bad-type", "severity": "advisory",
                            "detail": "frontmatter field %r should be %s" % (key, spec["type"])})
    return out


def _overlong_line_finding(label: str, text: str) -> "dict | None":
    """A HARD overlong-line finding for the widest line in `text`, or None. Shared by
    the skill and agent checks so the per-line readability cap is one definition."""
    worst = max((len(ln) for ln in text.splitlines()), default=0)
    if worst > MAX_LINE_CHARS:
        return {"rule": "overlong-line", "severity": "hard",
                "detail": "%s has a %d-char line (cap %d) — merge lines, do not compress rules"
                          % (label, worst, MAX_LINE_CHARS)}
    return None


def _body(skill_md: Path) -> str:
    """The SKILL.md body (everything after the leading frontmatter block), or the
    whole file when there is no frontmatter. Body-only is deliberate: a birth-marker
    or PII shape is a PROSE concern, so a `generated_on:` field inside frontmatter
    metadata is not a leak. Fail-soft: an unreadable file yields ""."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return skill_frontmatter.body(text)


def _description(skill_md: Path) -> str:
    """The frontmatter description, or "" when absent. Fail-soft."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return skill_frontmatter.description(text)


def check_skill(skill_dir: str, honor_grandfather: bool = True) -> dict:
    """Return a verdict dict for one skill directory.

    verdict: FAIL when any HARD finding is present, PASS_WITH_RISK when only advisory
    findings exist, PASS when clean. A directory without a SKILL.md is skipped.

    honor_grandfather (default True): downgrade grandfathered HARD findings to advisory
    (the repo-wide sweep view). Pass False (--strict, CI on changed files) to see the
    debt at full severity so it re-teeths on edit.
    """
    d = Path(skill_dir)
    skill_md = d / "SKILL.md"
    if not skill_md.is_file():
        return {"tool": "check_skill_structure", "skill": d.name,
                "verdict": "PASS", "skipped": "no SKILL.md", "findings": []}

    findings = []

    # Size gate governs GUIDANCE: measure the BODY (after frontmatter) in CHARS, not
    # metadata. Otherwise the schema frontmatter rollout would eat the body budget.
    body = _body(skill_md)
    nc = len(body)
    cap = skill_body_cap(d.name)
    if nc > cap:
        note = "" if cap == MAX_SKILL_CHARS else " (raised cap; see data/thin-core-caps.yaml)"
        findings.append({"rule": "skill-md-too-large", "severity": "hard",
                         "detail": "SKILL.md body is %d chars (max %d%s) — split detail into references/"
                                   % (nc, cap, note)})

    refs = d / "references"
    # rglob: nested drawers (references/<topic>/x.md) are guidance too and must not escape
    # the cap — a depth-1 glob let a 29k nested reference hide.
    ref_files = sorted(refs.rglob("*.md")) if refs.is_dir() else []
    # Read each reference once; reuse the text for both the size check and the overlong-line
    # check below (was two disk reads per ref, per skill, in a repo-wide sweep).
    ref_texts = [(ref, ref.read_text(encoding="utf-8", errors="replace")) for ref in ref_files]
    for ref, rtext in ref_texts:
        rc = len(rtext)
        if rc > MAX_REF_CHARS:
            findings.append({"rule": "reference-too-large", "severity": "hard",
                             "detail": "references/%s is %d chars (max %d)"
                                       % (ref.relative_to(refs).as_posix(), rc, MAX_REF_CHARS)})

    # overlong single line (HARD): a run-on line that is too wide to review/diff. Worst
    # offender per file, SKILL.md body + each reference.
    _line_targets = [("SKILL.md", body)]
    _line_targets += [("references/%s" % r.relative_to(refs).as_posix(), rtext)
                      for r, rtext in ref_texts]
    for label, text in _line_targets:
        f = _overlong_line_finding(label, text)
        if f:
            findings.append(f)

    # dangling local reference (HARD): a references/scripts/assets path the body links
    # must resolve inside the skill dir. linked names are collected here so the orphan
    # pass below can tell an unlinked on-disk reference from a missing one.
    linked_refs = set()
    for m in _LOCAL_REF_RE.finditer(body):
        if m.group(1) == "references":
            linked_refs.add(m.group(2))
        if not (d / m.group(1) / m.group(2)).is_file():
            findings.append({"rule": "broken-reference-link", "severity": "hard",
                             "detail": "body links %s/%s which does not exist in the skill dir"
                                       % (m.group(1), m.group(2))})

    # birth-marker leak (HARD): a machine-generated provenance shape in prose.
    bm = _BIRTH_MARKER_RE.search(body)
    if bm:
        findings.append({"rule": "birth-marker-leak", "severity": "hard",
                         "detail": "body carries a generated-provenance marker %r — strip it"
                                   % bm.group(0)})

    # injectable-gate-conflict (HARD): a skill claiming injectable:true whose BODY
    # calls a gate. Body-only (a call in the frontmatter is safe), call-shape-only (a
    # prose mention is safe), closed-enum (non-gate calls are safe).
    fm = _frontmatter(skill_md)
    if fm and fm.get("injectable") is True and _GATE_CALL_RE is not None:
        gm = _GATE_CALL_RE.search(body)
        if gm:
            findings.append({"rule": "injectable-gate-conflict", "severity": "hard",
                             "detail": "injectable:true but the body calls a gate (%r) — an "
                                       "injectable skill's methodology must not run a harness gate"
                                       % gm.group(0)})

    # orphan reference (ADVISORY): a references/*.md file NOTHING reaches.
    #
    # Reachability, not in-degree-from-prose. A body link is one inbound channel; a
    # `refs:` routing row in the hs-run registry is the other, and it is the stronger
    # one -- the file arrives at the state that needs it instead of sitting in a
    # paragraph read thousands of tokens earlier. Measured when the second channel
    # landed: `plan` had 16 references, 16 routed, 0 truly orphaned, and a prose-only
    # lint called all 16 orphans. An advisory wrong 16 times reads as "this skill is a
    # mess" and buries the 17th line, which would be the real one.
    if refs.is_dir():
        on_disk = {p.name for p in refs.glob("*.md") if p.is_file()}
        reachable = linked_refs | _ROUTED_REFS.get(d.name, set())
        for orphan in sorted(on_disk - reachable):
            findings.append({"rule": "orphan-reference", "severity": "advisory",
                             "detail": "references/%s is on disk but nothing reaches it — "
                                       "no body link and no hs-run routing row" % orphan})

    # PII (ADVISORY): tight email / US-SSN shapes in the body.
    if _EMAIL_RE.search(body):
        findings.append({"rule": "pii-possible", "severity": "advisory",
                         "detail": "body contains an email-shaped string"})
    if _SSN_RE.search(body):
        findings.append({"rule": "pii-possible", "severity": "advisory",
                         "detail": "body contains a US-SSN-shaped string"})

    desc = _description(skill_md)
    if not (DESC_MIN <= len(desc) <= DESC_MAX):
        findings.append({"rule": "description-length", "severity": "advisory",
                         "detail": "description is %d chars (want %d-%d)"
                                   % (len(desc), DESC_MIN, DESC_MAX)})
    if desc and not _TRIGGER_RE.search(desc):
        findings.append({"rule": "description-missing-trigger", "severity": "advisory",
                         "detail": 'description has no "Use when/for/to ..." trigger clause'})

    # frontmatter contract (skill-schema.json): required-present + known-field types.
    # Reuse the `fm` already parsed above so this does not re-read+parse SKILL.md.
    findings.extend(_schema_findings(skill_md, fm=fm))

    _apply_grandfather(d.name, findings, honor_grandfather)
    hard = any(f["severity"] == "hard" for f in findings)
    verdict = "FAIL" if hard else ("PASS_WITH_RISK" if findings else "PASS")
    return {"tool": "check_skill_structure", "skill": d.name,
            "verdict": verdict, "findings": findings}


def check_agent(agent_md: str, honor_grandfather: bool = True) -> dict:
    """Verdict dict for one agents/*.md file. Agents carry the SAME size + per-line
    discipline as skills. SIZE is measured over the WHOLE file (an agent's frontmatter —
    its trigger examples + tool list — is guidance too, so it counts toward the budget).
    The per-line cap is measured over the BODY only (frontmatter excluded): a `description:`
    is one YAML scalar — the agent's routing text — that cannot be prose-wrapped without a
    block scalar / semantic change, so the readability cap is a prose concern, consistent
    with how SKILL.md overlong-line is measured. A non-file path is inert (skipped).
    Content rules (birth-marker/PII/reference) stay skill-only."""
    p = Path(agent_md)
    if not p.is_file():
        return {"tool": "check_skill_structure", "kind": "agent", "agent": p.stem,
                "verdict": "PASS", "skipped": "no such file", "findings": []}
    text = p.read_text(encoding="utf-8", errors="replace")
    findings = []
    if len(text) > MAX_AGENT_CHARS:
        findings.append({"rule": "agent-too-large", "severity": "hard",
                         "detail": "%s is %d chars (max %d) — trim or split into references/"
                                   % (p.name, len(text), MAX_AGENT_CHARS)})
    f = _overlong_line_finding(p.name, skill_frontmatter.body(text))
    if f:
        findings.append(f)
    _apply_grandfather(p.stem, findings, honor_grandfather)
    hard = any(f["severity"] == "hard" for f in findings)
    verdict = "FAIL" if hard else ("PASS_WITH_RISK" if findings else "PASS")
    return {"tool": "check_skill_structure", "kind": "agent", "agent": p.stem,
            "verdict": verdict, "findings": findings}


def write_gate_reason(file_path) -> "str | None":
    """Compliance-core decision for the skill_quality_gate PostToolUse hook.

    None ⇒ allow; a string ⇒ block reason. Only a SKILL.md is gated, and only the HARD
    content rules (dangling reference / birth-marker leak) block at WRITE time — size
    stays a CI lint and shape/PII stay advisory (fail-open). check_skill is fail-soft,
    so an unreadable target produces no finding and passes.
    """
    p = Path(file_path)
    if p.name != "SKILL.md":
        return None
    result = check_skill(str(p.parent))
    hard = [f for f in result.get("findings", []) if f.get("rule") in _WRITE_GATE_RULES]
    if not hard:
        return None
    detail = "; ".join("%s — %s" % (f["rule"], f["detail"]) for f in hard)
    return "SKILL.md content gate at %s: %s" % (p, detail)


def _iter_skill_dirs(root: Path):
    """A root that directly holds a SKILL.md is one skill; otherwise its immediate
    children that hold a SKILL.md are the skills."""
    if (root / "SKILL.md").is_file():
        return [root]
    return sorted(c for c in root.iterdir() if c.is_dir() and (c / "SKILL.md").is_file())


def check_path(path: str, honor_grandfather: bool = True) -> dict:
    root = Path(path)
    if not root.exists():
        return {"tool": "check_skill_structure", "verdict": "PASS",
                "skipped": "no such path: %s" % path, "skills": []}
    dirs = _iter_skill_dirs(root)
    agents = []
    # When scanning a plugin's skills/ root, also pull in its siblings: a skill stashed
    # as install-disabled (disabled-skills/) still ships and must not drift below the
    # live standard, and agents/ carry the SAME size + per-line discipline.
    if root.name == "skills":
        stash = root.parent / "disabled-skills"
        if stash.is_dir():
            dirs = dirs + _iter_skill_dirs(stash)
        agents_dir = root.parent / "agents"
        if agents_dir.is_dir():
            agents = [check_agent(str(a), honor_grandfather) for a in sorted(agents_dir.glob("*.md"))]
    if not dirs and not agents:
        return {"tool": "check_skill_structure", "verdict": "PASS",
                "skipped": "no SKILL.md under %s" % path, "skills": []}
    skills = [check_skill(str(d), honor_grandfather) for d in dirs]
    entries = skills + agents
    hard = sum(len([f for f in e["findings"] if f["severity"] == "hard"]) for e in entries)
    advisory = sum(len([f for f in e["findings"] if f["severity"] == "advisory"]) for e in entries)
    result = {
        "tool": "check_skill_structure",
        "verdict": "FAIL" if hard else ("PASS_WITH_RISK" if advisory else "PASS"),
        "hard": hard,
        "advisory": advisory,
        "skills": skills,
    }
    if agents:
        result["agents"] = agents
    # Cross-skill confusable-pair warning (advisory, warn-only): two skills whose
    # descriptions read alike are hard to route between. Only meaningful across a
    # multi-skill root; never affects verdict or exit code.
    if len(dirs) > 1:
        import catalog  # lazy: only needed on a multi-skill scan
        pairs = catalog.confusable_pairs(root)
        if pairs:
            result["confusable"] = pairs
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Advisory structural lint for hs:* skills.")
    ap.add_argument("path", help="a skill directory, or a root holding skill dirs")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when a HARD finding is present (CI runs this on changed skills)")
    args = ap.parse_args(argv)
    # --strict is the CI-on-changed view: it bypasses the grandfather ledger so a
    # touched file's pre-existing debt surfaces at full severity and blocks.
    result = check_path(args.path, honor_grandfather=not args.strict)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if (args.strict and result.get("hard")) else 0


if __name__ == "__main__":
    sys.exit(main())
