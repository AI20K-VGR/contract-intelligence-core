from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable

from openai import BadRequestError, OpenAI, UnprocessableEntityError

from app.llm import usage_ledger
from app.llm.observability import llm_generation, record_completion

_FORMAT_ERRORS = (BadRequestError, UnprocessableEntityError)

logger = logging.getLogger(__name__)


class LLMRequestBudgetExceeded(RuntimeError):
    """No provider request may start after the per-job call quota is spent."""


class LLMEmptyResponseError(RuntimeError):
    """The provider completed a request without returning assistant content."""


def _is_format_error(error: Exception) -> bool:
    if not isinstance(error, _FORMAT_ERRORS):
        return False
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return False
    detail = body.get("error", body)
    if not isinstance(detail, dict):
        return False
    param = str(detail.get("param") or "")
    message = str(detail.get("message") or "").casefold()
    return (
        param == "response_format"
        or param.startswith("response_format.")
        or (
            any(token in message for token in ("response_format", "json_object"))
            and any(token in message for token in ("unsupported", "not supported", "invalid"))
        )
    )


def _json_mode_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """OpenAI rejects ``response_format=json_object`` with a 400 unless some
    message contains the word "json"; a prompt that only shows the shape
    (``{"slots": ...}``) is not enough."""
    if any("json" in message["content"].casefold() for message in messages):
        return messages
    system, *rest = messages
    return [{**system, "content": system["content"] + "\nReturn a JSON object."}, *rest]


def _is_gpt5(model: str) -> bool:
    """GPT-5 family, also behind a provider prefix such as ``openai/gpt-5.5``."""

    return model.rsplit("/", 1)[-1].strip().casefold().startswith("gpt-5")


_REASONING_EFFORTS = frozenset({"minimal", "low", "medium", "high"})


def _sampling_options(model: str) -> dict[str, Any]:
    """Keep deterministic sampling where supported; reasoning GPT-5 rejects temperature."""
    if _is_gpt5(model):
        return {}
    return {"temperature": 0}


def _output_limit(model: str, tokens: int) -> dict[str, int]:
    """Chat Completions output cap: GPT-5 refuses ``max_tokens`` and takes
    ``max_completion_tokens``; other models keep ``max_tokens``."""

    if _is_gpt5(model):
        return {"max_completion_tokens": tokens}
    return {"max_tokens": tokens}


def call_with_timeout(fn: Callable[[], Any], seconds: float, *, name: str = "ai2-llm") -> Any:
    """Run ``fn`` and give up after ``seconds``.

    A call still running at the limit is abandoned on a daemon thread and the
    caller gets ``TimeoutError``; the HTTP request itself is also bounded by the
    SDK timeout, so the thread does not outlive it for long.
    """

    outcome: dict[str, Any] = {}
    # The caller's context (Langfuse trace of the question) goes with the call.
    context = contextvars.copy_context()

    def run() -> None:
        try:
            outcome["value"] = context.run(fn)
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


def _trace_history_size() -> int | None:
    """Most recent traces kept process-wide: AI2_LLM_TRACE_HISTORY, 0 = all."""

    try:
        size = int(os.getenv("AI2_LLM_TRACE_HISTORY", "1000"))
    except ValueError:
        return 1000
    return None if size <= 0 else size


