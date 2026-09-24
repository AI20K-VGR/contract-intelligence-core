"""Per-job execution policy and resource accounting for AI2 processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from app.llm.client import NineRouterClient


class ProcessingTimeout(RuntimeError):
    """The request exceeded its Backend-provided processing deadline."""


def _is_retryable_provider_error(exc: Exception) -> bool:
    """Keep retries limited to transient transport/provider failures."""

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    return isinstance(status, int) and (status == 408 or status == 409 or status == 429 or status >= 500)


@dataclass
class ProcessingRuntime:
    """Mutable, request-scoped execution budget.

    ``max_llm_calls`` counts logical completion operations. A provider-level
    response-format fallback inside ``NineRouterClient`` remains one logical
    operation from the request budget's perspective.
    """

    egress_allowed: bool = False
    use_vector: bool = False
    max_processing_seconds: int = 300
    max_llm_calls: int = 0
    max_embedding_tokens: int = 0
    retry_limit: int = 1
    started_at: float = field(default_factory=monotonic)
    llm_calls_used: int = 0
    embedding_tokens_used: int = 0
    fallback_count: int = 0
    issues: list[tuple[str, str]] = field(default_factory=list)

    @property
    def deadline(self) -> float:
        return self.started_at + self.max_processing_seconds

    def checkpoint(self) -> None:
        if monotonic() > self.deadline:
            raise ProcessingTimeout("processing time budget exceeded")

    def add_issue(self, code: str, message: str) -> None:
        if (code, message) not in self.issues:
            self.issues.append((code, message))

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
        """Call NineRouter with one retry, then return ``None`` for fallback."""

        if not self.egress_allowed:
            self.add_issue("EGRESS_DENIED", "external model access is not approved")
            self.fallback_count += 1
            return None
        if client is None or not client.configured():
            self.add_issue("LLM_UNAVAILABLE", "NineRouter is not configured")
            self.fallback_count += 1
            return None

        attempts = self.retry_limit + 1
        for attempt in range(attempts):
            self.checkpoint()
            if self.llm_calls_used >= self.max_llm_calls:
                self.add_issue("LLM_BUDGET_EXCEEDED", "maximum logical LLM calls reached")
                self.fallback_count += 1
                return None
            self.llm_calls_used += 1
            try:
                data = client.complete_json(system, user, strong=strong)
                if not isinstance(data, dict):
                    raise ValueError("NineRouter response must be a JSON object")
                return data
            except Exception as exc:
                if not _is_retryable_provider_error(exc):
                    self.add_issue("LLM_NON_RETRYABLE", f"NineRouter rejected request: {type(exc).__name__}")
                    self.fallback_count += 1
                    return None
                if attempt + 1 < attempts:
                    continue
                self.add_issue("LLM_RETRY_EXHAUSTED", f"NineRouter failed: {type(exc).__name__}")
                self.fallback_count += 1
                return None
        return None

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
