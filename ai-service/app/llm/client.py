from __future__ import annotations

import json
import hashlib
import os
import re
import time
from typing import Any

from openai import OpenAI


class NineRouterClient:
    all_traces: list[dict[str, Any]] = []

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        strong_model: str | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("AI2_LLM_BASE_URL", "http://localhost:20128/v1")
        self.api_key = api_key or os.getenv("AI2_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.model = model or os.getenv("AI2_LLM_MODEL", "gpt-4o-mini")
        self.strong_model = strong_model or os.getenv("AI2_LLM_STRONG_MODEL", self.model)
        timeout = float(os.getenv("AI2_LLM_TIMEOUT_SECONDS", "45"))
        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key or "missing", timeout=timeout, max_retries=0)
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "sk-replace-me"

    def complete_json(self, system: str, user: str, *, strong: bool = False) -> dict[str, Any]:
        model = self.strong_model if strong else self.model
        started = time.perf_counter()
        trace: dict[str, Any] = {
            "model": model,
            "strong": strong,
            "request_digest": hashlib.sha256((system + "\n" + user).encode("utf-8")).hexdigest()[:16],
            "system_chars": len(system),
            "user_chars": len(user),
            "fallback_without_json_format": False,
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
            text = resp.choices[0].message.content or "{}"
        except Exception as first_error:
            trace["fallback_without_json_format"] = True
            trace["first_error_type"] = type(first_error).__name__
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                )
                text = resp.choices[0].message.content or "{}"
            except Exception as second_error:
                trace["error_type"] = type(second_error).__name__
                trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                self.traces.append(trace)
                NineRouterClient.all_traces.append(dict(trace))
                raise
        data = _parse_json(text)
        trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        trace["response_chars"] = len(text)
        trace["json_keys"] = sorted(data)[:32]
        usage = getattr(resp, "usage", None)
        if usage is not None:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = getattr(usage, key, None)
                if value is not None:
                    trace[key] = value
        self.traces.append(trace)
        NineRouterClient.all_traces.append(dict(trace))
        return data


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {"value": data}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"raw": text}
