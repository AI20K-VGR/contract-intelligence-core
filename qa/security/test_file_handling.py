"""Malicious file handling on upload.

Every upload runs through the backend's PDF validation before anything is stored
or sent to OCR, so these probes do not start a real pipeline. Local only (they
POST uploads); skipped on prod to avoid planting junk on a shared host.
"""

from __future__ import annotations

import zlib

import pytest

pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def _local_only(cfg):
    if cfg.is_prod:
        pytest.skip("upload probes are local only")


def _upload(api, operator, content: bytes, filename: str = "x.pdf", ctype: str = "application/pdf", meta: str | None = None):
    return api.post(
        "/api/v1/dossiers",
        headers=operator.headers,
        files={"contract": (filename, content, ctype), "metadata": (None, meta or '{"name":"qa-file"}')},
    )


def test_eicar_like_executable_disguised_as_pdf(api, operator):
    """A Windows PE (MZ...) renamed to .pdf is refused as not-a-PDF (422)."""
    r = _upload(api, operator, b"MZ\x90\x00\x03" + b"\x00" * 200)
    assert r.status_code == 422


def test_html_polyglot_refused(api, operator):
    """An HTML/script file renamed .pdf is refused (no polyglot smuggling)."""
    r = _upload(api, operator, b"<html><script>alert(1)</script></html>")
    assert r.status_code == 422


def test_pdf_decompression_bomb_handled(api, operator):
    """A PDF-looking file with a huge zlib bomb stream is rejected or capped, not a 500/hang."""
    bomb = zlib.compress(b"0" * (80 * 1024 * 1024))
    header = b"%PDF-1.4\n1 0 obj<</Length " + str(len(bomb)).encode() + b">>stream\n"
    content = header + bomb + b"\nendstream endobj\n%%EOF"
    r = _upload(api, operator, content, filename="bomb.pdf")
    assert r.status_code in (413, 422, 400), r.status_code


def test_pdf_with_javascript_action(api, operator):
    """A syntactically-valid PDF carrying an OpenAction /JS is accepted or rejected cleanly (never 500).

    AI1 rasterises/extracts text; it must not execute embedded JS. We assert no
    server error and, if accepted, clean up.
    """
    js_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R/OpenAction<</S/JavaScript/JS(app.alert('x'))>>>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF"
    )
    r = _upload(api, operator, js_pdf, filename="js.pdf")
    assert r.status_code != 500, r.text[:200]
    if r.status_code == 202:
        api.delete(f"/api/v1/dossiers/{r.json()['data']['dossier_id']}", headers=operator.headers)


def test_path_traversal_in_upload_filename(api, operator, admin):
    """A multipart filename of ../../etc/passateway must not escape storage; stored name stays safe."""
    from lib.pdf import sample_contract_pdf

    r = _upload(api, operator, sample_contract_pdf(), filename="../../../../etc/passwd.pdf", meta='{"name":"qa-traversal"}')
    assert r.status_code in (202, 422), r.text[:200]
    if r.status_code == 202:
        dossier_id = r.json()["data"]["dossier_id"]
        docs = api.get(f"/api/v1/dossiers/{dossier_id}/documents", headers=operator.headers).json()["data"]
        for d in docs:
            assert "/" not in d["filename"] and "\\" not in d["filename"], f"unsafe stored filename: {d['filename']!r}"
        api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)
