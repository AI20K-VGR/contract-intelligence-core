"""Per-job execution policy and resource accounting for AI2 processing."""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable

import openai

from app.llm.client import (
    LLMRequestBudgetExceeded,
    NineRouterClient,
    _safe_error_identifier,
    call_with_timeout,
)

logger = logging.getLogger(__name__)

# Vietnamese messages for every code a job can end with (ST-067, D-4). The UI
# shows them as-is, so they say what happened and that the result needs review.
ISSUE_MESSAGES_VI: dict[str, str] = {
    "LLM_RATE_LIMITED": (
        "Nhà cung cấp LLM giới hạn tần suất (429) sau số lần thử cho phép; "
        "phần còn lại chỉ trích xuất cục bộ, cần người xem lại."
    ),
    "LLM_UNAVAILABLE": (
        "Dịch vụ LLM không phản hồi hoặc đang quá tải (5xx/529/mất kết nối); "
        "phần còn lại chỉ trích xuất cục bộ, cần người xem lại."
    ),
    "LLM_TIMEOUT": "Lời gọi LLM quá thời gian chờ; phần còn lại chỉ trích xuất cục bộ, cần người xem lại.",
    "LLM_QUOTA_EXHAUSTED": (
        "Tài khoản nhà cung cấp LLM đã hết hạn mức/credit; AI2 ngừng gọi mô hình cho hồ sơ này, "
        "phần còn lại chỉ trích xuất cục bộ. Cần nạp hạn mức rồi xử lý lại."
    ),
    "LLM_BUDGET_EXCEEDED": (
        "Đã dùng hết số lượt gọi LLM cho hồ sơ này; các mục còn lại chỉ trích xuất cục bộ, cần người xem lại."
    ),
    "PROCESSING_TIMEOUT": (
        "Hết thời gian xử lý hồ sơ; kết quả gồm phần đã xong trước khi hết giờ, cần người xem lại."
    ),
    "EGRESS_DENIED": (
        "Chưa cho phép gửi dữ liệu ra mô hình bên ngoài; hồ sơ chỉ được trích xuất cục bộ, cần người xem lại."
    ),
    "AI2_WORKER_CRASHED": "Tiến trình xử lý hồ sơ này bị dừng (thường do hết bộ nhớ); có thể gửi lại hồ sơ.",
    "AI2_WORKER_RESTARTED": "Tiến trình xử lý AI2 bị dừng giữa chừng (khởi động lại); có thể gửi lại hồ sơ.",
}

# Runtime issues that explain why a job stopped using the LLM. They are
# surfaced as handoff issues so the code reaches the wire ``errors[]``.
TERMINATION_CODES = frozenset(
    {"LLM_RATE_LIMITED", "LLM_UNAVAILABLE", "LLM_TIMEOUT", "LLM_BUDGET_EXCEEDED", "LLM_QUOTA_EXHAUSTED"}
)
# 429 bodies that mean the account cannot be served at all, not "slow down": retrying only
# burns the job's call budget and time.
_QUOTA_EXHAUSTED_CODES = frozenset({
    "credit_balance_exhausted", "insufficient_quota", "billing_hard_limit_reached", "billing_not_active",
})


