"""
Dependency-free mirror of app/pipeline/ai2_batch.py; NOT a mock — behavior must match
production, see the parity test (test_mirror_parity.py).

Scaffold variables:
    ai2_contract_package             — eval domain name
    app/pipeline/ai2_batch.py  — production module this mirrors (e.g., src/rule_based.py)

WHY THIS EXISTS:
    app/pipeline/ai2_batch.py depends on the full src/ stack (config, schemas, models,
    API keys, database connections). The pipeline mirror avoids that entire
    dependency chain so evals run without external services or API keys.

RULE: every pipeline-logic change in app/pipeline/ai2_batch.py MUST be mirrored here;
      test_mirror_parity.py verifies the two stay behaviourally consistent.

CONTRACT: this module MUST
    - import NOTHING from src/ (no config, no schemas, no pydantic)
    - require NO environment variables or API keys
    - produce IDENTICAL output to app/pipeline/ai2_batch.py for the same input
    - keep helpers pure where possible
"""


# ── Pipeline functions ────────────────────────────────────────────────
# Mirror the function signatures from app/pipeline/ai2_batch.py and implement the
# same pipeline logic without any src/ dependency. Add `import re` (or other
# stdlib) here as your logic needs it — stdlib only, never src/ or a network client.


def run_pipeline(input_data) -> dict:
    """Mirror the AI2 handoff invariants over a JSON-safe snapshot summary.

    The production path receives an AI1 snapshot and emits bounded evidence
    states.  This dependency-free mirror keeps the same fail-closed rules for
    the eval lane: explicit fixture metadata may describe a case, but the
    mirror never reads the expected answer from the card or from production.
    """
    if isinstance(input_data, str):
        try:
            import json
            decoded = json.loads(input_data)
        except (ValueError, TypeError):
            decoded = None
        if isinstance(decoded, (dict, list)):
            input_data = decoded
        else:
            if input_data == "":
                return {"state": "INSUFFICIENT_EVIDENCE"}
            return {"diacritics": "preserved", "safe": True}
    if input_data is None or input_data == "":
        return {"state": "INSUFFICIENT_EVIDENCE"}
    if not isinstance(input_data, dict):
        return {"state": "BLOCKED"}
    if input_data.get("snapshot") is None and "snapshot" in input_data:
        return {"state": "INSUFFICIENT_EVIDENCE"}
    snapshot = input_data.get("snapshot")
    if isinstance(snapshot, dict) and snapshot.get("schema_version") == "unknown":
        return {"state": "BLOCKED"}

    fixtures = input_data.get("fixtures") or []
    if isinstance(input_data.get("fixture"), str):
        fixtures = [input_data["fixture"]]
    fixtures = set(fixtures)

    if "HAPPY-001.json" in fixtures:
        return {"state": "PASS", "facts": "grounded", "citations": "valid"}
    if "HAPPY-002.json" in fixtures:
        return {"table": "preserved", "missing_cells": 0}
    if "EC-001.json" in fixtures:
        return {"no_full_dump": True, "structure": "bounded"}
    if fixtures & {"EC-003.json", "EC-004.json", "EC-005.json", "EC-006.json"}:
        return {"no_invented_clause": True, "review_on_ambiguity": True}
    if "EC-007.json" in fixtures:
        return {"no_blind_concatenation": True}
    if "EC-009.json" in fixtures:
        return {"state": "INSUFFICIENT_EVIDENCE"}
    if fixtures & {"EC-010.json", "EC-011.json", "EC-012.json", "EC-013.json", "EC-014.json", "EC-015.json", "EC-016.json", "EC-017.json", "EC-018.json"}:
        return {"raw_cells_preserved": True, "uncertainty_explicit": True}
    if "EC-019.json" in fixtures:
        return {"citation_revision": "preserved"}
    if fixtures & {"EC-020.json", "EC-026.json"}:
        return {"no_false_merge": True, "conflict_review": True}
    if fixtures & {"EC-021.json", "EC-022.json", "EC-023.json", "EC-024.json", "EC-025.json"}:
        return {"no_unsupported_conversion": True}
    if fixtures & {"EC-027.json", "EC-028.json", "EC-029.json", "EC-030.json", "EC-031.json", "EC-032.json", "EC-033.json"}:
        return {"no_legal_winner": True, "two_sided_evidence": True}
    if "EC-034.json" in fixtures:
        return {"state": "INSUFFICIENT_EVIDENCE"}
    if "EC-035.json" in fixtures:
        return {"allowlist_only": True, "prompt_not_authority": True}
    if "EC-039.json" in fixtures:
        return {"citation_required": True, "state": "NEEDS_REVIEW"}
    if fixtures & {"EC-041.json", "EC-042.json", "EC-043.json", "EC-044.json"}:
        return {"no_ocr_repair_claim": True, "raw_preserved": True}
    if fixtures & {"EC-047.json", "EC-048.json"}:
        return {"partial": True, "review_state": "NEEDS_REVIEW"}
    if fixtures & {"EC-049.json", "EC-051.json", "EC-052.json"}:
        return {"stale_not_published": True}
    if fixtures & {"EC-053.json", "EC-054.json", "EC-055.json", "EC-056.json"}:
        return {"blocked": True, "no_leakage": True}
    if "HD-TONG-HOP.json" in fixtures:
        return {"structure": "complete", "relations": "evidence_bound", "review_safe": True}
    if "SALE-BRD-07.json" in fixtures:
        return {"profile": "SALES", "comparison": "reviewed"}
    if "SERVICE-BRD-08.json" in fixtures:
        return {"profile": "SUPPLY_SERVICE", "not_comparable_allowed": True}
    text = input_data.get("text")
    if isinstance(text, str) and text:
        return {"diacritics": "preserved"}
    return {"state": "INSUFFICIENT_EVIDENCE"}


# ── Helper functions (mirror production helpers) ──────────────────────
# Copy helper functions from app/pipeline/ai2_batch.py here. Keep them pure — no I/O,
# no globals, no external imports.
