#!/usr/bin/env python3
"""Repo hygiene guard (Phase 1).

Verifies that vendored/build/output artifacts are not tracked by git and
that `.gitignore` blocks them (and nested caches) without over-blocking
real source paths. Cross-platform (Windows/Linux/macOS); requires only the
`git` binary. If git is missing, or the current directory is not inside a
git work tree, this script prints a one-line skip reason and exits 0 so it
never fails CI images / checkouts that have no `.git`.

Exit code: 0 = all assertions passed (or skipped). Non-zero = failure.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a directory containing `.git`."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def main() -> int:
    script_path = Path(__file__)
    repo_root = find_repo_root(script_path.parent)

    if shutil.which("git") is None:
        print("SKIP: git binary not found on PATH; skipping repo hygiene check.")
        return 0

    if repo_root is None:
        print("SKIP: no .git directory found above script location; skipping repo hygiene check.")
        return 0

    check = run_git(repo_root, "rev-parse", "--is-inside-work-tree")
    if check.returncode != 0 or check.stdout.strip() != "true":
        print("SKIP: not inside a git work tree; skipping repo hygiene check.")
        return 0

    failures: list[str] = []

    # --- 1. Untracked artifact groups must be empty in `git ls-files`. ---
    untracked_paths = [
        "apps/web/node_modules",
        "apps/web/.vite",
        "output",
        "ocr-result.json",
        "result_khoiluong.json",
    ]
    for rel_path in untracked_paths:
        result = run_git(repo_root, "ls-files", rel_path)
        if result.returncode != 0:
            failures.append(f"`git ls-files {rel_path}` errored: {result.stderr.strip()}")
            continue
        tracked = [line for line in result.stdout.splitlines() if line.strip()]
        if tracked:
            failures.append(
                f"expected `git ls-files {rel_path}` to be empty, "
                f"found {len(tracked)} tracked file(s): {tracked[:5]}"
            )

    # --- 2. These patterns must be ignored (`git check-ignore -q` exit 0). ---
    must_be_ignored = [
        "node_modules/x",
        "output/foo",
        "ocr-result.json",
        "result_khoiluong.json",
        ".pytest-review-r2-ai2/x",
        ".uv-cache-x/y",
        "backend/backend/x",
    ]
    for rel_path in must_be_ignored:
        result = run_git(repo_root, "check-ignore", "-q", rel_path)
        if result.returncode != 0:
            failures.append(
                f"expected `git check-ignore -q {rel_path}` to succeed (ignored), "
                f"got exit code {result.returncode}"
            )

    # --- 3. Real source paths must NOT be ignored (negative check). ---
    candidate_source_paths = ["frontend/src/App.tsx", "frontend/src/data"]
    existing_source_paths = [
        rel for rel in candidate_source_paths if (repo_root / rel).exists()
    ]
    if not existing_source_paths:
        failures.append(
            "none of the candidate source paths exist on disk to run the "
            f"negative check: {candidate_source_paths}"
        )
    for rel_path in existing_source_paths:
        result = run_git(repo_root, "check-ignore", "-q", rel_path)
        if result.returncode == 0:
            failures.append(
                f"expected `git check-ignore -q {rel_path}` to FAIL (not ignored), "
                "but it was reported as ignored"
            )

    # --- 4. Untracked-but-still-on-disk paths must still exist. ---
    must_exist_on_disk = [
        "apps/web/node_modules",
        "apps/web/.vite",
        "output",
        "ocr-result.json",
        "result_khoiluong.json",
    ]
    for rel_path in must_exist_on_disk:
        full_path = repo_root / rel_path
        if not full_path.exists():
            failures.append(
                f"expected {rel_path} to still exist on disk (untrack must not delete "
                "working tree files), but it is missing"
            )

    if failures:
        print("FAIL: repo hygiene check failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("PASS: repo hygiene check passed (ls-files clean, check-ignore correct, files intact).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