class NineRouterClient:
    # Shared by every client for the life of the process (live evals read it):
    # bounded, or a long-running service keeps one entry per LLM call forever.
    all_traces: deque[dict[str, Any]] = deque(maxlen=_trace_history_size())

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
        self.model = model or os.getenv("AI2_LLM_MODEL", "gpt-5.5")
        self.strong_model = strong_model or os.getenv("AI2_LLM_STRONG_MODEL", self.model)
        if timeout is None:
            timeout = float(os.getenv("AI2_LLM_TIMEOUT_SECONDS", "45"))
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "missing",
            timeout=timeout,
            max_retries=0,
        )
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
        before_request: Callable[[], float] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """One logical completion. ``last_http_calls`` reports the HTTP requests it
        made (2 when the provider rejected ``response_format``) so the caller can
        charge every request to its budget. ``timeout`` overrides the per-request
        SDK timeout, e.g. with the time left before a job deadline.

        Inside a ``/query`` it is also one Langfuse generation with usage and cost."""

        model = self.strong_model if strong else self.model
        trace: dict[str, Any] = {}
        with llm_generation("ai2.llm.complete_json", model=model) as generation:
            try:
                return self._complete_json(
                    trace,
                    model,
                    system,
                    user,
                    strong=strong,
                    timeout=timeout,
                    before_request=before_request,
                    max_output_tokens=max_output_tokens,
                    reasoning_effort=reasoning_effort,
                )
            finally:
                record_completion(generation, trace)
                usage_ledger.record_trace(trace)

    def _complete_json(
        self,
        trace: dict[str, Any],
        model: str,
        system: str,
        user: str,
        *,
        strong: bool,
        timeout: float | None,
        before_request: Callable[[], float] | None,
        max_output_tokens: int | None,
        reasoning_effort: str | None,
    ) -> dict[str, Any]:
        """``complete_json`` itself; fills ``trace`` (also kept in ``self.traces``)."""

        sampling_options = _sampling_options(model)
        request_options: dict[str, Any] = {} if timeout is None else {"timeout": timeout}
        if max_output_tokens is not None:
            if type(max_output_tokens) is not int or max_output_tokens <= 0:
                raise ValueError("max_output_tokens must be a positive integer")
            request_options.update(_output_limit(model, max_output_tokens))
        if reasoning_effort is not None and _is_gpt5(model):
            if reasoning_effort not in _REASONING_EFFORTS:
                raise ValueError("unknown reasoning_effort")
            request_options["reasoning_effort"] = reasoning_effort
        # Local per call: a concurrent call on the same client must not reset this count.
        http_calls = 0
        started = time.perf_counter()
        trace.update(
            {
                "trace_id": uuid.uuid4().hex,
                "model": model,
                "strong": strong,
                "request_digest": hashlib.sha256(
                    (system + "\n" + user).encode("utf-8")
                ).hexdigest()[:16],
                "system_chars": len(system),
                "user_chars": len(user),
                "fallback_without_json_format": False,
            }
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            if before_request is not None:
                request_options["timeout"] = before_request()
            http_calls += 1
            resp = self._client.chat.completions.create(
                model=model,
                messages=_json_mode_messages(messages),
                response_format={"type": "json_object"},
                **sampling_options,
                **request_options,
            )
            text = resp.choices[0].message.content or ""
        except Exception as first_error:
            # Only a rejected request shape is worth a second request without
            # JSON mode; 429/5xx/timeouts go back to the caller's retry policy.
            if not _is_format_error(first_error):
                trace["error_type"] = type(first_error).__name__
                trace["http_calls"] = self.last_http_calls = http_calls
                trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                self.traces.append(trace)
                NineRouterClient.all_traces.append(dict(trace))
                raise
            trace["fallback_without_json_format"] = True
            trace["first_error_type"] = type(first_error).__name__
            try:
                if before_request is not None:
                    request_options["timeout"] = before_request()
                http_calls += 1
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **sampling_options,
                    **request_options,
                )
                text = resp.choices[0].message.content or ""
            except Exception as second_error:
                trace["error_type"] = type(second_error).__name__
                trace["http_calls"] = self.last_http_calls = http_calls
                trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                self.traces.append(trace)
                NineRouterClient.all_traces.append(dict(trace))
                raise
        trace["served_model"] = getattr(resp, "model", None)
        trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        trace["http_calls"] = self.last_http_calls = http_calls
        trace["response_chars"] = len(text)
        trace["finish_reason"] = getattr(resp.choices[0], "finish_reason", None)
        trace["truncated"] = trace["finish_reason"] == "length"
        usage = getattr(resp, "usage", None)
        if usage is not None:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = getattr(usage, key, None)
                if value is not None:
                    trace[key] = value
            details = getattr(usage, "completion_tokens_details", None)
            reasoning_tokens = getattr(details, "reasoning_tokens", None)
            if reasoning_tokens is not None:
                trace["reasoning_tokens"] = reasoning_tokens
            prompt_details = getattr(usage, "prompt_tokens_details", None)
            cached_tokens = getattr(prompt_details, "cached_tokens", None)
            if cached_tokens is not None:
                trace["cached_tokens"] = cached_tokens
        if not isinstance(text, str) or not text.strip():
            trace["error_type"] = "EmptyResponseError"
            trace["response_empty"] = True
            if trace["truncated"]:
                trace["truncated_by_reasoning"] = bool(trace.get("reasoning_tokens", 0))
            self.traces.append(trace)
            NineRouterClient.all_traces.append(dict(trace))
            raise LLMEmptyResponseError("provider returned an empty assistant response")
        try:
            data = _parse_json(text)
        except json.JSONDecodeError:
            trace["error_type"] = "ResponseParseError"
            self.traces.append(trace)
            NineRouterClient.all_traces.append(dict(trace))
            raise
        trace["json_keys"] = sorted(data)[:32]
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
                lambda: self._llm.complete_json(system, user, **kwargs),
                remaining,
                name="ai2-query-llm",
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
    except Exception as exc:
        # Model, HTTP status and exception type only: the message can echo the
        # request, and the key never belongs in a log.
        body = getattr(exc, "body", None)
        detail = body.get("error", body) if isinstance(body, dict) else {}
        detail = detail if isinstance(detail, dict) else {}
        logger.warning(
            "ai2.llm_probe_failed model=%s http_status=%s error=%s code=%s param=%s",
            client.model,
            getattr(exc, "status_code", None),
            type(exc).__name__,
            _safe_error_identifier(detail.get("code")),
            _safe_error_identifier(detail.get("param")),
        )
        return "unreachable"
    return "ready"


def _ping_configured_model(client: NineRouterClient) -> None:
    # Same parameter rules as complete_json(): a GPT-5 model refuses max_tokens
    # and temperature, which made /readyz report a working model unreachable.
    tokens = 64 if _is_gpt5(client.model) else 1
    timeout = 15.0 if _is_gpt5(client.model) else 3.0
    try:
        configured_tokens = int(os.getenv("AI2_LLM_PROBE_MAX_TOKENS", ""))
        if configured_tokens > 0:
            tokens = configured_tokens
    except ValueError:
        pass
    try:
        configured_timeout = float(os.getenv("AI2_LLM_PROBE_TIMEOUT_SECONDS", ""))
        if math.isfinite(configured_timeout) and configured_timeout > 0:
            timeout = configured_timeout
    except ValueError:
        pass
    # A one-token GPT-5 request can fail before producing an HTTP success.
    # Any successful response proves availability, even if finish_reason=length.
    client._client.with_options(timeout=timeout, max_retries=0).chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": "ping"}],
        **_output_limit(client.model, tokens),
        **_sampling_options(client.model),
    )


def _safe_error_identifier(value: Any) -> str | None:
    # Provider metadata is untrusted; never echo arbitrary text or credential-like values.
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]]{1,80}", value):
        return value
    return None


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
