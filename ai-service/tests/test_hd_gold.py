from __future__ import annotations

import json
import re
from pathlib import Path

from app.pipeline.ai1_ingest import ingest_files
from app.pipeline.idp import run_idp

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "fixtures" / "gold" / "hd_tong_hop_findings.json").read_text(encoding="utf-8"))


def _norm(value: str) -> str:
    compact = value.replace(" ", "").replace(",", ".")
    if re.fullmatch(r"-?\d+(\.\d+)?%?", compact):
        return compact.rstrip("%")
    digits = re.sub(r"\D", "", value)
    return digits or compact


def _pair_values(job) -> list[tuple[str, str, str, frozenset[str]]]:
    facts = {f.fact_id: f for f in job.contribution.facts}
    out = []
    for x in job.contribution.candidates:
        left = facts.get(x.left_id)
        right = facts.get(x.right_id)
        if not left or not right:
            continue
        vals = frozenset({_norm(left.normalized_value or left.raw_value), _norm(right.normalized_value or right.raw_value)})
        out.append(
            (
                x.item_key or "",
                x.scope.value if x.scope else "",
                x.disposition.value if x.disposition else "",
                vals,
            )
        )
    return out


def test_hd_tong_hop_gold_two_source_findings():
    pdf = ROOT / "fixtures" / "contracts" / "HD-TONG-HOP.sample.pdf"
    rec, env, _meta, _blobs = ingest_files([(pdf.name, pdf.read_bytes(), "body")])
    job = run_idp(rec, env)
    assert job.contribution is not None
    got = _pair_values(job)
    for req in GOLD["required"]:
        want = frozenset(_norm(v) for v in req["values"])
        assert any(
            item == req["item_key"] and scope == req["scope"] and disp == req["disposition"] and vals == want
            for item, scope, disp, vals in got
        ), req
    for key in GOLD["forbidden_difference_keys"]:
        assert not any(item == key and disp == "COMPARABLE_DIFFERENCE" for item, _s, disp, _v in got)
    for a, b in GOLD["must_not_pair"]:
        banned = frozenset({_norm(a), _norm(b)})
        assert not any(vals == banned for _i, _s, _d, vals in got)
    for x in job.contribution.candidates:
        assert x.finding_type.value != "LEGAL_WINNER"
        assert len(x.evidence_left) == 1 and len(x.evidence_right) == 1
