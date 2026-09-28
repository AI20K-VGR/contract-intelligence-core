"""OpenAI-compatible embedding discovery and client helpers.

The client is intentionally separate from chat completion: a NineRouter can
serve chat models without serving an embeddings model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import OpenAI


PROBE_TEXT = "ai2_embedding_capability_probe_v1"


@dataclass(frozen=True)
class EmbeddingModelInfo:
    model: str
    dimensions: int
    probed: bool = True
    error: str | None = None


@dataclass
class EmbeddingCapability:
    status: str
    models: list[EmbeddingModelInfo] = field(default_factory=list)
    selected_model: str | None = None
    dimensions: int | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "models": [
                {"model": item.model, "dimensions": item.dimensions, "error": item.error}
                for item in self.models
            ],
            "selected_model": self.selected_model,
            "dimensions": self.dimensions,
            "error": self.error,
        }


class OpenAICompatibleEmbeddingClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        client: Any | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("AI2_EMBEDDING_BASE_URL") or os.getenv(
            "AI2_LLM_BASE_URL", "http://localhost:20128/v1"
        )
        self.api_key = api_key or os.getenv("AI2_EMBEDDING_API_KEY") or os.getenv("AI2_LLM_API_KEY") or os.getenv(
            "OPENAI_API_KEY", ""
        )
        self.model = model or os.getenv("AI2_EMBEDDING_MODEL") or ""
        raw_dimensions = dimensions if dimensions is not None else os.getenv("AI2_EMBEDDING_DIMENSIONS")
        self.dimensions = int(raw_dimensions) if raw_dimensions else None
        self._client_injected = client is not None
        timeout = float(os.getenv("AI2_EMBEDDING_TIMEOUT_SECONDS", "45"))
        self.client = client or OpenAI(base_url=self.base_url, api_key=self.api_key or "missing", timeout=timeout, max_retries=0)
        self._capability: EmbeddingCapability | None = None

    def configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "sk-replace-me"

    def discover(self, *, egress_approved: bool = True, force: bool = False) -> EmbeddingCapability:
        if self._capability is not None and not force:
            return self._capability
        if not egress_approved:
            self._capability = EmbeddingCapability(status="EGRESS_DENIED")
            return self._capability
        if not self.configured():
            self._capability = EmbeddingCapability(status="UNAVAILABLE", error="embedding credentials not configured")
            return self._capability
        if self.model:
            candidates = [self.model]
        else:
            try:
                model_ids = self._list_embedding_model_ids()
            except Exception as exc:
                self._capability = EmbeddingCapability(status="PROVIDER_ERROR", error=type(exc).__name__)
                return self._capability
            candidates = _embedding_candidates(model_ids)
        if not candidates:
            self._capability = EmbeddingCapability(status="UNAVAILABLE", error="no candidate model advertised")
            return self._capability

        found: list[EmbeddingModelInfo] = []
        failures: list[str] = []
        for model in candidates[:16]:
            try:
                vector = self._embed([PROBE_TEXT], model=model)[0]
                if not vector or not all(isinstance(value, (int, float)) and value == value for value in vector):
                    raise ValueError("embedding response is empty or non-finite")
                found.append(EmbeddingModelInfo(model=model, dimensions=len(vector)))
            except Exception as exc:
                failures.append(f"{model}:{type(exc).__name__}")

        if self.model and not found:
            self._capability = EmbeddingCapability(status="PROVIDER_ERROR", error=";".join(failures))
        elif len(found) == 1:
            selected = found[0]
            self._capability = EmbeddingCapability(
                status="READY",
                models=found,
                selected_model=selected.model,
                dimensions=selected.dimensions,
            )
        elif len(found) > 1:
            self._capability = EmbeddingCapability(
                status="CONFIG_REQUIRED",
                models=found,
                error="multiple embedding models succeeded; set AI2_EMBEDDING_MODEL",
            )
        else:
            self._capability = EmbeddingCapability(status="UNAVAILABLE", error="no model accepted /embeddings")
        return self._capability

    def _list_embedding_model_ids(self) -> list[str]:
        """Read NineRouter's embedding catalog before generic `/models`.

        NineRouter exposes `/v1/models/embedding` separately from the chat
        model catalog. Generic OpenAI-compatible servers may not have that
        route, so the injected/test client falls back to `/models`.
        """
        if not self._client_injected:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            response = httpx.get(
                self.base_url.rstrip("/") + "/models/embedding",
                headers=headers,
                timeout=10.0,
            )
            if response.is_success:
                model_ids = sorted({_model_id(item) for item in _response_data(response.json()) if _model_id(item)})
                if model_ids:
                    return model_ids
        response = self.client.models.list()
        return sorted({_model_id(item) for item in _response_data(response) if _model_id(item)})

    def embed(self, texts: list[str], *, model: str | None = None, egress_approved: bool = True) -> list[list[float]]:
        if not egress_approved:
            raise PermissionError("embedding egress is not approved")
        if not texts or any(not str(text).strip() for text in texts):
            raise ValueError("embedding input must contain non-empty text")
        selected = model or self.model or (self._capability.selected_model if self._capability else None)
        if not selected:
            capability = self.discover(egress_approved=egress_approved)
            selected = capability.selected_model
        if not selected:
            raise RuntimeError("no embedding model selected")
        return self._embed(texts, model=selected)

    def _embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        kwargs: dict[str, Any] = {"model": model, "input": texts}
        if self.dimensions:
            kwargs["dimensions"] = self.dimensions
        response = self.client.embeddings.create(**kwargs)
        data = sorted(_response_data(response), key=lambda item: int(_item_value(item, "index", 0)))
        vectors = [list(_item_value(item, "embedding", [])) for item in data]
        if len(vectors) != len(texts):
            raise ValueError("embedding response count does not match input count")
        if self.dimensions and any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("embedding dimension mismatch")
        return vectors


def _embedding_candidates(model_ids: list[str]) -> list[str]:
    hints = ("embedding", "bge", "e5", "gte", "nomic")
    hinted = [model for model in model_ids if any(hint in model.casefold() for hint in hints)]
    # Never probe arbitrary chat/completion models: that adds cost and can
    # produce misleading provider errors. A generic provider can still be
    # selected explicitly through AI2_EMBEDDING_MODEL.
    return hinted


def _model_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or "")
    return str(getattr(item, "id", "") or "")


def _response_data(response: Any) -> list[Any]:
    if isinstance(response, dict):
        value = response.get("data", [])
    else:
        value = getattr(response, "data", [])
    return list(value or [])


def _item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
