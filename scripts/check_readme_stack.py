#!/usr/bin/env python3
"""README stack-claim guard (Phase 2).

Verifies that the repo-root `README.md` no longer describes the stack as
Java or Celery. The backend is Python FastAPI with a Kafka worker
(`python -m contract_intelligence.worker`). ai-service uses aiokafka, not
Celery. The structure section, role table, and quick start must not contain
`./mvnw`, `Java Spring Boot`, `Java 17`, or `Celery`.

Cross-platform (Windows/Linux/macOS); requires only stdlib. Does not call
`git` and does not import any application package.

Exit code: 0 = README stack claims are clean. Non-zero = stale Java/mvnw
claims still present (or README.md could not be found/read).
"""

from __future__ import annotations

import sys
from pathlib import Path

STALE_TOKENS = ["./mvnw", "Java Spring Boot", "Java 17", "Celery"]


def find_repo_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a directory containing `.git`."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def main() -> int:
    script_path = Path(__file__)
    repo_root = find_repo_root(script_path.parent) or script_path.resolve().parents[1]

    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        print(f"FAIL: README.md not found at {readme_path}")
        return 1

    text = readme_path.read_text(encoding="utf-8")

    hits = [token for token in STALE_TOKENS if token in text]
    if hits:
        print("FAIL: README.md still contains stale Java/mvnw/Celery stack claims:")
        for token in hits:
            print(f"  - found token: {token!r}")
        print(f"  README path: {readme_path}")
        return 1

    print("PASS: README.md stack claims are clean (no ./mvnw, Java, or Celery).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
