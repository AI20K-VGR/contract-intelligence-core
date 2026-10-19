"""E2E: upload -> Kafka -> AI1 OCR -> AI2 IDP -> PENDING_REVIEW -> read back.

Opt-in (QA_RUN_PIPELINE=1): a valid upload starts real OCR and AI2 work. Run
the stack in free mode first (AI1_OCR_ENGINE=pymupdf, AI2 egress off; see
qa/README.md) so no paid OCR/LLM call is made.

The test drives the same HTTP calls the frontend makes, records how long each
stage takes, checks what lands in the read model, and deletes the dossier at
the end (QA_KEEP_DOSSIER=1 keeps it for manual inspection).
"""

from __future__ import annotations

import json
import os
import time

import pytest

from lib.config import REPORTS_DIR
from lib.pdf import sample_annex_pdf, sample_contract_pdf

pytestmark = pytest.mark.e2e

TERMINAL_OK = {"pending_review", "approved", "completed"}
TERMINAL_BAD = {"failed", "cancelled", "error"}


@pytest.fixture(scope="module")
def pipeline_enabled(cfg):
    if not cfg.run_pipeline:
        pytest.skip("set QA_RUN_PIPELINE=1 (and run the stack in free mode) to run the full pipeline")


@pytest.fixture(scope="module")
def uploaded(pipeline_enabled, api, operator, admin, cfg):
    started = time.perf_counter()
    metadata = {"name": f"QA E2E {time.strftime('%Y-%m-%d %H:%M:%S')}", "tags": ["qa-e2e"]}
    r = api.post(
        "/api/v1/dossiers",
        headers=operator.headers,
        files=[
            ("contract", ("qa_contract.pdf", sample_contract_pdf(), "application/pdf")),
            ("annexes", ("qa_phu_luc_01.pdf", sample_annex_pdf(), "application/pdf")),
            ("metadata", (None, json.dumps(metadata))),
        ],
    )
    upload_ms = (time.perf_counter() - started) * 1000
    assert r.status_code == 202, r.text[:300]
    data = r.json()["data"]
    dossier_id = data["dossier_id"]

    timeline: list[tuple[float, str]] = []
    deadline = time.monotonic() + cfg.pipeline_timeout_s
    status = None
    while time.monotonic() < deadline:
        detail = api.get(f"/api/v1/dossiers/{dossier_id}", headers=operator.headers).json()["data"]
        current = (detail.get("latest_job_status") or "").lower()
        if current != status:
            status = current
            timeline.append((round(time.perf_counter() - started, 2), status))
        if status in TERMINAL_OK | TERMINAL_BAD:
            break
        time.sleep(2)

    result = {
        "dossier_id": dossier_id,
        "job_id": data.get("job_id"),
        "upload_ms": round(upload_ms, 1),
        "timeline": timeline,
        "final_status": status,
        "error_code": detail.get("latest_job_error_code"),
        "total_s": round(time.perf_counter() - started, 2),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "e2e.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    yield result

    if not os.getenv("QA_KEEP_DOSSIER"):
        api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)


def test_upload_accepted_quickly(uploaded):
    """POST /dossiers answers 202 within 5 s (files validated + stored, OCR runs async)."""
    assert uploaded["upload_ms"] < 5000


def test_pipeline_reaches_pending_review(uploaded, cfg):
    """The job reaches PENDING_REVIEW within QA_PIPELINE_TIMEOUT_S, without an error code."""
    assert uploaded["final_status"] in TERMINAL_OK, (
        f"stuck/failed at {uploaded['final_status']} (error={uploaded['error_code']}) "
        f"timeline={uploaded['timeline']}"
    )
    assert uploaded["error_code"] in (None, "")


def test_documents_registered_with_roles(uploaded, api, operator):
    """Both PDFs are stored: one CONTRACT and one ANNEX, each with 1 page and a sha256."""
    docs = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/documents", headers=operator.headers).json()["data"]
    roles = sorted(d["role"].upper() for d in docs)
    assert roles == ["ANNEX", "CONTRACT"]
    for d in docs:
        assert d["page_count"] == 1
        assert len(d["sha256"]) == 64


