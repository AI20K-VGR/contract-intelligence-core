"""Score a saved ai1.snapshot.v1 against page-aligned ground truth — no API calls.

Built for the ground truth a contract generator writes (make_ground_truth.py):

    <ground-truth>/contract-text.pdf               text-layer twin of the scanned PDF, page for page
    <ground-truth>/documents/*.md                  one file per section, tables in Markdown
    <ground-truth>/contradictions/00-tong-hop.md   planted contradictions (value A / value B)

Scores, per page and per section:

- Text: CER, WER (raw and whitespace-normalized, as in benchmark_ocr_production.py), CER after
  unifying dash and quote variants, diacritic error rate, the most frequent word confusions.
- Critical fields found by regex on each ground-truth page (money, quantities, percentages,
  dates, contract and tax numbers) and retained on the same OCR page.
- Planted contradiction values retained on the pages the ground truth has them on: a value OCR
  loses is a conflict AI2 can never report.
- Tables: ground-truth rows aligned to the snapshot's table rows in document order.
- Structure: articles and main-contract clauses against the snapshot's nodes.
- Review flags and line confidence against the lines that really are wrong.

    python scripts/benchmark_snapshot.py \\
        --snapshot data/generated/rerun/<dossier>/test-contract.snapshot.json \\
        --ground-truth /path/to/test-contract-ground-truth \\
        --out reports/benchmark/test-contract
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pymupdf
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from contract_ocr.domain.entities import CriticalField
from contract_ocr.infrastructure.metrics.ocr_metrics import (
    OCRMetrics,
    base,
    critical_accuracy,
    nfc,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRADICTION_HEADING = "## Mâu thuẫn cố ý trong tài liệu này"
# A run this long missing from the OCR is lost text, not a misread word.
LOST_SPAN_CHARS = 40
_TYPOGRAPHY = str.maketrans(
    {"–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-", "“": '"', "”": '"', "‘": "'", "’": "'"}
)
_LINE_REF = re.compile(r"^([a-z_]+:[a-z_]+):(.+:p\d{3}:l\d{3})$")
_TABLE_ROW = re.compile(r"^\s*\|(.*)\|\s*$")
_TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# Critical fields: a number is never matched from inside a longer number.
_EDGE_BEFORE = r"(?<!\d)(?<!\d[.,])"
_EDGE_AFTER = r"(?!\d)(?![.,]\d)"
_MONEY = re.compile(
    _EDGE_BEFORE + r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?)" + _EDGE_AFTER + r"(\s?(?:đồng|VNĐ|VND))?"
)
_PERCENT = re.compile(_EDGE_BEFORE + r"(\d+(?:,\d+)?)\s?%")
_DATE = re.compile(r"(?<!\d)(\d{1,2}/\d{1,2}/\d{4})(?!\d)")
_CONTRACT_NUMBER = re.compile(r"(?<![\w/])(\d{1,5}/\d{4}/[^\s,;()]*[^\s,;().])")
_TAX_CODE = re.compile(r"(?:MST|[Mm]ã số thuế)\s*:?\s*(\d{10}(?:-\d{3})?)(?!\d)")

_ARTICLE = re.compile(r"(?m)^Điều (\d+)\.\s")
_CLAUSE = re.compile(r"(?m)^(\d{1,2}\.\d{1,2})\.\s")


def _norm(text: str) -> str:
    return " ".join(text.split())


def _typo(text: str) -> str:
    return _norm(nfc(text).translate(_TYPOGRAPHY))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.2f}%"


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _plain(text: str) -> str:
    """A Markdown table row as its cells, one per line, the way the text layer lists them.

    Snapshot lines of a table carry the engine's Markdown row (``| a | b |``); comparing
    the pipes against a text layer would score the notation, not the reading.
    """
    if _TABLE_RULE.match(text):
        return ""
    row = _TABLE_ROW.match(text)
    if not row:
        return text
    return "\n".join(c.strip() for c in re.split(r"(?<!\\)\|", row.group(1)) if c.strip())


def _ocr_text(page: dict) -> str:
    return "\n".join(
        text for text in (_plain(line["text"]) for line in page.get("lines") or []) if text
    )


# -- ground truth ------------------------------------------------------------------


def load_ground_truth_pages(folder: Path) -> list[str]:
    with pymupdf.open(folder / "contract-text.pdf") as pdf:
        return [page.get_text().strip() for page in pdf]


def load_sections(folder: Path) -> list[dict[str, Any]]:
    """Title (first '# ' heading) and body of every ground-truth Markdown section, in order."""
    sections = []
    for path in sorted((folder / "documents").glob("*.md")):
        text = path.read_text(encoding="utf-8").split(CONTRADICTION_HEADING)[0]
        title = text.splitlines()[0].removeprefix("# ").strip()
        sections.append({"file": path.name, "title": title, "text": text})
    return sections


def section_start_pages(pages: list[str], titles: list[str]) -> list[int | None]:
    """First page (1-based) where each title opens a line, searched in document order.

    The first section is the main contract and starts on page 1 whatever its title.
    """
    starts: list[int | None] = []
    cursor = 1
    for index, title in enumerate(titles):
        if index == 0:
            starts.append(1)
            continue
        key = _typo(title)[:24]
        found = next(
            (
                n
                for n in range(cursor, len(pages) + 1)
                if any(_typo(line).startswith(key) for line in pages[n - 1].splitlines())
            ),
            None,
        )
        starts.append(found)
        if found is not None:
            cursor = found
    return starts


def page_sections(page_count: int, starts: list[int | None]) -> list[int | None]:
    """Section index of every page: the last section that starts on or before it."""
    known = sorted((start, i) for i, start in enumerate(starts) if start is not None)
    owner: list[int | None] = []
    for n in range(1, page_count + 1):
        owner.append(next((i for start, i in reversed(known) if start <= n), None))
    return owner


def extract_critical_fields(text: str, page: int) -> list[CriticalField]:
    """Critical fields of one ground-truth page, the kinds §19 of the AI1 architecture scores."""
    fields = []
    for match in _MONEY.finditer(text):
        kind = "MONEY" if match.group(2) else "QUANTITY"
        fields.append(
            CriticalField(
                type=kind, value=match.group(1), raw_text=match.group(0).strip(), page=page
            )
        )
    for match in _PERCENT.finditer(text):
        fields.append(
            CriticalField(
                type="PERCENTAGE", value=match.group(1), raw_text=match.group(0), page=page
            )
        )
    for match in _DATE.finditer(text):
        fields.append(
            CriticalField(type="DATE", value=match.group(1), raw_text=match.group(1), page=page)
        )
    for match in _CONTRACT_NUMBER.finditer(text):
        number = match.group(1)
        fields.append(
            CriticalField(type="CONTRACT_NUMBER", value=number, raw_text=number, page=page)
        )
    for match in _TAX_CODE.finditer(text):
        code = match.group(1)
        fields.append(CriticalField(type="TAX_CODE", value=code, raw_text=code, page=page))
    return fields


def _markdown_cells(line: str) -> list[str]:
    inner = line.strip()[1:-1]
    cells = re.split(r"(?<!\\)\|", inner)
    return [c.replace("\\|", "|").replace("<br>", " ").replace("\\\\", "\\").strip() for c in cells]


def parse_markdown_tables(text: str) -> list[dict[str, list]]:
    """Header and rows of every pipe table, leaving out the planted-contradiction appendix."""
    lines = text.split(CONTRADICTION_HEADING)[0].splitlines()
    tables, i = [], 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and re.fullmatch(
            r"\|(?:\s*:?-{3,}:?\s*\|)+", lines[i + 1].strip()
        ):
            header, rows = _markdown_cells(lines[i]), []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_markdown_cells(lines[i]))
                i += 1
            tables.append({"header": header, "rows": rows})
        else:
            i += 1
    return tables


def load_contradictions(folder: Path) -> list[dict[str, str]]:
    path = folder / "contradictions" / "00-tong-hop.md"
    if not path.exists():
        return []
    tables = parse_markdown_tables(path.read_text(encoding="utf-8"))
    if not tables:
        return []
    keys = ["id", "topic", "ref_a", "value_a", "file_a", "ref_b", "value_b", "file_b"]
    return [dict(zip(keys, row, strict=False)) for row in tables[0]["rows"]]


# -- scoring -----------------------------------------------------------------------


def score_pages(
    snapshot: dict, gt_pages: list[str], owner: list[int | None], sections: list[dict]
) -> list[dict[str, Any]]:
    metrics = OCRMetrics()
    scored = []
    for page in snapshot["pages"]:
        n = page["page_number"]
        ref = gt_pages[n - 1] if n <= len(gt_pages) else ""
        hyp = _ocr_text(page)
        raw, norm = metrics.text(ref, hyp), metrics.text(_norm(ref), _norm(hyp))
        ref_t, hyp_t = _typo(ref), _typo(hyp)
        typo = Levenshtein.distance(ref_t, hyp_t) / max(1, len(ref_t))
        lost = lost_spans(ref_t, hyp_t)
        by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        missed = []
        for field in extract_critical_fields(ref, n):
            ok = critical_accuracy([field], hyp)["critical_field_correct"]
            by_type[field.type][0] += ok
            by_type[field.type][1] += 1
            if not ok:
                missed.append(f"{field.type}: {field.raw_text}")
        section = owner[n - 1] if n <= len(owner) else None
        scored.append(
            {
                "page": n,
                "section": sections[section]["file"] if section is not None and sections else None,
                "status": page.get("status"),
                "tables": len(page.get("tables") or []),
                "ref_chars": len(ref),
                "ref_words": len(ref.split()),
                "ref_chars_norm": len(_norm(ref)),
                "ref_words_norm": len(_norm(ref).split()),
                "ref_chars_typo": len(_typo(ref)),
                "cer": raw["cer"],
                "wer": raw["wer"],
                "cer_norm": norm["cer"],
                "wer_norm": norm["wer"],
                "cer_typo": typo,
                "diacritic_errors": raw["diacritic_errors"],
                "diacritic_aligned": raw["diacritic_aligned_letters"],
                "crit_by_type": dict(by_type),
                "crit_missed": missed,
                "review_flags": sum(
                    w.startswith("needs_review") for w in page.get("warnings") or []
                ),
                "lost_spans": lost,
                "unread_ink_warning": any("unread_ink" in w for w in page.get("warnings") or []),
            }
        )
    return scored


def lost_spans(ref: str, hyp: str, min_chars: int = LOST_SPAN_CHARS) -> list[dict[str, Any]]:
    """Runs of ground-truth text the OCR has nothing for: at least ``min_chars`` in one piece."""
    spans = []
    for op in Levenshtein.opcodes(ref, hyp):
        missing = (op.src_end - op.src_start) - (op.dest_end - op.dest_start)
        if op.tag in {"delete", "replace"} and missing >= min_chars:
            spans.append({"chars": missing, "text": ref[op.src_start : op.src_end][:200]})
    return spans


def aggregate(pages: list[dict]) -> dict[str, Any]:
    """Micro-averaged over pages, weighted by ground-truth length."""

    def weighted(metric: str, weight: str) -> float:
        total = sum(p[weight] for p in pages)
        return sum(p[metric] * p[weight] for p in pages) / total if total else 0.0

    aligned = sum(p["diacritic_aligned"] for p in pages)
    ok = sum(v[0] for p in pages for v in p["crit_by_type"].values())
    total = sum(v[1] for p in pages for v in p["crit_by_type"].values())
    return {
        "pages": len(pages),
        "cer": weighted("cer", "ref_chars"),
        "wer": weighted("wer", "ref_words"),
        "cer_norm": weighted("cer_norm", "ref_chars_norm"),
        "wer_norm": weighted("wer_norm", "ref_words_norm"),
        "cer_typo": weighted("cer_typo", "ref_chars_typo"),
        "diacritic": sum(p["diacritic_errors"] for p in pages) / aligned if aligned else None,
        "crit_ok": ok,
        "crit_total": total,
        "crit": ok / total if total else None,
        "review": sum(p["review_flags"] for p in pages),
    }


def word_confusions(ref: str, hyp: str) -> tuple[Counter, Counter]:
    """Word substitutions: those differing only in diacritics, and all the others."""
    r, h = _typo(ref).split(), _typo(hyp).split()
    accent: Counter = Counter()
    other: Counter = Counter()
    for op in Levenshtein.opcodes(r, h):
        if op.tag == "replace" and op.src_end - op.src_start == op.dest_end - op.dest_start:
            for a, b in zip(
                r[op.src_start : op.src_end], h[op.dest_start : op.dest_end], strict=True
            ):
                (accent if base(a) == base(b) else other)[(a, b)] += 1
    return accent, other


def score_contradictions(
    rows: list[dict[str, str]],
    snapshot: dict,
    gt_pages: list[str],
    owner: list[int | None],
    sections: list[dict],
) -> list[dict[str, Any]]:
    """Each planted value, looked up where the ground truth has it, then on the same OCR pages."""
    ocr_pages = {p["page_number"]: _typo(_ocr_text(p)) for p in snapshot["pages"]}
    gt_norm = [_typo(t).casefold() for t in gt_pages]
    file_index = {s["file"]: i for i, s in enumerate(sections)}
    results = []
    for row in rows:
        for side in ("a", "b"):
            value = row.get(f"value_{side}", "")
            needle = _typo(value).casefold()
            section = file_index.get(row.get(f"file_{side}", ""))
            candidates = [
                n for n in range(1, len(gt_pages) + 1) if section is None or owner[n - 1] == section
            ]
            pages = [n for n in candidates if needle in gt_norm[n - 1]] or [
                n for n in range(1, len(gt_pages) + 1) if needle in gt_norm[n - 1]
            ]
            retained = any(needle in ocr_pages.get(n, "").casefold() for n in pages)
            closest = ""
            if pages and not retained:
                page_text = ocr_pages.get(pages[0], "")
                hit = fuzz.partial_ratio_alignment(_typo(value), page_text)
                if hit is not None:
                    closest = page_text[hit.dest_start : hit.dest_end]
            results.append(
                {
                    "id": row.get("id"),
                    "topic": row.get("topic"),
                    "side": side.upper(),
                    "ref": row.get(f"ref_{side}"),
                    "value": value,
                    "pages": pages,
                    "evaluated": bool(pages),
                    "retained": retained,
                    "closest_ocr": closest,
                }
            )
    return results


def _row_key(cells: list[str]) -> str:
    return " ‖ ".join(_typo(c) for c in cells)


def align_table_rows(gt_rows: list[list[str]], ocr_rows: list[list[str]]) -> list[dict[str, Any]]:
    """Outcome of every ground-truth row: exact, changed (paired to an OCR row), or missing.

    Rows are aligned in document order; an OCR row left unpaired is reported as extra.
    """
    gt_keys, ocr_keys = [_row_key(r) for r in gt_rows], [_row_key(r) for r in ocr_rows]
    outcome: list[dict[str, Any]] = [{"state": "missing"} for _ in gt_rows]
    extra = 0
    matcher = difflib.SequenceMatcher(None, gt_keys, ocr_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                outcome[i] = {
                    "state": "exact",
                    "cells_ok": len(gt_rows[i]),
                    "cells": len(gt_rows[i]),
                }
        elif tag == "replace":
            for i, j in zip(range(i1, i2), range(j1, j2), strict=False):
                ok = sum(
                    _typo(a) == _typo(b) for a, b in zip(gt_rows[i], ocr_rows[j], strict=False)
                )
                outcome[i] = {
                    "state": "changed",
                    "cells_ok": ok,
                    "cells": len(gt_rows[i]),
                    "gt": gt_keys[i],
                    "ocr": ocr_keys[j],
                }
            extra += max(0, (j2 - j1) - (i2 - i1))
        elif tag == "insert":
            extra += j2 - j1
    if outcome:
        outcome[0]["extra_ocr_rows"] = extra
    return outcome


def score_tables(sections: list[dict], snapshot: dict) -> dict[str, Any]:
    gt_tables = [
        {"section": s["file"], "index": k, **t}
        for s in sections
        for k, t in enumerate(parse_markdown_tables(s["text"]))
    ]
    gt_rows, row_table = [], []
    for t_index, table in enumerate(gt_tables):
        for row in table["rows"]:
            gt_rows.append(row)
            row_table.append(t_index)
    # A header repeated on a continuation page is not a data row, whether or not
    # the snapshot recognized it as that page's header.
    headers = {_row_key(t["header"]) for t in gt_tables}
    ocr_rows, ocr_tables = [], 0
    for page in snapshot["pages"]:
        for table in page.get("tables") or []:
            ocr_tables += 1
            page_header = _row_key(table.get("header") or [])
            for row in table.get("rows") or []:
                cells = [c.get("text", "") for c in row.get("cells") or []]
                if _row_key(cells) not in headers | {page_header}:
                    ocr_rows.append(cells)
    outcome = align_table_rows(gt_rows, ocr_rows)
    per_table = []
    for t_index, table in enumerate(gt_tables):
        rows = [o for o, t in zip(outcome, row_table, strict=True) if t == t_index]
        states = Counter(o["state"] for o in rows)
        cells = sum(len(r) for r in table["rows"])
        per_table.append(
            {
                "section": table["section"],
                "index": table["index"],
                "header": table["header"],
                "rows": len(rows),
                "exact": states["exact"],
                "changed": states["changed"],
                "missing": states["missing"],
                "cell_accuracy": sum(o.get("cells_ok", 0) for o in rows) / cells if cells else None,
            }
        )
    states = Counter(o["state"] for o in outcome)
    cells = sum(len(r) for r in gt_rows)
    return {
        "gt_tables": len(gt_tables),
        "gt_rows": len(gt_rows),
        "ocr_tables": ocr_tables,
        "ocr_rows": len(ocr_rows),
        "exact": states["exact"],
        "changed": states["changed"],
        "missing": states["missing"],
        "extra": outcome[0].get("extra_ocr_rows", 0) if outcome else len(ocr_rows),
        "cell_accuracy": sum(o.get("cells_ok", 0) for o in outcome) / cells if cells else None,
        "per_table": per_table,
        "changed_examples": [o for o in outcome if o["state"] == "changed"][:15],
    }


def score_structure(snapshot: dict, gt_pages: list[str], main_end: int) -> dict[str, Any]:
    """Articles over the whole document; clauses of the main contract (pages before annexes)."""
    gt_articles: dict[int, int] = {}
    for n, text in enumerate(gt_pages, 1):
        for match in _ARTICLE.finditer(text):
            gt_articles.setdefault(int(match.group(1)), n)
    gt_clauses = Counter(
        m.group(1) for n, t in enumerate(gt_pages[:main_end], 1) for m in _CLAUSE.finditer(t)
    )
    nodes = snapshot.get("nodes") or []
    articles = {}
    for node in nodes:
        found = re.fullmatch(r"Điều (\d+)", (node.get("label_raw") or "").strip())
        if node["type"] == "ARTICLE" and found:
            articles[int(found.group(1))] = node["page_start"]
    clauses = Counter(
        (n.get("label_raw") or "").strip().rstrip(".") for n in nodes if n["type"] == "CLAUSE"
    )
    both = sum((gt_clauses & clauses).values())
    crossing = [
        {
            "label": n.get("label_raw") or n["label_normalized"],
            "type": n["type"],
            "page_start": n["page_start"],
            "page_end": n["page_end"],
        }
        for n in nodes
        if n["type"] in {"ARTICLE", "CLAUSE"} and n["page_start"] <= main_end < n["page_end"]
    ]
    return {
        "main_contract_pages": main_end,
        "gt_articles": len(gt_articles),
        "ocr_articles": len(articles),
        "articles_matched": len(gt_articles.keys() & articles.keys()),
        "articles_same_page": sum(articles.get(k) == p for k, p in gt_articles.items()),
        "articles_missing": sorted(gt_articles.keys() - articles.keys()),
        "articles_extra": sorted(articles.keys() - gt_articles.keys()),
        "gt_clauses": sum(gt_clauses.values()),
        "ocr_clauses": sum(clauses.values()),
        "clause_recall": both / sum(gt_clauses.values()) if gt_clauses else None,
        "clause_precision": both / sum(clauses.values()) if clauses else None,
        "clauses_missing": sorted((gt_clauses - clauses).elements())[:40],
        "clauses_extra": sorted((clauses - gt_clauses).elements())[:40],
        "nodes_crossing_into_annexes": crossing,
    }


def line_errors(ref: str, lines: list[str]) -> list[bool]:
    """Which OCR lines hold at least one edit against the ground-truth page (typography-normalized)."""
    spans, parts, pos = [], [], 0
    for text in lines:
        part = _typo(text)
        spans.append((pos, pos + len(part)))
        parts.append(part)
        pos += len(part) + 1
    wrong = [False] * len(lines)
    for op in Levenshtein.opcodes(_typo(ref), " ".join(parts)):
        if op.tag == "equal":
            continue
        start, end = op.dest_start, max(op.dest_end, op.dest_start + 1)
        for k, (a, b) in enumerate(spans):
            if a < end and start <= b:
                wrong[k] = True
    return wrong


def score_flags(snapshot: dict, gt_pages: list[str]) -> dict[str, Any]:
    """Review flags and line confidence against real line errors, on pages without tables."""
    flagged: dict[str, set[str]] = defaultdict(set)
    total_lines = wrong_lines = 0
    wrong_ids: set[str] = set()
    by_confidence: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    line_ids: list[str] = []
    for page in snapshot["pages"]:
        lines = page.get("lines") or []
        if page.get("tables") or not lines or page["page_number"] > len(gt_pages):
            continue
        for warning in page.get("warnings") or []:
            found = _LINE_REF.match(warning)
            if found:
                flagged[found.group(1)].add(found.group(2))
        wrong = line_errors(
            gt_pages[page["page_number"] - 1], [_plain(line["text"]) for line in lines]
        )
        for line, is_wrong in zip(lines, wrong, strict=True):
            total_lines += 1
            wrong_lines += is_wrong
            line_ids.append(line["line_id"])
            if is_wrong:
                wrong_ids.add(line["line_id"])
            confidence = line.get("confidence")
            key = "—" if confidence is None else f"{confidence:.2f}"
            by_confidence[key][0] += 1
            by_confidence[key][1] += is_wrong
    scored = set(line_ids)
    any_flag = set().union(*flagged.values()) & scored if flagged else set()
    flags = {
        code: {
            "lines": len(ids & scored),
            "wrong": len(ids & scored & wrong_ids),
            "precision": len(ids & scored & wrong_ids) / len(ids & scored)
            if ids & scored
            else None,
        }
        for code, ids in sorted(flagged.items())
    }
    return {
        "lines": total_lines,
        "wrong_lines": wrong_lines,
        "wrong_rate": wrong_lines / total_lines if total_lines else None,
        "flagged_lines": len(any_flag),
        "flag_precision": len(any_flag & wrong_ids) / len(any_flag) if any_flag else None,
        "flag_recall": len(any_flag & wrong_ids) / len(wrong_ids) if wrong_ids else None,
        "by_flag": flags,
        "by_confidence": {
            k: {"lines": n, "wrong": w, "wrong_rate": w / n if n else None}
            for k, (n, w) in sorted(by_confidence.items(), reverse=True)
        },
    }


def run(snapshot_path: Path, gt_dir: Path, summary_path: Path | None) -> dict[str, Any]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot = data.get("snapshot", data)
    gt_pages = load_ground_truth_pages(gt_dir)
    sections = load_sections(gt_dir) if (gt_dir / "documents").is_dir() else []
    starts = section_start_pages(gt_pages, [s["title"] for s in sections]) if sections else []
    owner = page_sections(len(gt_pages), starts) if sections else [None] * len(gt_pages)
    annex_starts = [s for s in starts[1:] if s is not None]
    main_end = (min(annex_starts) - 1) if annex_starts else len(gt_pages)

    pages = score_pages(snapshot, gt_pages, owner, sections)
    accent: Counter = Counter()
    other: Counter = Counter()
    for page in snapshot["pages"]:
        n = page["page_number"]
        if n <= len(gt_pages):
            a, o = word_confusions(gt_pages[n - 1], _ocr_text(page))
            accent.update(a)
            other.update(o)
    summary = None
    if summary_path and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "snapshot": str(snapshot_path),
        "ground_truth": str(gt_dir),
        "snapshot_id": snapshot.get("snapshot_id"),
        "filename": snapshot.get("filename"),
        "run": summary,
        "page_count": {"snapshot": len(snapshot["pages"]), "ground_truth": len(gt_pages)},
        "markdown_table_lines": sum(
            bool(_TABLE_ROW.match(line["text"]))
            for page in snapshot["pages"]
            for line in page.get("lines") or []
        ),
        "sections": [
            {"file": s["file"], "title": s["title"], "start_page": start}
            for s, start in zip(sections, starts, strict=True)
        ],
        "pages": pages,
        "confusions": {
            "diacritic": [[a, b, n] for (a, b), n in accent.most_common(25)],
            "other": [[a, b, n] for (a, b), n in other.most_common(25)],
        },
        "contradictions": score_contradictions(
            load_contradictions(gt_dir), snapshot, gt_pages, owner, sections
        ),
        "tables": score_tables(sections, snapshot) if sections else None,
        "structure": score_structure(snapshot, gt_pages, main_end),
        "flags": score_flags(snapshot, gt_pages),
    }


# -- reporting ---------------------------------------------------------------------


def report(results: dict) -> str:
    pages = results["pages"]
    overall = aggregate(pages)
    run_info = results.get("run") or {}
    lines = [
        f"# Benchmark OCR — {results.get('filename')} so với ground truth",
        "",
        f"Snapshot `{results.get('snapshot_id')}`"
        + (f", AI1_COST_MODE=`{run_info['cost_mode']}`" if run_info.get("cost_mode") else "")
        + f". {results['page_count']['snapshot']} trang snapshot / "
        f"{results['page_count']['ground_truth']} trang ground truth.",
        "",
        f"{results.get('markdown_table_lines', 0)} dòng của snapshot là hàng bảng dạng Markdown "
        "(`| a | b |`); chúng được tách thành từng ô trước khi so, vì lớp chữ ground truth liệt kê "
        "mỗi ô một dòng.",
        "",
        "## Chất lượng chữ",
        "",
        "| CER | WER | CER chuẩn hoá | WER chuẩn hoá | CER bỏ khác biệt dấu gạch/nháy | Lỗi dấu | "
        "Critical Field Accuracy | Cờ review |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {_pct(overall['cer'])} | {_pct(overall['wer'])} | {_pct(overall['cer_norm'])} | "
        f"{_pct(overall['wer_norm'])} | {_pct(overall['cer_typo'])} | {_pct(overall['diacritic'])} | "
        f"{_pct(overall['crit'])} ({overall['crit_ok']}/{overall['crit_total']}) | {overall['review']} |",
        "",
    ]
    if results["sections"]:
        lines += [
            "| Phần | Trang bắt đầu | Số trang | CER chuẩn hoá | WER chuẩn hoá | Lỗi dấu | Critical Field |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for section in results["sections"]:
            own = [p for p in pages if p["section"] == section["file"]]
            if not own:
                lines.append(f"| {_cell(section['title'][:60])} | — | 0 | — | — | — | — |")
                continue
            a = aggregate(own)
            lines.append(
                f"| {_cell(section['title'][:60])} | {section['start_page']} | {a['pages']} | "
                f"{_pct(a['cer_norm'])} | {_pct(a['wer_norm'])} | {_pct(a['diacritic'])} | "
                f"{_pct(a['crit'])} ({a['crit_ok']}/{a['crit_total']}) |"
            )
        lines.append("")
    worst = sorted(pages, key=lambda p: p["cer_norm"], reverse=True)[:10]
    lines += [
        "10 trang có CER chuẩn hoá cao nhất:",
        "",
        "| Trang | Phần | CER chuẩn hoá | Bảng | Trạng thái | Cờ review |",
        "|---:|---|---:|---:|---|---:|",
    ]
    lines += [
        f"| {p['page']} | {p['section'] or '—'} | {_pct(p['cer_norm'])} | {p['tables']} | "
        f"{p['status']} | {p['review_flags']} |"
        for p in worst
    ]

    lost = [(p, span) for p in pages for span in p["lost_spans"]]
    silent = [(p, span) for p, span in lost if not p["unread_ink_warning"]]
    lines += [
        "",
        "## Chữ bị mất",
        "",
        f"{len(lost)} đoạn liền ≥ {LOST_SPAN_CHARS} ký tự có trong ground truth nhưng không có trong "
        f"OCR, tổng {sum(s['chars'] for _, s in lost)} ký tự; {len(silent)} đoạn nằm trên trang "
        "không có cảnh báo mực chưa đọc (`ocr:unread_ink_lines`), tức là mất mà không ai được báo.",
    ]
    if lost:
        lines += [
            "",
            "| Trang | Ký tự mất | Cảnh báo mực chưa đọc | Đầu đoạn (ground truth) |",
            "|---:|---:|---|---|",
        ]
        lines += [
            f"| {p['page']} | {s['chars']} | {'có' if p['unread_ink_warning'] else '**không**'} | "
            f"{_cell(s['text'][:120])} |"
            for p, s in sorted(lost, key=lambda item: -item[1]["chars"])[:30]
        ]

    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in pages:
        for kind, (ok, total) in p["crit_by_type"].items():
            by_type[kind][0] += ok
            by_type[kind][1] += total
    lines += [
        "",
        "## Critical field",
        "",
        "| Loại field | Đúng / Tổng | Accuracy |",
        "|---|---:|---:|",
    ]
    lines += [
        f"| {k} | {ok}/{t} | {_pct(ok / t if t else None)} |"
        for k, (ok, t) in sorted(by_type.items())
    ]
    missed: dict[str, list[int]] = defaultdict(list)
    for p in pages:
        for field in p["crit_missed"]:
            missed[field].append(p["page"])
    if missed:
        total = sum(len(v) for v in missed.values())
        lines += ["", f"Field sai/thiếu ({total} lần, {len(missed)} giá trị khác nhau):", ""]
        for field, where in sorted(missed.items(), key=lambda item: -len(item[1]))[:30]:
            shown = ", ".join(map(str, where[:8])) + (", …" if len(where) > 8 else "")
            lines.append(f"- `{field}` ×{len(where)} (tr. {shown})")

    contradictions = results["contradictions"]
    if contradictions:
        evaluated = [c for c in contradictions if c["evaluated"]]
        kept = sum(c["retained"] for c in evaluated)
        lines += [
            "",
            "## Giá trị mâu thuẫn cố ý",
            "",
            f"{kept}/{len(evaluated)} giá trị còn nguyên trên đúng trang OCR "
            f"({len(contradictions) - len(evaluated)} giá trị không định vị được trong ground truth).",
            "",
        ]
        lost = [c for c in evaluated if not c["retained"]]
        if lost:
            lines += [
                "| # | Chủ đề | Phía | Vị trí | Giá trị đúng | Trang | OCR đọc gần nhất |",
                "|---:|---|---|---|---|---|---|",
            ]
            lines += [
                f"| {c['id']} | {_cell(c['topic'])} | {c['side']} | {_cell(c['ref'])} | "
                f"{_cell(c['value'])} | {', '.join(map(str, c['pages'][:4]))} | {_cell(c['closest_ocr'])} |"
                for c in lost
            ]

    tables = results.get("tables")
    if tables:
        lines += [
            "",
            "## Bảng",
            "",
            f"Ground truth: {tables['gt_tables']} bảng logic, {tables['gt_rows']} hàng. "
            f"Snapshot: {tables['ocr_tables']} bảng theo trang, {tables['ocr_rows']} hàng.",
            "",
            "| Hàng đúng hoàn toàn | Hàng có ô sai | Hàng thiếu | Hàng thừa | Độ chính xác ô |",
            "|---:|---:|---:|---:|---:|",
            f"| {tables['exact']} ({_pct(tables['exact'] / tables['gt_rows'] if tables['gt_rows'] else None)}) | "
            f"{tables['changed']} | {tables['missing']} | {tables['extra']} | {_pct(tables['cell_accuracy'])} |",
            "",
            "| Phần | Bảng | Cột đầu | Hàng | Đúng | Có ô sai | Thiếu | Độ chính xác ô |",
            "|---|---:|---|---:|---:|---:|---:|---:|",
        ]
        lines += [
            f"| {t['section'][:40]} | {t['index'] + 1} | {_cell(' / '.join(t['header'][:3]))[:60]} | "
            f"{t['rows']} | {t['exact']} | {t['changed']} | {t['missing']} | {_pct(t['cell_accuracy'])} |"
            for t in tables["per_table"]
        ]
        if tables["changed_examples"]:
            lines += ["", "Ví dụ hàng có ô sai (ground truth → OCR):", ""]
            lines += [
                f"- `{_cell(e['gt'])[:140]}`<br>→ `{_cell(e['ocr'])[:140]}`"
                for e in tables["changed_examples"][:8]
            ]

    s = results["structure"]
    lines += [
        "",
        "## Cấu trúc",
        "",
        f"Hợp đồng chính: trang 1–{s['main_contract_pages']}.",
        "",
        "| Hạng mục | Ground truth | Snapshot | Khớp |",
        "|---|---:|---:|---:|",
        f"| Điều | {s['gt_articles']} | {s['ocr_articles']} | {s['articles_matched']} "
        f"(đúng trang: {s['articles_same_page']}) |",
        f"| Khoản (hợp đồng chính) | {s['gt_clauses']} | {s['ocr_clauses']} | "
        f"recall {_pct(s['clause_recall'])} · precision {_pct(s['clause_precision'])} |",
    ]
    if s["articles_missing"] or s["articles_extra"]:
        lines.append(
            f"\nĐiều thiếu: {s['articles_missing'] or '—'} · Điều thừa: {s['articles_extra'] or '—'}"
        )
    if s["clauses_missing"]:
        lines.append(f"\nKhoản thiếu (tối đa 40): {', '.join(s['clauses_missing'])}")
    if s["clauses_extra"]:
        lines.append(f"\nKhoản thừa (tối đa 40): {', '.join(s['clauses_extra'])}")
    for node in s["nodes_crossing_into_annexes"]:
        lines.append(
            f"\n**{node['type']} {node['label']}** kéo dài trang {node['page_start']}–{node['page_end']}: "
            "vượt qua ranh giới hợp đồng chính, nuốt nội dung phụ lục vào một node."
        )

    conf = results["confusions"]
    lines += [
        "",
        "## Lỗi đọc hay gặp",
        "",
        "Chỉ khác dấu:",
        "",
        "| Đúng | OCR | Số lần |",
        "|---|---|---:|",
    ]
    lines += [f"| {_cell(a)} | {_cell(b)} | {n} |" for a, b, n in conf["diacritic"][:15]]
    lines += ["", "Khác chữ:", "", "| Đúng | OCR | Số lần |", "|---|---|---:|"]
    lines += [f"| {_cell(a)} | {_cell(b)} | {n} |" for a, b, n in conf["other"][:15]]

    f = results["flags"]
    lines += [
        "",
        "## Cờ review và độ tin cậy dòng",
        "",
        f"Trên các trang không có bảng: {f['lines']} dòng, {f['wrong_lines']} dòng có ít nhất một lỗi "
        f"({_pct(f['wrong_rate'])}). Cờ review phủ {f['flagged_lines']} dòng: precision "
        f"{_pct(f['flag_precision'])}, recall {_pct(f['flag_recall'])}.",
        "",
        "| Cờ | Dòng | Dòng thật sự sai | Precision |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f"| `{k}` | {v['lines']} | {v['wrong']} | {_pct(v['precision'])} |"
        for k, v in f["by_flag"].items()
    ]
    lines += ["", "| Độ tin cậy dòng | Dòng | Dòng sai | Tỉ lệ sai |", "|---:|---:|---:|---:|"]
    lines += [
        f"| {k} | {v['lines']} | {v['wrong']} | {_pct(v['wrong_rate'])} |"
        for k, v in f["by_confidence"].items()
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, required=True, help="ai1.snapshot.v1 JSON")
    parser.add_argument(
        "--ground-truth", type=Path, required=True, help="folder with contract-text.pdf"
    )
    parser.add_argument(
        "--summary", type=Path, help="summary.json of the OCR run (default: next to the snapshot)"
    )
    parser.add_argument("--out", type=Path, help="default: reports/benchmark/<snapshot name>")
    args = parser.parse_args()
    summary = args.summary or args.snapshot.with_name("summary.json")
    out = args.out or ROOT / "reports" / "benchmark" / args.snapshot.stem.split(".")[0]
    results = run(args.snapshot, args.ground_truth, summary)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "report.md").write_text(report(results), encoding="utf-8")
    print(f"report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
