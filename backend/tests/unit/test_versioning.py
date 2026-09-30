"""Backend version: one source, bumped by the SemVer rule (Gate 1 review, item 6)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import contract_intelligence
from contract_intelligence.main import create_app
from contract_intelligence.shared import versioning

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Endpoints removed by PR#28. Removing an endpoint is a MAJOR change.
REMOVED_IN_2_0_0 = {
    ("POST", "/api/v1/dossiers/upload"),
}


def test_every_version_constant_agrees() -> None:
    pyproject = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == versioning.__version__
    assert contract_intelligence.__version__ == versioning.__version__


def test_current_version_has_a_changelog_entry() -> None:
    assert f"v{versioning.__version__} —" in (versioning.__doc__ or "")


def test_major_is_bumped_past_the_removed_endpoints() -> None:
    major = int(versioning.__version__.split(".")[0])
    assert major >= 2

    routes = {
        (method, route.path)
        for route in create_app().routes
        for method in getattr(route, "methods", None) or ()
    }
    assert not REMOVED_IN_2_0_0 & routes
    assert not {path for _, path in routes if path.startswith("/api/v1/reviews")}


def test_full_version_carries_the_semver() -> None:
    assert versioning.full_version().startswith(f"{versioning.__version__}+")


def test_contract_header_follows_the_doc_05b_version() -> None:
    from fastapi.testclient import TestClient

    response = TestClient(create_app()).get("/health")

    assert response.headers["X-API-Contract"] == versioning.__api_contract__ == "v1.2.0"
