"""In-step progress {"done", "total", "unit"}: validation and write throttle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from contract_intelligence.shared import step_progress

T0 = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)


def _p(done: int, total: int = 200, unit: str = "page") -> dict[str, object]:
    return {"done": done, "total": total, "unit": unit}


@pytest.mark.parametrize(
    ("done", "total", "expected_done"),
    [(37, 202, 37), (0, 202, 0), (250, 202, 202), (-3, 202, 0)],
)
def test_normalize_keeps_done_within_zero_and_total(
    done: int, total: int, expected_done: int
) -> None:
    value = step_progress.normalize(done, total, "page")
    assert value == {"done": expected_done, "total": total, "unit": "page"}
    assert value is not None and value["done"] <= value["total"]


@pytest.mark.parametrize(
    ("done", "total", "unit"),
    [
        (1, 0, "page"),  # nothing to count
        (1, -5, "page"),
        ("1", 10, "page"),  # strings are not counts
        (1.5, 10, "page"),
        (True, 10, "page"),  # bool is an int subclass, still not a count
        (1, 10, "sheep"),  # unknown unit: the frontend could not word it
        (1, 10, None),
    ],
)
def test_normalize_rejects_what_cannot_be_shown(done: object, total: object, unit: object) -> None:
    assert step_progress.normalize(done, total, unit) is None


def test_parse_reads_stored_json_and_drops_garbage() -> None:
    assert step_progress.parse('{"done": 5, "total": 10, "unit": "pair"}') == _p(5, 10, "pair")
    for stored in (None, "", "not json", "[1, 2]", '{"done": 5}'):
        assert step_progress.parse(stored) is None


def test_completed_sets_done_to_total_and_keeps_none() -> None:
    assert step_progress.completed(_p(37, 202)) == _p(202, 202)
    assert step_progress.completed(None) is None


def test_first_value_is_always_written() -> None:
    assert step_progress.should_write(None, None, _p(1), T0)


def test_value_reaching_total_is_written_at_once() -> None:
    assert step_progress.should_write(_p(199), T0, _p(200), T0)


def test_no_write_within_one_second_even_for_a_big_jump() -> None:
    assert not step_progress.should_write(_p(10), T0, _p(150), T0 + timedelta(seconds=0.5))


def test_five_percent_after_one_second_is_written_less_is_not() -> None:
    later = T0 + timedelta(seconds=2)
    assert step_progress.should_write(_p(10), T0, _p(20), later)  # +10/200 = 5 %
    assert not step_progress.should_write(_p(10), T0, _p(19), later)


def test_slow_step_still_refreshes_on_the_heartbeat() -> None:
    later = T0 + timedelta(seconds=step_progress.HEARTBEAT_SECONDS)
    assert step_progress.should_write(_p(10), T0, _p(11), later)


def test_never_moves_backwards_or_repeats() -> None:
    later = T0 + timedelta(minutes=5)
    assert not step_progress.should_write(_p(50), T0, _p(50), later)
    assert not step_progress.should_write(_p(50), T0, _p(40), later)


def test_new_total_or_unit_is_written() -> None:
    soon = T0 + timedelta(seconds=0.1)
    assert step_progress.should_write(_p(50), T0, _p(10, 300), soon)
    assert step_progress.should_write(_p(50), T0, _p(1, 200, "document"), soon)


def test_one_report_per_page_is_cut_to_a_bounded_number_of_writes() -> None:
    """A 200-page OCR reporting every page, 4 pages a second, writes ~20 times."""
    previous, previous_at, writes = None, None, 0
    for page in range(1, 201):
        now = T0 + timedelta(seconds=page / 4)
        value = _p(page)
        if step_progress.should_write(previous, previous_at, value, now):
            previous, previous_at, writes = value, now, writes + 1
    assert previous == _p(200)
    assert writes <= 22
