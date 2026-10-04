[CmdletBinding()]
param(
  [string]$EnvFile = '.env.e2e',
  [string]$PdfPath = ''
)

$ErrorActionPreference = 'Stop'
$compose = @('-f', 'docker-compose.yml', '--env-file', $EnvFile)

if (-not (Test-Path -LiteralPath $EnvFile)) {
  throw "Missing $EnvFile. Copy .env.e2e.example to .env.e2e and fill provider keys without committing it."
}

$values = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$' -and $Matches[1] -notmatch '^#') {
    $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
  }
}
$required = @('AI2_LLM_API_KEY', 'AI2_EMBEDDING_API_KEY')
if ($PdfPath) { $required += 'MISTRAL_API_KEY' }
$missing = @($required | Where-Object { -not $values.ContainsKey($_) -or [string]::IsNullOrWhiteSpace($values[$_]) })
if ($missing.Count -gt 0) {
  throw "Full LLM/vector preflight refused: required provider values are empty ($($missing -join ', ')). Values are never printed."
}
foreach ($flag in @('AI2_SEMANTIC_ENABLED','AI2_PROCESSING_EGRESS_ALLOWED','AI2_QUERY_EGRESS_ALLOWED','AI2_QUERY_USE_LLM','AI2_QUERY_USE_VECTOR','AI2_VECTOR_RECALL_ENABLED')) {
  $flagValue = if ($values.ContainsKey($flag)) { [string]$values[$flag] } else { '' }
  if ($flagValue.ToLowerInvariant() -notin @('1','true','yes','on')) { throw "Full AI2 preflight refused: $flag must be true." }
}

docker compose @compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose config validation failed.' }
docker compose @compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Compose startup failed.' }

$deadline = (Get-Date).AddMinutes(5)
$ready = $false
while ((Get-Date) -lt $deadline) {
  try {
    $front = Invoke-RestMethod -Uri 'http://localhost:5173/healthz' -TimeoutSec 3
    $back = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 3
    docker compose @compose exec -T ai2-service python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/readyz', timeout=5)" | Out-Null
    if ($front.status -eq 'ok' -and $back.status -eq 'ok' -and $LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 5
  } catch { Start-Sleep -Seconds 5 }
}
if (-not $ready) {
  docker compose @compose ps
  throw 'Frontend/backend health did not become ready. AI2 is internal-only; inspect it with docker compose exec ai2-service.'
}

Write-Host 'E2E stack is ready.'
Write-Host 'UI:      http://localhost:5173'
Write-Host 'Backend: http://localhost:8000/health'
Write-Host 'AI2:     internal-only; run docker compose -f docker-compose.yml --env-file .env.e2e exec ai2-service python -c "import urllib.request; print(urllib.request.urlopen(''http://localhost:8002/health'', timeout=5).read().decode())"'
Write-Host 'Status:  docker compose -f docker-compose.yml --env-file .env.e2e ps'
Write-Host 'Logs:    docker compose -f docker-compose.yml --env-file .env.e2e logs -f frontend backend backend-worker ai1-worker ai2-service'
if ($PdfPath) { Write-Host "PDF supplied for manual browser upload: $PdfPath" }
