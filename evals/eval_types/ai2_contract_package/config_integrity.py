"""
Config integrity check for ai2_contract_package — verifies the strategy card's canonical
JSON still matches its sha256 sidecar before any eval turn is allowed to score.

CONTRACT: stdlib only; path resolution is runtime, off __file__. The domain
card and its SHA-256 sidecar live under the evals/cards directory.

Card bytes are hashed after CRLF-to-LF normalization for cross-platform stability.

Honesty: this catches drift, not fraud; editing both files together still passes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ConfigDriftError(Exception):
    """The stamped card's hash no longer matches its sidecar, or the card was
    never written — the caller must stop scoring and re-run bootstrap."""


def _default_evals_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _domain_card_paths(root: Path):
    return (
        root / "cards" / "ai2_contract_package.json",
        root / "cards" / "ai2_contract_package.sha256",
    )


def load_verified_config(evals_root=None) -> dict:
    """Re-hash the domain card against its sidecar and return the parsed card.

    Raises ConfigDriftError on any of three distinct states: the card was
    never written, the sha256 sidecar is missing, or the hash no longer
    matches (card edited without re-approval).
    """
    root = Path(evals_root) if evals_root is not None else _default_evals_root()
    json_path, sha_path = _domain_card_paths(root)

    if not json_path.is_file():
        raise ConfigDriftError("ai2_contract_package.json missing — no domain card is installed")
    if not sha_path.is_file():
        raise ConfigDriftError("ai2_contract_package.sha256 missing — card has no SHA-256 sidecar")

    body = json_path.read_bytes().replace(b"\r\n", b"\n")
    expected = sha_path.read_text(encoding="utf-8").strip()
    actual = hashlib.sha256(body).hexdigest()
    if expected != actual:
        raise ConfigDriftError(
            f"ai2_contract_package.json hash mismatch (expected={expected} actual={actual}) — "
            "card was edited without re-approval")

    return json.loads(body.decode("utf-8"))


def verified_dimensions(evals_root=None) -> dict:
    """Convenience: dims from the verified card (single source of truth)."""
    return load_verified_config(evals_root)["dimensions"]


def verified_threshold(evals_root=None) -> int:
    """Convenience: threshold from the verified card (single source of truth)."""
    return load_verified_config(evals_root)["threshold"]
