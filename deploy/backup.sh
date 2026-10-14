#!/usr/bin/env bash
# Nightly backup: both Postgres databases and the MinIO buckets.
#   0 2 * * * /opt/contract-intelligence/deploy/backup.sh >> /var/log/ci-backup.log 2>&1
#
# With BACKUP_S3_ENDPOINT set in deploy/.env.prod the backup is also encrypted
# and copied off this server (deploy/README.md, "Backup ra ngoài máy").
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
docker run --rm --user 0:0 --network ci-network -v "$DEST/$stamp/minio:/backup" \
  -e MC_HOST_src="http://$(envval MINIO_ROOT_USER):$(envval MINIO_ROOT_PASSWORD)@minio:9000" \
  cgr.dev/chainguard/minio-client:latest mirror --quiet src /backup
echo "[backup] $DEST/$stamp $(du -sh "$DEST/$stamp" | cut -f1)"

# ---- Off-site copy (optional) ------------------------------------------------
# One encrypted archive of this run, cut into parts small enough for the
# bucket's per-file limit, under <bucket>/<stamp>/. Credentials reach rclone
# and openssl through the environment, never the command line.
REMOTE_ENDPOINT=$(envval BACKUP_S3_ENDPOINT || true)
REMOTE_KEEP_DAYS=$(envval BACKUP_REMOTE_KEEP_DAYS || true)
REMOTE_KEEP_DAYS=${REMOTE_KEEP_DAYS:-$KEEP_DAYS}
PART_SIZE=$(envval BACKUP_PART_SIZE || true)
PART_SIZE=${PART_SIZE:-45M}
RCLONE_IMAGE=rclone/rclone:latest
staging="$DEST/.offsite-$stamp"

rclone_remote() {
  docker run --rm \
    -e RCLONE_CONFIG_DST_TYPE=s3 -e RCLONE_CONFIG_DST_PROVIDER=Other \
    -e RCLONE_CONFIG_DST_ENDPOINT -e RCLONE_CONFIG_DST_REGION \
    -e RCLONE_CONFIG_DST_ACCESS_KEY_ID -e RCLONE_CONFIG_DST_SECRET_ACCESS_KEY \
    "$@"
}

# Every step is chained with && so a failure stops the copy and is reported
# (set -e does not apply inside a function called as `f || ...`).
offsite_copy() {
  local bucket
  bucket=$(envval BACKUP_S3_BUCKET || true)
  BACKUP_ENCRYPTION_PASSPHRASE=$(envval BACKUP_ENCRYPTION_PASSPHRASE || true)
  RCLONE_CONFIG_DST_ENDPOINT=$REMOTE_ENDPOINT
  RCLONE_CONFIG_DST_REGION=$(envval BACKUP_S3_REGION || true)
  RCLONE_CONFIG_DST_ACCESS_KEY_ID=$(envval BACKUP_S3_ACCESS_KEY_ID || true)
  RCLONE_CONFIG_DST_SECRET_ACCESS_KEY=$(envval BACKUP_S3_SECRET_ACCESS_KEY || true)
  export BACKUP_ENCRYPTION_PASSPHRASE RCLONE_CONFIG_DST_ENDPOINT RCLONE_CONFIG_DST_REGION \
    RCLONE_CONFIG_DST_ACCESS_KEY_ID RCLONE_CONFIG_DST_SECRET_ACCESS_KEY

  if [ -z "$bucket" ] || [ -z "$RCLONE_CONFIG_DST_ACCESS_KEY_ID" ] \
    || [ -z "$RCLONE_CONFIG_DST_SECRET_ACCESS_KEY" ]; then
    echo "[backup] off-site: BACKUP_S3_BUCKET / BACKUP_S3_ACCESS_KEY_ID / BACKUP_S3_SECRET_ACCESS_KEY missing" >&2
    return 1
  fi
  # Contract data never leaves this server unencrypted.
  if [ "${#BACKUP_ENCRYPTION_PASSPHRASE}" -lt 20 ]; then
    echo "[backup] off-site: BACKUP_ENCRYPTION_PASSPHRASE must be at least 20 characters" >&2
    return 1
  fi

  rm -rf "$staging" && mkdir -p "$staging" \
    && tar -C "$DEST" -cf - "$stamp" \
      | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
      | split -b "$PART_SIZE" -d -a 4 - "$staging/backup.tar.enc.part-" \
    && (cd "$staging" && sha256sum backup.tar.enc.part-* > SHA256SUMS) \
    && rclone_remote -v "$staging:/upload:ro" "$RCLONE_IMAGE" \
      copy /upload "dst:$bucket/$stamp" --s3-no-check-bucket --quiet \
    && rclone_remote "$RCLONE_IMAGE" \
      delete "dst:$bucket" --min-age "${REMOTE_KEEP_DAYS}d" --quiet \
    && echo "[backup] off-site: $bucket/$stamp $(du -sh "$staging" | cut -f1) in $(find "$staging" -name 'backup.tar.enc.part-*' | wc -l) part(s)"
}

status=0
if [ -n "$REMOTE_ENDPOINT" ]; then
  offsite_copy || { status=1; echo "[backup] off-site copy FAILED; the local backup $DEST/$stamp is intact" >&2; }
  rm -rf "$staging"
fi

find "$DEST" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} +
exit "$status"
