@echo off
rem hs-run — deterministic step-sequence CLI over the harness's plan/cook scripts
rem (Windows launcher). Resolves the harness root from this script's own
rem directory and delegates every domain/verb to harness\scripts\hs_run.py.
rem POSIX twin: hs-run (sh).
rem enabledelayedexpansion so !errorlevel! is read AFTER python runs, not at
rem parse-time — otherwise every verb (e.g. `hs-run plan next`) would exit 0
rem regardless of the child's real exit code.
setlocal enabledelayedexpansion
set "bin_dir=%~dp0"
set "run=%bin_dir%..\scripts\hs_run.py"
if not exist "%run%" (
    echo hs-run: cannot find "%run%" — is the harness installed?>&2
    exit /b 1
)
where python >nul 2>nul && (
    python "%run%" %*
    exit /b !errorlevel!
)
where py >nul 2>nul && (
    py "%run%" %*
    exit /b !errorlevel!
)
echo hs-run: python not found — install Python 3 to run the harness CLI.>&2
exit /b 1
