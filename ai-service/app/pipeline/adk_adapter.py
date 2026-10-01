"""Dependency-free optional ADK adapter contract.

This module intentionally does not import ``google.adk``. A future pinned
integration can implement ``ADKRuntime`` and pass it to the mapper without
making ADK part of the AI1 -> AI2 dependency or transport path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.pipeline.execution import (
    ExecutionArtifact,
    ExecutionContext,
    ExecutionError,
    ExecutionRequest,
    ExecutionResponse,
    validate_tool_result,
)


ADKToolResult = ExecutionArtifact


@dataclass(frozen=True, slots=True)
class ADKExecutionRequest:
    context: ExecutionContext
    snapshot: object


@dataclass(frozen=True, slots=True)
class ADKExecutionResponse:
    status: Literal["SUCCEEDED", "FAILED"]
    artifact: ADKToolResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class ADKRuntime(Protocol):
    api_version: str

    def execute(self, request: ADKExecutionRequest) -> ADKExecutionResponse:
        """Run a bounded ADK operation; canonical state stays outside ADK."""


class ADKExecutionAdapter:
    """Optional mapper for a version-pinned, externally supplied ADK runtime."""

    adapter_name = "adk"
    adapter_version = "contract.v1"

    def __init__(self, runtime: ADKRuntime, *, expected_version: str) -> None:
        self._runtime = runtime
        self._expected_version = expected_version

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        if self._runtime.api_version != self._expected_version:
            return ExecutionResponse(
                error=ExecutionError(
                    "ADK_VERSION_MISMATCH",
                    f"expected {self._expected_version}, got {self._runtime.api_version}",
                ),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        if request.context.cancel_requested:
            return ExecutionResponse(
                error=ExecutionError("RUN_CANCELLED", "run was cancelled before ADK execution"),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        response = self._runtime.execute(ADKExecutionRequest(request.context, request.record))
        if response.status != "SUCCEEDED":
            return ExecutionResponse(
                error=ExecutionError(
                    response.error_code or "ADK_EXECUTION_FAILED",
                    response.error_message or "ADK runtime failed",
                    retryable=response.error_code in {"TIMEOUT", "UNAVAILABLE"},
                ),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        if response.artifact is None:
            return ExecutionResponse(
                error=ExecutionError("ADK_ARTIFACT_MISSING", "ADK runtime returned no artifact"),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        artifact_error = validate_tool_result(response.artifact)
        if artifact_error is not None:
            return ExecutionResponse(
                error=artifact_error,
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        return ExecutionResponse(
            artifacts=(response.artifact,),
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
        )


__all__ = [
    "ADKExecutionAdapter",
    "ADKExecutionRequest",
    "ADKExecutionResponse",
    "ADKRuntime",
    "ADKToolResult",
]
