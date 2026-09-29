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

# Docker log rotation (5 x 20 MB per container), merged into any existing
# /etc/docker/daemon.json instead of skipping it. Only log keys are touched;
# values an operator already set win. Applies to containers created after the
# restart — deploy.sh (re)creates them.
changed=$(python3 - /etc/docker/daemon.json <<'MERGE'
import json, os, shutil, sys, time
path = sys.argv[1]
config = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    config = json.loads(text) if text else {}
before = json.dumps(config, sort_keys=True)
driver = config.setdefault("log-driver", "json-file")
if driver in ("json-file", "local"):
    opts = config.setdefault("log-opts", {})
    opts.setdefault("max-size", "20m")
    opts.setdefault("max-file", "5")
else:
    print(f"log-driver {driver!r} rotates on its own; left unchanged", file=sys.stderr)
if json.dumps(config, sort_keys=True) != before:
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.bak-{int(time.time())}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")
    print("yes")
MERGE
)
if [ "$changed" = yes ]; then
  echo "[bootstrap] Docker log rotation set in /etc/docker/daemon.json (5 x 20 MB); restarting Docker"
  systemctl restart docker
else
  echo "[bootstrap] Docker log rotation already configured"
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
