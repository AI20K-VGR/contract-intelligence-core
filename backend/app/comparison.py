from app.domain import Disposition


def compare(facts):
    findings = []
    contract = [f for f in facts if f["source_role"] == "contract"]
    annex = [f for f in facts if f["source_role"] == "appendix"]
    for a in contract:
        for b in annex:
            if a["type"] != b["type"]:
                continue
            # Values alone do not establish subject/time/tax/trigger comparability.
            # This baseline intentionally abstains until context is verified.
            findings.append(
                {
                    "id": f"finding:{len(findings)}",
                    "topic": a["type"],
                    "disposition": Disposition.INSUFFICIENT.value,
                    "comparison_kind": "structured",
                    "scope": "contract_annex",
                    "fact_ids": [a["id"], b["id"]],
                    "rule_version": "local-v1",
                    "values_equal": a["normalized"] == b["normalized"],
                    "rationale": "Subject, effective period, unit and conditions require review.",
                    "citations_a": a["citation_ids"],
                    "citations_b": b["citation_ids"],
                }
            )
    return findings
