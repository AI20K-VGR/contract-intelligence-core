#!/usr/bin/env bash
# Run the QA suites against a running stack and build qa/reports/SUMMARY.md.
#
#   ./qa/scripts/run-qa.sh                    # smoke + security + performance
#   ./qa/scripts/run-qa.sh smoke security     # chosen suites
#   QA_RUN_PIPELINE=1 ./qa/scripts/run-qa.sh smoke e2e   # full pipeline (free mode first!)
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8

suites=("$@")
[[ ${#suites[@]} -eq 0 ]] && suites=(smoke security performance)
rm -rf reports && mkdir -p reports

failed=0
for suite in "${suites[@]}"; do
  echo -e "\n=== $suite ==="
  uv run --quiet --with-requirements requirements.txt pytest "$suite" -p no:warnings \
    --junitxml "reports/junit-$suite.xml" || failed=$((failed + 1))
done
uv run --quiet --with-requirements requirements.txt python scripts/summarize.py
echo "Report: qa/reports/SUMMARY.md"
exit "$failed"
