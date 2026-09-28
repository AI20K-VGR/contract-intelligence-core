from __future__ import annotations

import re
from hashlib import sha256

from app.contracts.models import Citation, Fact, ReviewState, TenantProfile, ToolEnvelope
from app.llm.client import NineRouterClient
from app.pipeline.grounding import GroundingGate
from app.pipeline.runtime import ProcessingRuntime
from app.tools.gateway import ToolGateway


class FactExtractor:
    def __init__(
        self,
        gateway: ToolGateway,
        llm: NineRouterClient | None = None,
        runtime: ProcessingRuntime | None = None,
    ) -> None:
        self.gateway = gateway
        self.llm = llm
        self.runtime = runtime
        self.gate = GroundingGate()

    def extract(self, envelope: ToolEnvelope, node_id: str, profile: TenantProfile) -> Fact:
        payload = self.gateway.call("get_node", envelope, node_id=node_id)
        text = payload["text"]
        citation = Citation(**payload["citation"])
        raw = payload.get("structured_value") or _first_value(text)
        normalized, provenance = self._normalize(raw, text, profile)
        sk = str(payload.get("structured_key") or "")
        item_key = sk.split(":", 1)[1] if sk.startswith("item:") else None
        anc = payload.get("ancestors") or []
        blob_anc = " ".join(str(a) for a in anc)
        annex_m = re.search(r"(?:phụ lục|phu luc)\s+(\d+)", blob_anc, re.I)
        source_role = "annex" if annex_m else "body"
        period = None
        mper = re.search(r"từ\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", text, re.I)
        if mper:
            period = mper.group(1)
        scope = sk.split(":", 1)[1] if sk.startswith("scope:") else None
        if item_key is None and sk.startswith("mst"):
            item_key = sk
        if item_key is None and not scope:
            mi = re.search(r"\bitem\s+([A-Za-z0-9]+)\b", text, re.I) or re.search(
                r"hạng mục\s+([A-Za-z0-9]+)", text, re.I
            )
            if mi:
                item_key = mi.group(1)
        fact = Fact(
            fact_id="fact_" + sha256(f"{node_id}:{envelope.pins.source_snapshot_digest}:{envelope.pins.extraction_version}".encode()).hexdigest()[:24],
            raw_value=raw,
            normalized_value=normalized,
            subject=_context_subject(anc, payload.get("raw_label")),
            role=None,
            unit=_guess_unit(raw, text),
            currency="VND" if _guess_unit(raw, text) == "VND" else ("USD" if _guess_unit(raw, text) == "USD" else None),
            citation=citation,
            provenance=provenance,
            review_state=ReviewState.NEEDS_REVIEW,
            item_key=item_key,
            period_start=period,
            source_role=source_role,  # type: ignore[arg-type]
            scope=scope or item_key,
            validity=f"PL{annex_m.group(1)}" if annex_m else None,
            condition=_fact_condition(text, item_key),
            tax_basis=_tax_basis(text),
            vat_basis=_tax_basis(text),
        )
        return self.gate.ground_fact(fact, source_text=text, profile=profile)

    def _normalize(self, raw: str, text: str, profile: TenantProfile) -> tuple[str | None, str]:
        alias = _alias_match(raw, profile)
        if alias:
            return alias, "L0"
        compact = raw.replace(" ", "").replace(",", ".")
        if re.fullmatch(r"-?\d+(\.\d+)?%?", compact):
            return compact.rstrip("%"), "L0"
        if "%" not in raw:
            digits = re.sub(r"[^\d]", "", raw)
            if digits and re.search(r"vnd|đồng", raw, re.I):
                return digits, "L0"
        phrase = _scale_phrase_norm(raw)
        if phrase:
            return phrase, "L0"
        if self.llm and (self.runtime is None or self.llm.configured()):
            if self.runtime is not None:
                data = self.runtime.complete_json(
                    self.llm,
                    "Normalize a contract field. Return JSON {normalized, unit}. Do not invent values. Keep the original meaning. No legal conclusion.",
                    f"raw={raw}\ncontext={text[:1500]}",
                )
            else:
                data = self.llm.complete_json(
                    "Normalize a contract field. Return JSON {normalized, unit}. Do not invent values. Keep the original meaning. No legal conclusion.",
                    f"raw={raw}\ncontext={text[:1500]}",
                )
            if not data:
                return None, "L0"
            norm = data.get("normalized")
            if norm is None:
                if self.runtime is not None:
                    self.runtime.add_issue("LLM_INVALID_OUTPUT", "normalization response omitted normalized")
                    self.runtime.fallback_count += 1
                return None, "L0"
            if norm is not None and not isinstance(norm, str):
                norm = str(norm)
            return norm, "L2"
        return None, "L0"


def _first_value(text: str) -> str:
    if ":" in text:
        return text.split(":", 1)[1].strip() or text.strip()
    return text.strip()[:200]


def _subject(ancestors: list[str]) -> str | None:
    return ancestors[-1] if ancestors else None


def _guess_unit(raw: str, text: str) -> str | None:
    blob = f"{raw} {text}".lower()
    if "%" in blob or "/ngày" in blob or "/ngay" in blob:
        return "percent"
    if re.search(r"\busd\b", blob):
        return "USD"
    if re.search(r"\bvnd\b", blob) or re.search(r"(?<!hợp )đồng\b", blob):
        return "VND"
    return None


def _context_subject(ancestors: list, raw_label: str | None) -> str | None:
    labels = [str(a) for a in ancestors if a] + ([str(raw_label)] if raw_label else [])
    for lab in reversed(labels):
        if re.match(r"^(Điều|ĐIỀU|Phụ lục|PHỤ LỤC|Phần)\b", lab):
            return lab[:80]
    return labels[-1][:80] if labels else None


def _tax_basis(text: str) -> str | None:
    low = text.lower()
    if "chưa vat" in low or "chưa bao gồm vat" in low or "chua vat" in low:
        return "ex_vat"
    if "gồm vat" in low or "bao gồm vat" in low or "incl" in low:
        return "incl_vat"
    return None


def _fact_condition(text: str, item_key: str | None) -> str | None:
    low = text.lower()
    if item_key and item_key.startswith("penalty"):
        if "xây lắp" in low or "xay lap" in low:
            return "construction"
        if "thiết bị" in low or "thiet bi" in low:
            return "equipment"
        if "chung" in low:
            return "general"
    return None


def _scale_phrase_norm(raw: str) -> str | None:
    """Only full scale phrases (một tỷ), not lone năm/một in running text."""
    low = raw.lower().strip()
    m = re.search(r"(một|hai|ba)\s+(tỷ|triệu|nghìn|ngìn)\b", low)
    if not m:
        return None
    n = {"một": "1", "hai": "2", "ba": "3"}[m.group(1)]
    scale = {"tỷ": "000000000", "triệu": "000000", "nghìn": "000", "ngìn": "000"}[m.group(2)]
    return n + scale


def _alias_match(raw: str, profile: TenantProfile) -> str | None:
    low = raw.lower()
    for canonical, aliases in profile.aliases.items():
        for a in [canonical, *aliases]:
            if a.lower() == low:
                return canonical
    return None
