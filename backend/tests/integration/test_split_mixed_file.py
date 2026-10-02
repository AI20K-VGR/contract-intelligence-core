# The client/db fixtures are imported from test_ai_pipeline; pytest injects them by
# parameter name, which ruff reads as a redefinition.
# ruff: noqa: F811
"""Split a mixed upload into documents (Sprint 3 task 5).

A file holding a contract and its annexes is uploaded with
``metadata.split_pending``: nothing goes to OCR. The user confirms the page
ranges and roles; each part becomes its own document (cut PDF, own sha256),
the mixed file is dropped, roles are confirmed and OCR starts per document.
"""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from pypdf import PdfReader
from tests.integration.test_ai_pipeline import (  # noqa: F401 — fixtures
    _auth_headers,
    _override_settings,
    client,
    db_engine,
)
from tests.pdf_bytes import make_pdf

from contract_intelligence.infrastructure import messaging

pytestmark = pytest.mark.integration


def _uploaded_events() -> list[dict[str, Any]]:
    publish = messaging.publish_event
    assert isinstance(publish, AsyncMock)
    return [
        call.args[1]
        for call in publish.await_args_list
        if call.args[0] == "dossier_events" and call.args[1].get("event") == "dossier.uploaded"
    ]


async def _upload_mixed(
    client: AsyncClient, headers: dict[str, str], *, pages: int = 10, split_pending: bool = True
) -> str:
    metadata: dict[str, Any] = {"name": "Hợp đồng kèm phụ lục"}
    if split_pending:
        metadata["split_pending"] = True
    response = await client.post(
        "/api/v1/dossiers",
        headers=headers,
        files=[
            ("contract", ("tron.pdf", io.BytesIO(make_pdf(pages, "mixed")), "application/pdf")),
            ("metadata", (None, json.dumps(metadata))),
        ],
    )
    assert response.status_code == 202, response.text
    return str(response.json()["data"]["dossier_id"])


async def _documents(client: AsyncClient, headers: dict[str, str], dossier_id: str) -> list[Any]:
    response = await client.get(f"/api/v1/dossiers/{dossier_id}/documents", headers=headers)
    assert response.status_code == 200, response.text
    return list(response.json()["data"])


def _parts(*ranges: tuple[int, int, str]) -> list[dict[str, Any]]:
    return [{"page_start": a, "page_end": b, "role": role} for a, b, role in ranges]


