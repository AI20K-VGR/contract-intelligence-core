"""Remaining reviewer examples: OCR offsets, quota durability and Vietnamese titles."""

import httpx
import openai
import pytest

from app.contracts.models import PageSnapshot
from app.pipeline.citations import line_offsets
from app.pipeline.frame_context import _is_heading_only
from app.pipeline.runtime import ProcessingRuntime


@pytest.mark.parametrize("separator", ["\n", "\r\n", " "])
def test_empty_ocr_lines_do_not_consume_characters_in_page_text(separator):
    lines = {"a": "A", "empty1": "", "empty2": "", "b": "Thanh toán 30%", "c": "C"}
    page = PageSnapshot(
        page_revision_id="p",
        page_number=1,
        source_hash="a" * 64,
        text=separator.join(["A", "Thanh toán 30%", "C"]),
        line_texts=lines,
    )
    offsets = line_offsets(page)
    for key, value in lines.items():
        start, end = offsets[key]
        assert page.text[start:end] == value
    assert offsets["empty1"] == offsets["empty2"] == (1, 1)


@pytest.mark.parametrize(
    "title",
    [
        "Điều 2. Giá trị hợp đồng và phương thức thanh toán",
        "Điều 8. Trách nhiệm do vi phạm hợp đồng",
    ],
)
def test_long_vietnamese_noun_titles_are_headings(title):
    assert _is_heading_only(title)


@pytest.mark.parametrize(
    "sentence",
    [
        "Điều chỉnh giá hợp đồng được thực hiện khi có biến động giá vật liệu",
        "Phần lớn khối lượng công việc do nhà thầu phụ thực hiện",
        "Điều 15. Hợp đồng có hiệu lực kể từ ngày ký",
        "Điều 8. Bên A chịu trách nhiệm do vi phạm hợp đồng",
    ],
)
def test_substantive_sentences_still_extract(sentence):
    assert not _is_heading_only(sentence)


def test_quota_issue_survives_discarded_batch_sink():
    class Quota:
        def configured(self):
            return True

        def complete_json(self, *args, **kwargs):
            raise openai.RateLimitError(
                "quota exhausted",
                response=httpx.Response(429, request=httpx.Request("POST", "http://router.test")),
                body={"error": {"code": "insufficient_quota"}},
            )

    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=20)
    discarded_sink = []
    assert runtime.complete_json(Quota(), "s", "u", issue_sink=discarded_sink) is None
    assert runtime.provider_exhausted
    # The parallel prefix policy never commits this sink.
    assert [code for code, _ in runtime.issues] == ["LLM_QUOTA_EXHAUSTED"]
    used = runtime.llm_calls_used
    assert runtime.complete_json(Quota(), "s", "u") is None
    assert runtime.llm_calls_used == used
    runtime.commit_issues(discarded_sink)
    assert [code for code, _ in runtime.issues] == ["LLM_QUOTA_EXHAUSTED"]
