from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from typing import Any, Callable

from openai import BadRequestError, OpenAI, UnprocessableEntityError

_FORMAT_ERRORS = (BadRequestError, UnprocessableEntityError)


def call_with_timeout(fn: Callable[[], Any], seconds: float, *, name: str = "ai2-llm") -> Any:
    """Run ``fn`` and give up after ``seconds``.

    A call still running at the limit is abandoned on a daemon thread and the
    caller gets ``TimeoutError``; the HTTP request itself is also bounded by the
    SDK timeout, so the thread does not outlive it for long.
    """

    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["value"] = fn()
        except BaseException as exc:  # re-raised on the caller thread below
            outcome["error"] = exc

    worker = threading.Thread(target=run, name=name, daemon=True)
    worker.start()
    worker.join(max(seconds, 0.0))
    if worker.is_alive():
        raise TimeoutError(f"call exceeded {seconds:g}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


class NineRouterClient:
    all_traces: list[dict[str, Any]] = []

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        strong_model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("AI2_LLM_BASE_URL", "http://localhost:20128/v1")
        if api_key is None:
            self.api_key = os.getenv("AI2_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        else:
            self.api_key = api_key
        self.model = model or os.getenv("AI2_LLM_MODEL", "gpt-4o-mini")
        self.strong_model = strong_model or os.getenv("AI2_LLM_STRONG_MODEL", self.model)
        if timeout is None:
            timeout = float(os.getenv("AI2_LLM_TIMEOUT_SECONDS", "45"))
        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key or "missing", timeout=timeout, max_retries=0)
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "sk-replace-me"

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        strong: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """One logical completion. ``last_http_calls`` reports the HTTP requests it
        made (2 when the provider rejected ``response_format``) so the caller can
        charge every request to its budget. ``timeout`` overrides the per-request
        SDK timeout, e.g. with the time left before a job deadline."""

        model = self.strong_model if strong else self.model
        request_options: dict[str, Any] = {} if timeout is None else {"timeout": timeout}
        self.last_http_calls = 1
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
                **request_options,
            )
            text = resp.choices[0].message.content or "{}"
        except Exception as first_error:
            # Only a rejected request shape is worth a second request without
            # JSON mode; 429/5xx/timeouts go back to the caller's retry policy.
            if not isinstance(first_error, _FORMAT_ERRORS):
                trace["error_type"] = type(first_error).__name__
                trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                self.traces.append(trace)
                NineRouterClient.all_traces.append(dict(trace))
                raise
            trace["fallback_without_json_format"] = True
            trace["first_error_type"] = type(first_error).__name__
            self.last_http_calls = 2
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    **request_options,
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


QUERY_LLM_TIMEOUT_CAP_SECONDS = 15.0


def query_llm_timeout_seconds() -> float:
    """Total LLM budget for one ``/query``: ``min(15, AI2_QUERY_LLM_TIMEOUT_SECONDS)``.

    A missing, unparsable or non-positive value falls back to the 15 s cap.
    """

    try:
        value = float(os.getenv("AI2_QUERY_LLM_TIMEOUT_SECONDS", ""))
    except ValueError:
        return QUERY_LLM_TIMEOUT_CAP_SECONDS
    return min(QUERY_LLM_TIMEOUT_CAP_SECONDS, value) if value > 0 else QUERY_LLM_TIMEOUT_CAP_SECONDS


class DeadlineLLM:
    """Bound the total wall time one request spends in LLM calls.

    The SDK timeout covers a single HTTP attempt, but ``complete_json`` may
    make two attempts and L2 may call more than once. The budget starts at the
    first call and is shared by later ones. A call still running at the
    deadline is abandoned on a daemon thread and the caller gets
    ``TimeoutError``, which L2 turns into its retrieval-only fallback.
    """

    def __init__(self, llm: Any, seconds: float) -> None:
        self._llm = llm
        self._seconds = seconds
        self._deadline: float | None = None

    @property
    def traces(self) -> list[dict[str, Any]]:
        return self._llm.traces

    def configured(self) -> bool:
        return self._llm.configured()

    def complete_json(self, system: str, user: str, **kwargs: Any) -> dict[str, Any]:
        now = time.monotonic()
        if self._deadline is None:
            self._deadline = now + self._seconds
        remaining = self._deadline - now
        if remaining <= 0:
            raise TimeoutError(f"query LLM budget of {self._seconds:g}s is spent")
        try:
            return call_with_timeout(
                lambda: self._llm.complete_json(system, user, **kwargs), remaining, name="ai2-query-llm"
            )
        except TimeoutError as exc:
            raise TimeoutError(f"query LLM exceeded its {self._seconds:g}s budget") from exc


def llm_status(
    client: NineRouterClient,
    probe: Callable[[NineRouterClient], None] | None = None,
) -> str:
    """off = no key, ready = the configured model answered, unreachable = the call failed."""

    if not client.configured():
        return "off"
    check = probe or _ping_configured_model
    try:
        check(client)
    except Exception:
        return "unreachable"
    return "ready"


def _ping_configured_model(client: NineRouterClient) -> None:
    client._client.with_options(timeout=3.0, max_retries=0).chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
        temperature=0,
    )


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
