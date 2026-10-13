#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE=.env.e2e
PDF_PATH=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE=${2:?missing value for --env-file}; shift 2 ;;
    --pdf) PDF_PATH=${2:?missing value for --pdf}; shift 2 ;;
    -h|--help) echo 'usage: ./scripts/run-golive-e2e.sh [--env-file .env.e2e] [--pdf path]'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE; copy .env.e2e.example and fill provider keys." >&2; exit 2; }
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(AI2_LLM_API_KEY AI2_EMBEDDING_API_KEY)
[[ -n "$PDF_PATH" ]] && required+=(MISTRAL_API_KEY)
missing=()
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || missing+=("$name")
done
if ((${#missing[@]})); then
  echo "Full LLM/vector preflight refused: required provider values are empty (${missing[*]}). Values are never printed." >&2
  exit 2
fi
if [[ -z "${AI2_SEMANTIC_PROFILE_CONFIG:-}" ]]; then
  echo 'Full semantic preflight refused: AI2_SEMANTIC_PROFILE_CONFIG is missing.' >&2
  exit 2
fi
if ! AI2_SEMANTIC_PROFILE_CONFIG="$AI2_SEMANTIC_PROFILE_CONFIG" python - <<'PY'
import json
import os
import sys

try:
    profile = json.loads(os.environ["AI2_SEMANTIC_PROFILE_CONFIG"])
    required = {"version", "contract_type", "context_bounds", "alias_proposal_minimum_length"}
    if not isinstance(profile, dict) or not required.issubset(profile):
        raise ValueError
except (KeyError, TypeError, ValueError, json.JSONDecodeError):
    sys.exit(1)
PY
then
  echo 'Full semantic preflight refused: AI2_SEMANTIC_PROFILE_CONFIG is not a valid trusted profile.' >&2
  exit 2
fi
for name in AI2_SEMANTIC_ENABLED AI2_PROCESSING_EGRESS_ALLOWED AI2_QUERY_EGRESS_ALLOWED AI2_QUERY_USE_LLM AI2_QUERY_USE_VECTOR AI2_VECTOR_RECALL_ENABLED; do
  case "${!name:-}" in 1|true|yes|on) ;; *) echo "Full AI2 preflight refused: $name must be true." >&2; exit 2 ;; esac
done

compose=(docker compose -f docker-compose.yml --env-file "$ENV_FILE")
"${compose[@]}" config --quiet
"${compose[@]}" up --build -d

deadline=$((SECONDS + 300))
until curl -fsS --max-time 3 http://localhost:5173/healthz >/dev/null && curl -fsS --max-time 3 http://localhost:8000/health >/dev/null && "${compose[@]}" exec -T ai2-service python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/readyz', timeout=5)" >/dev/null; do
  (( SECONDS < deadline )) || { "${compose[@]}" ps; echo 'Frontend/backend health did not become ready. AI2 is internal-only; inspect it with docker compose exec ai2-service.' >&2; exit 1; }
  sleep 5
done

python scripts/check_frontend_pdf_worker.py

echo 'E2E stack is ready.'
echo 'UI:      http://localhost:5173'
echo 'Backend: http://localhost:8000/health'
echo "AI2:     internal-only; run ${compose[*]} exec ai2-service python -c \"import urllib.request; print(urllib.request.urlopen('http://localhost:8002/health', timeout=5).read().decode())\""
echo "Status:  ${compose[*]} ps"
echo "Logs:    ${compose[*]} logs -f frontend backend backend-worker ai1-worker ai2-service"
[[ -z "$PDF_PATH" ]] || echo "PDF supplied for manual browser upload: $PDF_PATH"
