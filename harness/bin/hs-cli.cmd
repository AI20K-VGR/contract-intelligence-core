@echo off
rem hs-cli — operator front-end over the harness scripts (Windows launcher).
rem Resolves the harness root from this script's own directory and delegates
rem every verb to harness\scripts\hs_cli.py. POSIX twin: hs-cli (sh).
rem enabledelayedexpansion so !errorlevel! is read AFTER python runs, not at
rem parse-time — otherwise every verb (e.g. `hs doctor`) would exit 0 regardless
rem of the child's real exit code.
setlocal enabledelayedexpansion
set "bin_dir=%~dp0"
set "cli=%bin_dir%..\scripts\hs_cli.py"
if not exist "%cli%" (
    echo hs-cli: cannot find "%cli%" — is the harness installed?>&2
    exit /b 1
)
where python >nul 2>nul && (
    python "%cli%" %*
    exit /b !errorlevel!
)
where py >nul 2>nul && (
    py "%cli%" %*
    exit /b !errorlevel!
)
echo hs-cli: python not found — install Python 3 to run the harness CLI.>&2
exit /b 1
