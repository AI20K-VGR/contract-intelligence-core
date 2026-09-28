#!/usr/bin/env python3
"""detect_techstack — read-only tech-stack profile of a target repo.

The harness installs INTO other repos (`sh install.sh <tarball> <repo>`) but its
verification skills default to pytest. This detector lets a skill adapt to the
target's actual stack: it scans a repo root for build/dependency markers and
returns {languages, test command, package manager, CI} — observing the repo,
never mutating it. The read-only Shape-A self-learning surface consumed by
hs:setup / hs:test / hs:insights.

Detection is presence-based (a marker file's existence) and fail-soft: a missing
or unreadable root yields an empty profile rather than raising — a detector that
crashes the host is worse than one that finds nothing. The package manager is
read from the lockfile/marker, not guessed; the test command is the conventional
one for the stack (and for Node, only when a `scripts.test` is actually declared).

CLI:
    detect_techstack.py [--root <dir>]   # prints the JSON profile, exit 0
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _read(path: Path) -> str:
    """Best-effort text read; unreadable → empty (fail-soft, never raises)."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _python_stack(root: Path) -> Optional[Dict[str, Any]]:
    marker = next((m for m in ("pyproject.toml", "setup.py", "setup.cfg",
                               "requirements.txt", "Pipfile")
                   if (root / m).is_file()), None)
    if not marker:
        return None
    # pkg-mgr from a real [tool.poetry] TABLE header (line-anchored), never a
    # commented-out or prose mention — the docstring promises the marker is read, not
    # guessed, so a migration-note comment must not override an actual uv.lock below.
    _pyproject = _read(root / "pyproject.toml") if (root / "pyproject.toml").is_file() else ""
    _has_poetry = any(s == "[tool.poetry]" or s.startswith("[tool.poetry.")
                      for s in (ln.strip() for ln in _pyproject.splitlines()))
    pkg_mgr = "pip"
    if _has_poetry:
        pkg_mgr = "poetry"
    elif (root / "uv.lock").is_file():
        pkg_mgr = "uv"
    elif (root / "Pipfile").is_file():
        pkg_mgr = "pipenv"
    return {"language": "python", "marker": marker, "test_cmd": "pytest", "pkg_mgr": pkg_mgr}


def _node_stack(root: Path) -> Optional[Dict[str, Any]]:
    if not (root / "package.json").is_file():
        return None
    language = "typescript" if (root / "tsconfig.json").is_file() else "javascript"
    if (root / "pnpm-lock.yaml").is_file():
        pkg_mgr = "pnpm"
    elif (root / "yarn.lock").is_file():
        pkg_mgr = "yarn"
    elif (root / "bun.lockb").is_file():
        pkg_mgr = "bun"
    else:
        pkg_mgr = "npm"
    # test_cmd only when a test script is actually declared (honest: don't invent one)
    test_cmd = None
    try:
        pkg = json.loads(_read(root / "package.json"))
        if isinstance(pkg, dict) and isinstance(pkg.get("scripts"), dict) \
                and pkg["scripts"].get("test"):
            test_cmd = f"{pkg_mgr} test"
    except (ValueError, TypeError):
        pass  # malformed package.json → stack still detected, just no test_cmd
    return {"language": language, "marker": "package.json",
            "test_cmd": test_cmd, "pkg_mgr": pkg_mgr}


def _go_stack(root: Path) -> Optional[Dict[str, Any]]:
    if not (root / "go.mod").is_file():
        return None
    return {"language": "go", "marker": "go.mod",
            "test_cmd": "go test ./...", "pkg_mgr": "go"}


def _rust_stack(root: Path) -> Optional[Dict[str, Any]]:
    if not (root / "Cargo.toml").is_file():
        return None
    return {"language": "rust", "marker": "Cargo.toml",
            "test_cmd": "cargo test", "pkg_mgr": "cargo"}


def _java_stack(root: Path) -> Optional[Dict[str, Any]]:
    if (root / "pom.xml").is_file():
        return {"language": "java", "marker": "pom.xml",
                "test_cmd": "mvn test", "pkg_mgr": "maven"}
    if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        marker = "build.gradle" if (root / "build.gradle").is_file() else "build.gradle.kts"
        return {"language": "java", "marker": marker,
                "test_cmd": "gradle test", "pkg_mgr": "gradle"}
    return None


# Fixed precedence — also the order `primary` is chosen by.
_DETECTORS = (_python_stack, _node_stack, _go_stack, _rust_stack, _java_stack)


def _detect_ci(root: Path) -> List[str]:
    ci: List[str] = []
    wf = root / ".github" / "workflows"
    if wf.is_dir() and any(wf.iterdir()):
        ci.append("github-actions")
    if (root / ".gitlab-ci.yml").is_file():
        ci.append("gitlab-ci")
    if (root / ".circleci" / "config.yml").is_file():
        ci.append("circleci")
    return ci


def detect(root) -> Dict[str, Any]:
    """Return the tech-stack profile of `root`. Never raises; missing → empty."""
    root = Path(root)
    if not root.is_dir():
        return {"root": str(root), "stacks": [], "ci": [], "primary": None}
    stacks = [s for s in (d(root) for d in _DETECTORS) if s]
    ci = _detect_ci(root)
    return {"root": str(root), "stacks": stacks, "ci": ci,
            "primary": stacks[0]["language"] if stacks else None}


def main(argv=None) -> int:
    try:
        from encoding_utils import configure_utf8_console
        configure_utf8_console()
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Read-only tech-stack profile of a repo.")
    ap.add_argument("--root", default=".", help="repo root to scan (default: cwd)")
    args = ap.parse_args(argv)
    print(json.dumps(detect(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
