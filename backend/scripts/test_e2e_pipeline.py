#!/usr/bin/env python3
"""End-to-end Sprint 2 pipeline smoke test (FE → Backend → Kafka → AI1/AI2).

Runs sequentially against a live stack:

    1. Upload dossier (multipart PDF)
    2. Wait for the Kafka worker to drive the job to ``pending_review``
       (AI1 OCR via ``ci.ai1.ocr.*`` then AI2 processing)
    3. HITL review action (confirm) on the first open review item
    4. Dossier approve

Prerequisites:
    - Backend API on http://localhost:8000, ``contract_intelligence.worker``, AI1, AI2, Kafka
    - Keycloak JWT with ADMINISTRATOR role in env ``CI_E2E_BEARER_TOKEN``
      (upload, review and approve all require auth)
    - ``CI_E2E_TENANT_ID`` matching the token's tenant claim

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
PIPELINE_TIMEOUT_SECONDS = float(os.getenv("CI_E2E_PIPELINE_TIMEOUT", "600"))

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


async def step_wait_for_review(client: httpx.AsyncClient, *, dossier_id: str) -> None:
    """Step 2 — Kafka worker: AI1 OCR → AI2 → pending_review."""
    print("[Step 2] Waiting for Kafka pipeline to reach pending_review …")
    deadline = asyncio.get_running_loop().time() + PIPELINE_TIMEOUT_SECONDS
    status = None
    while asyncio.get_running_loop().time() < deadline:
        response = await client.get(f"{BASE_URL}/dossiers/{dossier_id}", headers=_auth_headers())
        _assert_status(response, 200, "[Step 2] Dossier detail")
        data = response.json().get("data") or {}
        status = data.get("latest_job_status") or data.get("status")
        if status == "pending_review":
            print(f"[Step 2] Pipeline Success — dossier {dossier_id} is pending_review")
            return
        if status == "failed":
            raise E2EFailure(f"[Step 2] Pipeline failed for dossier {dossier_id}: {data}")
        await asyncio.sleep(3)
    raise E2EFailure(f"[Step 2] Timed out waiting for pending_review (last status: {status})")


async def step_hitl_review(client: httpx.AsyncClient, *, dossier_id: str) -> None:
    """Step 3 — FE → BE HITL review action on a real review item."""
    print("[Step 3] Submitting HITL confirm action …")
    response = await client.get(
        f"{BASE_URL}/dossiers/{dossier_id}/review-items",
        params={"status": "open", "limit": 1},
        headers=_auth_headers(),
    )
    _assert_status(response, 200, "[Step 3] Review queue")
    items: list[dict[str, Any]] = response.json().get("data") or []
    if not items:
        print("[Step 3] No open review item — skipping review action")
        return
    item = items[0]
    response = await client.post(
        f"{BASE_URL}/review-items/{item['id']}/actions",
        json={"action": "confirm", "base_version": item["version"]},
        headers={**_auth_headers(), "Idempotency-Key": str(uuid4())},
    )
    _assert_status(response, 200, "[Step 3] HITL review")
    print(f"[Step 3] HITL Review Success — confirm applied to {item['id']}")


async def step_approve(client: httpx.AsyncClient, *, dossier_id: str) -> None:
    """Step 4 — FE → BE dossier approval."""
    print(f"[Step 4] Approving dossier {dossier_id} …")
    response = await client.post(
        f"{BASE_URL}/dossiers/{dossier_id}/approve",
        headers=_auth_headers(),
    )
    _assert_status(response, 200, "[Step 4] Approve")
    print(f"[Step 4] Approve Success — Dossier {dossier_id} marked APPROVED")


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

        dossier_id, _job_id = await step_upload(client)
        await step_wait_for_review(client, dossier_id=dossier_id)
        await step_hitl_review(client, dossier_id=dossier_id)
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
