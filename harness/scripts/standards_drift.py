#!/usr/bin/env python3
"""
standards_drift — deterministic "code moved but the auto-loaded prose standards
didn't" detector.

SCRIPT-only, pure judgment. `hs:plan` / `hs:cook` READ two prose standards into
context before working: docs/system-architecture.md + docs/code-standards.md (plus
the full reference docs/system-architecture/). When a session edits
architecture/standards-bearing CODE under harness/ but touches none of those docs,
the context those skills load risks drifting from reality — a high-signal, cheap
thing to flag.

This is the event-triggered twin of decision_capture: it has a concrete trigger
(the session's edited paths), so it judges on what THIS session wrote rather than
the whole working tree. No git read, no LLM judgment — the pure `assess` is the
whole detector and is unit-tested without a repo. ALWAYS degrades to None on empty
or non-arch input (advisory is not an error).

Signal (or None):
    {"type": "standards_drift", "subjects": [<paths>], "total": <int>}

CLI (debug):
    standards_drift.py path [path ...]   # emit {"signal": {...}|null}, exit 0
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SIGNAL_TYPE = "standards_drift"

# Module-constant FALLBACK trees — used only when neither the env override nor the
# shipped standards.yaml carries a drift: section. Kept as this repo's dogfood set
# so a broken-config run still watches something sane here; the SHIPPED default that
# consumers see lives in harness/data/standards.yaml and is generic (anti-leak).
# Matched as a path-substring so absolute and repo-relative paths both resolve.
_ARCH_CODE_TREES = (
    "harness/hooks/",
    "harness/scripts/",
    "harness/plugins/",
    "harness/data/",
    "harness/schemas/",
)

# The prose standards hs:plan / hs:cook auto-read, plus the full reference. Touching
# ANY of these means the author kept the docs in sync this session → no nudge.
_CONTEXT_DOCS = (
    "docs/system-architecture.md",
    "docs/system-architecture/",
    "docs/code-standards.md",
)

# Env seam pointing at a .harness-dev/standards.yaml-shaped file whose drift: section
# overrides the shipped default (consistent with HARNESS_GUARD_POLICY / _STAGE_POLICY).
_CONFIG_ENV = "HARNESS_STANDARDS_CONFIG"

# Generated/byte artifacts under an arch tree are not authored architecture.
_SKIP = ("__pycache__/", ".pyc")

_MAX_SUBJECTS = 8


def _repo_root(root=None) -> Path:
    """Resolve off an explicit root, else $HARNESS_ROOT, else this file's location
    (harness/scripts/x.py → repo root) — never CWD (hooks run from .claude/)."""
    if root is not None:
        return Path(root)
    env = os.environ.get("HARNESS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


def _read_drift_section(root=None) -> Optional[dict]:
    """The drift: mapping from the highest-precedence readable source, or None.
    Precedence: $HARNESS_STANDARDS_CONFIG file → shipped harness/data/standards.yaml.
    Fail-open (this feeds a nudge, which must never raise): any unreadable/malformed
    source is skipped, a source without a drift: mapping falls through."""
    candidates: List[Path] = []
    env_cfg = os.environ.get(_CONFIG_ENV)
    if env_cfg:
        candidates.append(Path(env_cfg))
    candidates.append(_repo_root(root) / "harness" / "data" / "standards.yaml")
    for path in candidates:
        try:
            import yaml_io
            data = yaml_io.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — missing/malformed source → next candidate
            continue
        if isinstance(data, dict) and isinstance(data.get("drift"), dict):
            return data["drift"]
    return None


def _load_config(root=None) -> Tuple[tuple, tuple]:
    """Resolve (watch_trees, context_docs) via the precedence chain, each falling
    back to the module constants when its key is absent/empty. Fail-open."""
    drift = _read_drift_section(root)
    trees, docs = _ARCH_CODE_TREES, _CONTEXT_DOCS
    if drift:
        wt = drift.get("watch_trees")
        cd = drift.get("context_docs")
        if isinstance(wt, list) and wt:
            trees = tuple(wt)
        if isinstance(cd, list) and cd:
            docs = tuple(cd)
    return trees, docs


def _norm(path: str) -> str:
    norm = path.replace("\\", "/")
    return norm[2:] if norm.startswith("./") else norm


def _arch_subject(norm: str, trees) -> Optional[str]:
    """The arch-relative subject for an architecture/standards code path, or None.
    Trims an absolute path down to its `<tree>/...` tail for a stable, readable
    subject; drops generated/byte artifacts."""
    for tree in trees:
        idx = norm.find(tree)
        if idx != -1:
            subject = norm[idx:]
            if any(skip in subject for skip in _SKIP):
                return None
            return subject
    return None


def _is_context_doc(norm: str, context_docs) -> bool:
    """True when `norm` IS a listed context doc, or lives inside a listed dir.

    An entry ending in "/" names a directory (the architecture reference is a
    tree of chapters, not one file); matching it by `endswith` alone could
    never fire, since no file path ends in a slash. The `/` is what keeps the
    directory arm from becoming a prefix match -- `docs/system-architecture-
    notes.md` shares the entry's characters but is a sibling, not a child."""
    for doc in context_docs:
        if doc.endswith("/"):
            if norm.startswith(doc) or ("/" + doc) in norm:
                return True
        elif norm.endswith(doc):
            return True
    return False


def assess(paths: List[str], *, trees=None, context_docs=None) -> Optional[Dict]:
    """Pure judgment: signal when code under a watched tree was edited this session
    without any context doc being touched. Subjects sorted + de-duped + capped.
    `trees`/`context_docs` inject the watched sets (tests); when either is None it is
    resolved via _load_config (env override → shipped standards.yaml → constants)."""
    if trees is None or context_docs is None:
        cfg_trees, cfg_docs = _load_config()
        if trees is None:
            trees = cfg_trees
        if context_docs is None:
            context_docs = cfg_docs
    norms = [_norm(p) for p in paths if p]
    docs_synced = any(_is_context_doc(n, context_docs) for n in norms)
    subjects = sorted({s for n in norms for s in (_arch_subject(n, trees),) if s})
    if subjects and not docs_synced:
        return {"type": SIGNAL_TYPE,
                "subjects": subjects[:_MAX_SUBJECTS],
                "total": len(subjects)}
    return None


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    sys.stdout.write(json.dumps({"signal": assess(argv)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
