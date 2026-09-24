#!/usr/bin/env python3
"""End-to-end Sprint 2 pipeline smoke test (FE/AI → Backend control plane).

Runs sequentially against a live backend:

    1. Upload dossier (multipart PDF)
    2. AI1 OCR snapshot webhook
    3. AI2 findings webhook
    4. HITL review action (CONFIRM)
    5. Dossier approve

Prerequisites:
    - Backend listening on http://localhost:8000
    - Valid Keycloak JWT for OPERATOR/ADMINISTRATOR in env ``CI_E2E_BEARER_TOKEN``
      (upload + approve require auth; webhooks/review-actions do not)

Usage::

    export CI_E2E_BEARER_TOKEN="<access_token>"
    uv run python scripts/test_e2e_pipeline.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import uuid4

import httpx

BASE_URL = os.getenv("CI_E2E_BASE_URL", "http://localhost:8000/api/v1")
TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Minimal syntactically-valid PDF bytes for multipart upload.
DUMMY_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF\n"
)


class E2EFailure(RuntimeError):
    """Raised when a pipeline step does not meet its success criteria."""


def _auth_headers() -> dict[str, str]:
    token = os.getenv("CI_E2E_BEARER_TOKEN") or os.getenv("BEARER_TOKEN")
    if not token:
        msg = (
            "Missing CI_E2E_BEARER_TOKEN (or BEARER_TOKEN). "
            "Export a Keycloak access token with OPERATOR or ADMINISTRATOR role."
        )
        raise E2EFailure(msg)
    headers = {
        "Authorization": f"Bearer {token}",
    }
    tenant = os.getenv("CI_E2E_TENANT_ID")
    if tenant:
        headers["X-Tenant-Id"] = tenant
    return headers


def _assert_status(response: httpx.Response, expected: int, step: str) -> None:
    if response.status_code != expected:
        raise E2EFailure(
            f"{step} expected HTTP {expected}, got {response.status_code}: {response.text[:800]}"
        )


async def step_upload(client: httpx.AsyncClient) -> tuple[str, str]:
    """Step 1 — FE → BE dossier upload."""
    print("[Step 1] Uploading dummy PDF dossier …")
    metadata = json.dumps({"name": f"E2E Pipeline Demo {uuid4().hex[:8]}"})
    files = {
        "contract": ("e2e-contract.pdf", DUMMY_PDF, "application/pdf"),
        "metadata": (None, metadata),
    }
    response = await client.post(
        f"{BASE_URL}/dossiers",
        files=files,
        headers=_auth_headers(),
    )
    _assert_status(response, 202, "[Step 1] Upload")
    payload = response.json()
    data = payload.get("data") or payload
    dossier_id = data.get("dossier_id")
    job_id = data.get("job_id")
    if not dossier_id or not job_id:
        raise E2EFailure(f"[Step 1] Upload response missing ids: {payload}")
    print(f"[Step 1] Upload Success — Dossier ID: {dossier_id} | Job ID: {job_id}")
    return str(dossier_id), str(job_id)


async def step_ai1_webhook(
    client: httpx.AsyncClient,
    *,
    dossier_id: str,
    job_id: str,
    run_id: str,
) -> None:
    """Step 2 — AI1 → BE OCR snapshot callback."""
    print("[Step 2] Posting AI1 OCR snapshot webhook …")
    body: dict[str, Any] = {
        "snapshot_id": f"snap_{uuid4().hex[:12]}",
        "version": "1",
        "digest": f"sha256:{uuid4().hex}",
        "quality_state": {"score": 0.95, "engine": "e2e-stub"},
        "pages": [{"page": 1, "width": 612, "height": 792}],
        "nodes": [],
        "tables": [],
        "source_files": [{"dossier_id": dossier_id, "job_id": job_id}],
        "provenance": {
            "dossier_id": dossier_id,
            "job_id": job_id,
            "run_id": run_id,
        },
    }
    response = await client.post(f"{BASE_URL}/webhooks/ai1/snapshot", json=body)
    _assert_status(response, 200, "[Step 2] AI1 webhook")
    print(f"[Step 2] AI1 Webhook Success — snapshot accepted for dossier {dossier_id}")


async def step_ai2_webhook(client: httpx.AsyncClient, *, run_id: str) -> None:
    """Step 3 — AI2 → BE findings callback."""
    print("[Step 3] Posting AI2 findings webhook …")
    body: dict[str, Any] = {
        "run_id": run_id,
        "facts": [{"fact_id": "fct_e2e_1", "label": "contract_value", "value": "1000"}],
        "findings": [
            {
                "finding_id": "fnd_e2e_1",
                "severity": "MEDIUM",
                "summary": "E2E dummy finding",
            }
        ],
        "index_contribution": {"vectors": 0, "tokens": 12},
    }
    response = await client.post(f"{BASE_URL}/webhooks/ai2/findings", json=body)
    _assert_status(response, 200, "[Step 3] AI2 webhook")
    print(f"[Step 3] AI2 Webhook Success — findings applied for run {run_id}")


async def step_hitl_review(client: httpx.AsyncClient) -> None:
    """Step 4 — FE → BE HITL review action."""
    print("[Step 4] Submitting HITL CONFIRM action …")
    body = {"action": "CONFIRM", "base_version": 1}
    response = await client.post(
        f"{BASE_URL}/review-items/dummy-item-123/actions",
        json=body,
    )
    _assert_status(response, 200, "[Step 4] HITL review")
    print("[Step 4] HITL Review Success — CONFIRM applied to dummy-item-123")


async def step_approve(client: httpx.AsyncClient, *, dossier_id: str) -> None:
    """Step 5 — FE → BE dossier approval."""
    print(f"[Step 5] Approving dossier {dossier_id} …")
    response = await client.post(
        f"{BASE_URL}/dossiers/{dossier_id}/approve",
        headers=_auth_headers(),
    )
    _assert_status(response, 200, "[Step 5] Approve")
    print(f"[Step 5] Approve Success — Dossier {dossier_id} marked APPROVED")


async def run_pipeline() -> None:
    print("=" * 60)
    print("E2E Pipeline Test — Sprint 2 Control Plane")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Liveness probe
        health_url = BASE_URL.replace("/api/v1", "/health")
        try:
            health = await client.get(health_url)
        except httpx.HTTPError as exc:
            raise E2EFailure(
                f"Cannot reach backend at {health_url}: {exc}. Is the API running?"
            ) from exc
        if health.status_code != 200:
            raise E2EFailure(f"Backend /health returned {health.status_code}")

        dossier_id, job_id = await step_upload(client)
        run_id = f"run_e2e_{uuid4().hex[:10]}"

        await step_ai1_webhook(
            client,
            dossier_id=dossier_id,
            job_id=job_id,
            run_id=run_id,
        )
        await step_ai2_webhook(client, run_id=run_id)
        await step_hitl_review(client)
        await step_approve(client, dossier_id=dossier_id)

    print("=" * 60)
    print("E2E Pipeline Test — ALL STEPS PASSED")
    print("=" * 60)


def main() -> None:
    try:
        asyncio.run(run_pipeline())
    except E2EFailure as exc:
        print(f"\nE2E FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError as exc:
        print(f"\nE2E FAILED (HTTP transport): {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
