#!/usr/bin/env python3
"""Measure the per-turn context floor: the byte/token weight of the blocks the
harness wraps around a session.

Blocks:
  first_turn     — the diet armed first-turn injection (inject_prompt_context.build_context)
  full_legacy    — the rollback heavy block (build_full_context, mode=full)
  voice_register — the SessionStart register (register_block.build_register)
  claude_md      — the static CLAUDE.md file
  memory_index   — the MEMORY.md index file (outside the repo; pass --memory-index)

bytes/4 ≈ tokens. Acceptance tool for the context diet — re-runs after any change.
Blocks needing live config (voice) fail-soft to 0.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "hooks"))

from token_estimate import est_tokens  # noqa: E402  (needs the path above)


def _voice_payload() -> bytes:
    try:
        import output_config
        import register_block
        return register_block.build_register(output_config.resolve_all()).encode("utf-8")
    except Exception:  # noqa: BLE001 - live config optional; degrade to 0
        return b""


def _file_payload(path) -> bytes:
    """Read a block's bytes, or empty when it is absent or not a regular file."""
    if path is None or not path.is_file():
        return b""
    try:
        return path.read_bytes()
    except OSError:
        return b""


def measure(root, memory_index=None) -> dict:
    import inject_prompt_context as ipc
    root = pathlib.Path(root)
    # Keep the bytes, not just their length: the token estimate is corrected by
    # the share of non-ASCII bytes, and a size alone cannot say what that is.
    payloads = {
        "first_turn": ipc.build_context(root).encode("utf-8"),
        "full_legacy": ipc.build_full_context(root).encode("utf-8"),
        "voice_register": _voice_payload(),
        "claude_md": _file_payload(root / "CLAUDE.md"),
        "memory_index": _file_payload(
            pathlib.Path(memory_index) if memory_index else None),
    }
    blocks = {k: len(v) for k, v in payloads.items()}
    total = sum(blocks.values())
    return {
        "root": str(root),
        "blocks": blocks,
        "total_bytes": total,
        "est_tokens": sum(est_tokens(v) for v in payloads.values()),
        "est_tokens_by_block": {k: est_tokens(v) for k, v in payloads.items()},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure the per-turn context floor")
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--memory-index", default=None,
                    help="path to MEMORY.md (outside the repo)")
    a = ap.parse_args(argv)
    print(json.dumps(measure(a.root, a.memory_index), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
