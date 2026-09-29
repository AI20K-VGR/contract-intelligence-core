#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu/Debian VPS, run from the repo root:
#
#   sudo deploy/bootstrap.sh
#
# Installs Docker, opens only SSH/HTTP/HTTPS, adds swap on small machines and
# writes deploy/.env.prod with random secrets and sslip.io hostnames for this
# server's public IP. Safe to re-run: an existing deploy/.env.prod is kept.
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=deploy/.env.prod

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root (sudo deploy/bootstrap.sh)" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[bootstrap] installing Docker"
  curl -fsSL https://get.docker.com | sh
fi
docker compose version

if [ ! -f /etc/docker/daemon.json ]; then
  echo "[bootstrap] Docker log rotation: 5 x 20 MB per container"
  cat > /etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "20m", "max-file": "5" } }
JSON
  systemctl restart docker
fi

if command -v ufw >/dev/null 2>&1; then
  echo "[bootstrap] firewall: allow SSH, 80, 443 only"
  ufw allow OpenSSH >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw allow 443/udp >/dev/null
  ufw --force enable >/dev/null
fi

mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$mem_kb" -lt 15000000 ] && ! swapon --show | grep -q .; then
  echo "[bootstrap] adding 4G swap (RAM < 16G)"
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if [ -f "$ENV_FILE" ]; then
  echo "[bootstrap] $ENV_FILE exists, not touching it"
else
  ip=$(curl -fsS https://api.ipify.org)
  dashed=${ip//./-}
  echo "[bootstrap] public IP $ip → api-$dashed.sslip.io / auth-$dashed.sslip.io"
  cp deploy/.env.prod.example "$ENV_FILE"
  sed -i "s/^API_HOST=.*/API_HOST=api-$dashed.sslip.io/; s/^AUTH_HOST=.*/AUTH_HOST=auth-$dashed.sslip.io/" "$ENV_FILE"
  while grep -q '=generate$' "$ENV_FILE"; do
    sed -i "0,/=generate\$/s//=$(openssl rand -hex 24)/" "$ENV_FILE"
  done
  chmod 600 "$ENV_FILE"
  echo "[bootstrap] wrote $ENV_FILE (secrets generated). Fill AI2_LLM_* before deploying."
fi

if [ ! -f ai-service/.env ]; then
  cp ai-service/.env.example ai-service/.env
  chmod 600 ai-service/.env
  echo "[bootstrap] created ai-service/.env from the example: add MISTRAL_API_KEY (AI1)."
fi

echo "[bootstrap] next: edit $ENV_FILE and ai-service/.env, then run deploy/deploy.sh"
