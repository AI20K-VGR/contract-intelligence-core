"""EscalationController."""

from __future__ import annotations

from contract_ocr.table_reconstruct.types import Word
from contract_ocr.word_adapters import EscalationController, Region

from .factories import FakeVisionAdapter, blank_image


def _word(text: str) -> Word:
    return Word(text=text, x0=0.0, y0=0.0, x1=10.0, y1=10.0, page=1, source="ocr")


class TestShouldEscalateForWords:
    def test_low_valid_word_ratio_triggers_escalation(self):
        controller = EscalationController(FakeVisionAdapter([]), min_valid_word_ratio=0.6)
        words = [_word("###"), _word("@@@"), _word("Hàng")]
        assert controller.should_escalate_for_words(words) is True

    def test_clean_words_do_not_trigger_escalation(self):
        controller = EscalationController(FakeVisionAdapter([]), min_valid_word_ratio=0.6)
        words = [_word("Hàng"), _word("A"), _word("1.000.000")]
        assert controller.should_escalate_for_words(words) is False


class TestShouldEscalateForChecks:
    def test_failing_sum_check_triggers_escalation(self):
        controller = EscalationController(FakeVisionAdapter([]))
        checks = {
            "row_count_ok": {"passed": True},
            "sum_check": {"passed": False},
            "vn_words_check": {"passed": True},
        }
        assert controller.should_escalate_for_checks(checks) is True

    def test_failing_structural_check_alone_does_not_trigger(self):
        # A wrong row/anchor count isn't something a cell-level vision
        # re-read can fix — only the two checksum checks should matter.
        controller = EscalationController(FakeVisionAdapter([]))
        checks = {
            "row_count_ok": {"passed": False},
            "anchor_continuous": {"passed": False},
            "arity_ok": {"passed": False},
            "sum_check": {"passed": True},
            "vn_words_check": {"passed": True},
        }
        assert controller.should_escalate_for_checks(checks) is False

    def test_all_passing_does_not_trigger(self):
        controller = EscalationController(FakeVisionAdapter([]))
        checks = {"sum_check": {"passed": True}, "vn_words_check": {"passed": True}}
        assert controller.should_escalate_for_checks(checks) is False


class TestEscalate:
    def test_escalation_calls_the_vision_adapter_and_returns_its_words(self):
        vision = FakeVisionAdapter([_word("recovered")])
        controller = EscalationController(vision)
        region = Region(page=1, bbox=(0.0, 0.0, 50.0, 20.0))

        result = controller.escalate(blank_image(), region)

        assert result.escalated is True
        assert [w.text for w in result.words] == ["recovered"]
        assert len(vision.calls) == 1

    def test_hard_cap_of_two_escalations_per_page(self):
        vision = FakeVisionAdapter([_word("x")])
        controller = EscalationController(vision, max_escalations_per_page=2)
        region = Region(page=1, bbox=(0.0, 0.0, 50.0, 20.0))

        first = controller.escalate(blank_image(), region)
        second = controller.escalate(blank_image(), region)
        third = controller.escalate(blank_image(), region)

        assert first.escalated is True
        assert second.escalated is True
        assert third.escalated is False
        assert third.reason == "escalation_cap_reached"
        assert third.words == []
        assert len(vision.calls) == 2

    def test_cap_is_tracked_independently_per_page(self):
        vision = FakeVisionAdapter([_word("x")])
        controller = EscalationController(vision, max_escalations_per_page=1)

        page1_region = Region(page=1, bbox=(0.0, 0.0, 50.0, 20.0))
        page2_region = Region(page=2, bbox=(0.0, 0.0, 50.0, 20.0))

        assert controller.escalate(blank_image(), page1_region).escalated is True
        assert controller.escalate(blank_image(), page1_region).escalated is False
        # Page 2's own budget is untouched by page 1 hitting its cap.
        assert controller.escalate(blank_image(), page2_region).escalated is True

    def test_escalations_used_reports_the_running_count(self):
        vision = FakeVisionAdapter([_word("x")])
        controller = EscalationController(vision, max_escalations_per_page=2)
        region = Region(page=7, bbox=(0.0, 0.0, 50.0, 20.0))

        assert controller.escalations_used(7) == 0
        controller.escalate(blank_image(), region)
        assert controller.escalations_used(7) == 1
