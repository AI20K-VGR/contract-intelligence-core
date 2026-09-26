import base64
import json
import os
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.entities import Context, Line, OCRResult
from contract_ocr.infrastructure.observability import observation, response_usage
from contract_ocr.infrastructure.ocr.prompts import OCR_SYSTEM_PROMPT

# gpt-5.6-terra is OpenAI's mid-tier GPT-5.6 model (~$2.00/1M input, $12.00/1M output as
# of writing) with vision support — between the flagship gpt-5.6-sol and the budget
# gpt-5.6-luna. Model naming moves fast; override with the `model` config key if this no
# longer matches https://developers.openai.com/api/docs/models.
DEFAULT_MODEL = "gpt-5.6-terra"

# USD per token, keyed by model id, used to compute `cost_details` for Langfuse. Langfuse
# only auto-prices models it recognizes by name; a model id it doesn't know (any of this
# module's, so far) shows $0 unless we compute and attach the cost ourselves. Update
# alongside DEFAULT_MODEL's price comment above when OpenAI's pricing changes.
_PRICE_PER_TOKEN_USD = {
    "gpt-5.6-terra": {"input": 2.00 / 1_000_000, "output": 12.00 / 1_000_000},
}


def _cost_details(model: str, usage: dict[str, int] | None) -> dict[str, float] | None:
    prices = _PRICE_PER_TOKEN_USD.get(model)
    if not prices or not usage:
        return None
    input_cost = usage.get("input", 0) * prices["input"]
    output_cost = usage.get("output", 0) * prices["output"]
    return {"input": input_cost, "output": output_cost, "total": input_cost + output_cost}


class OpenAIVisionOCREngine(OCREngine):
    """Sends the rendered page image to an OpenAI vision model. Not local: page images
    leave this machine. Only use with non-confidential documents."""

    name = "openai_vision"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", DEFAULT_MODEL)
        self.prompt = config.get("prompt", OCR_SYSTEM_PROMPT)
        self.runtime_info = {"provider": "openai", "model": self.model}
        self._client = None
        self._unavailable = None

    def _load(self) -> None:
        if self._unavailable:
            raise EngineUnavailable(self._unavailable)
        if self._client is not None:
            return
        start = perf_counter()
        try:
            if not self.config.get("enabled", True):
                raise RuntimeError("OpenAI vision engine disabled in configuration")
            api_key = self.config.get("api_key") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            from openai import OpenAI

            client_kwargs: dict[str, Any] = {"api_key": api_key}
            if self.config.get("base_url"):
                client_kwargs["base_url"] = self.config["base_url"]
            self._client = OpenAI(**client_kwargs)
        except Exception as exc:
            self._unavailable = f"OpenAI vision unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        image = Image.fromarray(page_image).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        # gpt-5.6+ rejects the legacy max_tokens param (needs max_completion_tokens) and
        # rejects temperature overrides other than its default (1), so both are only
        # sent if explicitly configured rather than hardcoded.
        kwargs: dict[str, Any] = {
            "max_completion_tokens": self.config.get("max_tokens", 4096),
        }
        if "temperature" in self.config:
            kwargs["temperature"] = self.config["temperature"]
        with observation(
            "transcribe-page",
            as_type="generation",
            input={
                "document_id": context.document_id,
                "page_number": context.page,
                "image_width": image.width,
                "image_height": image.height,
            },
            metadata={"provider": "openai", "feature": "document-ocr"},
            model=self.model,
            model_parameters=kwargs,
        ) as generation:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url, "detail": "high"},
                            },
                        ],
                    },
                ],
                **kwargs,
            )
            text = response.choices[0].message.content or ""
            if generation is not None:
                usage = response_usage(response)
                generation.update(
                    output={"character_count": len(text)},
                    usage_details=usage,
                    cost_details=_cost_details(self.model, usage),
                )

        directory = Path(context.output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "raw.md"
        path.write_text(text, encoding="utf-8")

        lines = [
            Line(line_id=f"{context.document_id}-p{context.page:03d}-l{i:04d}", text=line_text)
            for i, line_text in enumerate(text.splitlines(), 1)
            if line_text.strip()
        ]
        return OCRResult(lines=lines, raw_markdown=text, raw_output_path=str(path.resolve()))


_REGION_INSTRUCTIONS = """\
Each image below is a crop of one region of the same contract page, labelled with \
its region id. Transcribe every crop independently under the rules above. Skip any \
line that is cut off at the top or bottom edge of a crop -- transcribe only lines \
fully inside it. Reply with JSON only, no prose, in exactly this shape:
{"regions": [{"id": "<region id>", "text": "<transcription, line breaks as \\n>"}]}"""


def _parse_regions(text: str) -> dict[str, str]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    regions = payload.get("regions") if isinstance(payload, dict) else None
    return {
        str(item["id"]): str(item["text"])
        for item in regions or []
        if isinstance(item, dict) and "id" in item and isinstance(item.get("text"), str)
    }


class OpenAIRegionReader(OpenAIVisionOCREngine):
    """Blind re-reads of a few page regions, batched into one request per page.

    Used as the tie-breaking third reader: it is shown only the crops, never
    another engine's transcription, so its reading stays independent.
    """

    name = "openai_region_reader"

    def read_regions(self, crops: dict[str, np.ndarray], context: Context) -> dict[str, str]:
        if not crops:
            return {}
        self._load()
        content: list[dict[str, Any]] = [{"type": "text", "text": _REGION_INSTRUCTIONS}]
        for region_id, crop in crops.items():
            buffer = BytesIO()
            Image.fromarray(crop).convert("RGB").save(buffer, format="PNG")
            url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
            content.append({"type": "text", "text": f"Region {region_id}:"})
            content.append({"type": "image_url", "image_url": {"url": url, "detail": "high"}})
        kwargs: dict[str, Any] = {"max_completion_tokens": self.config.get("max_tokens", 4096)}
        with observation(
            "arbitrate-regions",
            as_type="generation",
            input={
                "document_id": context.document_id,
                "page_number": context.page,
                "region_count": len(crops),
            },
            metadata={"provider": "openai", "feature": "document-ocr-arbitration"},
            model=self.model,
            model_parameters=kwargs,
        ) as generation:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": content},
                ],
                **kwargs,
            )
            text = response.choices[0].message.content or ""
            regions = _parse_regions(text)
            if generation is not None:
                usage = response_usage(response)
                generation.update(
                    output={"region_count": len(regions)},
                    usage_details=usage,
                    cost_details=_cost_details(self.model, usage),
                )
        return regions
