---
phase: 3
title: "Packaging Ghcr Image"
status: pending
plan: 260929-2323-ai2-b-versioned-service
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — Packaging Ghcr Image

## Overview
Đóng gói AI2 thành image GHCR tự chứa, được gắn release version và Backend pin bằng tag cùng digest. Bao gồm `/version` thuần cấu hình, schema trong image, loại dữ liệu cục bộ khỏi build context, workflow có cổng evidence A và provenance/SBOM/attestation. Phụ thuộc P1 (version/contracts) và P2 (cấu hình LLM chốt sau HC-B1a); không phát GA.

## Requirements
- Runtime load schemas từ `AI2_CONTRACT_ROOT` với mặc định bên trong image; chạy không mount `docs/`. Không đóng gói `data/`, SQLite, `.env`, venv hay dữ liệu phát triển; vẫn tạo runtime `data/ai2` khi cần.
- `GET /version` và `/api/v1/version` không tạo client/gọi mạng; trả service version, API/contract versions, contract bundle SHA256, model/provider host, LLM enabled, git SHA và build time; không trả secret/path.
- Gate release chỉ nhận tag `ai2-vX.Y.Z[-rc.N]`, kiểm evidence JSON khớp tree hash `ai-service/`, rules RC/GA theo VD-B1/D-6. Không phát `latest`; image `linux/amd64`, GHCR private; provenance, SBOM và artifact attestation.
- Override compose pin `tag@sha256`; runbook ghi PAT `read:packages`, kiểm digest, rollback và thủ tục evidence. Rollback LLM phải nêu rõ env được load khi process khởi động: set ba deny flags, restart/recreate AI2 và Backend (không cần build/push image mới), rồi dùng fake-provider zero-call probe trước khi xác nhận; không hứa env edit tự đổi cấu hình process đang chạy. CODEOWNERS yêu cầu review workflow HC-B2.

## Related Code Files
**Create**
- `ai-service/.dockerignore`, `docker-compose.ai2-image.yml`
- `.github/workflows/ai2-release.yml`
- `evals/scripts/ai2_release_evidence.py`, `evals/tests/test_ai2_release_evidence.py`
- `ai-service/tests/test_version_endpoint.py`, `ai-service/tests/test_packaging_hygiene.py`
- `docs/ai2/AI2-17-release-runbook.vi.md`

**Modify**
- `ai-service/Dockerfile.ai2`, `ai-service/app/contracts/schema_validation.py`, `ai-service/app/api/main.py`, `ai-service/pyproject.toml`, `ai-service/.env.example`, `docker-compose.yml`, `.github/CODEOWNERS`, `ai-service/README.md`

**Delete:** không có.

## Implementation Steps
1. Preflight A/P1/P2 artifacts, verify `threshold_verdict` JSON key, live summary schema, pricing data, release owner, GitHub environment and tag rules; record real anchors. Stop before publish if required repository configuration is unavailable.
2. RED packaging tests: schemas load from image root without docs mount; image has no SQLite/env; `/version` reports injected metadata without network; release evidence accepts/rejects exact RC/GA cases and tree mismatch.
3. Copy contract schemas into app package, add `AI2_CONTRACT_ROOT` resolution and schema bundle hash; update Dockerfile and `.dockerignore`, remove `COPY data/`, gate `load_dotenv` for image while preserving local dev behavior.
4. Add version endpoints and build metadata; test no provider/embedding initialization or network calls on either endpoint. Keep `/healthz` cheap and existing `/health` compatibility documented.
5. Implement `ai2_release_evidence.py make/check`: include gate + live summary references and `ai-service/` tree hash; fail closed for missing/malformed verdict, invalid SemVer, changed tree or regression. Exercise all 7 cases in plan acceptance.
6. Add tag-triggered workflow, least required permissions, `linux/amd64`, metadata tags semver + sha, `latest=false`, SBOM/provenance and `actions/attest`; gate publish behind `ai2-release` environment. Do not publish if HC-B1b evidence, HC-B2 review or HC-B3 repo setup is missing.
7. Add compose override pinning image by tag@digest, runbook and CODEOWNERS. Validate compose rendering and workflow on PR/Actions. HC-B4 is a human-controlled publish/tag/deploy action after evidence is committed.