def _quota_exhausted(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    body = getattr(exc, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    return status == 429 and isinstance(detail, dict) and (
        detail.get("code") in _QUOTA_EXHAUSTED_CODES or detail.get("type") in _QUOTA_EXHAUSTED_CODES
    )

_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 8.0


class ProcessingTimeout(RuntimeError):
    """The request exceeded its Backend-provided processing deadline."""


def classify_provider_error(exc: BaseException) -> str | None:
    """Termination code for a transient provider failure, ``None`` if not retryable.

    ``APITimeoutError`` subclasses ``APIConnectionError``, so timeouts are
    checked first.
    """

    if isinstance(exc, (openai.APITimeoutError, TimeoutError)):
        return "LLM_TIMEOUT"
    if isinstance(exc, openai.RateLimitError):
        return "LLM_RATE_LIMITED"
    if isinstance(exc, (openai.APIConnectionError, ConnectionError)):
        return "LLM_UNAVAILABLE"
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if not isinstance(status, int):
        return None
    if status == 429:
        return "LLM_RATE_LIMITED"
    if status == 408:
        return "LLM_TIMEOUT"
    if status == 409 or status >= 500:
        return "LLM_UNAVAILABLE"
    return None


def _log_provider_failure(client: Any, exc: BaseException, attempt: int, operation: str | None) -> None:
    # Identifiers only: the provider message can echo contract text.
    body = getattr(exc, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    logger.warning(
        "ai2.llm_call_failed operation=%s model=%s attempt=%s error=%s http_status=%s code=%s param=%s retry_code=%s",
        operation or "unlabelled",
        getattr(client, "model", None),
        attempt + 1,
        type(exc).__name__,
        getattr(exc, "status_code", None),
        _safe_error_identifier(detail.get("code")),
        _safe_error_identifier(detail.get("param")),
        classify_provider_error(exc),
    )


# Span-picking calls need no long reasoning (#124). Off unless set; production compose
# defaults it to "low". Sent to GPT-5 models only.
LIGHT_REASONING_ENV = "AI2_LLM_LIGHT_REASONING_EFFORT"
LIGHT_REASONING_OPERATIONS = frozenset({"slot_context", "alias"})


def _reasoning_effort(operation: str | None) -> str | None:
    if operation not in LIGHT_REASONING_OPERATIONS:
        return None
    return os.getenv(LIGHT_REASONING_ENV, "").strip().casefold() or None


def _log_call(client: Any, attempt: int, operation: str | None) -> None:
    # Timing and token counts only, never the prompt or the answer.
    traces = getattr(client, "traces", None)
    trace = traces[-1] if isinstance(traces, list) and traces else {}
    logger.info(
        "ai2.llm_call operation=%s model=%s served_model=%s attempt=%s latency_ms=%s http_calls=%s "
        "prompt_tokens=%s completion_tokens=%s reasoning_tokens=%s",
        operation or "unlabelled",
        trace.get("model", getattr(client, "model", None)),
        trace.get("served_model"),
        attempt + 1,
        trace.get("latency_ms"),
        trace.get("http_calls"),
        trace.get("prompt_tokens"),
        trace.get("completion_tokens"),
        trace.get("reasoning_tokens"),
    )


def _retry_after_seconds(exc: BaseException) -> float | None:
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    try:
        value = float(headers.get("retry-after", ""))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _env_positive(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass
class ProcessingRuntime:
    """Mutable, request-scoped execution budget.

    ``max_llm_calls`` counts HTTP requests to the provider, including retries
    and the client's response-format fallback. ``max_attempts`` bounds retries
    of one logical call (env ``AI2_LLM_MAX_RETRIES``, default 3). Each request
    is cut at ``min(AI2_LLM_TIMEOUT_SECONDS, time left before the deadline)``.
    """

    egress_allowed: bool = False
    use_vector: bool = False
    max_processing_seconds: int = 300
    max_llm_calls: int = 0
    max_embedding_tokens: int = 0
    max_attempts: int = field(default_factory=lambda: int(_env_positive("AI2_LLM_MAX_RETRIES", 3)))
    call_timeout_seconds: float = field(default_factory=lambda: _env_positive("AI2_LLM_TIMEOUT_SECONDS", 45))
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    started_at: float | None = None
    llm_calls_used: int = 0
    embedding_tokens_used: int = 0
    fallback_count: int = 0
    # Set once the provider reports an exhausted quota; later calls in the job send nothing.
    provider_exhausted: bool = False
    default_max_output_tokens: int | None = None
    default_operation_deadline: float | None = None
    issues: list[tuple[str, str]] = field(default_factory=list)
    # Receives {step, done, total, unit} for GET /jobs while RUNNING; advisory, never fails a job.
    on_progress: Callable[[dict[str, Any]], None] | None = field(default=None, repr=False)
    _request_lock: Any = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = self.clock()

    @property
    def deadline(self) -> float:
        return self.started_at + self.max_processing_seconds

    def remaining(self) -> float:
        return self.deadline - self.clock()

    def report_progress(self, step: str, done: int, total: int, unit: str) -> None:
        if self.on_progress is None:
            return
        try:
            self.on_progress({"step": step, "done": max(0, min(done, total)), "total": max(total, 1), "unit": unit})
        except Exception:
            logger.warning("ai2.progress_report_failed step=%s", step, exc_info=True)

    def checkpoint(self) -> None:
        if self.remaining() < 0:
            raise ProcessingTimeout("processing time budget exceeded")

    def add_issue(self, code: str, message: str) -> None:
        if (code, message) not in self.issues:
            self.issues.append((code, message))

    def _fall_back(self, code: str, message: str | None = None) -> None:
        self.add_issue(code, message or ISSUE_MESSAGES_VI.get(code, code))
        self.fallback_count += 1

    def account_embedding_tokens(self, tokens: int) -> bool:
        """Account embedding work without allowing a provider call past quota."""

        if tokens < 0:
            raise ValueError("tokens must be non-negative")
        if self.max_embedding_tokens and self.embedding_tokens_used + tokens > self.max_embedding_tokens:
            self.add_issue("EMBEDDING_BUDGET_EXCEEDED", "maximum embedding tokens reached")
            return False
        self.embedding_tokens_used += tokens
        return True

    def complete_json(
        self,
        client: NineRouterClient | None,
        system: str,
        user: str,
        *,
        strong: bool = False,
        max_output_tokens: int | None = None,
        operation_deadline: float | None = None,
        operation: str | None = None,
    ) -> dict[str, Any] | None:
        """Call the LLM within budget and deadline; ``None`` means use the local fallback.

        Raises ``ProcessingTimeout`` when the job deadline passes, so the caller
        can stop and keep what it already extracted.
        """

        max_output_tokens = max_output_tokens if max_output_tokens is not None else self.default_max_output_tokens
        operation_deadline = operation_deadline if operation_deadline is not None else self.default_operation_deadline
        if operation_deadline is not None and (type(operation_deadline) not in {int, float}
                                               or not math.isfinite(operation_deadline)):
            raise ValueError("operation_deadline must be finite")
        def operation_remaining():
            return min(self.remaining(), operation_deadline - self.clock()) if operation_deadline is not None else self.remaining()
        def context_exhausted():
            self._fall_back("CONTEXT_TIME_CAP", "Context operation deadline exceeded; job remains reviewable")
        if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
            raise ValueError("max_output_tokens must be a positive integer")
        if not self.egress_allowed:
            self._fall_back("EGRESS_DENIED")
            return None
        if client is None or not client.configured():
            self._fall_back("LLM_UNAVAILABLE", "NineRouter is not configured")
            return None
        if self.provider_exhausted:
            return None

        last_code: str | None = None
        for attempt in range(max(self.max_attempts, 1)):
            if self.remaining() <= 0:
                raise ProcessingTimeout("processing time budget exceeded")
            remaining = operation_remaining()
            if remaining <= 0:
                context_exhausted()
                return None
            if self.llm_calls_used >= self.max_llm_calls:
                self._fall_back(last_code or "LLM_BUDGET_EXCEEDED")
                return None
            call_timeout = min(self.call_timeout_seconds, remaining)
            call_deadline = self.clock() + call_timeout
            cancelled = threading.Event()
            reserve = partial(self._reserve_http_request, call_deadline, cancelled)
            try:
                data = call_with_timeout(
                    partial(self._invoke, client, system, user, strong, call_timeout, reserve, max_output_tokens,
                            _reasoning_effort(operation)), call_timeout,
                )
            except LLMRequestBudgetExceeded:
                self._fall_back("LLM_BUDGET_EXCEEDED")
                return None
            except Exception as exc:
                _log_provider_failure(client, exc, attempt, operation)
                if _quota_exhausted(exc):
                    self.provider_exhausted = True
                    self._fall_back("LLM_QUOTA_EXHAUSTED")
                    return None
                if self.remaining() <= 0:
                    raise ProcessingTimeout("processing time budget exceeded") from exc
                if operation_remaining() <= 0:
                    context_exhausted()
                    return None
                code = classify_provider_error(exc)
                if code is None:
                    self._fall_back("LLM_NON_RETRYABLE", f"NineRouter rejected request: {type(exc).__name__}")
                    return None
                last_code = code
                if attempt + 1 >= self.max_attempts or self.llm_calls_used >= self.max_llm_calls:
                    break
                delay = _retry_after_seconds(exc)
                if delay is None:
                    delay = min(_BACKOFF_CAP_SECONDS, _BACKOFF_BASE_SECONDS * 2**attempt)
                if delay >= operation_remaining():
                    if operation_deadline is not None and operation_deadline < self.deadline:
                        context_exhausted()
                        return None
                    break  # waiting would run past the deadline
                self.sleep(delay)
                continue
            finally:
                cancelled.set()
            if operation_remaining() <= 0:
                context_exhausted()
                return None
            _log_call(client, attempt, operation)
            if not isinstance(data, dict):
                self._fall_back("LLM_NON_RETRYABLE", "NineRouter response must be a JSON object")
                return None
            return data
        self._fall_back(last_code or "LLM_BUDGET_EXCEEDED")
        return None

    def _reserve_http_request(self, call_deadline: float, cancelled: threading.Event) -> float:
        with self._request_lock:
            remaining = self.remaining()
            if remaining <= 0:
                raise ProcessingTimeout("processing time budget exceeded")
            if cancelled.is_set() or self.clock() >= call_deadline:
                raise TimeoutError("LLM call deadline exceeded")
            if self.llm_calls_used >= self.max_llm_calls:
                raise LLMRequestBudgetExceeded("maximum LLM HTTP requests reached")
            self.llm_calls_used += 1
            return min(self.call_timeout_seconds, remaining, call_deadline - self.clock())

    def _invoke(
        self, client: Any, system: str, user: str, strong: bool, timeout: float,
        reserve: Callable[[], float],
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> Any:
        # Only the real client takes a per-request timeout; test doubles keep
        # the plain signature and are bounded by ``call_with_timeout``.
        if isinstance(client, NineRouterClient):
            token_options = {} if max_output_tokens is None else {"max_output_tokens": max_output_tokens}
            if reasoning_effort is not None:
                token_options["reasoning_effort"] = reasoning_effort
            return client.complete_json(
                system, user, strong=strong, timeout=timeout,
                before_request=reserve,
                **token_options,
            )
        reserve()
        return client.complete_json(system, user, strong=strong)

    def snapshot(self) -> dict[str, Any]:
        return {
            "egress_allowed": self.egress_allowed,
            "use_vector": self.use_vector,
            "max_processing_seconds": self.max_processing_seconds,
            "max_llm_calls": self.max_llm_calls,
            "max_embedding_tokens": self.max_embedding_tokens,
            "llm_calls_used": self.llm_calls_used,
            "llm_calls_remaining": max(0, self.max_llm_calls - self.llm_calls_used),
            "embedding_tokens_used": self.embedding_tokens_used,
            "embedding_tokens_remaining": max(0, self.max_embedding_tokens - self.embedding_tokens_used)
            if self.max_embedding_tokens
            else None,
            "fallback_count": self.fallback_count,
        }
