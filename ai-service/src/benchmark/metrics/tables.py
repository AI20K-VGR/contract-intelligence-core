from __future__ import annotations

from benchmark.metrics.text import normalize_text
from benchmark.schemas import GroundTruthTable, OCRTable


def _cell_accuracy(reference: list[list[str]], prediction: list[list[str]]) -> tuple[int, int]:
    correct = total = 0
    for row_index, row in enumerate(reference):
        for col_index, value in enumerate(row):
            total += 1
            predicted = (
                prediction[row_index][col_index]
                if row_index < len(prediction) and col_index < len(prediction[row_index])
                else ""
            )
            correct += normalize_text(value) == normalize_text(predicted)
    return correct, total


def evaluate_tables(reference: list[GroundTruthTable], prediction: list[OCRTable]) -> dict:
    # MVP pairs tables by page overlap then order; counts remain explicit so later
    # aggregation can compute corpus-level precision/recall without averaging F1s.
    unmatched = list(prediction)
    matched: list[tuple[GroundTruthTable, OCRTable]] = []
    for expected in reference:
        found = next((table for table in unmatched if set(table.pages) & set(expected.pages)), None)
        if found is not None:
            matched.append((expected, found))
            unmatched.remove(found)
    tp, fp, fn = len(matched), len(unmatched), len(reference) - len(matched)
    precision = tp / (tp + fp) if tp + fp else (1.0 if not reference else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    row_ok = sum(len(a.rows) == len(b.rows) for a, b in matched)
    col_ok = sum(
        max((len(r) for r in a.rows), default=0) == max((len(r) for r in b.rows), default=0)
        for a, b in matched
    )
    cell_correct = cell_total = continuation_correct = continuation_total = 0
    for expected, found in matched:
        correct, total = _cell_accuracy(expected.rows, found.rows)
        cell_correct += correct
        cell_total += total
        if expected.is_multi_page:
            continuation_total += 1
            continuation_correct += found.is_multi_page or len(found.pages) > 1
    return {
        "table_tp": tp,
        "table_fp": fp,
        "table_fn": fn,
        "table_detection_precision": precision,
        "table_detection_recall": recall,
        "table_detection_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "row_count_accuracy": row_ok / len(matched) if matched else None,
        "column_count_accuracy": col_ok / len(matched) if matched else None,
        "cell_text_correct": cell_correct,
        "cell_text_total": cell_total,
        "cell_text_accuracy": cell_correct / cell_total if cell_total else None,
        "table_continuation_correct": continuation_correct,
        "table_continuation_total": continuation_total,
        "table_continuation_accuracy": continuation_correct / continuation_total if continuation_total else None,
    }
