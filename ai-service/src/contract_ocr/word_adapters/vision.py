"""Vision-LLM adapter (default backend: GPT-5.6 Terra) — last resort, used
only where PyMuPDF/OcrAdapter cannot be trusted.

Vision models cannot report reliable coordinates, so this adapter never
asks for any and never uses one even if a response smuggled one in — every
`Word` it returns takes its bbox from the caller-supplied `Region`
(`region.bbox` in "region" mode, or the matching entry of `region.cells` in
"cells" mode), never from the model.

Two modes:
  - "region": one crop, transcribed as free text (like the existing
    `infrastructure/ocr/prompts.OCR_SYSTEM_PROMPT` contract); every
    resulting `Word` shares `region.bbox` since there is no finer geometry
    to give it.
  - "cells": `region.cells` gives N individual cell boxes; each is cropped
    and sent together in one call, and the model must return exactly N
    JSON results, in order — see `CELLS_SYSTEM_PROMPT`. A response with a
    different element count is a hard error (`VisionCellCountMismatch`);
    this adapter never guesses a realignment the way some other
    OCR-reconciliation code in this codebase does (e.g.
    `backend/app/document_processing.py`'s similarity-based line
    alignment) — a cell-for-cell contract is either satisfied exactly or
    rejected.
"""

from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from typing import Any, Literal

from contract_ocr.application.ports.ocr_engine import EngineUnavailable
from contract_ocr.infrastructure.ocr.openai_vision_ocr import DEFAULT_MODEL
from contract_ocr.infrastructure.ocr.prompts import OCR_SYSTEM_PROMPT
from contract_ocr.table_reconstruct.types import Bbox, Word

from .protocols import VisionClient
from .types import Region

VisionMode = Literal["region", "cells"]

CELLS_SYSTEM_PROMPT = """\
You are a precise OCR transcription engine reading individual table cells \
cropped from a Vietnamese contract. You will be shown one or more cell \
images, in the exact order they belong to the table.

Rules, in order of priority:
1. Transcribe each cell's visible text EXACTLY as printed — verbatim. \
Never compute, round, reformat, translate, or correct anything. Preserve \
Vietnamese diacritics exactly as shown.
2. Never invent, guess, or auto-complete a value you cannot clearly read.
3. An empty or blank cell -> null.
4. A cell whose text cannot be confidently read (illegible, cut off, \
smudged, ambiguous) -> the literal string "UNREADABLE". An honest \
"UNREADABLE" is always better than a confident wrong guess.
5. You MUST return exactly one result per cell image shown, in the same \
order, as {"cells": [...]}. Never merge, split, skip, reorder, or \
renumber cells. Do not include any coordinate, position, or bounding-box \
field — the caller already knows where each cell is.
6. Return JSON only. No markdown, no code fences, no commentary outside \
the JSON object.
"""


class VisionCellCountMismatch(RuntimeError):
    """The model returned a different number of cell results than cells
    were sent (or a malformed response). Raised, never silently realigned
    — see module docstring."""


class VisionAdapter:
    def __init__(self, mode: VisionMode = "region", client: VisionClient | None = None) -> None:
        self.mode = mode
        self._client = client

    def extract(self, image: Any, region: Region) -> list[Word]:
        if self.mode == "cells":
            return self._extract_cells(image, region)
        return self._extract_region(image, region)

    def _get_client(self) -> VisionClient:
        if self._client is None:
            self._client = _OpenAIVisionClient()
        return self._client

    def _extract_region(self, image: Any, region: Region) -> list[Word]:
        client = self._get_client()
        crop = _crop(image, region.bbox)
        raw = client.complete(
            images=[crop], system_prompt=OCR_SYSTEM_PROMPT, user_prompt="", json_mode=False
        )
        x0, y0, x1, y1 = region.bbox
        return [
            Word(text=line, x0=x0, y0=y0, x1=x1, y1=y1, page=region.page, source="vision")
            for line in raw.splitlines()
            if line.strip()
        ]

    def _extract_cells(self, image: Any, region: Region) -> list[Word]:
        if not region.cells:
            raise ValueError("VisionAdapter(mode='cells') requires region.cells")

        client = self._get_client()
        region_crop = _crop(image, region.bbox)
        cell_crops = [_crop(region_crop, _relative(cell, region.bbox)) for cell in region.cells]

        raw = client.complete(
            images=cell_crops,
            system_prompt=CELLS_SYSTEM_PROMPT,
            user_prompt=_cells_user_prompt(len(region.cells)),
            json_mode=True,
        )
        values = _parse_cells_response(raw, expected=len(region.cells))

        words: list[Word] = []
        for cell_bbox, value in zip(region.cells, values):
            if value is None:
                continue
            x0, y0, x1, y1 = cell_bbox
            words.append(Word(text=value, x0=x0, y0=y0, x1=x1, y1=y1, page=region.page, source="vision"))
        return words


