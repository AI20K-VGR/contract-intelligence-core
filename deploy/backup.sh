#!/usr/bin/env bash
# Nightly backup: both Postgres databases and the MinIO buckets.
#   0 2 * * * /opt/contract-intelligence/deploy/backup.sh >> /var/log/ci-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=deploy/.env.prod
DEST=${BACKUP_DIR:-/var/backups/contract-intelligence}
KEEP_DAYS=${BACKUP_KEEP_DAYS:-7}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
envval() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }

mkdir -p "$DEST/$stamp"
docker exec ci-backend-db pg_dump -U ci -d contract_intelligence -Fc > "$DEST/$stamp/backend.dump"
docker exec ci-keycloak-db pg_dump -U keycloak -d keycloak -Fc > "$DEST/$stamp/keycloak.dump"
docker run --rm --network ci-network -v "$DEST/$stamp/minio:/backup" \
  -e MC_HOST_src="http://$(envval MINIO_ROOT_USER):$(envval MINIO_ROOT_PASSWORD)@minio:9000" \
  quay.io/minio/mc:latest mirror --quiet src /backup
find "$DEST" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} +
echo "[backup] $DEST/$stamp $(du -sh "$DEST/$stamp" | cut -f1)"
