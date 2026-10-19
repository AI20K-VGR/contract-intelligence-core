#!/usr/bin/env bash
# Software Composition Analysis: scan Python deps, npm deps and container images
# for known vulnerabilities. Writes JSON + a short summary to qa/reports/sca/.
#
#   ./qa/scripts/sca-scan.sh            # whatever tools are installed
#   ./qa/scripts/sca-scan.sh --images   # also scan built docker images with trivy
#
# Tools are optional: each step is skipped (not failed) when its tool is absent,
# so the script runs anywhere and reports what it could cover.
set -uo pipefail
cd "$(dirname "$0")/../.."
OUT="qa/reports/sca"
mkdir -p "$OUT"
summary="$OUT/SUMMARY.txt"
: > "$summary"
note() { echo "$*" | tee -a "$summary"; }

note "SCA scan — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
note ""

# --- Python (backend + ai-service) via pip-audit --------------------------------
if command -v uv >/dev/null 2>&1; then
  for proj in backend ai-service; do
    if [[ -f "$proj/pyproject.toml" ]]; then
      note "## pip-audit: $proj"
      uv run --quiet --with pip-audit pip-audit -f json -o "$OUT/pip-audit-$proj.json" \
        $( [[ -f "$proj/uv.lock" ]] && echo "" ) 2> "$OUT/pip-audit-$proj.log" \
        && note "  wrote $OUT/pip-audit-$proj.json" \
        || note "  pip-audit reported findings or errored (see $OUT/pip-audit-$proj.log)"
    fi
  done
else
  note "## pip-audit: skipped (uv not on PATH)"
fi
note ""

# --- Frontend via npm audit -----------------------------------------------------
if command -v npm >/dev/null 2>&1 && [[ -f frontend/package-lock.json ]]; then
  note "## npm audit: frontend"
  ( cd frontend && npm audit --json > "../$OUT/npm-audit-frontend.json" 2> "../$OUT/npm-audit-frontend.log" )
  node -e "try{const a=require('./$OUT/npm-audit-frontend.json').metadata.vulnerabilities;console.log('  vulnerabilities:',JSON.stringify(a))}catch(e){console.log('  (could not parse npm audit json)')}" | tee -a "$summary"
else
  note "## npm audit: skipped (npm or lockfile missing)"
fi
note ""

# --- Container images via trivy -------------------------------------------------
if [[ "${1:-}" == "--images" ]]; then
  if command -v trivy >/dev/null 2>&1; then
    for img in contract-intelligence-stack-backend contract-intelligence-stack-backend-worker \
               contract-intelligence-stack-ai1-worker contract-intelligence-stack-ai2-service; do
      if docker image inspect "$img" >/dev/null 2>&1; then
        note "## trivy: $img"
        trivy image --quiet --severity HIGH,CRITICAL -f json -o "$OUT/trivy-${img##*-}.json" "$img" \
          && note "  wrote $OUT/trivy-${img##*-}.json" || note "  trivy errored for $img"
      fi
    done
  else
    note "## trivy: skipped (not installed — https://aquasecurity.github.io/trivy)"
  fi
fi

note ""
note "Done. JSON reports in $OUT/."
