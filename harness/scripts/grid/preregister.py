"""Pre-registration — constraint-rule freeze/verify (grid/v2).

Closes the "mint-a-rule" Goodhart hole na-option3 left open: that option lets
an N/A cell count toward coverage when its attestation cites a "rule:<id>"
constraint rule, but nothing stopped an agent from inventing that rule at
fill-time to launder a cell it was too lazy to fill. Timestamp-based framing
("frozen_at before fill_started_at") does not close this at tầng-1 — the
agent writes the very mark being checked against, so it is not external
evidence (`architectural-constraints.md` "agent-authored receipt never
self-authenticating").

The fix re-anchors freeze to ``plan_hash`` (`plan_approval.py`): the sha256
digest over the plan content a human actually clicked Approve on. A rule
only counts if it is a member of the FROZEN set (universal tier: shipped in
``grid-axes.yaml``, reviewed as code; local tier: derived from plan
step-metadata, then rendered into the plan body BEFORE approval so its
content-hash sits under ``plan_hash``). Verify never touches a clock — it
checks five re-derivable, deterministic propositions: parse-id,
set-membership, applicability (rule.combo ⊆ cell.coordinates), tamper
(content-hash match), and verdict (only a forbidding rule credits an N/A).
Minting a rule mid-fill means editing plan content, which moves plan_hash,
which the drift guard catches and forces back through re-approval — the
freeze is tamper-EVIDENT (every edit leaves a mark), not tamper-proof
(nothing here can physically block the edit; that needs a clock/actor/key
tầng-1 does not hold).
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml_io

from .types import CellResolution

# Both regexes must be the SAME objects plan_hash strips with — a hash line
# living in a region one side strips and the other keeps would be an anchor
# freezing nothing. Import, never re-declare. Dual entrance as in artifact.py.
try:
    from harness.scripts.plan_approval import _FRONTMATTER_RE, _PHASES_SECTION_RE
except ImportError:
    from plan_approval import _FRONTMATTER_RE, _PHASES_SECTION_RE

_AXES_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "grid-axes.yaml"

# Verdicts the loader accepts at freeze-time. Only "forbidden" credits an N/A
# (checked by verify); "allowed" exists so a non-forbidding rule can be
# frozen and machine-checked for propositions 1-4 without vacuously passing
# proposition 5 (test_verify_rejects_non_forbidden_verdict).
_KNOWN_VERDICTS = frozenset({"forbidden", "allowed"})

_RULE_REF_RE = re.compile(r"^rule:([A-Za-z0-9_\-]+)")
_HASH_LINE_RE = re.compile(r"^grid_ruleset_hash:\s*(\S+)\s*$", re.MULTILINE)


class MalformedConstraintRuleError(Exception):
    """``constraint_rules`` (or a derived combo) is malformed — fail closed,
    never a silently-empty rule list (mirrors ``density.UnknownDensityTierError``)."""


class AmendmentNotConfirmedError(Exception):
    """``amend_ruleset`` called without a human confirm-token — amendment is
    HITL-gated, never automatic."""


@dataclass
class UniversalRule:
    id: str
    combo: Dict[str, str]
    verdict: str = "forbidden"
    rationale: str = ""
    version: int = 1


@dataclass
class LocalRule:
    id: str
    combo: Dict[str, str]
    verdict: str = "forbidden"
    rationale: str = ""
    source: str = "plan-preflight"
    derived_from: str = ""


@dataclass
class FrozenRuleset:
    rules: List[Any]
    ruleset_hash: str
    tier_counts: Dict[str, int]
    # Telemetry ONLY — no load-bearing check reads this.
    frozen_at: Optional[str] = None


@dataclass
class VerifyResult:
    ok: bool
    reason: str = "ok"


@dataclass
class Violation:
    cell_coordinates: Dict[str, str]
    rule_id: Optional[str]
    reason: str


@dataclass
class RegenReceipt:
    grid: Any
    regenerated_cell_count: int
    cell_set_added: List[Dict[str, str]] = field(default_factory=list)
    cell_set_removed: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class AmendmentReceipt:
    added_rule_id: str
    prior_hash: str
    new_hash: str
    regenerated_cell_count: int
    cell_set_added: List[Dict[str, str]]
    cell_set_removed: List[Dict[str, str]]
    confirmed_by: str
    # Telemetry ONLY, symmetric with FrozenRuleset.frozen_at.
    amended_at: Optional[str] = None


@dataclass
class AmendmentResult:
    frozen: FrozenRuleset
    grid: Any
    receipt: AmendmentReceipt


# ------------------------------------------------------------- combo-shape ---

def _validate_combo_shape(rule_id: str, combo: Dict[str, str]) -> None:
    """A forbidden-COMBINATION needs >=2 keys. An empty combo is a
    subset of every cell (infinite credit); a 1-key combo is a subset of a
    whole axis column (credits an entire column). Reject both, fail-closed."""
    if not combo or len(combo) < 2:
        raise MalformedConstraintRuleError(
            "rule %r has combo %r — a forbidden-combination rule needs >=2 "
            "keys (empty combo credits every cell; 1-key credits a whole "
            "axis column)" % (rule_id, combo)
        )


# ----------------------------------------------------------------- loader ---

def _load_axes_doc(path=None) -> dict:
    src = Path(path) if path else _AXES_DATA
    try:
        text = src.read_text(encoding="utf-8")
    except OSError as exc:
        raise MalformedConstraintRuleError("grid-axes.yaml unreadable: %s" % exc) from exc
    return yaml_io.safe_load(text) or {}


def load_universal_rules(path=None) -> List[UniversalRule]:
    """Read the universal (build-engine, code-reviewed) tier from
    ``constraint_rules`` in ``grid-axes.yaml``. Fail-closed on anything
    malformed — never a silent empty list (mirror ``density.UnknownDensityTierError``)."""
    doc = _load_axes_doc(path)
    cr = doc.get("constraint_rules")
    if not isinstance(cr, dict) or "rules" not in cr:
        raise MalformedConstraintRuleError(
            "grid-axes.yaml constraint_rules missing or malformed (no 'rules' key)"
        )
    version = cr.get("version", 1)
    rules: List[UniversalRule] = []
    for raw in cr["rules"] or []:
        if not isinstance(raw, dict):
            raise MalformedConstraintRuleError("constraint_rules entry is not a mapping: %r" % raw)
        rid = raw.get("id")
        combo = raw.get("combo")
        verdict = raw.get("verdict")
        if not rid or not isinstance(combo, dict):
            raise MalformedConstraintRuleError("constraint_rules entry missing id/combo: %r" % raw)
        _validate_combo_shape(rid, combo)
        if verdict not in _KNOWN_VERDICTS:
            raise MalformedConstraintRuleError("rule %r has unknown verdict %r" % (rid, verdict))
        rules.append(UniversalRule(
            id=rid, combo=dict(combo), verdict=verdict,
            rationale=raw.get("rationale", ""), version=version,
        ))
    return rules


def _combo_slug(combo: Dict[str, str]) -> str:
    return "-x-".join("%s-%s" % (k, v) for k, v in sorted(combo.items()))


def derive_local_rules(step_metadata: dict) -> List[LocalRule]:
    """Derive local-tier rules from a plan step's declared
    ``forbidden_combos`` — never hand-typed at fill-time. Same combo-shape
    guard as ``load_universal_rules``."""
    step = step_metadata.get("step")
    entries = step_metadata.get("forbidden_combos") or []
    rules: List[LocalRule] = []
    for entry in entries:
        if isinstance(entry, dict) and "combo" in entry:
            combo = entry["combo"]
            rationale = entry.get("rationale", step_metadata.get("rationale", ""))
        else:
            combo = entry
            rationale = step_metadata.get("rationale", "")
        rid = _combo_slug(combo) if isinstance(combo, dict) else None
        _validate_combo_shape(rid, combo if isinstance(combo, dict) else {})
        rules.append(LocalRule(
            id=rid, combo=dict(combo), verdict="forbidden", rationale=rationale,
            source="plan-preflight", derived_from="step:%s" % step,
        ))
    return rules


# -------------------------------------------------------------- freeze/hash ---

def ruleset_content_hash(rules) -> str:
    """Stable hash over sorted(id+combo+verdict) — tamper-evidence, NO
    timestamp. Sorting by id makes the hash independent of rule order."""
    parts = []
    for r in sorted(rules, key=lambda r: r.id):
        combo_str = ",".join("%s=%s" % (k, v) for k, v in sorted(r.combo.items()))
        parts.append("%s|%s|%s" % (r.id, combo_str, r.verdict))
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _tier_counts(rules) -> Dict[str, int]:
    universal = sum(1 for r in rules if isinstance(r, UniversalRule))
    local = sum(1 for r in rules if isinstance(r, LocalRule))
    return {"universal": universal, "local": local}


def freeze_ruleset(universal, local, frozen_at=None) -> FrozenRuleset:
    """Merge the two tiers + stamp a content-hash. ``frozen_at`` is optional
    TELEMETRY only — freeze works identically whether it is
    supplied or left ``None``."""
    rules = list(universal) + list(local)
    return FrozenRuleset(
        rules=rules,
        ruleset_hash=ruleset_content_hash(rules),
        tier_counts=_tier_counts(rules),
        frozen_at=frozen_at,
    )


# --------------------------------------------------------------- machine-check ---

def parse_na_rule_ref(attestation) -> Optional[str]:
    """Extract the ``<id>`` from a ``rule:<id>`` attestation prefix (the
    convention shared across the grid engine). ``None`` for free-text (breadth-seen
    only — never routes into the depth/credit numerator)."""
    if not attestation:
        return None
    m = _RULE_REF_RE.match(attestation.strip())
    return m.group(1) if m else None


def _combo_subset(combo: Dict[str, str], cell_coords: Dict[str, str]) -> bool:
    return all(cell_coords.get(k) == v for k, v in combo.items())


def verify_na_points_to_frozen_rule(rule_id, frozen: Optional[FrozenRuleset], cell_coords: Dict[str, str]) -> VerifyResult:
    """Five deterministic, re-derivable propositions — NO timestamp:
    (1) parse-id ok, (2) rule_id in frozen.rules, (3) rule.combo subset of
    cell_coords (applicability), (4) content-hash matches (tamper-evidence),
    (5) rule.verdict == "forbidden" (only a forbidding rule credits an N/A).
    ``frozen=None`` fails closed (matches the invariants module's
    ``compute_coverage_ratio``
    default-None contract)."""
    if frozen is None:
        return VerifyResult(ok=False, reason="frozen-ruleset-missing")
    if not rule_id:
        return VerifyResult(ok=False, reason="no-rule-id")
    rule = next((r for r in frozen.rules if r.id == rule_id), None)
    if rule is None:
        return VerifyResult(ok=False, reason="rule-not-frozen")
    if not _combo_subset(rule.combo, cell_coords):
        return VerifyResult(ok=False, reason="combo-not-applicable")
    if ruleset_content_hash(frozen.rules) != frozen.ruleset_hash:
        return VerifyResult(ok=False, reason="hash-mismatch")
    if rule.verdict != "forbidden":
        return VerifyResult(ok=False, reason="verdict-not-forbidden")
    return VerifyResult(ok=True, reason="ok")


def _iter_cells(grid):
    return grid.cells if hasattr(grid, "cells") else list(grid)


def assert_no_unfrozen_rule_ref(grid, frozen: Optional[FrozenRuleset]) -> List[Violation]:
    """Sweep every N/A cell: one whose attestation cites a ``rule:<id>`` that
    does NOT pass ``verify_na_points_to_frozen_rule`` is a fraud (mint-at-fill
    or point-at-an-inapplicable-rule). A free-text N/A (no ``rule:`` prefix)
    is breadth-seen only and is never flagged."""
    violations: List[Violation] = []
    for cell in _iter_cells(grid):
        if cell.resolution != CellResolution.NA:
            continue
        rule_id = parse_na_rule_ref(cell.attestation or "")
        if rule_id is None:
            continue
        result = verify_na_points_to_frozen_rule(rule_id, frozen, cell.coordinates)
        if not result.ok:
            violations.append(Violation(
                cell_coordinates=dict(cell.coordinates), rule_id=rule_id, reason=result.reason,
            ))
    return violations


# --------------------------------------------------------------- regen/amend ---

def regenerate_whole_grid(build_fn: Callable[[], Any], frozen: Optional[FrozenRuleset] = None) -> RegenReceipt:
    """Actually INVOKE ``build_fn`` (a real CA re-run, deterministic/0-token)
    rather than trust a self-reported boolean. Reports the fresh cell count
    plus which N/A cells the given ``frozen`` ruleset currently credits.
    There is no per-cell patch path — regen always rebuilds the whole grid."""
    grid = build_fn()
    cells = _iter_cells(grid)
    credited: List[Dict[str, str]] = []
    if frozen is not None:
        for cell in cells:
            if cell.resolution != CellResolution.NA:
                continue
            rule_id = parse_na_rule_ref(cell.attestation or "")
            if rule_id and verify_na_points_to_frozen_rule(rule_id, frozen, cell.coordinates).ok:
                credited.append(dict(cell.coordinates))
    return RegenReceipt(grid=grid, regenerated_cell_count=len(cells), cell_set_added=credited, cell_set_removed=[])


def amend_ruleset(frozen: FrozenRuleset, new_rule, confirm_token: str, build_fn: Callable[[], Any]) -> AmendmentResult:
    """HITL-gated: an empty ``confirm_token`` raises. On confirm, the new
    rule joins the frozen set (bumping the content-hash) and the WHOLE grid
    is re-run for real via ``build_fn`` — never a targeted single-cell patch.
    The receipt reports which N/A cells gained or lost credit because of the
    rule change (computed by re-verifying each N/A cell against the OLD vs
    NEW frozen set over the same freshly-built grid)."""
    if not confirm_token:
        raise AmendmentNotConfirmedError("amend_ruleset requires a non-empty confirm_token (HITL gate)")
    _validate_combo_shape(new_rule.id, new_rule.combo)

    prior_hash = frozen.ruleset_hash
    new_rules = list(frozen.rules) + [new_rule]
    new_frozen = FrozenRuleset(
        rules=new_rules,
        ruleset_hash=ruleset_content_hash(new_rules),
        tier_counts=_tier_counts(new_rules),
        frozen_at=None,
    )

    regen = regenerate_whole_grid(build_fn, new_frozen)
    grid = regen.grid

    added: List[Dict[str, str]] = []
    removed: List[Dict[str, str]] = []
    for cell in _iter_cells(grid):
        if cell.resolution != CellResolution.NA:
            continue
        rule_id = parse_na_rule_ref(cell.attestation or "")
        if rule_id is None:
            continue
        was_ok = verify_na_points_to_frozen_rule(rule_id, frozen, cell.coordinates).ok
        is_ok = verify_na_points_to_frozen_rule(rule_id, new_frozen, cell.coordinates).ok
        if is_ok and not was_ok:
            added.append(dict(cell.coordinates))
        elif was_ok and not is_ok:
            removed.append(dict(cell.coordinates))

    receipt = AmendmentReceipt(
        added_rule_id=new_rule.id,
        prior_hash=prior_hash,
        new_hash=new_frozen.ruleset_hash,
        regenerated_cell_count=regen.regenerated_cell_count,
        cell_set_added=added,
        cell_set_removed=removed,
        confirmed_by=confirm_token,
        amended_at=None,
    )
    return AmendmentResult(frozen=new_frozen, grid=grid, receipt=receipt)


# ------------------------------------------------------- hash-anchor + render ---

def record_ruleset_hash_line(frozen: FrozenRuleset) -> str:
    """The exact line to paste into the plan body — matched verbatim by
    ``verify_ruleset_hash_matches_plan``."""
    return "grid_ruleset_hash: %s" % frozen.ruleset_hash


def render_ruleset_section(frozen: FrozenRuleset) -> str:
    """Human-readable markdown table (id|combo|verdict|rationale) plus the
    hash-anchor line — a plan reviewer sees the actual RULES, not just a
    12-hex digest."""
    lines = [
        "## Grid constraint rules (frozen)", "",
        "| id | combo | verdict | rationale |",
        "|---|---|---|---|",
    ]
    for r in frozen.rules:
        combo_str = ", ".join("%s=%s" % (k, v) for k, v in sorted(r.combo.items()))
        lines.append("| %s | %s | %s | %s |" % (r.id, combo_str, r.verdict, r.rationale))
    lines.append("")
    lines.append(record_ruleset_hash_line(frozen))
    return "\n".join(lines)


# ------------------------------------------------------ --rules sidecar io ---

def dump_frozen_ruleset(frozen: FrozenRuleset) -> dict:
    """Serialize a ``FrozenRuleset`` to the ``--rules`` sidecar JSON shape
    (grid_engine.py) -- ``{universal: [...], local: [...], frozen_at,
    ruleset_hash}``. Symmetric with ``load_frozen_ruleset`` below."""
    universal = [
        {"id": r.id, "combo": dict(r.combo), "verdict": r.verdict,
         "rationale": r.rationale, "version": r.version}
        for r in frozen.rules if isinstance(r, UniversalRule)
    ]
    local = [
        {"id": r.id, "combo": dict(r.combo), "verdict": r.verdict,
         "rationale": r.rationale, "source": r.source, "derived_from": r.derived_from}
        for r in frozen.rules if isinstance(r, LocalRule)
    ]
    return {
        "universal": universal,
        "local": local,
        "frozen_at": frozen.frozen_at,
        "ruleset_hash": frozen.ruleset_hash,
    }


def load_frozen_ruleset(path) -> FrozenRuleset:
    """Load + tamper-check a ``--rules`` sidecar (the runtime counterpart of
    ``dump_frozen_ruleset``). Rebuilds ``UniversalRule``/``LocalRule`` entries,
    re-freezes them, then requires the recomputed ``ruleset_hash`` to match
    the stored one -- a sidecar hand-edited after freeze fails CLOSED (raises
    ``MalformedConstraintRuleError``), never silently trusting the stored
    hash (mirrors ``verify_na_points_to_frozen_rule``'s hash-mismatch check)."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise MalformedConstraintRuleError("frozen-ruleset sidecar %r unreadable: %s" % (path, exc)) from exc
    except ValueError as exc:
        raise MalformedConstraintRuleError("frozen-ruleset sidecar %r is not valid JSON: %s" % (path, exc)) from exc
    if not isinstance(raw, dict):
        raise MalformedConstraintRuleError("frozen-ruleset sidecar %r is not a JSON object" % path)

    universal: List[UniversalRule] = []
    for entry in raw.get("universal") or []:
        if not isinstance(entry, dict) or "id" not in entry or not isinstance(entry.get("combo"), dict):
            raise MalformedConstraintRuleError("universal rule entry missing id/combo: %r" % entry)
        universal.append(UniversalRule(
            id=entry["id"], combo=dict(entry["combo"]),
            verdict=entry.get("verdict", "forbidden"), rationale=entry.get("rationale", ""),
            version=entry.get("version", 1),
        ))
    local: List[LocalRule] = []
    for entry in raw.get("local") or []:
        if not isinstance(entry, dict) or "id" not in entry or not isinstance(entry.get("combo"), dict):
            raise MalformedConstraintRuleError("local rule entry missing id/combo: %r" % entry)
        local.append(LocalRule(
            id=entry["id"], combo=dict(entry["combo"]),
            verdict=entry.get("verdict", "forbidden"), rationale=entry.get("rationale", ""),
            source=entry.get("source", "plan-preflight"), derived_from=entry.get("derived_from", ""),
        ))

    stored_hash = raw.get("ruleset_hash")
    frozen = freeze_ruleset(universal, local, frozen_at=raw.get("frozen_at"))
    if not stored_hash or frozen.ruleset_hash != stored_hash:
        raise MalformedConstraintRuleError(
            "frozen-ruleset sidecar %r tamper-check failed: recomputed hash %r != stored %r"
            % (path, frozen.ruleset_hash, stored_hash)
        )
    return frozen


def extract_ruleset_hash_from_plan(plan_md_text: str) -> Optional[str]:
    """The ``grid_ruleset_hash:`` value actually anchored in ``plan_md_text``,
    or ``None`` when no such line exists. Normalizes IDENTICALLY to
    ``plan_approval.plan_hash`` (strip frontmatter + ``## Phases``) first — a
    hash line placed in either stripped region is invisible to ``plan_hash``
    and therefore does not freeze anything, so it must not count as an
    anchor either. This is the shared primitive behind
    ``verify_ruleset_hash_matches_plan`` (which compares against a known
    ``FrozenRuleset``) and ``grid_emit_guard._ruleset_mark_ok`` (which
    compares against an emitted record's self-reported ``ruleset_hash`` mark
    — the second layer of the anchor check, closing the hole where a
    well-shaped mark could name a hash frozen nowhere at all)."""
    stripped = _FRONTMATTER_RE.sub("", plan_md_text, count=1)
    stripped = _PHASES_SECTION_RE.sub("", stripped, count=1)
    m = _HASH_LINE_RE.search(stripped)
    return m.group(1) if m else None


def verify_ruleset_hash_matches_plan(frozen: FrozenRuleset, plan_md_text: str) -> bool:
    """Normalize ``plan_md_text`` IDENTICALLY to ``plan_approval.plan_hash``
    (strip frontmatter + ``## Phases``) before matching the
    ``grid_ruleset_hash:`` line — a hash line placed in either stripped
    region is invisible to ``plan_hash`` and therefore does not freeze
    anything; placing it there must FAIL, not silently pass."""
    anchored = extract_ruleset_hash_from_plan(plan_md_text)
    return anchored is not None and anchored == frozen.ruleset_hash