def test_ocr_text_readable(uploaded, api, operator):
    """OCR lines of the contract contain the text that was uploaded."""
    docs = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/documents", headers=operator.headers).json()["data"]
    contract = next(d for d in docs if d["role"].upper() == "CONTRACT")
    pages = api.get(f"/api/v1/documents/{contract['id']}/lines", headers=operator.headers)
    assert pages.status_code == 200
    text = " ".join(line["text"] for page in pages.json()["data"] for line in page.get("ocr_lines", []))
    assert "HOP DONG MUA BAN" in text.upper()
    assert "1.500.000.000" in text


def test_structure_extracted(uploaded, api, operator):
    """Clause structure was rebuilt for the contract (at least one clause node)."""
    docs = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/documents", headers=operator.headers).json()["data"]
    contract = next(d for d in docs if d["role"].upper() == "CONTRACT")
    clauses = api.get(f"/api/v1/documents/{contract['id']}/clauses", headers=operator.headers)
    assert clauses.status_code == 200
    assert len(clauses.json()["data"]) >= 1


def _items(response) -> list:
    data = response.json()["data"]
    return data if isinstance(data, list) else data.get("items", [])


def test_owner_reads_analysis(uploaded, api, operator):
    """The uploading OPERATOR (owner) reads findings, conflicts and facts of the new dossier."""
    for part in ("findings", "conflicts", "facts"):
        r = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/{part}", headers=operator.headers)
        assert r.status_code == 200, f"{part}: {r.status_code}"


def test_ai2_flags_contract_annex_differences(uploaded, api, operator):
    """AI2 raises at least one finding: the annex changes payment (30%/7d -> 50%/10d) and delivery (15d -> 20d)."""
    r = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/findings", headers=operator.headers)
    assert len(_items(r)) >= 1


def test_operator_cannot_open_review_queue(uploaded, api, operator):
    """Review items are REVIEWER/ADMINISTRATOR only: the uploading OPERATOR gets 403."""
    r = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/review-items", headers=operator.headers)
    assert r.status_code == 403


def test_admin_cannot_read_unshared_dossier(uploaded, api, admin):
    """Privacy by design (CONTEXT.md §4.4): an ADMINISTRATOR without a share grant cannot read findings."""
    r = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/findings", headers=admin.headers)
    assert r.status_code == 403


def test_reviewer_without_grant_is_denied(uploaded, api, reviewer):
    """A REVIEWER in the same tenant cannot open the review queue before the dossier is shared."""
    r = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/review-items", headers=reviewer.headers)
    assert r.status_code == 403


def test_share_with_reviewer_opens_review_queue(uploaded, api, operator, reviewer, cfg):
    """OPERATOR shares the dossier with the REVIEWER, who then sees the AI2 review items (HITL hand-off)."""
    if cfg.is_prod:
        pytest.skip("prod validates share recipients by email and would send a real invite; local only")
    me = api.get("/api/v1/auth/me", headers=reviewer.headers).json()["data"]
    # Grants match on id. No email: a new grant with an email makes the backend
    # send a real invitation through the configured SMTP server.
    grant = {"id": me["id"], "permission": "edit", "status": "active"}
    r = api.put(
        f"/api/v1/dossiers/{uploaded['dossier_id']}/access",
        headers=operator.headers,
        json={"scope": "shared_out", "shared_with": [grant]},
    )
    assert r.status_code in (200, 204), r.text[:300]
    queue = api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}/review-items", headers=reviewer.headers)
    assert queue.status_code == 200, queue.text[:300]
    assert len(_items(queue)) >= 1


def test_pipeline_run_recorded(uploaded, api, operator):
    """A pipeline run is recorded for the dossier and finished."""
    runs = api.get("/api/v1/runs", headers=operator.headers, params={"dossier_id": uploaded["dossier_id"]})
    assert runs.status_code == 200
    data = runs.json()["data"]
    assert data, "no pipeline run recorded"
    assert data[0]["status"] in ("completed", "succeeded")


def test_other_tenant_header_cannot_read_new_dossier(uploaded, api, operator):
    """The new dossier is not readable with another tenant in X-Tenant-Id."""
    headers = dict(operator.headers, **{"X-Tenant-Id": "tenant_other"})
    assert api.get(f"/api/v1/dossiers/{uploaded['dossier_id']}", headers=headers).status_code == 403
