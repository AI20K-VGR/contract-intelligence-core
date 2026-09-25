import json

from contract_intelligence.extraction.infrastructure.persistence.repository_impl import (
    _infer_legacy_continuity,
)


def _fragment(table_id: str, page_no: int, start: int) -> dict:
    cells = [
        {
            "row_idx": index,
            "col_idx": 0,
            "text": str(start + index).zfill(2),
        }
        for index in range(3)
    ]
    return {
        "id": table_id,
        "page_no": page_no,
        "rows_count": 3,
        "cols_count": 7,
        "is_multi_page": False,
        "continued_from": None,
        "cells": json.dumps(cells),
    }


def test_infers_legacy_cross_page_table_from_continuous_stt() -> None:
    rows = _infer_legacy_continuity(
        [_fragment("t-1", 1, 1), _fragment("t-2", 2, 4)]
    )

    assert rows[0]["is_multi_page"] is True
    assert rows[1]["is_multi_page"] is True
    assert rows[1]["continued_from"] == "t-1"


def test_does_not_infer_when_sequence_resets() -> None:
    rows = _infer_legacy_continuity(
        [_fragment("t-1", 1, 1), _fragment("t-2", 2, 1)]
    )

    assert rows[0]["is_multi_page"] is False
    assert rows[1]["continued_from"] is None
