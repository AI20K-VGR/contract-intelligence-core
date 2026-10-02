#!/usr/bin/env bash
# Check the online stack FROM OUTSIDE the server (a dev machine or CI runner).
# Probing the VPS's own public IP from the VPS can loop back inside the host
# and skip the cloud firewall, so a "closed" result there proves little.
#
#   deploy/check_external.sh api-1-2-3-4.sslip.io auth-1-2-3-4.sslip.io
#
# Exit code 0 only when HTTPS works, /admin is blocked, /grafana refuses an
# anonymous caller and every internal port (AI2 8002, databases, Kafka, MinIO,
# Keycloak, mailpit, Grafana, Prometheus, exporters) is unreachable.
set -uo pipefail

API_HOST=${1:?usage: check_external.sh API_HOST AUTH_HOST}
AUTH_HOST=${2:?usage: check_external.sh API_HOST AUTH_HOST}
IP=$(python3 -c "import socket, sys; print(socket.gethostbyname(sys.argv[1]))" "$API_HOST")
# Every port the local stack publishes; production must publish none of them.
INTERNAL_PORTS=(8002 8000 8080 8443 5432 5433 5434 9000 9001 9092 9093 29092 1025 8025
  3000 9090 9100 9101 9108)
failures=0

ok() { echo "  ok    $*"; }
fail() { echo "  FAIL  $*"; failures=$((failures + 1)); }

echo "Checking $API_HOST / $AUTH_HOST ($IP) from $(hostname)"

if body=$(curl -fsS --max-time 10 "https://$API_HOST/health"); then
  ok "https://$API_HOST/health → $body"
else
  fail "https://$API_HOST/health unreachable"
fi

issuer=$(curl -fsS --max-time 10 \
  "https://$AUTH_HOST/realms/contract-intelligence/.well-known/openid-configuration" \
  | python3 -c "import json, sys; print(json.load(sys.stdin)['issuer'])" 2>/dev/null)
if [ "$issuer" = "https://$AUTH_HOST/realms/contract-intelligence" ]; then
  ok "OIDC issuer $issuer"
else
  fail "OIDC issuer is '${issuer:-unreachable}'"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$AUTH_HOST/admin/master/console/")
[ "$code" = 404 ] && ok "Keycloak /admin blocked (404)" || fail "Keycloak /admin answered $code"

# Monitoring: Grafana only behind the backend's ADMINISTRATOR check, and a
# forged auth-proxy header must not help.
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10   -H 'X-WEBAUTH-USER: admin' "https://$API_HOST/grafana/")
[ "$code" = 401 ] && ok "/grafana refuses anonymous + forged header (401)"   || fail "/grafana answered $code to an anonymous caller"

for port in "${INTERNAL_PORTS[@]}"; do
  if timeout 4 bash -c "exec 3<>/dev/tcp/$IP/$port" 2>/dev/null; then
    fail "port $port is reachable from outside"
  else
    ok "port $port closed"
  fi
done

if [ "$failures" -eq 0 ]; then
  echo "All external checks passed."
else
  echo "$failures external check(s) failed."
fi
exit "$failures"
