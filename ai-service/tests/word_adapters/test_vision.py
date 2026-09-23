"""VisionAdapter — region and cells modes, both against a faked VisionClient."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from contract_ocr.word_adapters import Region, VisionAdapter
from contract_ocr.word_adapters.vision import _OpenAIVisionClient

from .factories import FakeVisionClient, blank_image


class TestVisionAdapterRegionMode:
    def test_splits_response_lines_into_words_sharing_the_region_bbox(self):
        client = FakeVisionClient("Điều 1: Đối tượng hợp đồng\nBên A cam kết ...")
        adapter = VisionAdapter(mode="region", client=client)
        region = Region(page=5, bbox=(10.0, 20.0, 300.0, 200.0))

        words = adapter.extract(blank_image(), region)

        assert [w.text for w in words] == ["Điều 1: Đối tượng hợp đồng", "Bên A cam kết ..."]
        assert all(w.source == "vision" for w in words)
        assert all(w.page == 5 for w in words)
        assert all((w.x0, w.y0, w.x1, w.y1) == region.bbox for w in words)

    def test_blank_lines_in_the_response_are_dropped(self):
        client = FakeVisionClient("Line one\n\n   \nLine two")
        adapter = VisionAdapter(mode="region", client=client)
        words = adapter.extract(blank_image(), Region(page=1, bbox=(0.0, 0.0, 100.0, 100.0)))
        assert [w.text for w in words] == ["Line one", "Line two"]

    def test_sends_one_image_and_no_json_mode(self):
        client = FakeVisionClient("text")
        VisionAdapter(mode="region", client=client).extract(
            blank_image(), Region(page=1, bbox=(0.0, 0.0, 100.0, 100.0))
        )
        assert len(client.calls) == 1
        assert len(client.calls[0]["images"]) == 1
        assert client.calls[0]["json_mode"] is False


class TestVisionAdapterCellsMode:
    def test_each_word_gets_its_own_cell_bbox_never_the_model_output(self):
        cells = ((0.0, 0.0, 50.0, 20.0), (60.0, 0.0, 110.0, 20.0))
        # The model is deliberately made to hallucinate a "bbox" field —
        # it must be ignored entirely; only "text" and the caller's own
        # cell bbox may end up on the resulting Word.
        response = json.dumps(
            {
                "cells": [
                    {"text": "1", "bbox": [999, 999, 999, 999]},
                    {"text": "Hàng A", "bbox": [1, 2, 3, 4]},
                ]
            }
        )
        client = FakeVisionClient(response)
        adapter = VisionAdapter(mode="cells", client=client)
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)

        words = adapter.extract(blank_image(), region)

        assert [w.text for w in words] == ["1", "Hàng A"]
        assert (words[0].x0, words[0].y0, words[0].x1, words[0].y1) == cells[0]
        assert (words[1].x0, words[1].y0, words[1].x1, words[1].y1) == cells[1]
        assert all(w.source == "vision" for w in words)

    def test_plain_string_cell_values_also_work(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient(json.dumps({"cells": ["Hàng A"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        [word] = VisionAdapter(mode="cells", client=client).extract(blank_image(), region)
        assert word.text == "Hàng A"

    def test_null_cell_produces_no_word(self):
        cells = ((0.0, 0.0, 50.0, 20.0), (60.0, 0.0, 110.0, 20.0))
        client = FakeVisionClient(json.dumps({"cells": [None, "Hàng A"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        words = VisionAdapter(mode="cells", client=client).extract(blank_image(), region)
        assert [w.text for w in words] == ["Hàng A"]

    def test_unreadable_cell_keeps_the_literal_marker(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient(json.dumps({"cells": ["UNREADABLE"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        [word] = VisionAdapter(mode="cells", client=client).extract(blank_image(), region)
        assert word.text == "UNREADABLE"

    def test_one_bad_element_type_skips_only_that_cell(self):
        # A malformed single element (e.g. the model returned a number instead
        # of a string/null) must not fail the whole batch -- the neighboring
        # cell's real, correctly-typed text is still worth keeping.
        cells = ((0.0, 0.0, 50.0, 20.0), (60.0, 0.0, 110.0, 20.0))
        client = FakeVisionClient(json.dumps({"cells": [123, "Hàng A"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        words = VisionAdapter(mode="cells", client=client).extract(blank_image(), region)
        assert [w.text for w in words] == ["Hàng A"]

    def test_too_few_elements_keeps_the_ones_that_matched_by_position(self):
        # The model dropped the second cell (miscounted) instead of leaving it
        # null -- the first cell's real text must not be thrown away over it.
        cells = ((0.0, 0.0, 50.0, 20.0), (60.0, 0.0, 110.0, 20.0))
        client = FakeVisionClient(json.dumps({"cells": ["only one"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        words = VisionAdapter(mode="cells", client=client).extract(blank_image(), region)
        assert [w.text for w in words] == ["only one"]
        assert (words[0].x0, words[0].y0, words[0].x1, words[0].y1) == cells[0]

    def test_too_many_elements_drops_the_extras_by_position(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient(json.dumps({"cells": ["Hàng A", "extra", "extra2"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        words = VisionAdapter(mode="cells", client=client).extract(blank_image(), region)
        assert [w.text for w in words] == ["Hàng A"]

    def test_malformed_json_yields_no_words_without_raising(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient("not json at all")
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        assert VisionAdapter(mode="cells", client=client).extract(blank_image(), region) == []

    def test_missing_cells_key_yields_no_words_without_raising(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient(json.dumps({"rows": ["x"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        assert VisionAdapter(mode="cells", client=client).extract(blank_image(), region) == []

    def test_requires_region_cells(self):
        client = FakeVisionClient(json.dumps({"cells": []}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0))
        with pytest.raises(ValueError):
            VisionAdapter(mode="cells", client=client).extract(blank_image(), region)

    def test_prompt_states_the_exact_cell_count_and_uses_json_mode(self):
        cells = ((0.0, 0.0, 50.0, 20.0), (60.0, 0.0, 110.0, 20.0), (120.0, 0.0, 170.0, 20.0))
        client = FakeVisionClient(json.dumps({"cells": ["a", "b", "c"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)

        VisionAdapter(mode="cells", client=client).extract(blank_image(), region)

        call = client.calls[0]
        assert call["json_mode"] is True
        assert "3" in call["user_prompt"]
        assert len(call["images"]) == 3


class _FakeOpenAISDK:
    """Stands in for the real `openai.OpenAI` client, capturing exactly the
    kwargs `_OpenAIVisionClient` sends to `chat.completions.create` -- this is
    the one layer `FakeVisionClient` never exercises, since it replaces
    `_OpenAIVisionClient` entirely rather than the SDK object underneath it.
    """

    def __init__(self, content: str) -> None:
        self.captured_kwargs: dict | None = None
        self._content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.captured_kwargs = kwargs
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class TestOpenAIVisionClientNeverSendsTemperature:
    """Regression coverage for a real bug found by running this adapter
    against the live API on an actual hard_case scan: gpt-5.6-terra rejects
    `temperature=0` outright ("Only the default (1) value is supported"),
    but `complete()` used to hardcode it for every JSON-mode ("cells") call
    -- meaning cells mode had never actually worked against the real model,
    only against `FakeVisionClient` in the tests above. No unit test caught
    this because nothing exercised `_OpenAIVisionClient` itself before now.
    """

    def test_region_mode_sends_no_temperature(self):
        client = _OpenAIVisionClient(api_key="test")
        sdk = _FakeOpenAISDK("some text")
        client._client = sdk
        client.complete(images=[blank_image()], system_prompt="sys", user_prompt="", json_mode=False)
        assert "temperature" not in sdk.captured_kwargs

    def test_json_mode_sends_no_temperature_either(self):
        client = _OpenAIVisionClient(api_key="test")
        sdk = _FakeOpenAISDK('{"cells": ["x"]}')
        client._client = sdk
        client.complete(images=[blank_image()], system_prompt="sys", user_prompt="", json_mode=True)
        assert "temperature" not in sdk.captured_kwargs
        assert sdk.captured_kwargs["response_format"] == {"type": "json_object"}
