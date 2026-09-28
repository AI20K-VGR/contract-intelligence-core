"""Run Alembic migrations to head (sync CLI wrapper for local / CI)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    backend_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_root,
        check=False,
    )
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
