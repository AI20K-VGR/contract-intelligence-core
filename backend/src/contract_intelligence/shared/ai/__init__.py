"""Cross-cutting AI service module.

Public API cho backend dùng AI service:
    - AiServiceClient  : abstract interface (HTTP | Stub)
    - BackgroundDispatcher : chạy polling loop in-process
    - PipelineOrchestrator : drive OCR → Extract → Compare chain
    - persistence      : ghi canonical payload xuống DB (Semantic Gate)
    - schemas          : DOC-05c Pydantic models (canonical handoffs)

Khi AI service team ready, đổi ``settings.ai_service_mode`` từ "stub" → "http"
để switch sang HttpAiServiceClient. Application layer KHÔNG đổi.
"""

from contract_intelligence.shared.ai.client import (
    AiServiceClient,
    HttpAiServiceClient,
    StubAiServiceClient,
    get_ai_service_client,
    reset_ai_service_client,
)
from contract_intelligence.shared.ai.dispatcher import (
    BackgroundDispatcher,
    get_background_dispatcher,
    reset_background_dispatcher,
)
from contract_intelligence.shared.ai.persistence import (
    persist_ai1_snapshot,
    persist_ai2_comparison,
    persist_ai2_extraction,
    persist_usage_ledger,
    update_pipeline_run_status,
    update_pipeline_step,
)
from contract_intelligence.shared.ai.pipeline_orchestrator import (
    DocumentJob,
    PipelineContext,
    PipelineOrchestrator,
    get_pipeline_orchestrator,
    reset_pipeline_orchestrator,
)
from contract_intelligence.shared.ai.schemas import (
    Ai1SnapshotPayload,
    Ai2ComparisonPayload,
    Ai2ExtractionPayload,
    BBox,
    CompareJobRequest,
    ExtractJobRequest,
    JobStatus,
    JobStatusReport,
    JobSubmission,
    OcrJobRequest,
    ReOcrJobRequest,
    UsageLedgerReport,
)

__all__ = [
    # Client
    "AiServiceClient",
    "HttpAiServiceClient",
    "StubAiServiceClient",
    "get_ai_service_client",
    "reset_ai_service_client",
    # Dispatcher
    "BackgroundDispatcher",
    "get_background_dispatcher",
    "reset_background_dispatcher",
    # Pipeline orchestrator
    "DocumentJob",
    "PipelineContext",
    "PipelineOrchestrator",
    "get_pipeline_orchestrator",
    "reset_pipeline_orchestrator",
    # Persistence
    "persist_ai1_snapshot",
    "persist_ai2_comparison",
    "persist_ai2_extraction",
    "persist_usage_ledger",
    "update_pipeline_run_status",
    "update_pipeline_step",
    # Schemas (re-export)
    "Ai1SnapshotPayload",
    "Ai2ComparisonPayload",
    "Ai2ExtractionPayload",
    "BBox",
    "CompareJobRequest",
    "ExtractJobRequest",
    "JobStatus",
    "JobStatusReport",
    "JobSubmission",
    "OcrJobRequest",
    "ReOcrJobRequest",
    "UsageLedgerReport",
]
