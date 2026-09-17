"""Architecture test — verify Dependency Rule bằng import-linter.

Chạy trong CI để đảm bảo không ai vi phạm layer boundary.

Run: pytest tests/architecture/test_layer_conformance.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


class TestLayerConformance:
    """Chạy import-linter trên toàn bộ src/."""

    @pytest.fixture(scope="class")
    def backend_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    def test_import_linter_passes(self, backend_root: Path) -> None:
        """import-linter phải pass — fail nếu vi phạm Dependency Rule."""
        result = subprocess.run(
            ["python", "-m", "import_linter", "--config", ".importlinter"],
            cwd=str(backend_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(
                f"import-linter FAILED — Dependency Rule vi phạm:\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}",
            )
        assert result.returncode == 0, result.stderr

    def test_ruff_passes(self, backend_root: Path) -> None:
        """ruff check phải pass."""
        result = subprocess.run(
            ["python", "-m", "ruff", "check", "src/"],
            cwd=str(backend_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(f"ruff FAILED:\n{result.stdout}\n{result.stderr}")
        assert result.returncode == 0

    def test_no_fastapi_in_domain_layer(self, backend_root: Path) -> None:
        """Domain entities không được import FastAPI."""
        domain_paths = list((backend_root / "src" / "contract_intelligence").rglob("*/domain/**/*.py"))
        content = ""
        for path in domain_paths:
            content += path.read_text(encoding="utf-8") + "\n"
        assert "from fastapi" not in content, "domain layer không được import FastAPI"
        assert "import fastapi" not in content

    def test_no_sqlalchemy_in_domain_layer(self, backend_root: Path) -> None:
        """Domain entities không được import SQLAlchemy ORM."""
        domain_paths = list((backend_root / "src" / "contract_intelligence").rglob("*/domain/**/*.py"))
        content = ""
        for path in domain_paths:
            content += path.read_text(encoding="utf-8") + "\n"
        assert "from sqlalchemy" not in content, "domain layer không được import SQLAlchemy"
