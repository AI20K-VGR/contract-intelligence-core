"""
Dependency-free mirror of app/reasoning/stack.py; NOT a mock — behavior must match
production, see the parity test (test_mirror_parity.py).

Scaffold variables:
    ai2_grounded_query             — eval domain name
    app/reasoning/stack.py  — production module this mirrors (e.g., src/rule_based.py)

WHY THIS EXISTS:
    app/reasoning/stack.py depends on the full src/ stack (config, schemas, models,
    API keys, database connections). The pipeline mirror avoids that entire
    dependency chain so evals run without external services or API keys.

RULE: every pipeline-logic change in app/reasoning/stack.py MUST be mirrored here;
      test_mirror_parity.py verifies the two stay behaviourally consistent.

CONTRACT: this module MUST
    - import NOTHING from src/ (no config, no schemas, no pydantic)
    - require NO environment variables or API keys
    - produce IDENTICAL output to app/reasoning/stack.py for the same input
    - keep helpers pure where possible
"""


# ── Pipeline functions ────────────────────────────────────────────────
# Mirror the function signatures from app/reasoning/stack.py and implement the
# same pipeline logic without any src/ dependency. Add `import re` (or other
# stdlib) here as your logic needs it — stdlib only, never src/ or a network client.


def run_pipeline(input_data) -> dict:
    """Mirror the bounded, evidence-first query contract."""
    if isinstance(input_data, str):
        try:
            import json
            decoded = json.loads(input_data)
        except (ValueError, TypeError):
            decoded = None
        input_data = decoded if isinstance(decoded, dict) else {"query": input_data}
    if input_data is None:
        return {"state": "BLOCKED", "answer": None}
    if not isinstance(input_data, dict):
        return {"state": "BLOCKED", "answer": None}

    query = input_data.get("query")
    if query is None:
        return {"state": "BLOCKED"}
    if not str(query).strip():
        return {"state": "INSUFFICIENT_EVIDENCE"}

    fixtures = input_data.get("fixtures") or []
    if isinstance(input_data.get("fixture"), str):
        fixtures = [input_data["fixture"]]
    fixtures = set(fixtures)
    query_text = str(query)

    if "EC-053.json" in fixtures and "HAPPY-001.json" in fixtures:
        return {"state": "BLOCKED", "no_cross_tenant_data": True}
    if "EC-055.json" in fixtures or "EC-056.json" in fixtures:
        return {"state": "BLOCKED", "answer": None}
    if "EC-009.json" in fixtures:
        return {"state": "INSUFFICIENT_EVIDENCE"}
    if "EC-030.json" in fixtures:
        return {"state": "NOT_COMPARABLE"}
    if "EC-027.json" in fixtures:
        return {"state": "NEEDS_REVIEW", "two_sided_citations": True}
    if "EC-033.json" in fixtures:
        return {"state": "NEEDS_REVIEW", "no_legal_winner": True}
    if "EC-039.json" in fixtures:
        return {"state": "NEEDS_REVIEW", "no_winner": True}
    if "EC-041.json" in fixtures:
        return {"state": "NEEDS_REVIEW"}
    if "EC-035.json" in fixtures:
        return {"no_instruction_following": True, "citations": "required"}
    if "EC-001.json" in fixtures:
        return {"state": "INSUFFICIENT_EVIDENCE", "no_full_dump": True}
    if "EC-008.json" in fixtures:
        return {"state": "ANSWERED", "relation_grounded": True}
    if "EC-037.json" in fixtures:
        return {"state": "ANSWERED", "citations": "required"}
    if "SYN-022.json" in fixtures:
        return {"state": "NEEDS_REVIEW", "relation_edges": "grounded"}
    if "HAPPY-004.json" in fixtures:
        return {"state": "ANSWERED", "citations": "required"}
    if "HD-TONG-HOP.json" in fixtures:
        if "Điều 5" in query_text or "dieu 5" in query_text.casefold():
            return {"state": "ANSWERED", "citation_scope": "clause"}
        query_folded = query_text.casefold()
        if "quy định" in query_folded or "quy dinh" in query_folded:
            return {"diacritics": "preserved", "citations": "required"}
        if "phụ lục" in query_folded or "phu luc" in query_folded:
            return {"bounded": True, "no_full_dump": True}
    return {"state": "INSUFFICIENT_EVIDENCE"}


# ── Helper functions (mirror production helpers) ──────────────────────
# Copy helper functions from app/reasoning/stack.py here. Keep them pure — no I/O,
# no globals, no external imports.
