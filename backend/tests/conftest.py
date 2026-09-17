import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import api
from app.config import Settings
from app.db import Base, make_engine


@pytest.fixture
def system(tmp_path, monkeypatch):
    config = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        artifact_root=tmp_path / "artifacts",
        _env_file=None,
        accounts={
            "admin-token": {"id": "alice", "role": "admin"},
            "reader-token": {"id": "mentor", "role": "mentor-readonly"},
        },
        max_attempts=1,
    )
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api, "Session", factory)
    monkeypatch.setattr(api, "settings", config)
    import app.policy

    monkeypatch.setattr(app.policy, "settings", config)
    with TestClient(api.app) as client:
        client.headers["Authorization"] = "Bearer admin-token"
        yield client, factory, config
    engine.dispose()


def pdf_bytes(
    text="Article 1. Payment\nParty A: Synthetic Company\n100.000.000 VND\nwithin 30 days", pages=1
):
    with pymupdf.open() as pdf:
        for _ in range(pages):
            page = pdf.new_page()
            page.insert_text((60, 80), text)
        return pdf.tobytes()


def create_job(client, pages=1, annex=False):
    dossier = client.post(
        "/api/v1/dossiers", json={"title": "Synthetic only"}, headers={"Idempotency-Key": "create"}
    ).json()["id"]
    response = client.post(
        f"/api/v1/dossiers/{dossier}/documents",
        files={"file": ("synthetic.pdf", pdf_bytes(pages=pages), "application/pdf")},
        data={"role": "contract"},
        headers={"Idempotency-Key": "upload"},
    )
    assert response.status_code == 201, response.text
    if annex:
        response = client.post(
            f"/api/v1/dossiers/{dossier}/documents",
            files={"file": ("annex.pdf", pdf_bytes("120.000.000 VND"), "application/pdf")},
            data={"role": "appendix"},
            headers={"Idempotency-Key": "annex"},
        )
        assert response.status_code == 201
    response = client.post(f"/api/v1/dossiers/{dossier}/jobs", headers={"Idempotency-Key": "start"})
    assert response.status_code == 202, response.text
    return dossier, response.json()["id"]
