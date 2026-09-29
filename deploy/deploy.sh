#!/usr/bin/env bash
# Build and (re)start the whole stack, configure Keycloak, smoke-test the
# public URLs. Run from the repo root on the server:
#
#   deploy/deploy.sh            # deploy the checked-out commit
#   deploy/deploy.sh --pull     # git pull --ff-only first
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=deploy/.env.prod
COMPOSE=(docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file "$ENV_FILE")

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE — run deploy/bootstrap.sh first" >&2; exit 1; }
[ -f ai-service/.env ] || { echo "missing ai-service/.env" >&2; exit 1; }

envval() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }

if [ -z "$(envval AI2_LLM_BASE_URL)" ]; then
  echo "AI2_LLM_BASE_URL is empty in $ENV_FILE (Lead picks the LLM provider)" >&2
  exit 1
fi

if [ "${1:-}" = "--pull" ]; then
  git pull --ff-only
fi
echo "[deploy] commit $(git rev-parse --short HEAD) on $(git rev-parse --abbrev-ref HEAD)"

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d --remove-orphans

echo "[deploy] waiting for backend health"
for _ in $(seq 1 60); do
  status=$(docker inspect -f '{{.State.Health.Status}}' ci-backend 2>/dev/null || echo starting)
  [ "$status" = healthy ] && break
  sleep 5
done
[ "$status" = healthy ] || { "${COMPOSE[@]}" logs --tail 80 backend; exit 1; }

echo "[deploy] configuring Keycloak"
"${COMPOSE[@]}" run --rm --no-deps -T \
  -v "$PWD/deploy:/deploy:ro" \
  -e KEYCLOAK_ADMIN_PASSWORD="$(envval KEYCLOAK_ADMIN_PASSWORD)" \
  -e FRONTEND_ORIGINS="$(envval FRONTEND_ORIGINS)" \
  -e BACKEND_KEYCLOAK_ADMIN_SECRET="$(envval BACKEND_KEYCLOAK_ADMIN_SECRET)" \
  -e DEMO_ADMIN_PASSWORD="$(envval DEMO_ADMIN_PASSWORD)" \
  -e DEMO_REVIEWER_PASSWORD="$(envval DEMO_REVIEWER_PASSWORD)" \
  -e DEMO_OPERATOR_PASSWORD="$(envval DEMO_OPERATOR_PASSWORD)" \
  -e SMTP_HOST="$(envval SMTP_HOST)" -e SMTP_PORT="$(envval SMTP_PORT)" \
  -e SMTP_FROM="$(envval SMTP_FROM)" -e SMTP_USER="$(envval SMTP_USER)" \
  -e SMTP_PASSWORD="$(envval SMTP_PASSWORD)" -e SMTP_STARTTLS="$(envval SMTP_STARTTLS)" \
  backend python /deploy/keycloak_configure.py

api="https://$(envval API_HOST)"
auth="https://$(envval AUTH_HOST)"
echo "[deploy] smoke test"
for _ in $(seq 1 30); do
  curl -fsS "$api/health" >/dev/null 2>&1 && break
  sleep 5  # first run: Caddy is fetching certificates
done
curl -fsS "$api/health" && echo
curl -fsS "$auth/realms/contract-intelligence/.well-known/openid-configuration" \
  | grep -o '"issuer":"[^"]*"'
code=$(curl -s -o /dev/null -w '%{http_code}' "$auth/admin/master/console/")
[ "$code" = 404 ] && echo "admin console blocked publicly: ok" || echo "WARNING: admin console answered $code"
echo "Ports: run deploy/check_external.sh (or the deploy-external-check workflow) from"
echo "another machine — probing this server's own public IP from here can bypass the"
echo "provider firewall, so it is not a valid check."

cat <<INFO

[deploy] done. Next, from outside this server:
  deploy/check_external.sh $(envval API_HOST) $(envval AUTH_HOST)
Frontend (.env.local):
  VITE_API_BASE_URL=$api
  VITE_KEYCLOAK_URL=$auth
  VITE_KEYCLOAK_REALM=contract-intelligence
  VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
API docs: $api/docs
INFO
