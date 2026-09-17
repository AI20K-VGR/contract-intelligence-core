param([ValidateSet('core','ops')][string]$Profile = 'core')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$composeFile = Join-Path $repoRoot 'infra/compose/compose.yaml'
$envFile = Join-Path $repoRoot 'infra/compose/.env'
if (-not (Test-Path -LiteralPath $envFile)) {
  throw 'Create infra/compose/.env from .env.example, set tokens/password and an approved absolute CI_DATA_DIR.'
}
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop (Linux containers) first.' }
$composeArgs = @('compose', '--env-file', $envFile, '-f', $composeFile)
if ($Profile -eq 'ops') { $composeArgs += @('--profile', 'ops') }
& docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid.' }
& docker @composeArgs up --build -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Inspect docker compose logs.' }
Write-Host 'Web: http://localhost:8080 | API: http://localhost:8000/docs'
