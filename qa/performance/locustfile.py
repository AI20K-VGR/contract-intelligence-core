"""Soak / load test with Locust (longer than the pytest budget checks).

    uv run --with locust --with-requirements qa/requirements.txt \
        locust -f qa/performance/locustfile.py --headless -u 50 -r 5 -t 5m \
        --host http://127.0.0.1:8000 --csv qa/reports/locust

Every simulated user logs in once through Keycloak (PKCE) as OPERATOR or
REVIEWER and then browses like the UI does. Read-only: nothing is uploaded.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from locust import HttpUser, between, task

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.auth import login_as  # noqa: E402


class Reviewer(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        session = login_as(random.choice(["OPERATOR", "REVIEWER"]))
        self.client.headers.update(session.headers)
        listing = self.client.get("/api/v1/dossiers?limit=20", name="/api/v1/dossiers").json()["data"]
        items = listing if isinstance(listing, list) else listing.get("items", [])
        self.dossier_ids = [i["id"] for i in items] or [None]

    @task(5)
    def list_dossiers(self) -> None:
        self.client.get("/api/v1/dossiers?limit=20", name="/api/v1/dossiers")

    @task(3)
    def open_dossier(self) -> None:
        dossier_id = random.choice(self.dossier_ids)
        if dossier_id:
            self.client.get(f"/api/v1/dossiers/{dossier_id}", name="/api/v1/dossiers/{id}")
            self.client.get(f"/api/v1/dossiers/{dossier_id}/documents", name="/api/v1/dossiers/{id}/documents")

    @task(2)
    def findings(self) -> None:
        dossier_id = random.choice(self.dossier_ids)
        if dossier_id:
            self.client.get(f"/api/v1/dossiers/{dossier_id}/findings", name="/api/v1/dossiers/{id}/findings")

    @task(1)
    def me(self) -> None:
        self.client.get("/api/v1/auth/me")
