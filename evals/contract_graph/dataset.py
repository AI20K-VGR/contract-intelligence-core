"""Fetch (cached) amending/VBHN pages, normalize them and freeze pairs with a sha256 manifest.

Only normalized text is committed; raw HTML/DOCX stays in the git-ignored cache
``data/contract_graph_cache/`` keyed by sha256(url).

File digests are taken over LF-normalized bytes, so a checkout that rewrites line endings
(``core.autocrlf``) does not read as tampering while any content change still does.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

from evals.contract_graph.gold import EXTRACTOR_VERSION, build_gold, gold_summary
from evals.contract_graph.normalize import docx_to_text, html_to_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = REPO_ROOT / "data" / "contract_graph_cache"
DEFAULT_DATA = REPO_ROOT / "evals" / "contract_graph" / "data"
MANIFEST = "manifest.json"
PAIR_FILES = ("amending.txt", "vbhn.txt", "gold.jsonl")
SCHEMA = "contract-graph-dataset/1"
USER_AGENT = "Mozilla/5.0 (compatible; contract-graph-eval/1.0)"
FETCH_TIMEOUT_S = 90
_PAIR_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
_REQUIRED = ("pair_id", "issuer", "amending_doc", "vbhn_doc", "amending_url", "vbhn_url")


class CacheMiss(LookupError):
    """Offline run asked for a page that was never fetched."""


def cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def fetch_cached(
    url: str, cache_dir: Path, offline: bool = False, timeout: float = FETCH_TIMEOUT_S
) -> bytes:
    path = Path(cache_dir) / cache_key(url)
    if path.exists():
        return path.read_bytes()
    if offline:
        raise CacheMiss(f"{url} not cached at {path} (offline run)")
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.5"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise OSError(f"{url}: HTTP {status}")
        data = response.read()
    if not data:
        raise OSError(f"{url}: empty response")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return data


def raw_to_text(data: bytes) -> str:
    return docx_to_text(data) if data[:2] == b"PK" else html_to_text(data)


def build_pair(source: dict, cache_dir: Path, offline: bool = False) -> dict:
    """One sources.json entry → normalized texts + gold records (nothing written)."""

    missing = [key for key in _REQUIRED if not source.get(key)]
    if missing:
        raise ValueError(f"source {source.get('pair_id')!r} lacks {missing}")
    if not _PAIR_ID.fullmatch(source["pair_id"]):
        raise ValueError(f"pair_id {source['pair_id']!r} must match {_PAIR_ID.pattern}")
    raws = {
        key: fetch_cached(source[f"{key}_url"], cache_dir, offline) for key in ("amending", "vbhn")
    }
    vbhn_text = raw_to_text(raws["vbhn"])
    cached = Path(cache_dir) / cache_key(source["vbhn_url"])
    return {
        "pair_id": source["pair_id"],
        "issuer": source["issuer"],
        "amending_doc": source["amending_doc"],
        "vbhn_doc": source["vbhn_doc"],
        "amending_url": source["amending_url"],
        "vbhn_url": source["vbhn_url"],
        "operative_article": str(source.get("operative_article", "1")),
        "fetched_at": dt.datetime.fromtimestamp(cached.stat().st_mtime, dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "raw_sha256": {key: hashlib.sha256(data).hexdigest() for key, data in raws.items()},
        "amending_text": raw_to_text(raws["amending"]),
        "vbhn_text": vbhn_text,
        "gold": build_gold(source["pair_id"], vbhn_text, source["amending_doc"]),
    }


def freeze(pairs: list[dict], out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for pair in sorted(pairs, key=lambda p: p["pair_id"]):
        pair_dir = out_dir / pair["pair_id"]
        pair_dir.mkdir(exist_ok=True)
        _write(pair_dir / "amending.txt", pair["amending_text"] + "\n")
        _write(pair_dir / "vbhn.txt", pair["vbhn_text"] + "\n")
        _write(pair_dir / "gold.jsonl", "".join(_json_line(r) for r in pair["gold"]))
        meta = {k: v for k, v in pair.items() if k not in ("amending_text", "vbhn_text", "gold")}
        entries.append(
            {
                **meta,
                "files": {name: file_digest(pair_dir / name) for name in PAIR_FILES},
                "gold_by_op": gold_summary(pair["gold"]),
                "n_gold": len(pair["gold"]),
            }
        )
    manifest = {
        "schema": SCHEMA,
        "extractor_version": EXTRACTOR_VERSION,
        "ground_truth": "vbhn-note auto-gold (approved=false)",
        "digest": "sha256 of UTF-8 text with LF line endings",
        "pairs": entries,
        "total_bytes": sum(
            _size(out_dir / e["pair_id"] / name) for e in entries for name in PAIR_FILES
        ),
    }
    _write(
        out_dir / MANIFEST,
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
    )
    return manifest


def verify_manifest(data_dir: Path) -> list[str]:
    """Problems that make the frozen dataset untrustworthy; [] means every file matches."""

    data_dir = Path(data_dir)
    path = data_dir / MANIFEST
    if not path.is_file():
        return [f"{path}: manifest missing"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        entries = manifest["pairs"]
    except (ValueError, KeyError, TypeError) as exc:
        return [f"{path}: unreadable manifest ({exc})"]
    problems: list[str] = []
    listed = set()
    total = 0
    for entry in entries:
        pid = entry.get("pair_id", "?")
        listed.add(pid)
        for name, digest in sorted(entry.get("files", {}).items()):
            file = data_dir / pid / name
            if not file.is_file():
                problems.append(f"{pid}/{name}: missing")
                continue
            total += _size(file)
            if file_digest(file) != digest:
                problems.append(f"{pid}/{name}: sha256 mismatch")
        if sorted(entry.get("files", {})) != sorted(PAIR_FILES):
            problems.append(
                f"{pid}: manifest lists {sorted(entry.get('files', {}))}, expected {sorted(PAIR_FILES)}"
            )
        pair_dir = data_dir / pid
        if pair_dir.is_dir():
            extra = sorted(
                p.name for p in pair_dir.iterdir() if p.name not in entry.get("files", {})
            )
            problems.extend(f"{pid}/{name}: file not in manifest" for name in extra)
    for child in sorted(data_dir.iterdir()):
        if child.is_dir() and child.name not in listed:
            problems.append(f"{child.name}: directory not in manifest")
    if not problems and manifest.get("total_bytes") != total:
        problems.append(f"total_bytes {manifest.get('total_bytes')} != {total}")
    return problems


def load_gold(pair_dir: Path) -> list[dict]:
    text = (Path(pair_dir) / "gold.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _size(path: Path) -> int:
    return len(Path(path).read_bytes().replace(b"\r\n", b"\n"))


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _json_line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
