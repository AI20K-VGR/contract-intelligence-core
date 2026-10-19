# Switch the local compose stack between free mode (no paid OCR/LLM) and the
# normal paid mode, by recreating only backend-worker and ai2-service.
#
#   .\qa\scripts\stack-mode.ps1 free   # AI1_OCR_ENGINE=pymupdf, AI2 egress off
#   .\qa\scripts\stack-mode.ps1 paid   # back to docker-compose.yml defaults
#
# Uses the images already built (--no-build) and touches no volume.
param([Parameter(Mandatory = $true)][ValidateSet("free", "paid")][string]$Mode)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $root
try {
    $flags = "AI2_PROCESSING_EGRESS_ALLOWED", "AI2_QUERY_EGRESS_ALLOWED", "AI2_QUERY_USE_LLM", `
        "AI2_QUERY_USE_VECTOR", "AI2_VECTOR_RECALL_ENABLED"
    if ($Mode -eq "free") {
        $env:AI1_OCR_ENGINE = "pymupdf"
        foreach ($f in $flags) { Set-Item -Path "env:$f" -Value "false" }
    } else {
        Remove-Item env:AI1_OCR_ENGINE -ErrorAction SilentlyContinue
        foreach ($f in $flags) { Remove-Item "env:$f" -ErrorAction SilentlyContinue }
    }
    docker compose up -d --no-deps --no-build --force-recreate backend-worker ai2-service
    Write-Host "Stack mode: $Mode"
    docker exec ci-backend-worker printenv AI1_OCR_ENGINE
    docker exec ci-ai2-service printenv AI2_PROCESSING_EGRESS_ALLOWED
} finally {
    Pop-Location
}
