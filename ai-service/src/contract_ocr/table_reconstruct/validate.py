"""Table-level consistency checks."""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal

from .columns import _looks_like_anchor_value, _normalize_confusables, pick_anchor_column
from .config import Config
from .numbers import is_total_row, parse_vn_number, vn_words_to_number
from .types import LogicalRow, LogicalTable

_BANG_CHU_RE = re.compile(r"bằng\s*chữ\s*:?\s*(.*)", re.IGNORECASE)


def validate(table: LogicalTable, config: Config = Config()) -> dict:
    """Run all five checks against a finished table. Each entry is
    `{"passed", "expected", "actual", "offending_rows"}`."""
    preview = [[c.text for c in row.cells] for row in table.rows[: config.anchor_preview_rows]]
    anchor_col = pick_anchor_column(preview, config) if preview else 0

    return {
        "row_count_ok": _check_row_count(table, anchor_col, config),
        "anchor_continuous": _check_anchor_continuous(table, anchor_col, config),
        "arity_ok": _check_arity(table),
        "sum_check": _check_sum(table, anchor_col, config),
        "vn_words_check": _check_vn_words(table, anchor_col, config),
    }


def _numeric_anchor(text: str, config: Config) -> int | None:
    normalized = _normalize_confusables(text.strip(), config)
    return int(normalized) if _looks_like_anchor_value(normalized) else None


def _check_row_count(table: LogicalTable, anchor_col: int, config: Config) -> dict:
    values = [
        v
        for row in table.rows
        if anchor_col < len(row.cells)
        and (v := _numeric_anchor(row.cells[anchor_col].text, config)) is not None
    ]
    expected = len(table.rows)
    actual = max(values) if values else 0
    passed = actual == expected
    return {
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "offending_rows": [] if passed else [row.index for row in table.rows],
    }


def _check_anchor_continuous(table: LogicalTable, anchor_col: int, config: Config) -> dict:
    offending: list[int] = []
    prev_value: int | None = None
    for row in table.rows:
        if anchor_col >= len(row.cells):
            continue
        value = _numeric_anchor(row.cells[anchor_col].text, config)
        if value is None:
            continue
        if prev_value is not None and (value < prev_value or value - prev_value > 1):
            offending.append(row.index)
        prev_value = value
    return {
        "passed": not offending,
        "expected": "no gaps in the anchor sequence",
        "actual": f"{len(offending)} jump(s)",
        "offending_rows": offending,
    }


def _check_arity(table: LogicalTable) -> dict:
    expected = len(table.header)
    offending = [row.index for row in table.rows if len(row.cells) != expected]
    return {
        "passed": not offending,
        "expected": expected,
        "actual": sorted({len(row.cells) for row in table.rows}),
        "offending_rows": offending,
    }


def _pick_money_column(
    rows: Sequence[LogicalRow], total_rows: Sequence[LogicalRow], anchor_col: int
) -> int | None:
    """The non-anchor column with the most parseable-as-a-number values
    among the non-total rows. The anchor (STT) column is excluded — its
    values also happen to parse as numbers, and a tie would otherwise
    resolve to it since it's leftmost.
    """
    total_indices = {row.index for row in total_rows}
    data_rows = [row for row in rows if row.index not in total_indices]
    if not data_rows:
        return None

    num_cols = max(len(row.cells) for row in data_rows)
    best_col: int | None = None
    best_count = 0
    for c in range(num_cols):
        if c == anchor_col:
            continue
        count = 0
        for row in data_rows:
            if c >= len(row.cells):
                continue
            try:
                parse_vn_number(row.cells[c].text)
                count += 1
            except ValueError:
                pass
        if count > best_count:
            best_col, best_count = c, count
    return best_col


def _check_sum(table: LogicalTable, anchor_col: int, config: Config) -> dict:
    total_rows = [row for row in table.rows if is_total_row(row)]
    if not total_rows:
        return {"passed": True, "expected": None, "actual": None, "offending_rows": []}

    money_col = _pick_money_column(table.rows, total_rows, anchor_col)
    if money_col is None:
        return {"passed": True, "expected": None, "actual": None, "offending_rows": []}

    total_indices = {row.index for row in total_rows}
    computed = Decimal(0)
    for row in table.rows:
        if row.index in total_indices or money_col >= len(row.cells):
            continue
        try:
            computed += parse_vn_number(row.cells[money_col].text)
        except ValueError:
            continue

    offending: list[int] = []
    declared: Decimal | None = None
    for row in total_rows:
        if money_col >= len(row.cells):
            continue
        try:
            declared = parse_vn_number(row.cells[money_col].text)
        except ValueError:
            continue
        if declared != computed:
            offending.append(row.index)

    return {
        "passed": not offending,
        "expected": computed,
        "actual": declared,
        "offending_rows": offending,
    }


def _check_vn_words(table: LogicalTable, anchor_col: int, config: Config) -> dict:
    for row in table.rows:
        for cell in row.cells:
            match = _BANG_CHU_RE.search(cell.text)
            if not match or not match.group(1).strip():
                continue
            phrase = match.group(1).strip().rstrip(")").strip()
            return _evaluate_vn_words_cell(table, row, phrase, anchor_col)

    return {"passed": True, "expected": None, "actual": None, "offending_rows": []}


def _evaluate_vn_words_cell(
    table: LogicalTable, row: LogicalRow, phrase: str, anchor_col: int
) -> dict:
    try:
        words_value = vn_words_to_number(phrase)
    except ValueError:
        return {"passed": False, "expected": None, "actual": phrase, "offending_rows": [row.index]}

    total_rows = [r for r in table.rows if is_total_row(r)]
    money_col = _pick_money_column(table.rows, total_rows, anchor_col)
    reference: Decimal | None = None
    if total_rows and money_col is not None and money_col < len(total_rows[0].cells):
        try:
            reference = parse_vn_number(total_rows[0].cells[money_col].text)
        except ValueError:
            reference = None

    if reference is None:
        return {"passed": True, "expected": words_value, "actual": None, "offending_rows": []}

    passed = reference == words_value
    return {
        "passed": passed,
        "expected": reference,
        "actual": words_value,
        "offending_rows": [] if passed else [row.index],
    }
