"""Minimal "AI2" layer on top of an ai1.snapshot.v1 DocumentSnapshot: document
classification, clause structure (Dieu -> Khoan -> Diem), typed facts with
citations and a confidence signal, and a contract-vs-N-appendix comparison.
Shared by scripts/demo_ai2_pipeline.py (CLI) and contract_ocr.web.app (the
`/api/ai2/analyze` backend endpoint) so both surfaces run the exact same
extraction logic instead of drifting apart.

See scripts/demo_ai2_pipeline.py's module docstring for how this maps to (and
deliberately simplifies) docs/architecture.md sections 5-9 and 27 — that
docstring is the canonical explanation of the design tradeoffs; this module is
just where the code moved to so a second caller (the web API) could reuse it.
"""

import re
import unicodedata

from contract_ocr.domain.snapshot import DocumentSnapshot, SnapshotLine, SnapshotPage


def fold_diacritics(text: str) -> str:
    """Best-effort ASCII fold so the fixed regexes below also match real
    Vietnamese text ("Điều"/"đồng"/"ngày"), not just ASCII fixtures. `đ`/`Đ`
    don't decompose under NFKD (they're distinct letters, not d+stroke), so
    they're replaced by hand first; every other diacritic is removed via NFKD
    + stripping combining marks. This is 1:1 in length with the input for
    normally-composed (NFC) PDF text, which is what PyMuPDF's `get_text()`
    returns in practice — so match.start()/.end() on the folded string can be
    used directly to slice the *original* string when a citation needs the
    real, accented quote."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# Three heading levels, matching architecture.md section 8.1's node types
# (article/clause/point). ARTICLE_RE only fires on a literal "Dieu N."/"Muc N.";
# CLAUSE_RE/POINT_RE only get a chance once we're already inside an article
# (see extract_clauses), otherwise an ordinary sentence that happens to start
# with "1. " or "a) " in the preamble would be misread as a heading — a real
# risk with this kind of fixed-regex demo layer, not eliminated, just fenced.
ARTICLE_RE = re.compile(r"^(Dieu|Muc)\s+(\d+)\.?\s*(.*)$")
CLAUSE_RE = re.compile(r"^(?:Khoan\s+)?(\d+)\.\s*(.*)$")
POINT_RE = re.compile(r"^([a-zA-Z])\)\s*(.*)$")

# Field set matches architecture.md section 27.11's Sprint-1 MVP list ("parties,
# amount, date, payment term"). Party names use a dedicated regex (PARTY_RE)
# instead of this list because the field name ("party_a" vs "party_b") comes
# from a captured group, not a fixed string like the others.
FACT_PATTERNS = [
    (
        "money",
        "contract_value",
        re.compile(r"\d{1,3}(?:[.,]\d{3})+\s*(?:VND|dong)", re.IGNORECASE),
    ),
    (
        "duration_days",
        "payment_term_days",
        re.compile(r"trong\s+vong\s+(\d+)\s*ngay", re.IGNORECASE),
    ),
    (
        "date",
        "signing_date",
        re.compile(r"\d{1,2}/\d{1,2}/\d{4}"),
    ),
]
PARTY_RE = re.compile(r"^Ben\s+([AB])\s*[:\-]\s*(.+)$")

# Very small stand-in for architecture.md section 27.2's "Classification"
# output (contract/appendix/other + confirmed/needs_review): first-page
# keyword sniffing, nowhere near the real evidence-based classifier in the
# full design, but enough to show the output shape in this demo.
CLASSIFICATION_KEYWORDS = [("PHU LUC", "appendix"), ("HOP DONG", "contract")]


def classify_document(snapshot: DocumentSnapshot) -> dict:
    first_page_text = fold_diacritics(snapshot.pages[0].text).upper() if snapshot.pages else ""
    for keyword, role in CLASSIFICATION_KEYWORDS:
        if keyword in first_page_text:
            return {"predicted_role": role, "status": "confirmed", "evidence": keyword}
    return {"predicted_role": "other", "status": "needs_review", "evidence": None}


def extract_clauses(snapshot: DocumentSnapshot) -> list[dict]:
    """Builds a 4-level structure: preamble (before any "Dieu N."/"Muc N.",
    where parties/signing date usually live — an earlier version dropped
    these lines entirely, silently losing the fields section 27.11 asks for)
    -> article -> clause -> point, each clause dict carrying `parent_clause_id`
    so callers can reconstruct the tree. Every line ends up in exactly one of
    these; nothing is dropped."""
    # BuildSnapshot has already run the text-first boundary detector. Reuse
    # those nodes instead of deriving content again from positioned lines (a
    # second derivation would lose OCR lines for which geometry is absent).
    if snapshot.nodes:
        return [
            {
                "clause_id": node.node_id,
                "level": node.type.lower(),
                "label": node.label_raw or node.label_normalized,
                "title": node.label_normalized,
                "parent_clause_id": node.parent_id,
                "page_number": node.page_start,
                "text": node.text,
                "line_ids": list(node.line_ids),
                "regions": [region.model_dump() for region in node.regions],
            }
            for node in snapshot.nodes
        ]

    clauses: list[dict] = []
    counter = 0

    def start_clause(
        level: str, label: str, title: str, parent_id: str | None, page_number: int
    ) -> dict:
        nonlocal counter
        counter += 1
        clause = {
            "clause_id": f"{snapshot.document_id}:clause-{counter}",
            "level": level,
            "label": label,
            "title": title,
            "parent_clause_id": parent_id,
            "page_number": page_number,
            "line_ids": [],
        }
        clauses.append(clause)
        return clause

    first_page_number = snapshot.pages[0].page_number if snapshot.pages else 1
    preamble = start_clause(
        "preamble", "Mo dau", "Truoc dieu khoan dau tien (ben, ngay ky...)", None, first_page_number
    )
    active = preamble
    current_article: dict | None = None
    current_clause: dict | None = None

    for page in snapshot.pages:
        for line in page.lines:
            folded = fold_diacritics(line.text)
            article_match = ARTICLE_RE.match(folded)
            clause_match = (
                CLAUSE_RE.match(folded) if current_article and not article_match else None
            )
            point_match = (
                POINT_RE.match(folded)
                if current_article and not article_match and not clause_match
                else None
            )

            if article_match:
                current_article = start_clause(
                    "article",
                    f"{line.text[article_match.start(1) : article_match.end(1)]} {article_match.group(2)}",
                    line.text[article_match.start(3) : article_match.end(3)].strip(),
                    None,
                    page.page_number,
                )
                current_clause = None
                active = current_article
            elif clause_match:
                current_clause = start_clause(
                    "clause",
                    f"Khoan {clause_match.group(1)}",
                    line.text[clause_match.start(2) : clause_match.end(2)].strip(),
                    current_article["clause_id"],
                    page.page_number,
                )
                active = current_clause
            elif point_match:
                parent = current_clause or current_article
                active = start_clause(
                    "point",
                    f"Diem {point_match.group(1).lower()}",
                    line.text[point_match.start(2) : point_match.end(2)].strip(),
                    parent["clause_id"],
                    page.page_number,
                )
            active["line_ids"].append(line.line_id)

    return [c for c in clauses if c["line_ids"]]


def _line_lookup(snapshot: DocumentSnapshot) -> dict[str, tuple[SnapshotPage, SnapshotLine]]:
    return {line.line_id: (page, line) for page in snapshot.pages for line in page.lines}


def _word_envelope(page: SnapshotPage, line: SnapshotLine, start: int, end: int):
    words_by_id = {w.word_id: w for w in page.words}
    words = [
        words_by_id[word_id]
        for word_id in line.word_ids
        if words_by_id[word_id].line_char_end > start and words_by_id[word_id].line_char_start < end
    ]
    if not words:
        return None, []
    x0 = min(w.bbox_normalized[0] for w in words)
    y0 = min(w.bbox_normalized[1] for w in words)
    x1 = max(w.bbox_normalized[2] for w in words)
    y1 = max(w.bbox_normalized[3] for w in words)
    return [x0, y0, x1, y1], [w.word_id for w in words]


def _citation(
    snapshot: DocumentSnapshot, page: SnapshotPage, line: SnapshotLine, start: int, end: int
) -> dict:
    bbox, word_ids = _word_envelope(page, line, start, end)
    anchor_precision = "word" if bbox else "line"
    return {
        "citation_id": f"cit-{snapshot.document_id}-{line.line_id}-{start}",
        "schema_version": "1.0",
        "document_id": snapshot.document_id,
        "document_role": snapshot.document_role,
        "document_sha256": snapshot.source_digest,
        "extraction_revision_id": snapshot.snapshot_id,
        "segments": [
            {
                "page_number": page.page_number,
                "line_id": line.line_id,
                "char_start": start,
                "char_end": end,
                "quote": line.text[start:end],
                "word_ids": word_ids,
                "bbox": bbox or line.bbox_normalized,
                "coordinate_space": "canonical_normalized",
                "anchor_precision": anchor_precision,
            }
        ],
        "validation_status": "valid",
    }


def _fact_confidence(anchor_precision: str) -> dict:
    """Signals, not a fabricated probability — architecture.md section 27.8 is
    explicit that an unexplained `confidence=0.98` shouldn't be read as 98%
    accurate. `score` stays null/uncalibrated; review_priority is the only
    thing meant to drive UI behavior."""
    is_word = anchor_precision == "word"
    return {
        "score": None,
        "calibrated": False,
        "calibration_version": None,
        "signals": {
            "source_resolved": True,
            "span_exact_match": True,
            "anchor_precision_word": is_word,
        },
        "review_priority": "low" if is_word else "medium",
        "reason_codes": [] if is_word else ["LINE_LEVEL_ANCHOR_ONLY"],
    }


def _finding_confidence(is_match: bool, contract_fact: dict, annex_fact: dict) -> dict:
    fact_priorities = {
        contract_fact["confidence"]["review_priority"],
        annex_fact["confidence"]["review_priority"],
    }
    reason_codes = []
    if not is_match:
        reason_codes.append("VALUE_MISMATCH")
    if "medium" in fact_priorities:
        reason_codes.append("LINE_LEVEL_ANCHOR_ONLY")
    # A difference always gets reviewed regardless of how clean the anchors
    # were — section 27.8: "Critical money/date/MST co disagreement luon
    # review du heuristic score cao."
    review_priority = "high" if not is_match else ("medium" if fact_priorities - {"low"} else "low")
    return {
        "score": None,
        "calibrated": False,
        "calibration_version": None,
        "review_priority": review_priority,
        "reason_codes": reason_codes,
    }


def _normalize_fact(fact_type: str, raw: str, match: re.Match) -> dict:
    if fact_type == "money":
        digits = re.match(r"[\d.,]+", raw)
        amount = digits.group(0).replace(".", "").replace(",", "") if digits else ""
        return {"amount": amount, "currency": "VND"}
    if fact_type == "duration_days":
        return {"days": int(match.group(1))}
    # "date": kept as the raw matched string, not parsed into ISO — dd/mm/yyyy
    # vs mm/dd/yyyy is genuinely ambiguous without a locale, and
    # architecture.md section 8.3 explicitly warns against guessing that.
    return {"raw": raw}


def extract_facts(snapshot: DocumentSnapshot, clauses: list[dict]) -> list[dict]:
    lines_by_id = _line_lookup(snapshot)
    facts = []
    for clause in clauses:
        for line_id in clause["line_ids"]:
            page, line = lines_by_id[line_id]
            folded = fold_diacritics(line.text)
            context = {
                "clause_id": clause["clause_id"],
                "clause_label": clause["label"],
                "clause_title": clause["title"],
            }

            for fact_type, field_name, pattern in FACT_PATTERNS:
                match = pattern.search(folded)
                if not match:
                    continue
                # Sliced from the original (not folded) text so the quote and
                # displayed raw value keep real Vietnamese diacritics.
                raw = line.text[match.start() : match.end()]
                citation = _citation(snapshot, page, line, match.start(), match.end())
                facts.append(
                    {
                        "fact_id": f"fact-{snapshot.document_id}-{field_name}",
                        "type": fact_type,
                        "field": field_name,
                        "raw": raw,
                        "normalized": _normalize_fact(fact_type, raw, match),
                        "context": context,
                        "citation": citation,
                        "confidence": _fact_confidence(citation["segments"][0]["anchor_precision"]),
                        "human_correction": None,
                    }
                )

            party_match = PARTY_RE.match(folded)
            if party_match:
                field_name = f"party_{party_match.group(1).lower()}"
                raw = line.text[party_match.start(2) : party_match.end(2)].strip()
                citation = _citation(snapshot, page, line, party_match.start(2), party_match.end(2))
                facts.append(
                    {
                        "fact_id": f"fact-{snapshot.document_id}-{field_name}",
                        "type": "party",
                        "field": field_name,
                        "raw": raw,
                        "normalized": {"name": raw},
                        "context": context,
                        "citation": citation,
                        "confidence": _fact_confidence(citation["segments"][0]["anchor_precision"]),
                        "human_correction": None,
                    }
                )
    return facts


def compare_facts(contract_facts: list[dict], annex_facts: list[dict]) -> list[dict]:
    """Candidate generation here is "same field name" instead of the
    keyword/embedding retrieval in architecture.md section 9.2 — fine with two
    documents and a handful of facts each, not a stand-in for the real thing
    at scale."""
    by_field = {f["field"]: f for f in annex_facts}
    findings = []
    for contract_fact in contract_facts:
        annex_fact = by_field.get(contract_fact["field"])
        if annex_fact is None:
            continue
        is_match = contract_fact["normalized"] == annex_fact["normalized"]
        findings.append(
            {
                "finding_id": f"finding-{contract_fact['field']}",
                "comparison_kind": "structured",
                "scope": "contract_annex",
                "topic": contract_fact["field"],
                "disposition": "comparable_match" if is_match else "comparable_difference",
                "rationale": (
                    f"'{contract_fact['field']}' khop giua hop dong va phu luc."
                    if is_match
                    else (
                        f"'{contract_fact['field']}' khac nhau: hop dong ghi "
                        f"'{contract_fact['raw']}', phu luc ghi '{annex_fact['raw']}'."
                    )
                ),
                "value_a": contract_fact["raw"],
                "value_b": annex_fact["raw"],
                "citations_a": [contract_fact["citation"]],
                "citations_b": [annex_fact["citation"]],
                "confidence": _finding_confidence(is_match, contract_fact, annex_fact),
            }
        )
    return findings


def compare_facts_multi(
    contract_facts: list[dict], annexes: list[tuple[str, str, list[dict]]]
) -> list[dict]:
    """Runs compare_facts() against each appendix independently (architecture.md
    section 9.2: comparison scope is contract-vs-one-annex, never annex-vs-annex
    implicitly) and tags every finding with which appendix it came from, so a
    dossier with several appendices doesn't collapse them into one ambiguous
    list. `annexes` is a list of (document_id, filename, facts)."""
    findings = []
    for document_id, filename, annex_facts in annexes:
        for finding in compare_facts(contract_facts, annex_facts):
            finding["annex_document_id"] = document_id
            finding["annex_filename"] = filename
            findings.append(finding)
    return findings
