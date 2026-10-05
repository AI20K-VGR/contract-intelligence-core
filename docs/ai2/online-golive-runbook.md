# Online and clean-checkout runbook

This is the canonical deployment path after the AI2 integration. The online
stack builds the Frontend image, serves it through Caddy, keeps AI2 internal,
and stores AI2 runs in PostgreSQL schema `ai2`. No SQLite file or path from a
developer machine is required.

## First deployment on a Linux server

```bash
git clone https://github.com/AI20K-VGR/contract-intelligence-core.git /opt/contract-intelligence
cd /opt/contract-intelligence
sudo deploy/bootstrap.sh
sudoedit deploy/.env.prod
sudoedit ai-service/.env
sudo deploy/deploy.sh
```

Set `APP_HOST`, `API_HOST`, `AUTH_HOST`, `FRONTEND_ORIGINS` and
`FRONTEND_BASE_URL` to the server's public HTTPS names. Set the AI2 LLM and
embedding provider URL/key, PostgreSQL/Keycloak/MinIO/HMAC secrets and the AI1
OCR key. `deploy/.env.prod` and `ai-service/.env` stay on the server with mode
600 and are never committed.

The online environment has these flags explicitly enabled:

```env
AI2_SEMANTIC_ENABLED=true
AI2_PROCESSING_EGRESS_ALLOWED=true
AI2_QUERY_EGRESS_ALLOWED=true
AI2_QUERY_USE_LLM=true
AI2_QUERY_USE_VECTOR=true
AI2_VECTOR_RECALL_ENABLED=true
AI2_EMBEDDING_DISCOVERY_ENABLED=true
```

Compose fails before startup when provider URL/key, AI2 PostgreSQL role or HMAC
is missing. It does not silently switch to lexical retrieval or SQLite.

## Verify the online stack

```bash
docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file deploy/.env.prod ps
docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file deploy/.env.prod logs -f frontend backend backend-worker ai1-worker ai2-service
```

Open `https://APP_HOST` in a browser. The API is `https://API_HOST`, OIDC is
`https://AUTH_HOST`, and AI2 `8002` is not exposed publicly. Backend-to-AI2
traffic stays on the private Compose network and carries the service HMAC.

## Clean checkout E2E

PowerShell:

```powershell
git clone https://github.com/AI20K-VGR/contract-intelligence-core.git
cd contract-intelligence-core
Copy-Item .env.e2e.example .env.e2e
.\scripts\run-golive-e2e.ps1 -EnvFile .env.e2e -PdfPath <path-to-pdf>
```

Linux/macOS:

```bash
git clone https://github.com/AI20K-VGR/contract-intelligence-core.git
cd contract-intelligence-core
cp .env.e2e.example .env.e2e
./scripts/run-golive-e2e.sh --env-file .env.e2e --pdf <path-to-pdf>
```

The runner validates the full flags and required provider values without
printing secrets, validates Compose, builds the Frontend image, waits for the
browser/backend health endpoints and prints the internal AI2 health command.
Upload, login, query, HITL and reprocess are then exercised in the browser so
the same `dossier_id`, `run_id`, snapshot digest, citations and review state can
be checked end to end.