def _cells_user_prompt(count: int) -> str:
    return (
        f"You are being sent exactly {count} cell image(s), in order. Return "
        f'{{"cells": [...]}} with exactly {count} element(s), one per cell, in the '
        "same order — follow every rule in the system prompt exactly."
    )


def _parse_cells_response(raw: str, expected: int) -> list[str | None]:
    try:
        payload = json.loads(raw)
        values = payload["cells"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise VisionCellCountMismatch(f"malformed cells response: {raw!r}") from exc

    if not isinstance(values, list) or len(values) != expected:
        got = len(values) if isinstance(values, list) else type(values).__name__
        raise VisionCellCountMismatch(f"expected {expected} cell result(s), got {got}")

    return [_parse_cell_value(v) for v in values]


def _parse_cell_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # The model added structure despite instructions not to (e.g. a
        # stray "bbox"/"coordinates" key) — only "text" ever survives;
        # model-reported coordinates are never used for anything.
        text = value.get("text")
        return text if isinstance(text, str) else None
    raise VisionCellCountMismatch(f"unexpected cell value type: {value!r}")


def _crop(image: Any, bbox: Bbox) -> Any:
    x0, y0, x1, y1 = (int(round(v)) for v in bbox)
    return image[y0:y1, x0:x1]


def _relative(bbox: Bbox, origin_bbox: Bbox) -> Bbox:
    ox0, oy0, _, _ = origin_bbox
    x0, y0, x1, y1 = bbox
    return (x0 - ox0, y0 - oy0, x1 - ox0, y1 - oy0)


class _OpenAIVisionClient:
    """Default `VisionClient`: OpenAI's vision API, `gpt-5.6-terra` by
    default (`infrastructure/ocr/openai_vision_ocr.DEFAULT_MODEL`). JSON
    mode uses `temperature=0` (matching
    `reconstruction.llm_resolver.OpenAIBoundaryResolver`'s structured-output
    call); free-text region mode leaves temperature at the model's default,
    matching `OpenAIVisionOCREngine` — gpt-5.6+ rejects non-default
    temperature on that call shape.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or DEFAULT_MODEL
        self._api_key = api_key
        self._client: Any = None

    def _load(self) -> Any:
        if self._client is None:
            key = self._api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise EngineUnavailable("OPENAI_API_KEY is not set")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise EngineUnavailable("openai package is not installed") from exc
            self._client = OpenAI(api_key=key)
        return self._client

    def complete(
        self, *, images: list[Any], system_prompt: str, user_prompt: str, json_mode: bool
    ) -> str:
        client = self._load()
        content: list[dict[str, Any]] = []
        if user_prompt:
            content.append({"type": "text", "text": user_prompt})
        for image in images:
            content.append(
                {"type": "image_url", "image_url": {"url": _to_data_url(image), "detail": "high"}}
            )

        kwargs: dict[str, Any] = {"max_completion_tokens": 4096}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            kwargs["temperature"] = 0

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            **kwargs,
        )
        return response.choices[0].message.content or ""


def _to_data_url(image: Any) -> str:
    from PIL import Image

    pil_image = image if isinstance(image, Image.Image) else Image.fromarray(image)
    buffer = BytesIO()
    pil_image.convert("RGB").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
