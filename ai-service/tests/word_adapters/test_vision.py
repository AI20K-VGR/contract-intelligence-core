"""VisionAdapter — region and cells modes, both against a faked VisionClient."""

from __future__ import annotations

import json

import pytest

from contract_ocr.word_adapters import Region, VisionAdapter, VisionCellCountMismatch

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

    def test_wrong_element_count_raises_and_never_auto_realigns(self):
        cells = ((0.0, 0.0, 50.0, 20.0), (60.0, 0.0, 110.0, 20.0))
        client = FakeVisionClient(json.dumps({"cells": ["only one"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        with pytest.raises(VisionCellCountMismatch):
            VisionAdapter(mode="cells", client=client).extract(blank_image(), region)

    def test_malformed_json_raises(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient("not json at all")
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        with pytest.raises(VisionCellCountMismatch):
            VisionAdapter(mode="cells", client=client).extract(blank_image(), region)

    def test_missing_cells_key_raises(self):
        cells = ((0.0, 0.0, 50.0, 20.0),)
        client = FakeVisionClient(json.dumps({"rows": ["x"]}))
        region = Region(page=1, bbox=(0.0, 0.0, 200.0, 50.0), cells=cells)
        with pytest.raises(VisionCellCountMismatch):
            VisionAdapter(mode="cells", client=client).extract(blank_image(), region)

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
