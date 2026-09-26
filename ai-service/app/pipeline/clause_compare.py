"""Deterministic clause-level comparison between a contract body and its annex files.

The fact extractor only compares values that carry an ``item_key``.  Free-form
contract prose ("Thời gian thực hiện: 08 tuần") never gets one, so a dossier
made of a contract plus a separately uploaded annex used to produce zero
findings even when the annex openly rewrote several clauses.

This module rebuilds a light outline (``Điều N`` → ``N.x``) for every source
file, aligns articles across files by title, aligns sub-clauses by index, and
emits one ``COMPARABLE_DIFFERENCE`` candidate for every aligned pair whose
quantities (durations, percentages, amounts) differ.  Every candidate carries
exact, verifiable citations on both documents.  It never picks a legal
winner; the disposition is always a review request.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.contracts.models import (
    Candidate,
    Citation,
    ComparisonScope,
    Disposition,
    FindingType,
    ModelDisposition,
    PageSnapshot,
    ReviewState,
    StructuralNode,
)
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.citations import canonical_page_text, quote_digest
from app.tools.store import DossierRecord

ARTICLE_RE = re.compile(r"^dieu\s+(\d{1,3})\s*[.:\-]?\s*(.*)$")
SUB_RE = re.compile(r"^(\d{1,3})\.(\d{1,2})\s*[.,:\-]?\s+(.*)$")
ANNEX_HEADING_RE = re.compile(r"^phu\s+luc\s+(?:so\s*)?(\d+)\b")
SECTION_BREAK_RE = re.compile(r"^(?:dai\s+dien|chuong\s+[ivx\d]|phan\s+[ivx\d]|muc\s+\d)")
PAGE_FOOTER_RE = re.compile(r"^(?:trang\s+\d+|\d+\s*/\s*\d+|-\s*\d+\s*-|\d{1,3})$")
DOC_NUMBER_RE = re.compile(r"^(?:so\s*:?\s*)?\d+\s*/\s*\d{4}\s*/")
DATE_RE = re.compile(
    r"\b\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}\b"
    r"|\bngay\s+\d{1,2}\s+thang\s+\d{1,2}\s+nam\s+\d{4}\b"
    r"|\b(?:thang|nam)\s+\d{4}\b"
)
QUANTITY_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?:\s*\([^)]{0,40}\))?\s*"
    r"(%|phan\s+tram|tuan|thang|nam|ngay|gio|dong|vnd|usd)(?![a-z])"
)
REFERENCE_TAIL_RE = re.compile(r"^(?:cua|va|nay|tren|duoi|khoan|diem|,|\))")
# OCR lines per clause unit; longer runs are almost always a table or a new
# unlabelled section that the outline could not detect.
MAX_UNIT_LINES = 8
STOPWORDS = {
    "va", "cua", "ve", "cac", "trong", "cho", "den", "tu", "theo", "thi", "la", "co",
    "bi", "doi", "voi", "ben", "hop", "dong", "nay", "duoc", "khi", "de", "khac",
}
UNIT_LABEL = {
    "%": "%",
    "phan tram": "%",
    "tuan": "tuần",
    "thang": "tháng",
    "nam": "năm",
    "ngay": "ngày",
    "gio": "giờ",
    "dong": "đồng",
    "vnd": "đồng",
    "usd": "USD",
}


@dataclass
class _Line:
    page: PageSnapshot
    line_id: str
    text: str
    node: StructuralNode | None


@dataclass
class _Unit:
    """One comparable text unit: an article without sub-clauses, or one sub-clause."""

    article_number: int
    sub_index: int | None
    lines: list[_Line] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.sub_index is None:
            return f"Điều {self.article_number}"
        return f"Điều {self.article_number}.{self.sub_index}"

    def body_text(self) -> str:
        parts: list[str] = []
        for index, line in enumerate(self.lines):
            folded = fold_for_match(line.text).strip()
            if index == 0:
                match = SUB_RE.match(folded) if self.sub_index is not None else ARTICLE_RE.match(folded)
                folded = match.group(3 if self.sub_index is not None else 2) if match else folded
            parts.append(folded)
        return " ".join(parts)


@dataclass
class _Article:
    number: int
    title: str
    lines: list[_Line] = field(default_factory=list)
    subs: list[_Unit] = field(default_factory=list)

    def title_tokens(self) -> set[str]:
        return _tokens(fold_for_match(self.title))

    def all_text(self) -> str:
        own = " ".join(fold_for_match(line.text) for line in self.lines)
        return own + " " + " ".join(sub.body_text() for sub in self.subs)


@dataclass
class _Outline:
    file_id: str
    label: str
    articles: list[_Article]


def compare_clauses_across_files(record: DossierRecord) -> list[Candidate]:
    """Return review candidates for clause quantities that differ between body and annex files."""

    roles = {item.file_id: item.role for item in record.source_files}
    body_ids = [file_id for file_id, role in roles.items() if role == "body"]
    annex_ids = [file_id for file_id, role in roles.items() if role == "annex"]
    if not body_ids or not annex_ids:
        return []

    outlines = {file_id: _build_outline(record, file_id) for file_id in [*body_ids, *annex_ids]}
    candidates: list[Candidate] = []
    for body_id in body_ids:
        body = outlines[body_id]
        if not body.articles:
            continue
        for annex_id in annex_ids:
            annex = outlines[annex_id]
            if not annex.articles:
                continue
            for left_article, right_article in _align_articles(body.articles, annex.articles):
                for left_unit, right_unit in _align_units(left_article, right_article):
                    candidate = _compare_units(record, body, annex, left_article, left_unit, right_unit)
                    if candidate is not None:
                        candidates.append(candidate)
    return candidates


# --------------------------------------------------------------------------- outline


def _build_outline(record: DossierRecord, file_id: str) -> _Outline:
    pages = sorted(
        (page for page in record.pages if page.source_file_id == file_id),
        key=lambda item: item.page_number,
    )
    node_by_line: dict[tuple[str, str], StructuralNode] = {}
    for node in record.evidence_nodes():
        if node.source_file_id != file_id or len(node.source_line_ids) != 1:
            continue
        node_by_line.setdefault((node.page_revision_id or "", node.source_line_ids[0]), node)

    repeated = _repeated_lines(pages)
    lines: list[_Line] = []
    label = "Phụ lục"
    for page in pages:
        for line_id, text in page.line_texts.items():
            folded = fold_for_match(text).strip()
            if not folded:
                continue
            heading = ANNEX_HEADING_RE.match(folded)
            if heading and label == "Phụ lục":
                label = f"Phụ lục {heading.group(1)}"
            if _is_noise(folded, repeated):
                continue
            lines.append(_Line(page=page, line_id=line_id, text=text, node=node_by_line.get((page.page_revision_id, line_id))))

    articles: list[_Article] = []
    current: _Article | None = None
    current_sub: _Unit | None = None
    for line in lines:
        folded = fold_for_match(line.text).strip()
        article_match = _article_heading(line.text, folded)
        if article_match:
            current = _Article(number=int(article_match.group(1)), title=_title_from(line.text), lines=[line])
            current_sub = None
            articles.append(current)
            continue
        if current is None:
            continue
        if _is_section_break(line.text, folded):
            current = None
            current_sub = None
            continue
        sub_match = SUB_RE.match(folded)
        if sub_match and int(sub_match.group(1)) == current.number:
            current_sub = _Unit(article_number=current.number, sub_index=int(sub_match.group(2)), lines=[line])
            current.subs.append(current_sub)
            continue
        if current_sub is not None:
            if len(current_sub.lines) < MAX_UNIT_LINES:
                current_sub.lines.append(line)
        else:
            if not current.title and not current.subs:
                current.title = line.text.strip()
            if len(current.lines) < MAX_UNIT_LINES:
                current.lines.append(line)

    return _Outline(file_id=file_id, label=label, articles=articles)


def _repeated_lines(pages: list[PageSnapshot]) -> set[str]:
    seen: dict[str, set[int]] = {}
    for page in pages:
        for text in page.line_texts.values():
            folded = fold_for_match(text).strip()
            if len(folded) >= 4:
                seen.setdefault(folded, set()).add(page.page_number)
    return {text for text, numbers in seen.items() if len(numbers) >= 3}


def _is_noise(folded: str, repeated: set[str]) -> bool:
    if folded in repeated:
        return True
    if PAGE_FOOTER_RE.match(folded):
        return True
    if DOC_NUMBER_RE.match(folded):
        return True
    return False


def _article_heading(raw: str, folded: str) -> re.Match[str] | None:
    """Match ``Điều N`` only when the line is a heading, not a wrapped reference."""

    match = ARTICLE_RE.match(folded)
    if not match:
        return None
    stripped = raw.strip()
    if not stripped or not stripped[0].isupper():
        return None
    if REFERENCE_TAIL_RE.match(match.group(2)):
        return None
    return match


def _is_section_break(raw: str, folded: str) -> bool:
    if SECTION_BREAK_RE.match(folded):
        return True
    if ANNEX_HEADING_RE.match(folded):
        return _looks_like_heading(raw, min_words=2, max_len=80)
    # An all-caps title ("BẢNG DỮ LIỆU KIỂM THỬ", "PHẦN II") ends the running
    # article so that a following table is not read as clause prose.
    return _looks_like_heading(raw, min_words=3, max_len=100)


def _looks_like_heading(raw: str, *, min_words: int, max_len: int) -> bool:
    stripped = raw.strip()
    if len(stripped) > max_len or stripped[-1:] in {",", ";", ":"}:
        return False
    words = [word for word in re.split(r"\s+", stripped) if any(ch.isalpha() for ch in word)]
    if len(words) < min_words:
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    upper = sum(1 for ch in letters if ch.isupper())
    return bool(letters) and upper / len(letters) >= 0.8


def _title_from(raw: str) -> str:
    folded = fold_for_match(raw).strip()
    match = ARTICLE_RE.match(folded)
    if not match:
        return raw.strip()
    remainder = match.group(2)
    if not remainder:
        return ""
    # ``fold_for_match`` maps every Vietnamese character 1:1, so the folded
    # offset locates the same title inside the raw line.
    start = len(folded) - len(remainder)
    stripped = raw.strip()
    return stripped[start:].strip(" .:-") if len(stripped) == len(folded) else remainder


def _tokens(folded: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]+", folded) if token not in STOPWORDS and len(token) > 1}


# --------------------------------------------------------------------------- alignment


def _align_articles(left: list[_Article], right: list[_Article]) -> list[tuple[_Article, _Article]]:
    scored: list[tuple[float, int, int, int]] = []
    for left_index, left_article in enumerate(left):
        left_tokens = left_article.title_tokens()
        for right_index, right_article in enumerate(right):
            right_tokens = right_article.title_tokens()
            score = _containment(left_tokens, right_tokens)
            if score < 0.6:
                # Fall back to whole-article wording only when the numbering agrees.
                if left_article.number != right_article.number:
                    continue
                score = _jaccard(_tokens(left_article.all_text()), _tokens(right_article.all_text()))
                if score < 0.5:
                    continue
            same_number = 0 if left_article.number == right_article.number else 1
            scored.append((-score, same_number, left_index, right_index))
    scored.sort()
    used_left: set[int] = set()
    used_right: set[int] = set()
    pairs: list[tuple[_Article, _Article]] = []
    for _score, _same, left_index, right_index in scored:
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        pairs.append((left[left_index], right[right_index]))
    pairs.sort(key=lambda pair: (pair[0].number, pair[1].number))
    return pairs


def _align_units(left: _Article, right: _Article) -> list[tuple[_Unit, _Unit]]:
    if not left.subs and not right.subs:
        return [(_Unit(left.number, None, list(left.lines)), _Unit(right.number, None, list(right.lines)))]
    right_by_index = {unit.sub_index: unit for unit in right.subs}
    pairs: list[tuple[_Unit, _Unit]] = []
    used: set[int | None] = set()
    for unit in left.subs:
        partner = right_by_index.get(unit.sub_index)
        if partner is not None and _jaccard(_word_tokens(unit), _word_tokens(partner)) >= 0.25:
            pairs.append((unit, partner))
            used.add(partner.sub_index)
            continue
        best: tuple[float, _Unit] | None = None
        for other in right.subs:
            if other.sub_index in used:
                continue
            score = _jaccard(_word_tokens(unit), _word_tokens(other))
            if score >= 0.5 and (best is None or score > best[0]):
                best = (score, other)
        if best is not None:
            pairs.append((unit, best[1]))
            used.add(best[1].sub_index)
    return pairs


def _word_tokens(unit: _Unit) -> set[str]:
    return _tokens(unit.body_text())


def _containment(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


# --------------------------------------------------------------------------- comparison


def _quantities(folded_text: str) -> dict[str, list[tuple[float, str]]]:
    cleaned = DATE_RE.sub(" ", folded_text)
    values: dict[str, list[tuple[float, str]]] = {}
    for match in QUANTITY_RE.finditer(cleaned):
        raw_number, raw_unit = match.group(1), re.sub(r"\s+", " ", match.group(2))
        unit = UNIT_LABEL.get(raw_unit, raw_unit)
        number = _parse_number(raw_number)
        if number is None:
            continue
        values.setdefault(unit, []).append((number, _display_number(raw_number, unit)))
    return values


def _parse_number(raw: str) -> float | None:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
        return float(re.sub(r"[.,]", "", raw))
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _display_number(raw: str, unit: str) -> str:
    if unit == "%":
        return f"{raw}%"
    return f"{raw} {unit}"


def _compare_units(
    record: DossierRecord,
    body: _Outline,
    annex: _Outline,
    article: _Article,
    left: _Unit,
    right: _Unit,
) -> Candidate | None:
    left_values = _quantities(left.body_text())
    right_values = _quantities(right.body_text())
    differences: list[tuple[str, str]] = []
    for unit in left_values:
        if unit not in right_values:
            continue
        left_list = left_values[unit]
        right_list = right_values[unit]
        if sorted(value for value, _ in left_list) == sorted(value for value, _ in right_list):
            continue
        if len(left_list) == len(right_list):
            for (lv, ltext), (rv, rtext) in zip(left_list, right_list):
                if lv != rv:
                    differences.append((ltext, rtext))
        else:
            differences.append(
                (", ".join(text for _, text in left_list), ", ".join(text for _, text in right_list))
            )
    if not differences:
        return None

    left_citation = _unit_citation(left)
    right_citation = _unit_citation(right)
    if left_citation is None or right_citation is None:
        return None

    title = article.title.strip()
    topic = f"{left.label} · {title.capitalize()}" if title else left.label
    left_summary = "; ".join(item[0] for item in differences)
    right_summary = "; ".join(item[1] for item in differences)
    reason = (
        f"Nguồn 1 · Hợp đồng · {left.label}: {left_summary}  ↔  "
        f"Nguồn 2 · {annex.label} · {right.label}: {right_summary}. "
        "Giá trị khác nhau giữa thân hợp đồng và phụ lục; cần rà soát điều khoản hiệu lực, AI2 không kết luận bên nào thắng."
    )
    seed = f"{record.pins.source_snapshot_digest}|{left_citation.node_id}|{right_citation.node_id}"
    return Candidate(
        candidate_id="cand_clause_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12],
        left_id=left_citation.node_id,
        right_id=right_citation.node_id,
        finding_type=FindingType.COMPARABLE_DIFFERENCE,
        model_disposition=ModelDisposition.UNCLEAR,
        review_state=ReviewState.NEEDS_REVIEW,
        evidence_left=[left_citation],
        evidence_right=[right_citation],
        reason=reason,
        disposition=Disposition.COMPARABLE_DIFFERENCE,
        scope=ComparisonScope.CONTRACT_ANNEX,
        item_key=topic,
    )


def _unit_citation(unit: _Unit) -> Citation | None:
    """Cite the unit's lines on its first page with exact offsets and line ids."""

    if not unit.lines:
        return None
    page = unit.lines[0].page
    lines = [line for line in unit.lines if line.page is page]
    text = canonical_page_text(page)
    ranges: dict[str, tuple[int, int]] = {}
    cursor = 0
    for line_id, line_text in page.line_texts.items():
        start = text.find(line_text, cursor)
        if start < 0:
            continue
        ranges[line_id] = (start, start + len(line_text))
        cursor = start + len(line_text)
    covered = [line for line in lines if line.line_id in ranges]
    if not covered:
        return None
    start = ranges[covered[0].line_id][0]
    end = ranges[covered[-1].line_id][1]
    span = text[start:end]
    if not span.strip():
        return None
    node = covered[0].node
    bboxes = [page.line_bboxes.get(line.line_id) for line in covered]
    fragments = [list(box) for box in bboxes if box and len(box) == 4]
    bbox = _union(fragments)
    return Citation(
        node_id=node.node_id if node else f"page:{page.page_revision_id}",
        page_revision_id=page.page_revision_id,
        bbox=bbox,
        bbox_fragments=fragments if len(fragments) > 1 else [],
        text_span=span,
        source_file_id=page.source_file_id,
        page=page.page_number,
        page_range=[page.page_number],
        line_ids=[line.line_id for line in covered],
        char_start=start,
        char_end=end,
        source_hash=page.source_hash,
        quote_sha256=quote_digest(span),
        geometry_available=bool(bbox),
    )


def _union(boxes: list[list[float]]) -> list[float]:
    valid = [box for box in boxes if all(0 <= value <= 1 for value in box) and box[2] > box[0] and box[3] > box[1]]
    if not valid:
        return []
    return [
        min(box[0] for box in valid),
        min(box[1] for box in valid),
        max(box[2] for box in valid),
        max(box[3] for box in valid),
    ]
