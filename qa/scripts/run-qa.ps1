# Run the QA suites against a running stack and build qa/reports/SUMMARY.md.
#
#   .\qa\scripts\run-qa.ps1                  # smoke + security + performance
#   .\qa\scripts\run-qa.ps1 -Suites smoke    # one suite
#   .\qa\scripts\run-qa.ps1 -Pipeline        # also the full upload pipeline (free mode first!)
param(
    [string[]]$Suites = @("smoke", "security", "performance"),
    [switch]$Pipeline
)

$ErrorActionPreference = "Continue"
$qa = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $qa
try {
    $env:PYTHONIOENCODING = "utf-8"
    Remove-Item -Recurse -Force reports -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force reports | Out-Null
    if ($Pipeline) { $env:QA_RUN_PIPELINE = "1"; $Suites += "e2e" }

    $failed = 0
    foreach ($suite in $Suites) {
        Write-Host "`n=== $suite ===" -ForegroundColor Cyan
        uv run --quiet --with-requirements requirements.txt pytest $suite -p no:warnings `
            --junitxml "reports/junit-$suite.xml"
        if ($LASTEXITCODE -ne 0) { $failed++ }
    }
    uv run --quiet --with-requirements requirements.txt python scripts/summarize.py
    Write-Host "`nReport: $qa\reports\SUMMARY.md"
    exit $failed
} finally {
    Pop-Location
}