@pytest.mark.asyncio
async def test_mixed_file_waits_then_splits_into_documents(
    client: AsyncClient, make_keycloak_token: Any
) -> None:
    headers = _auth_headers(make_keycloak_token)
    dossier_id = await _upload_mixed(client, headers)
    # Nothing sent to OCR while the split is pending.
    assert all(e["dossier_id"] != dossier_id for e in _uploaded_events())
    (source,) = await _documents(client, headers, dossier_id)

    response = await client.post(
        f"/api/v1/dossiers/{dossier_id}/split",
        headers=headers,
        json={"document_id": source["id"], "parts": _parts((1, 6, "contract"), (7, 10, "annex"))},
    )
    assert response.status_code == 202, response.text
    created = response.json()["data"]["documents"]
    assert [(d["role"], d["page_count"]) for d in created] == [("contract", 6), ("annex", 4)]

    documents = await _documents(client, headers, dossier_id)
    assert source["id"] not in {d["id"] for d in documents}
    assert sorted((d["role"].lower(), d["page_count"]) for d in documents) == [
        ("annex", 4),
        ("contract", 6),
    ]
    assert len({d["sha256"] for d in documents}) == 2

    # Each part is a real PDF with exactly its pages.
    for document in documents:
        blob = await client.get(f"/api/v1/documents/{document['id']}/content", headers=headers)
        assert blob.status_code == 200
        assert len(PdfReader(io.BytesIO(blob.content)).pages) == document["page_count"]

    # Roles confirmed, OCR started once for the dossier (the worker sends one
    # command per document).
    manifest = await client.get(f"/api/v1/dossiers/{dossier_id}/manifest", headers=headers)
    assert manifest.json()["data"]["status"] == "confirmed"
    assert [e["dossier_id"] for e in _uploaded_events()].count(dossier_id) == 1

    # Once processing has started, splitting again would re-OCR: refused.
    again = await client.post(
        f"/api/v1/dossiers/{dossier_id}/split",
        headers=headers,
        json={"document_id": created[0]["id"], "parts": _parts((1, 6, "contract"))},
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_single_part_keeps_the_file_and_starts_processing(
    client: AsyncClient, make_keycloak_token: Any
) -> None:
    headers = _auth_headers(make_keycloak_token)
    dossier_id = await _upload_mixed(client, headers, pages=4)
    (source,) = await _documents(client, headers, dossier_id)

    response = await client.post(
        f"/api/v1/dossiers/{dossier_id}/split",
        headers=headers,
        json={"document_id": source["id"], "parts": _parts((1, 4, "contract"))},
    )
    assert response.status_code == 202, response.text
    assert [d["id"] for d in await _documents(client, headers, dossier_id)] == [source["id"]]
    assert [e["dossier_id"] for e in _uploaded_events()].count(dossier_id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("parts", "reason"),
    [
        (_parts((1, 5, "contract"), (7, 10, "annex")), "expected page 6"),
        (_parts((1, 6, "contract"), (6, 10, "annex")), "expected page 7"),
        (_parts((1, 6, "contract"), (7, 9, "annex")), "the file has 10"),
        (_parts((1, 6, "annex"), (7, 10, "annex")), "contract_required"),
        (_parts((1, 6, "contract"), (7, 10, "contract")), "contract_not_unique"),
        (
            _parts(
                *((n, n, "contract" if n == 1 else "annex") for n in range(1, 7)), (7, 10, "annex")
            ),
            "DOSSIER_TOO_MANY_DOCUMENTS",
        ),
        (_parts((3, 1, "contract")), "page_end"),
    ],
)
async def test_bad_parts_are_refused(
    client: AsyncClient, make_keycloak_token: Any, parts: list[dict[str, Any]], reason: str
) -> None:
    headers = _auth_headers(make_keycloak_token)
    dossier_id = await _upload_mixed(client, headers)
    (source,) = await _documents(client, headers, dossier_id)

    response = await client.post(
        f"/api/v1/dossiers/{dossier_id}/split",
        headers=headers,
        json={"document_id": source["id"], "parts": parts},
    )
    assert response.status_code == 422, response.text
    assert reason in response.text
    assert [d["id"] for d in await _documents(client, headers, dossier_id)] == [source["id"]]


@pytest.mark.asyncio
async def test_split_into_too_many_documents_names_documents_not_pages(
    client: AsyncClient, make_keycloak_token: Any
) -> None:
    """The limit counts documents, so the message must not read as a page limit."""
    headers = _auth_headers(make_keycloak_token)
    dossier_id = await _upload_mixed(client, headers)
    (source,) = await _documents(client, headers, dossier_id)
    parts = _parts(
        *((n, n, "contract" if n == 1 else "annex") for n in range(1, 7)), (7, 10, "annex")
    )

    response = await client.post(
        f"/api/v1/dossiers/{dossier_id}/split",
        headers=headers,
        json={"document_id": source["id"], "parts": parts},
    )

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["message"] == (
        "Sau khi tách, hồ sơ tối đa 6 tài liệu. Cách tách này làm hồ sơ có 7 tài liệu."
    )
    assert error["details"] == {"limit": 6, "count": 7}


@pytest.mark.asyncio
async def test_normal_upload_cannot_be_split(client: AsyncClient, make_keycloak_token: Any) -> None:
    headers = _auth_headers(make_keycloak_token)
    dossier_id = await _upload_mixed(client, headers, split_pending=False)
    (source,) = await _documents(client, headers, dossier_id)
    response = await client.post(
        f"/api/v1/dossiers/{dossier_id}/split",
        headers=headers,
        json={"document_id": source["id"], "parts": _parts((1, 6, "contract"), (7, 10, "annex"))},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_upload_of_more_than_six_files_is_refused(
    client: AsyncClient, make_keycloak_token: Any
) -> None:
    """DEC-BE-AI2-01 D5: AI2 takes at most 6 documents per dossier."""
    headers = _auth_headers(make_keycloak_token)
    before = len(_uploaded_events())
    response = await client.post(
        "/api/v1/dossiers",
        headers=headers,
        files=[
            ("contract", ("hd.pdf", io.BytesIO(make_pdf(1, "c")), "application/pdf")),
            *(
                ("annexes", (f"pl{n}.pdf", io.BytesIO(make_pdf(1, f"a{n}")), "application/pdf"))
                for n in range(1, 7)
            ),
            ("metadata", (None, json.dumps({"name": "Bảy tệp"}))),
        ],
    )

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "DOSSIER_TOO_MANY_DOCUMENTS"
    assert error["message"] == (
        "Hồ sơ tối đa 6 file PDF (1 hợp đồng và tối đa 5 phụ lục). Bạn đã chọn 7 file."
    )
    assert error["details"] == {"limit": 6, "count": 7}
    assert len(_uploaded_events()) == before
