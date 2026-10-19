"""BOLA / IDOR: one operator must not reach another operator's objects.

Two throwaway OPERATOR users are created in Keycloak (local only). Operator A
uploads a private dossier; Operator B — same tenant, no share grant — must be
refused on every id addressed inside that dossier: the dossier, its documents,
OCR lines, clauses, pages, findings, review items, facts, runs.

Local only: it provisions Keycloak users and uploads files. Skipped on prod.
"""

from __future__ import annotations

import json
import time

import pytest

from lib.auth import login
from lib.pdf import sample_contract_pdf

pytestmark = pytest.mark.security


@pytest.fixture(scope="module")
def two_operators(cfg, admin, api):
    if cfg.is_prod:
        pytest.skip("IDOR setup provisions Keycloak users; local only")
    from lib.kc_admin import KcAdmin, KcAdminError

    try:
        kc = KcAdmin(cfg)
    except KcAdminError as exc:
        pytest.skip(f"Keycloak master admin not available: {exc}")

    stamp = str(int(time.time()))
    try:
        ua = kc.create_user(f"qa-idor-a-{stamp}@ci.local", "Qa-Idor-A-2026", "tenant_vgr_01", "OPERATOR")
        ub = kc.create_user(f"qa-idor-b-{stamp}@ci.local", "Qa-Idor-B-2026", "tenant_vgr_01", "OPERATOR")
    except KcAdminError as exc:
        kc.cleanup()
        pytest.skip(f"could not provision test operators: {exc}")

    a = login(ua.username, ua.password, role="OPERATOR", cfg=cfg)
    b = login(ub.username, ub.password, role="OPERATOR", cfg=cfg)

    # Operator A uploads a private dossier (its own objects to probe).
    r = api.post(
        "/api/v1/dossiers",
        headers=a.headers,
        files=[
            ("contract", ("idor.pdf", sample_contract_pdf(), "application/pdf")),
            ("metadata", (None, json.dumps({"name": f"QA IDOR {stamp}"}))),
        ],
    )
    assert r.status_code == 202, r.text[:300]
    dossier_id = r.json()["data"]["dossier_id"]

    ids = {"dossier_id": dossier_id, "document_id": None, "run_id": None}
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        docs = api.get(f"/api/v1/dossiers/{dossier_id}/documents", headers=a.headers).json()["data"]
        if docs:
            ids["document_id"] = docs[0]["id"]
        runs = api.get("/api/v1/runs", headers=a.headers, params={"dossier_id": dossier_id}).json()["data"]
        if runs:
            ids["run_id"] = runs[0]["run_id"]
        status = api.get(f"/api/v1/dossiers/{dossier_id}", headers=a.headers).json()["data"]["latest_job_status"]
        if ids["document_id"] and status in ("pending_review", "extracted", "failed"):
            break
        time.sleep(2)

    yield {"a": a, "b": b, "ids": ids}

    api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)
    kc.cleanup()


def _denied(resp) -> bool:
    return resp.status_code in (403, 404)


def test_operator_b_cannot_read_a_dossier(two_operators, api):
    """Operator B cannot open Operator A's dossier."""
    ids = two_operators["ids"]
    r = api.get(f"/api/v1/dossiers/{ids['dossier_id']}", headers=two_operators["b"].headers)
    assert _denied(r), r.status_code


@pytest.mark.parametrize("part", ["documents", "findings", "review-items", "conflicts", "facts"])
def test_operator_b_cannot_read_a_dossier_subresources(two_operators, api, part):
    """Operator B cannot list A's documents/findings/review-items/conflicts/facts."""
    ids = two_operators["ids"]
    r = api.get(f"/api/v1/dossiers/{ids['dossier_id']}/{part}", headers=two_operators["b"].headers)
    assert _denied(r), f"{part}: {r.status_code}"


def test_operator_b_cannot_read_a_document_by_id(two_operators, api):
    """Operator B cannot read A's document, its OCR lines, clauses or pages by document id (IDOR)."""
    ids = two_operators["ids"]
    if not ids["document_id"]:
        pytest.skip("document id not available")
    for suffix in ("", "/lines", "/clauses", "/pages", "/content", "/tables", "/facts"):
        r = api.get(f"/api/v1/documents/{ids['document_id']}{suffix}", headers=two_operators["b"].headers)
        assert _denied(r), f"documents/{{id}}{suffix}: {r.status_code}"


def test_operator_b_cannot_read_a_run(two_operators, api):
    """Operator B cannot read A's pipeline run, its steps or events by run id."""
    ids = two_operators["ids"]
    if not ids["run_id"]:
        pytest.skip("run id not available")
    for suffix in ("", "/steps", "/events"):
        r = api.get(f"/api/v1/runs/{ids['run_id']}{suffix}", headers=two_operators["b"].headers)
        assert _denied(r), f"runs/{{id}}{suffix}: {r.status_code}"


def test_operator_a_can_read_own_dossier(two_operators, api):
    """Positive control: Operator A reads its own dossier."""
    ids = two_operators["ids"]
    r = api.get(f"/api/v1/dossiers/{ids['dossier_id']}", headers=two_operators["a"].headers)
    assert r.status_code == 200


def test_operator_b_cannot_delete_or_patch_a_dossier(two_operators, api):
    """Operator B cannot modify or delete A's dossier."""
    ids = two_operators["ids"]
    patch = api.patch(
        f"/api/v1/dossiers/{ids['dossier_id']}", headers=two_operators["b"].headers, json={"name": "hijacked"}
    )
    assert _denied(patch), f"patch: {patch.status_code}"
    delete = api.delete(f"/api/v1/dossiers/{ids['dossier_id']}", headers=two_operators["b"].headers)
    assert _denied(delete), f"delete: {delete.status_code}"
