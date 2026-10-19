#!/usr/bin/env bash
# Switch the local compose stack between free mode (no paid OCR/LLM) and the
# normal paid mode, by recreating only backend-worker and ai2-service.
#
#   ./qa/scripts/stack-mode.sh free   # AI1_OCR_ENGINE=pymupdf, AI2 egress off
#   ./qa/scripts/stack-mode.sh paid   # back to docker-compose.yml defaults
set -euo pipefail
cd "$(dirname "$0")/../.."

case "${1:-}" in
  free)
    export AI1_OCR_ENGINE=pymupdf
    for f in AI2_PROCESSING_EGRESS_ALLOWED AI2_QUERY_EGRESS_ALLOWED AI2_QUERY_USE_LLM \
             AI2_QUERY_USE_VECTOR AI2_VECTOR_RECALL_ENABLED; do export "$f=false"; done ;;
  paid)
    unset AI1_OCR_ENGINE AI2_PROCESSING_EGRESS_ALLOWED AI2_QUERY_EGRESS_ALLOWED \
          AI2_QUERY_USE_LLM AI2_QUERY_USE_VECTOR AI2_VECTOR_RECALL_ENABLED ;;
  *) echo "usage: $0 free|paid" >&2; exit 2 ;;
esac

docker compose up -d --no-deps --no-build --force-recreate backend-worker ai2-service
echo "Stack mode: $1"
docker exec ci-backend-worker printenv AI1_OCR_ENGINE
docker exec ci-ai2-service printenv AI2_PROCESSING_EGRESS_ALLOWED
