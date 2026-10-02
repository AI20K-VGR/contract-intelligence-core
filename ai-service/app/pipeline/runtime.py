"""Per-job execution policy and resource accounting for AI2 processing."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable

import openai

from app.llm.client import LLMRequestBudgetExceeded, NineRouterClient, call_with_timeout

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
    "LLM_BUDGET_EXCEEDED": (
        "Đã dùng hết số lượt gọi LLM cho hồ sơ này; các mục còn lại chỉ trích xuất cục bộ, cần người xem lại."
    ),
    "PROCESSING_TIMEOUT": (
        "Hết thời gian xử lý hồ sơ; kết quả gồm phần đã xong trước khi hết giờ, cần người xem lại."
    ),
    "EGRESS_DENIED": (
        "Chưa cho phép gửi dữ liệu ra mô hình bên ngoài; hồ sơ chỉ được trích xuất cục bộ, cần người xem lại."
    ),
    "AI2_WORKER_RESTARTED": "Tiến trình xử lý AI2 bị dừng giữa chừng (khởi động lại); có thể gửi lại hồ sơ.",
}

# Runtime issues that explain why a job stopped using the LLM. They are
# surfaced as handoff issues so the code reaches the wire ``errors[]``.
TERMINATION_CODES = frozenset(
    {"LLM_RATE_LIMITED", "LLM_UNAVAILABLE", "LLM_TIMEOUT", "LLM_BUDGET_EXCEEDED"}
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
    issues: list[tuple[str, str]] = field(default_factory=list)
    _request_lock: Any = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = self.clock()

    @property
    def deadline(self) -> float:
        return self.started_at + self.max_processing_seconds

    def remaining(self) -> float:
        return self.deadline - self.clock()

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
    ) -> dict[str, Any] | None:
        """Call the LLM within budget and deadline; ``None`` means use the local fallback.

        Raises ``ProcessingTimeout`` when the job deadline passes, so the caller
        can stop and keep what it already extracted.
        """

        if not self.egress_allowed:
            self._fall_back("EGRESS_DENIED")
            return None
        if client is None or not client.configured():
            self._fall_back("LLM_UNAVAILABLE", "NineRouter is not configured")
            return None

        last_code: str | None = None
        for attempt in range(max(self.max_attempts, 1)):
            remaining = self.remaining()
            if remaining <= 0:
                raise ProcessingTimeout("processing time budget exceeded")
            if self.llm_calls_used >= self.max_llm_calls:
                self._fall_back(last_code or "LLM_BUDGET_EXCEEDED")
                return None
            call_timeout = min(self.call_timeout_seconds, remaining)
            call_deadline = self.clock() + call_timeout
            cancelled = threading.Event()
            reserve = partial(self._reserve_http_request, call_deadline, cancelled)
            try:
                data = call_with_timeout(
                    partial(self._invoke, client, system, user, strong, call_timeout, reserve), call_timeout,
                )
            except LLMRequestBudgetExceeded:
                self._fall_back("LLM_BUDGET_EXCEEDED")
                return None
            except Exception as exc:
                if self.remaining() <= 0:
                    raise ProcessingTimeout("processing time budget exceeded") from exc
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
                if delay >= self.remaining():
                    break  # waiting would run past the deadline
                self.sleep(delay)
                continue
            finally:
                cancelled.set()
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
    ) -> Any:
        # Only the real client takes a per-request timeout; test doubles keep
        # the plain signature and are bounded by ``call_with_timeout``.
        if isinstance(client, NineRouterClient):
            return client.complete_json(
                system, user, strong=strong, timeout=timeout,
                before_request=reserve,
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
            "embedding_tokens_used": self.embedding_tokens_used,
            "fallback_count": self.fallback_count,
        }
