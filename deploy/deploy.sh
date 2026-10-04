#!/usr/bin/env bash
# Build and (re)start the whole stack, configure Keycloak, smoke-test the
# public URLs. Run from the repo root on the server:
#
#   deploy/deploy.sh            # deploy the checked-out commit
#   deploy/deploy.sh --pull     # git pull --ff-only first
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=deploy/.env.prod

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE — run deploy/bootstrap.sh first" >&2; exit 1; }
[ -f ai-service/.env ] || { echo "missing ai-service/.env" >&2; exit 1; }

envval() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }

# APP_HOST set: this server also builds and serves the frontend.
app_host=$(envval APP_HOST)
COMPOSE=(docker compose -f docker-compose.yml -f deploy/compose.prod.yml)
if [ -n "$app_host" ]; then
  COMPOSE+=(-f deploy/compose.frontend.yml)
  case ",$(envval FRONTEND_ORIGINS)," in
    *",https://$app_host,"*) ;;
    *) echo "FRONTEND_ORIGINS in $ENV_FILE must contain https://$app_host" >&2; exit 1 ;;
  esac
fi
COMPOSE+=(--env-file "$ENV_FILE")

if [ -z "$(envval AI2_LLM_BASE_URL)" ]; then
  echo "AI2_LLM_BASE_URL is empty in $ENV_FILE (Lead picks the LLM provider)" >&2
  exit 1
fi
for required in AI2_LLM_API_KEY AI2_EMBEDDING_BASE_URL AI2_EMBEDDING_API_KEY APP_HOST; do
  if [ -z "$(envval "$required")" ]; then
    echo "$required is empty in $ENV_FILE; full online LLM/vector startup is fail-fast" >&2
    exit 1
  fi
done

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

# Inside the running backend container, not `compose run`: a second backend
# container would ask for the same fixed ci-monitoring address and fail with
# "Address already in use".
echo "[deploy] waiting for AI2 full LLM/vector readiness"
ai2_ready=0
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T ai2-service /app/.venv/bin/python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8002/readyz', timeout=5)" \
      >/dev/null 2>&1; then
    ai2_ready=1
    break
  fi
  sleep 5
done
if [ "$ai2_ready" -ne 1 ]; then
  echo "[deploy] AI2 did not become ready; refusing to report a successful deployment" >&2
  "${COMPOSE[@]}" logs --tail 120 ai2-service >&2 || true
  exit 1
fi
echo "[deploy] AI2 full capability: ready"

echo "[deploy] configuring Keycloak"
"${COMPOSE[@]}" exec -T \
  -e KEYCLOAK_ADMIN_PASSWORD="$(envval KEYCLOAK_ADMIN_PASSWORD)" \
  -e KEYCLOAK_PUBLIC_URL="https://$(envval AUTH_HOST)" \
  -e FRONTEND_ORIGINS="$(envval FRONTEND_ORIGINS)" \
  -e BACKEND_KEYCLOAK_ADMIN_SECRET="$(envval BACKEND_KEYCLOAK_ADMIN_SECRET)" \
  -e DEMO_ADMIN_PASSWORD="$(envval DEMO_ADMIN_PASSWORD)" \
  -e DEMO_REVIEWER_PASSWORD="$(envval DEMO_REVIEWER_PASSWORD)" \
  -e DEMO_OPERATOR_PASSWORD="$(envval DEMO_OPERATOR_PASSWORD)" \
  -e SMTP_HOST="$(envval SMTP_HOST)" -e SMTP_PORT="$(envval SMTP_PORT)" \
  -e SMTP_FROM="$(envval SMTP_FROM)" -e SMTP_USER="$(envval SMTP_USER)" \
  -e SMTP_PASSWORD="$(envval SMTP_PASSWORD)" -e SMTP_STARTTLS="$(envval SMTP_STARTTLS)" \
  backend python - < deploy/keycloak_configure.py

api="https://$(envval API_HOST)"
auth="https://$(envval AUTH_HOST)"
echo "[deploy] smoke test"
for _ in $(seq 1 30); do
  curl -fsS "$api/health" >/dev/null 2>&1 && break
  sleep 5  # first run: Caddy is fetching certificates
done
curl -fsS "$api/health" && echo
app="https://$(envval APP_HOST)"
curl -fsS "$app/healthz" >/dev/null && echo "frontend health: ok"
curl -fsS "$auth/realms/contract-intelligence/.well-known/openid-configuration" \
  | grep -o '"issuer":"[^"]*"'
code=$(curl -s -o /dev/null -w '%{http_code}' "$auth/admin/master/console/")
[ "$code" = 404 ] && echo "admin console blocked publicly: ok" || echo "WARNING: admin console answered $code"
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'X-WEBAUTH-USER: admin' "$api/grafana/")
[ "$code" = 401 ] && echo "grafana refuses anonymous callers: ok" || echo "WARNING: /grafana answered $code"
if [ -n "$app_host" ]; then
  # A client-side route has no file behind it: 200 proves the index.html fallback.
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://$app_host/dossiers")
  [ "$code" = 200 ] && echo "frontend served at https://$app_host: ok" || echo "WARNING: frontend answered $code"
fi
echo "Ports: run deploy/check_external.sh (or the deploy-external-check workflow) from"
echo "another machine — probing this server's own public IP from here can bypass the"
echo "provider firewall, so it is not a valid check."

if [ -n "$app_host" ]; then
  frontend_note="https://$app_host"
else
  frontend_note="not served by this server (APP_HOST is empty)"
fi

cat <<INFO

[deploy] done. Next, from outside this server:
  deploy/check_external.sh $(envval API_HOST) $(envval AUTH_HOST) $app_host
Frontend online: $frontend_note
Frontend on a dev machine (.env.local):
  VITE_APP_URL=$app
  VITE_API_BASE_URL=$api
  VITE_KEYCLOAK_URL=$auth
  VITE_KEYCLOAK_REALM=contract-intelligence
  VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
API docs: $api/docs
INFO