## TDD
### Tests-before (RED)
- `test_version_endpoint.py`: both paths; required fields; no API key/data path; no provider/embedding construction or outbound call.
- `test_packaging_hygiene.py`: Dockerfile has no broad data copy; ignore excludes `.env`, sqlite, venv; bundled schemas validate with no host docs mount; version/git SHA metadata injected.
- `test_ai2_release_evidence.py`: GA PASS→0, GA FAIL→1, RC no regression→0, RC regression→1, tree mismatch→1, evidence missing→2, malformed tag→2.

### Tests-after / Gate
- CI image-check builds and runs image; zero `*.sqlite*`; `/app/.env` absent; schema validation succeeds unmounted; `/version` version/SHA match build; `/healthz` returns 200 within 60s.
- Static workflow tests/checks; `docker compose -f docker-compose.yml -f docker-compose.ai2-image.yml config` renders exact tag@digest.
- Human HC-B2 review, HC-B3 environment/package/ruleset setup, HC-B1b live evidence, HC-B4 publish and attestation verification are recorded in `verification-P3.json`; no local Docker assumption (PB-B18).

## File inventory

| Action | Files | Approx. size / impact |
|---|---|---|
| Create | dockerignore, image compose override, release workflow, evidence script/tests, version/packaging tests, runbook | 9 files; image/release gates |
| Modify | Dockerfile, schema loader, API, package config, env sample, compose, CODEOWNERS, README | 8 files; startup/schema paths and deploy |

## Test scenario matrix

| Severity | Scenario | Expected check |
|---|---|---|
| Critical | Image starts without host docs/data mount | schema bundle loads and checksum matches `/version` |
| Critical | Local DB or secret enters image | build inspection finds zero SQLite and no `.env` |
| Critical | GA release evidence fails threshold/tree | gate blocks publish with documented exit code |
| High | `/version` health probe causes egress or leaks paths | zero network/client construction; allow-listed response only |
| High | Rebuilt or retagged release drift | digest pin and protected immutable tag procedure; no `latest` |
| Medium | Private GHCR pull or compose override misconfigured | documented PAT and rendered digest pin |

## Dependency map
- **Upstream:** P1 `versions.py` and schemas; P2 final LLM settings/benchmark verdict; A gate + live benchmark/pricing.
- **Downstream:** P4 image release is reissued as rc.2 with observability; C consumes pinned rc image; P4 updates release runbook owned here.
- **Human gates:** HC-B1b, HC-B2, HC-B3, HC-B4 block evidence/review/repo config/publish respectively.

## Success Criteria
- [ ] CI image-check proves zero SQLite, no `.env`, schema load without docs mount, correct `/version`, and `/healthz` within 60s.
- [ ] Evidence gate passes all 7 positive/negative cases and binds verdict to `ai-service/` tree hash.
- [ ] Workflow publishes only exact SemVer tag plus sha tag, never `latest`; SBOM/provenance and attestation verify.
- [ ] Compose renders GHCR `tag@sha256:digest`; runbook documents private pull and rollback.
- [ ] Review/setup/live evidence/publish evidence are recorded; no GA tag is emitted by B.

## Risks

| Risk | Likelihood × impact | Mitigation |
|---|---|---|
| Build context contains contract data or secrets | Medium × Critical | `.dockerignore`, no `COPY data/`, image inspection gate |
| Evidence gate reads wrong report field or stale tree | Medium × Critical | inspect A schemas at step 1; schema tests; tree hash mismatch blocks |
| Local host cannot build image | High × Low | required build runs on GitHub Actions; local static checks remain optional |
| GHCR tag overwrite/private access surprises | Medium × High | immutable-tag ruleset, digest pin, runbook PAT; never repush a published tag |
