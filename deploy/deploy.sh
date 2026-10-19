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
# BACKEND_DB_HOST / KEYCLOAK_DB_HOST set: the databases run on a DB server of
# their own (deploy/compose.db.yml), not here. Both or neither.
backend_db_host=$(envval BACKEND_DB_HOST || true)
keycloak_db_host=$(envval KEYCLOAK_DB_HOST || true)
backend_db_port=$(envval BACKEND_DB_PORT || true)
keycloak_db_port=$(envval KEYCLOAK_DB_PORT || true)
if [ -n "$backend_db_host$keycloak_db_host" ]; then
  for required in BACKEND_DB_HOST BACKEND_DB_PORT KEYCLOAK_DB_HOST KEYCLOAK_DB_PORT; do
    if [ -z "$(envval "$required" || true)" ]; then
      echo "$required is empty in $ENV_FILE; a DB server needs all four DB host/port settings" >&2
      exit 1
    fi
  done
  COMPOSE+=(-f deploy/compose.external-db.yml)
fi
# A Cloudflare Origin Certificate on disk: the hosts sit behind Cloudflare's
# proxy (deploy/compose.cloudflare.yml, deploy/README.md "Đứng sau Cloudflare").
if [ -f deploy/certs/origin.pem ] || [ -f deploy/certs/origin.key ]; then
  if [ ! -f deploy/certs/origin.pem ] || [ ! -f deploy/certs/origin.key ]; then
    echo "deploy/certs needs both origin.pem and origin.key (Cloudflare Origin Certificate)" >&2
    exit 1
  fi
  COMPOSE+=(-f deploy/compose.cloudflare.yml)
  # Zone-level Authenticated Origin Pulls once our CA is on the server.
  if [ -f deploy/certs/origin-pull-ca.pem ]; then
    COMPOSE+=(-f deploy/compose.cloudflare-aop.yml)
  fi
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
expected_sha=${SHA:-$(git rev-parse HEAD)}
actual_sha=$(git rev-parse HEAD)
[ "$actual_sha" = "$expected_sha" ] || {
  echo "[deploy] expected SHA $expected_sha but checkout is $actual_sha" >&2
  exit 1
}
echo "[deploy] deploying SHA $actual_sha"

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build

# A DB server that does not answer fails the deploy here, before `up -d`
# touches the running stack. pg_isready proves the address and port, not the
# password: a wrong password shows up as the backend never turning healthy.
if [ -n "$backend_db_host" ]; then
  echo "[deploy] preflight: DB server ($backend_db_host:$backend_db_port, $keycloak_db_host:$keycloak_db_port)"
  for db in "$backend_db_host $backend_db_port ci contract_intelligence" \
            "$keycloak_db_host $keycloak_db_port keycloak keycloak"; do
    read -r host port user name <<<"$db"
    if ! docker run --rm pgvector/pgvector:pg16 pg_isready -h "$host" -p "$port" -U "$user" -d "$name" -t 10 >/dev/null; then
      echo "[deploy] database $name on $host:$port does not answer; nothing was restarted." >&2
      echo "         Check deploy/compose.db.yml on the DB server and the security group." >&2
      exit 1
    fi
  done
fi

# Preflight: probe AI2's LLM and embedding providers with the NEW image and
# env in a throwaway container, before `up -d` replaces the running stack (and
# before the backend or AI2 apply migrations). A missing key or unreachable
# provider then fails the deploy while the previous version keeps serving.
# The probe imports only the provider clients, never the app, so it opens no
# database; AI2 on PostgreSQL is checked through /readyz after `up -d`.
echo "[deploy] preflight: AI2 LLM/embedding providers (new image, old stack untouched)"
ai2_probe='
from app.llm.client import NineRouterClient, llm_status
from app.llm.embeddings import OpenAICompatibleEmbeddingClient
llm = llm_status(NineRouterClient())
embedding = OpenAICompatibleEmbeddingClient().discover(egress_approved=True).as_dict()["status"]
print(f"llm={llm} embedding={embedding}")
raise SystemExit(0 if (llm, embedding) == ("ready", "READY") else 1)
'
ai2_preflight=0
for attempt in 1 2 3; do
  if "${COMPOSE[@]}" run --rm --no-deps -T ai2-service       /app/.venv/bin/python -c "$ai2_probe" >/tmp/ai2-preflight.log 2>&1; then
    ai2_preflight=1
    break
  fi
  echo "[deploy] AI2 preflight attempt $attempt: $(tail -n 1 /tmp/ai2-preflight.log)" >&2
  sleep 10
