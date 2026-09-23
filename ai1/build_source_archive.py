"""Refresh the compact AI1 source archive without local secrets or caches."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "ai-service"
DESTINATION = ROOT / "ai1" / "ai-service-source.zip"
DIRECTORIES = ("src", "scripts", "tests", "configs", "docs")
FILES = ("pyproject.toml", "uv.lock", "README.md", ".env.example")
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def main() -> None:
    paths = [SERVICE / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(path for path in (SERVICE / directory).rglob("*") if path.is_file())
    with ZipFile(DESTINATION, "w", ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES or path.name == ".env":
                continue
            archive.write(path, path.relative_to(SERVICE))
    print(DESTINATION)


if __name__ == "__main__":
    main()
