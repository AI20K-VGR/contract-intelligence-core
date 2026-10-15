from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
COMMITTED_DATA = REPO_ROOT / "evals" / "contract_graph" / "data"

for _path in (REPO_ROOT, REPO_ROOT / "ai-service"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network access is blocked in contract_graph tests")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def seed_cache(cache_dir: Path, url: str, fixture_name: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        FIXTURES / fixture_name, cache_dir / hashlib.sha256(url.encode("utf-8")).hexdigest()
    )


MINI_SOURCES = [
    {
        "pair_id": "mini",
        "issuer": "Chính phủ",
        "amending_doc": "20/2021/NĐ-CP",
        "vbhn_doc": "05/VBHN-BXD",
        "amending_url": "https://example.test/mini_amending.html",
        "vbhn_url": "https://example.test/mini_vbhn.html",
    },
    {
        "pair_id": "mini-suffix",
        "issuer": "Bộ Xây dựng",
        "amending_doc": "30/2022/NĐ-CP",
        "vbhn_doc": "07/VBHN-BXD",
        "amending_url": "https://example.test/mini_suffix_amending.html",
        "vbhn_url": "https://example.test/mini_suffix_vbhn.html",
    },
]


@pytest.fixture
def mini_dataset(tmp_path: Path) -> Path:
    """Freeze the mini fixture pairs (offline, from a seeded cache) into tmp_path/data."""

    from evals.contract_graph.dataset import build_pair, freeze

    cache = tmp_path / "cache"
    for source in MINI_SOURCES:
        for key in ("amending_url", "vbhn_url"):
            seed_cache(cache, source[key], source[key].rsplit("/", 1)[1])
    pairs = [build_pair(source, cache, offline=True) for source in MINI_SOURCES[:1]]
    out = tmp_path / "data"
    freeze(pairs, out)
    return out