done
if [ "$ai2_preflight" -ne 1 ]; then
  echo "[deploy] AI2 providers are not ready with the new build; nothing was restarted." >&2
  tail -n 40 /tmp/ai2-preflight.log >&2 || true
  exit 1
fi
echo "[deploy] AI2 preflight: $(tail -n 1 /tmp/ai2-preflight.log)"

"${COMPOSE[@]}" up -d --remove-orphans

# Caddy reads its config through single-file bind mounts. `git checkout`
# replaces those files with new inodes, so a running ci-caddy keeps the old
# content, and `up -d` sees no compose change to recreate it. A Caddyfile edit
# then stays inactive (#129's 404 on /api/v1/auth/backchannel-logout did).
# Restart Caddy when any mounted file differs, after `caddy validate` loads the
# new config in a throwaway container (same mounts, env and image). validate
# also provisions modules, so a missing TLS file or a bad module value stops the
# deploy here, while the running Caddy keeps serving the old config. `adapt`
# only parses and would let those through to a restart that never comes up.
caddy_changed=0
while IFS='|' read -r caddy_source caddy_target; do
  [ -f "$caddy_source" ] || continue
  host_sum=$(sha256sum "$caddy_source" | cut -d' ' -f1)
  live_sum=$(docker exec ci-caddy sha256sum "$caddy_target" 2>/dev/null | cut -d' ' -f1 || true)
  if [ "$host_sum" != "$live_sum" ]; then
    echo "[deploy] Caddy config changed: $caddy_target"
    caddy_changed=1
  fi
done < <(docker inspect -f '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}|{{.Destination}}{{"\n"}}{{end}}{{end}}' ci-caddy)
if [ "$caddy_changed" -eq 1 ]; then
  if ! "${COMPOSE[@]}" run --rm --no-deps -T caddy \
      caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/tmp/caddy-validate.log 2>&1; then
    echo "[deploy] the new Caddy config does not load; Caddy keeps serving the old one" >&2
    tail -n 20 /tmp/caddy-validate.log >&2 || true
    exit 1
  fi
  "${COMPOSE[@]}" restart caddy
  echo "[deploy] Caddy restarted with the new config"
fi

# Prometheus mounts prometheus.yml as a single file too, so a scrape job added
# in git stays inactive the same way (#139's ai2-service job did until a manual
# restart). Same check: when the mounted file differs, `promtool check config`
# loads it in a throwaway container first, then Prometheus restarts. The data
# lives in the prometheus_data volume and survives the restart.
prometheus_changed=0
if docker inspect ci-prometheus >/dev/null 2>&1; then
  while IFS='|' read -r prometheus_source prometheus_target; do
    [ -f "$prometheus_source" ] || continue
    host_sum=$(sha256sum "$prometheus_source" | cut -d' ' -f1)
    live_sum=$(docker exec ci-prometheus sha256sum "$prometheus_target" 2>/dev/null | cut -d' ' -f1 || true)
    if [ "$host_sum" != "$live_sum" ]; then
      echo "[deploy] Prometheus config changed: $prometheus_target"
      prometheus_changed=1
    fi
  done < <(docker inspect -f '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}|{{.Destination}}{{"\n"}}{{end}}{{end}}' ci-prometheus)
fi
if [ "$prometheus_changed" -eq 1 ]; then
  if ! "${COMPOSE[@]}" run --rm --no-deps -T --entrypoint promtool prometheus \
      check config /etc/prometheus/prometheus.yml >/tmp/prometheus-check.log 2>&1; then
    echo "[deploy] the new Prometheus config does not load; Prometheus keeps the old one" >&2
    tail -n 20 /tmp/prometheus-check.log >&2 || true
    exit 1
  fi
  "${COMPOSE[@]}" restart prometheus
  echo "[deploy] Prometheus restarted with the new config"
