"""AI2 package API version 1.

This is the stable entry point for the current AI1 OCR-lab snapshot profile.
The implementation remains behind ``app.pipeline`` so the package boundary is
small and can be versioned independently from internal modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.pipeline.ai1_snapshot_adapter import SnapshotAdapterResult, adapt_ai1_input
from app.pipeline.ai2_batch import Ai2BatchResult, run_ai2_from_ai1_files, run_ai2_from_ai1_payloads


API_VERSION = "ai2.package.v1"
INPUT_PROFILE = "ai1.snapshot.v1/ocr-lab"


def process_files(
    paths: Sequence[str | Path],
    *,
    use_llm: bool = False,
    relation_policy: str = "INDEPENDENT",
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
) -> Ai2BatchResult:
    """Process AI1 snapshot files through the versioned AI2 API."""

    return run_ai2_from_ai1_files(
        paths,
        relation_policy=relation_policy,
        use_llm=use_llm,
        tenant_id=tenant_id,
        actor_id=actor_id,
    )


def process_payloads(
    payloads: Sequence[Mapping[str, Any]],
    *,
    use_llm: bool = False,
    relation_policy: str = "INDEPENDENT",
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
) -> list[SnapshotAdapterResult]:
    """Validate/adapt in-memory AI1 snapshots without writing source files."""

    if relation_policy != "INDEPENDENT":
        raise ValueError("only relation_policy=INDEPENDENT is enabled for package v1")
    # Payload processing is intentionally exposed as an adapter-level API. The
    # file API is the full batch runner; callers that need execution can write
    # an immutable input artifact and call process_files so the same lineage
    # and reporting path is used.
    results: list[SnapshotAdapterResult] = []
    for payload in payloads:
        document_id = str(payload.get("document_id"))
        dossier_id = str(payload.get("dossier_id"))
        results.append(
            adapt_ai1_input(
                payload,
                tenant_id=tenant_id,
                actor_id=actor_id,
                scope_id=f"{dossier_id}:{document_id}",
            )
        )
    return results


def process_payloads_full(
    payloads: Sequence[Mapping[str, Any]],
    *,
    use_llm: bool = False,
    relation_policy: str = "INDEPENDENT",
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
) -> Ai2BatchResult:
    """Run full AI2 on in-memory AI1 payloads and return batch results."""

    return run_ai2_from_ai1_payloads(
        list(payloads),
        relation_policy=relation_policy,
        use_llm=use_llm,
        tenant_id=tenant_id,
        actor_id=actor_id,
    )


__all__ = [
    "API_VERSION",
    "INPUT_PROFILE",
    "Ai2BatchResult",
    "SnapshotAdapterResult",
    "process_files",
    "process_payloads",
    "process_payloads_full",
]
