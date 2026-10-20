
#!/usr/bin/env python3
"""Live evidence for ST-035..ST-039 against the docker compose stack.

Logs in through Keycloak (Authorization Code + PKCE, the SPA client), then drives
upload → AI1 OCR (Kafka) → AI2 (HTTP) → review action → search/ask through the
real API and records every request/response (tokens masked) as JSON.

Usage::

    uv run python scripts/collect_st035_039_evidence.py \
        --contract C:/tmp/contract.pdf --annex C:/tmp/annex.pdf \
        --out ../docs/evidence/ST-035-039/live
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx

API = "http://localhost:8000/api/v1"
KEYCLOAK = "http://localhost:8080/realms/contract-intelligence/protocol/openid-connect"
CLIENT_ID = "contract-intel-frontend"
REDIRECT_URI = "http://localhost:5173/auth/callback"
TENANT = "tenant_vgr_01"
USERS = {
    "operator": ("operator@ci.local", "Operator@CI123"),
    "reviewer": ("reviewer@ci.local", "Reviewer@CI123"),
    "admin": ("admin@ci.local", "Admin@CI123"),
}


def login(username: str, password: str) -> str:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    with httpx.Client(follow_redirects=False, timeout=30) as client:
        page = client.get(
            f"{KEYCLOAK}/auth",
            params={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": "openid",
                "state": secrets.token_hex(8),
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        match = re.search(r'action="([^"]*login-actions/authenticate[^"]*)"', page.text)
        if not match:
            raise RuntimeError(f"Keycloak login form not found (HTTP {page.status_code})")
        # Keycloak marks its session cookies Secure; httpx won't send those over http://.
        cookie = "; ".join(f"{c.name}={c.value}" for c in client.cookies.jar)
        submitted = client.post(
            html.unescape(match.group(1)),
            data={"username": username, "password": password, "credentialId": ""},
            headers={"Cookie": cookie},
        )
        location = submitted.headers.get("location", "")
        code = parse_qs(urlparse(location).query).get("code", [""])[0]
        if not code:
            raise RuntimeError(f"Login failed for {username} (HTTP {submitted.status_code})")
        token = client.post(
            f"{KEYCLOAK}/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        token.raise_for_status()
        return str(token.json()["access_token"])


@dataclass
class Recorder:
    tokens: dict[str, str]
    steps: list[dict[str, Any]] = field(default_factory=list)
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=120))

    def call(
        self,
        task: str,
        name: str,
        method: str,
        path: str,
        *,
        as_user: str | None,
        expect: int,
        tenant: str | None = TENANT,
        json_body: Any = None,
        files: Any = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = dict(extra_headers or {})
        if as_user:
            headers["Authorization"] = f"Bearer {self.tokens[as_user]}"
        if tenant:
            headers["X-Tenant-Id"] = tenant
        started = time.perf_counter()
        response = self.client.request(
            method, f"{API}{path}", headers=headers, json=json_body, files=files
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text[:2000]
        shown_headers = {
            k: ("Bearer <" + (as_user or "?") + "-jwt>" if k == "Authorization" else v)
            for k, v in headers.items()
        }
        passed = response.status_code == expect
        self.steps.append(
            {
                "task": task,
                "step": name,
                "request": {
                    "method": method,
                    "path": path,
                    "as_user": as_user,
                    "headers": shown_headers,
                    "json": json_body,
                    "files": [f[1][0] for f in files] if files else None,
                },
                "expected_status": expect,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "pass": passed,
                "response": body,
            }
        )
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {task} {name}: HTTP {response.status_code} (expect {expect})")
        return response


def _data(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def run(contract: Path, annex: Path, out: Path, timeout_s: float) -> int:
    out.mkdir(parents=True, exist_ok=True)
    tokens = {role: login(*creds) for role, creds in USERS.items()}
    print("[info] logged in:", ", ".join(tokens))
    rec = Recorder(tokens)
    meta = json.dumps({"name": f"Evidence ST-035..039 {uuid4().hex[:6]}"})

    def upload_files() -> list[tuple[str, tuple[str | None, Any, str | None]]]:
        return [
            ("contract", (contract.name, contract.read_bytes(), "application/pdf")),
            ("annexes", (annex.name, annex.read_bytes(), "application/pdf")),
            ("metadata", (None, meta, None)),
        ]

    # ---- ST-035: POST /dossiers ------------------------------------------------
    t = "ST-035"
    rec.call(t, "no JWT → 401", "POST", "/dossiers", as_user=None, expect=401, files=upload_files())
    rec.call(
        t,
        "missing X-Tenant-Id → 400",
        "POST",
        "/dossiers",
        as_user="operator",
        tenant=None,
        expect=400,
        files=upload_files(),
    )
    rec.call(
        t,
        "X-Tenant-Id ≠ JWT tenant → 403",
        "POST",
        "/dossiers",
        as_user="operator",
        tenant="tenant_other",
        expect=403,
        files=upload_files(),
    )
    rec.call(
        t,
        "REVIEWER role → 403",
        "POST",
        "/dossiers",
        as_user="reviewer",
        expect=403,
        files=upload_files(),
    )
    created = rec.call(
        t,
        "OPERATOR upload contract + annex → 202",
        "POST",
        "/dossiers",
        as_user="operator",
        expect=202,
        files=upload_files(),
    )
    if created.status_code != 202:
        return _finish(rec, out, {})
    ids = _data(created)
    dossier_id, job_id = ids["dossier_id"], ids["job_id"]
    ctx: dict[str, Any] = {"dossier_id": dossier_id, "job_id": job_id}

    rec.call(
        t,
        "share with reviewer + admin",
        "PUT",
        f"/dossiers/{dossier_id}/access",
        as_user="operator",
        expect=200,
        json_body={
            "scope": "shared_out",
            "shared_with": [
                {"id": USERS["reviewer"][0], "email": USERS["reviewer"][0]},
                {"id": USERS["admin"][0], "email": USERS["admin"][0]},
            ],
        },
    )

    # ---- ST-036/037: manifest, then Kafka AI1 → HTTP AI2 → pending_review ------
    manifest = _data(
        rec.call(
            "ST-037",
            "get manifest",
            "GET",
            f"/dossiers/{dossier_id}/manifest",
            as_user="operator",
            expect=200,
        )
    )
    if manifest.get("status") != "confirmed":
        rec.call(
            "ST-037",
            "confirm manifest",
            "POST",
            f"/dossiers/{dossier_id}/manifest/confirm",
            as_user="operator",
            expect=200,
            json_body={
                "version": manifest["version"],
                "members": manifest["members"],
                "relations": [
                    {**r, "confirmation": "confirmed"} for r in manifest.get("relations") or []
                ],
            },
        )

    seen: list[tuple[float, str]] = []
    started = time.monotonic()
    status = None
    while time.monotonic() - started < timeout_s:
        detail = rec.client.get(
            f"{API}/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {tokens['operator']}", "X-Tenant-Id": TENANT},
        )
        status = (_data(detail) or {}).get("latest_job_status")
        if not seen or seen[-1][1] != status:
            seen.append((round(time.monotonic() - started, 1), str(status)))
            print(f"[info] t+{seen[-1][0]}s job status = {status}")
        if status in {"pending_review", "failed"}:
            break
        time.sleep(3)
    ctx["status_timeline"] = [{"t_seconds": s, "status": v} for s, v in seen]
    rec.call(
        "ST-036",
        "dossier detail after pipeline",
        "GET",
        f"/dossiers/{dossier_id}",
        as_user="operator",
        expect=200,
    )
    if status != "pending_review":
        return _finish(rec, out, ctx)

    rec.call(
        "ST-037",
        "findings persisted",
        "GET",
        f"/dossiers/{dossier_id}/findings",
        as_user="reviewer",
        expect=200,
    )
    items = (
        _data(
            rec.call(
                "ST-037",
                "review items queued",
                "GET",
                f"/dossiers/{dossier_id}/review-items?limit=50",
                as_user="reviewer",
                expect=200,
            )
        )
        or []
    )
    if not items:
        # AI2 queued nothing for this input: open review items the way the FE does,
        # by reviewing clauses (first clause review creates the review_item).
        ctx["review_items_source"] = "clause_review"
        documents = (
            _data(
                rec.call(
                    "ST-038",
                    "list documents",
                    "GET",
                    f"/dossiers/{dossier_id}/documents",
                    as_user="reviewer",
                    expect=200,
                )
            )
            or []
        )
        contract_doc = next(d for d in documents if d["role"] == "CONTRACT")
        clauses = (
            _data(
                rec.call(
                    "ST-038",
                    "clause tree",
                    "GET",
                    f"/documents/{contract_doc['id']}/clauses",
                    as_user="reviewer",
                    expect=200,
                )
            )
            or []
        )
        targets = [c for c in clauses if "giá trị hợp đồng" in (c.get("text") or "")][:2]
        for clause in targets:
            rec.call(
                "ST-038",
                f"open review item via clause {clause['number']}",
                "POST",
                f"/clause-nodes/{clause['id']}/review",
                as_user="reviewer",
                expect=200,
                json_body={
                    "action": "reject",
                    "base_version": 0,
                    "comment": "Giá trị hợp đồng mâu thuẫn giữa các điều khoản",
                },
            )
        items = (
            _data(
                rec.call(
                    "ST-038",
                    "review items after clause review",
                    "GET",
                    f"/dossiers/{dossier_id}/review-items?limit=50",
                    as_user="reviewer",
                    expect=200,
                )
            )
            or []
        )
    else:
        ctx["review_items_source"] = "ai2"

    # ---- ST-038: review actions ------------------------------------------------
    t = "ST-038"
    if items:
        item = items[0]
        item_id, version = item["id"], int(item["version"])
        action = {"action": "confirm", "base_version": version}
        rec.call(
            t,
            "operator cannot act → 403",
            "POST",
            f"/review-items/{item_id}/actions",
            as_user="operator",
            expect=403,
            json_body=action,
            extra_headers={"Idempotency-Key": str(uuid4())},
        )
        rec.call(
            t,
            "base_version 0 → 422",
            "POST",
            f"/review-items/{item_id}/actions",
            as_user="reviewer",
            expect=422,
            json_body={**action, "base_version": 0},
            extra_headers={"Idempotency-Key": str(uuid4())},
        )
        rec.call(
            t,
            "confirm at current version → 200",
            "POST",
            f"/review-items/{item_id}/actions",
            as_user="reviewer",
            expect=200,
            json_body=action,
            extra_headers={"Idempotency-Key": str(uuid4())},
        )
        rec.call(
            t,
            "stale base_version → 409 VERSION_CONFLICT",
            "POST",
            f"/review-items/{item_id}/actions",
            as_user="reviewer",
            expect=409,
            json_body={"action": "reject", "base_version": version},
            extra_headers={"Idempotency-Key": str(uuid4())},
        )
        rec.call(
            t,
            "append-only revision trail",
            "GET",
            f"/review-items/{item_id}/revisions",
            as_user="reviewer",
            expect=200,
        )
        ctx["review_item_id"] = item_id

    # ---- ST-039: search / query / ask -----------------------------------------
    t = "ST-039"
    question = {"query": "Thời hạn thanh toán là bao nhiêu ngày?"}
    rec.call(
        t,
        "search → 200 (ACL + trace)",
        "POST",
        f"/dossiers/{dossier_id}/search",
        as_user="reviewer",
        expect=200,
        json_body=question,
    )
    rec.call(
        t,
        "client policy_flags rejected → 422",
        "POST",
        f"/dossiers/{dossier_id}/query",
        as_user="reviewer",
        expect=422,
        json_body={**question, "policy_flags": {"egress_allowed": True}},
    )
    rec.call(
        t,
        "ask without X-Tenant-Id → 400",
        "POST",
        f"/dossiers/{dossier_id}/ask",
        as_user="reviewer",
        tenant=None,
        expect=400,
        json_body=question,
    )
    rec.call(
        t,
        "ask with foreign X-Tenant-Id → 403",
        "POST",
        f"/dossiers/{dossier_id}/ask",
        as_user="reviewer",
        tenant="tenant_other",
        expect=403,
        json_body=question,
    )
    rec.call(
        t,
        "query → 200",
        "POST",
        f"/dossiers/{dossier_id}/query",
        as_user="reviewer",
        expect=200,
        json_body=question,
    )
    rec.call(
        t,
        "ask → 200",
        "POST",
        f"/dossiers/{dossier_id}/ask",
        as_user="reviewer",
        expect=200,
        json_body=question,
    )

    # ---- ST-038 (cont.): locked dossier refuses further actions ----------------
    if len(items) > 1:
        rec.call(
            "ST-038",
            "admin locks dossier",
            "POST",
            f"/dossiers/{dossier_id}/lock",
            as_user="admin",
            expect=200,
        )
        second = items[1]
        rec.call(
            "ST-038",
            "action on locked dossier → 409 INVARIANT_VIOLATION",
            "POST",
            f"/review-items/{second['id']}/actions",
            as_user="reviewer",
            expect=409,
            json_body={"action": "confirm", "base_version": int(second["version"])},
            extra_headers={"Idempotency-Key": str(uuid4())},
        )

    return _finish(rec, out, ctx)


def _finish(rec: Recorder, out: Path, ctx: dict[str, Any]) -> int:
    failed = [s for s in rec.steps if not s["pass"]]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "api": API,
        "tenant": TENANT,
        "context": ctx,
        "summary": {"steps": len(rec.steps), "passed": len(rec.steps) - len(failed)},
        "steps": rec.steps,
    }
    (out / "http_transcript.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[info] {report['summary']} → {out / 'http_transcript.json'}")
    print(json.dumps(ctx, ensure_ascii=False))
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--annex", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(run(args.contract, args.annex, args.out, args.timeout))


if __name__ == "__main__":
    main()