fi

echo "[deploy] waiting for backend health"
for _ in $(seq 1 60); do
  status=$(docker inspect -f '{{.State.Health.Status}}' ci-backend 2>/dev/null || echo starting)
  [ "$status" = healthy ] && break
  sleep 5
done
[ "$status" = healthy ] || { "${COMPOSE[@]}" logs --tail 80 backend; exit 1; }

kc_status=$(docker inspect -f '{{.State.Health.Status}}' ci-keycloak-readiness 2>/dev/null || echo missing)
[ "$kc_status" = healthy ] || {
  echo "[deploy] Keycloak readiness probe is $kc_status" >&2
  exit 1
}

# Inside the running backend container, not `compose run`: a second backend
# container would ask for the same fixed ci-monitoring address and fail with
# "Address already in use".
echo "[deploy] waiting for AI2 full LLM/vector readiness"
ai2_ready=0
ai2_deadline=$((SECONDS + 600))
while (( SECONDS < ai2_deadline )); do
  ai2_remaining=$((ai2_deadline - SECONDS))
  ai2_probe_timeout=$((ai2_remaining < 90 ? ai2_remaining : 90))
  if timeout --kill-after=5s "${ai2_probe_timeout}s" \
      "${COMPOSE[@]}" exec -T ai2-service /app/.venv/bin/python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8002/readyz', timeout=$ai2_probe_timeout)" \
      >/dev/null 2>&1; then
    ai2_ready=1
    break
  fi
  ai2_remaining=$((ai2_deadline - SECONDS))
  (( ai2_remaining > 0 )) || break
  sleep "$((ai2_remaining < 5 ? ai2_remaining : 5))"
done
if [ "$ai2_ready" -ne 1 ]; then
  echo "[deploy] AI2 did not become ready; refusing to report a successful deployment" >&2
  timeout --kill-after=5s 10s "${COMPOSE[@]}" logs --tail 120 ai2-service >&2 || true
  exit 1
fi
echo "[deploy] AI2 full capability: ready"

echo "[deploy] configuring Keycloak"
"${COMPOSE[@]}" exec -T \
  -e KEYCLOAK_ADMIN_PASSWORD="$(envval KEYCLOAK_ADMIN_PASSWORD)" \
  -e KEYCLOAK_PUBLIC_URL="https://$(envval AUTH_HOST)" \
  -e FRONTEND_ORIGINS="$(envval FRONTEND_ORIGINS)" \
  -e KEYCLOAK_KEEP_LOCAL_REDIRECTS="$(envval KEYCLOAK_KEEP_LOCAL_REDIRECTS || true)" \
  -e BACKEND_KEYCLOAK_ADMIN_SECRET="$(envval BACKEND_KEYCLOAK_ADMIN_SECRET)" \
  -e DEMO_ADMIN_PASSWORD="$(envval DEMO_ADMIN_PASSWORD)" \
  -e DEMO_REVIEWER_PASSWORD="$(envval DEMO_REVIEWER_PASSWORD)" \
  -e DEMO_OPERATOR_PASSWORD="$(envval DEMO_OPERATOR_PASSWORD)" \
  -e SMTP_HOST="$(envval SMTP_HOST)" -e SMTP_PORT="$(envval SMTP_PORT)" \
  -e SMTP_FROM="$(envval SMTP_FROM)" -e SMTP_USER="$(envval SMTP_USER)" \
  -e SMTP_PASSWORD="$(envval SMTP_PASSWORD)" -e SMTP_STARTTLS="$(envval SMTP_STARTTLS)" \
  backend python - < deploy/keycloak_configure.py

# Nightly backup (deploy/backup.sh). The schedule is written here rather than
# kept in a hand-edited crontab, so every server built from the repo has one:
# production ran without any until 19/10/2026. BACKUP_SCHEDULE in
# deploy/.env.prod is a cron expression in the server's clock (UTC on AWS), or
# "off". Default 19:00 UTC = 02:00 in Vietnam, outside working hours.
backup_schedule=$(envval BACKUP_SCHEDULE || true)
backup_schedule=${backup_schedule:-0 19 * * *}
backup_cron=${BACKUP_CRON_FILE:-/etc/cron.d/ci-backup}
if [ "$backup_schedule" = off ]; then
  if [ -e "$backup_cron" ]; then
    rm -f "$backup_cron"
    echo "[deploy] nightly backup: off (BACKUP_SCHEDULE=off), schedule removed"
  fi
