"""Score AI2 facts, pairs, and citations against the approved case list.

Calls run_idp. Does not call the LLM. Does not replace evals/eval_config.json.
Exit 0 when the weighted score is at least the card threshold and every P0
check on the scored cases passes. Exit 1 when the pipeline misses. Exit 2
when a case file or import is missing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "ai-service"
CASES = ROOT / "evals" / "eval_types" / "ai2_fact_pair_citation" / "cases.json"
CARD = ROOT / "evals" / "cards" / "ai2_fact_pair_citation.json"


def _page(number: int, lines: list[str]) -> dict:
    return {
        "page_no": number,
        "input_type": "SCANNED_OCR",
        "status": "SUCCESS",
        "raw_text_digest": "b" * 64,
        "render": {},
        "transform": {"rotation_degrees": 0, "profile_version": "eval"},
        "lines": [
            {
                "line_id": f"p{number}:l{index}",
                "raw_text": text,
                "bbox": [0.1, min(0.9, 0.08 + index * 0.05), 0.9, min(0.95, 0.12 + index * 0.05)],
            }
            for index, text in enumerate(lines, start=1)
            if text.strip()
        ],
        "tables": [],
        "warnings": [],
        "text": "\n".join(lines),
    }


def _snapshot(name: str, pages: list[list[str]]) -> dict:
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": f"snap-{name}",
        "dossier_id": f"dos-{name}",
        "document_id": f"doc-{name}",
        "run_id": f"run-{name}",
        "source_digest": "c" * 64,
        "execution": {},
        "producer": {},
        "status": "SUCCESS",
        "pages": [_page(index, lines) for index, lines in enumerate(pages, start=1)],
    }


def _run(name: str, pages: list[list[str]]):
    from app.pipeline.ai1_snapshot_adapter import adapt_snapshot
    from app.pipeline.idp import run_idp
    from app.tools.store import InMemorySnapshotStore

    adapted = adapt_snapshot(_snapshot(name, pages))
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    return run_idp(adapted.record, adapted.envelope, store=store)


def _facts(job):
    contribution = job.contribution
    if contribution is None:
        return []
    return list(contribution.facts)


def _score_case(case: dict) -> dict:
    expect = case["expect"]
    checks: list[tuple[str, bool]] = []
    if case.get("snapshot", "present") is None:
        from app.pipeline.ai1_snapshot_adapter import (
            SnapshotContractError,
            adapt_snapshot,
        )

        blocked = False
        try:
            adapt_snapshot(None)
        except SnapshotContractError:
            blocked = True
        checks.append(("state", blocked))
        return {"case": case["case"], "checks": checks}

    job = _run(case["case"], case["pages"])
    facts = _facts(job)
    keys = sorted({fact.item_key for fact in facts if fact.item_key})
    if "fact_keys" in expect:
        wanted = expect["fact_keys"]
        if wanted == []:
            checks.append(("fact_keys", keys == []))
        else:
            checks.append(("fact_keys", set(wanted).issubset(keys)))
    if "normalized" in expect:
        for key, value in expect["normalized"].items():
            got = [fact.normalized_value for fact in facts if fact.item_key == key]
            checks.append((f"normalized:{key}", value in got))
    if expect.get("citation_line"):
        cited = [
            fact for fact in facts
            if fact.item_key and fact.citation and fact.citation.line_ids and fact.citation.text_span
        ]
        checks.append(("citation_line", bool(cited)))
    if "disposition" in expect:
        contribution = job.contribution
        candidates = contribution.candidates if contribution else []
        hit = any(item.disposition.value == expect["disposition"] for item in candidates)
        checks.append(("disposition", hit))
    if expect.get("relation"):
        findings = job.contribution.contract_context.findings if job.contribution else []
        hit = any(
            (item.metadata or {}).get("relation") == expect["relation"]
            for item in findings
        )
        checks.append(("relation", hit))
    if expect.get("no_legal_winner"):
        contribution = job.contribution
        reasons = " ".join(item.reason for item in (contribution.candidates if contribution else []))
        checks.append(("no_legal_winner", "không kết luận bên nào thắng" in reasons))
    return {"case": case["case"], "checks": checks}


def _dimension(rows: list[dict], names: set[str]) -> float:
    picked = [ok for row in rows for name, ok in row["checks"] if name.split(":")[0] in names or name in names]
    if not picked:
        return 100.0
    return 100.0 * sum(1 for ok in picked if ok) / len(picked)


def main() -> int:
    sys.path.insert(0, str(AI))
    if not CASES.is_file() or not CARD.is_file():
        print("ERROR: missing cases or card", file=sys.stderr)
        return 2
    card = json.loads(CARD.read_text(encoding="utf-8"))
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    rows = [_score_case(case) for case in payload["cases"]]
    fact = _dimension(rows, {"fact_keys", "normalized"})
    pair = _dimension(rows, {"disposition", "relation", "no_legal_winner"})
    cite = _dimension(rows, {"citation_line"})
    weights = card["dimensions"]
    score = (
        fact * weights["fact_accuracy"]
        + pair * weights["pair_disposition"]
        + cite * weights["citation_identity"]
    ) / 100.0
    print(f"fact_accuracy {fact:.1f}")
    print(f"pair_disposition {pair:.1f}")
    print(f"citation_identity {cite:.1f}")
    print(f"score {score:.1f} threshold {card['threshold']}")
    failed = False
    for row in rows:
        bad = [name for name, ok in row["checks"] if not ok]
        status = "PASS" if not bad else "FAIL " + ",".join(bad)
        print(f"{row['case']}: {status}")
        failed = failed or bool(bad)
    return 1 if failed or score < card["threshold"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