else
  read -r -a backup_fields <<< "$backup_schedule"
  if [ "${#backup_fields[@]}" -ne 5 ] || [[ "$backup_schedule" =~ [^0-9*/,\ -] ]]; then
    echo "[deploy] BACKUP_SCHEDULE is not a 5-field cron expression: $backup_schedule" >&2
    exit 1
  fi
  backup_entry="# Managed by deploy/deploy.sh: BACKUP_SCHEDULE in deploy/.env.prod, \"off\" removes it.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
$backup_schedule root $PWD/deploy/backup.sh >> /var/log/ci-backup.log 2>&1"
  if [ "$(cat "$backup_cron" 2>/dev/null || true)" != "$backup_entry" ]; then
    # cron.d ignores files that are group/world writable or have a dot in the name.
    printf '%s\n' "$backup_entry" > "$backup_cron.new"
    chmod 644 "$backup_cron.new"
    mv "$backup_cron.new" "$backup_cron"
    echo "[deploy] nightly backup scheduled: $backup_schedule (server time) -> $backup_cron"
  fi
  if command -v systemctl >/dev/null && ! systemctl is-active --quiet cron 2>/dev/null; then
    echo "WARNING: the cron service is not running; the nightly backup will not run" >&2
  fi
fi

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
case "$code" in  # 404 from Caddy, 403 when Cloudflare's WAF stops it first
  404|403) echo "admin console blocked publicly ($code): ok" ;;
  *) echo "WARNING: admin console answered $code" ;;
esac
# Keycloak reports ended sessions to the backend inside ci-network only (#129).
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -d 'logout_token=x' "$api/api/v1/auth/backchannel-logout")
case "$code" in  # 404 from Caddy, 403 when Cloudflare's WAF stops it first
  404|403) echo "back-channel logout blocked publicly ($code): ok" ;;
  *) echo "WARNING: back-channel logout answered $code from the Internet (Caddy config not live?)" ;;
esac
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'X-WEBAUTH-USER: admin' "$api/grafana/")
[ "$code" = 401 ] && echo "grafana refuses anonymous callers: ok" || echo "WARNING: /grafana answered $code"
if [ -n "$app_host" ]; then
  # A client-side route has no file behind it: 200 proves the index.html fallback.
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://$app_host/dossiers")
  [ "$code" = 200 ] && echo "frontend served at https://$app_host: ok" || echo "WARNING: frontend answered $code"
  # The SPA calls the API on its own origin (deploy/frontend.caddy), so the
  # same checks hold there: the API answers, the back-channel path and anonymous
  # Grafana stay closed.
  # The backend's health route is /health, outside /api. An anonymous call to an
  # /api route proves the app origin reaches the backend: its 401 is JSON, while
  # a route Caddy missed would fall through to the SPA and answer 200 HTML.
  api_body=$(mktemp)
  code=$(curl -s -o "$api_body" -w '%{http_code}' "https://$app_host/api/v1/dossiers")
  if [ "$code" = 401 ] && grep -q 'Authorization' "$api_body"; then
    echo "API on the app origin: ok"
  else
    echo "WARNING: https://$app_host/api/v1/dossiers answered $code, expected the backend's 401"
  fi
  rm -f "$api_body"
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -d 'logout_token=x' "https://$app_host/api/v1/auth/backchannel-logout")
  case "$code" in
    404|403) echo "back-channel logout blocked on the app origin ($code): ok" ;;
    *) echo "WARNING: back-channel logout answered $code on the app origin" ;;
  esac
  code=$(curl -s -o /dev/null -w '%{http_code}' -H 'X-WEBAUTH-USER: admin' "https://$app_host/grafana/")
  [ "$code" = 401 ] && echo "grafana on the app origin refuses anonymous callers: ok" || echo "WARNING: https://$app_host/grafana/ answered $code"
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
