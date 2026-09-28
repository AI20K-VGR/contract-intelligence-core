#!/usr/bin/env python3
"""dismissals_store.py — the per-repo review-dismissals store.

Single responsibility: store I/O + fingerprint for review-finding dismissals. It does
NOT decide a verdict (that is prose in the code-review skill) and it never auto-suppresses
— `lookup` exists so a later review can SHOW a prior dismissal, with the reviewer still in
the loop. The store is append-only JSONL at ``docs/review/dismissals.jsonl`` (git-visible:
``docs/`` is not gitignored, and a shipped ``docs/review/.gitkeep`` keeps the dir tracked in
a freshly cloned repo).

Record shape: ``harness/schemas/review-dismissal.json``. Every record carries
``actor``+``ts`` (attribution, not authentication) and a ``schema_version`` a consumer can
pin. The fingerprint excludes the line number — stable across a reformat — and hashes the
normalized snippet so the same rule firing twice in one file stays distinct.

Concurrency: appends are wrapped in an exclusive ``flock`` so a record larger than
``PIPE_BUF`` (the ``code_evidence`` snippet can be) written by two concurrent reviewers does
not splice. ``lookup`` skips an unparseable line (an old splice) with a warning instead of
raising. ``docs/`` has no ownership zone, so the writer does not route through
``fs_guard.assert_under`` (that helper is only for scripts with a declared zone).
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve()
_HOOKS = _HERE.parents[1] / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))
from hook_runtime import resolve_actor  # noqa: E402

SCHEMA_VERSION = "1"

_STORE_REL = ("docs", "review", "dismissals.jsonl")


def _repo_root() -> Path:
    # harness/scripts/dismissals_store.py -> repo root is two parents up from scripts/
    return _HERE.parents[2]


def _resolve_store(root=None, store_path=None) -> Path:
    if store_path is not None:
        return Path(store_path)
    base = Path(root) if root is not None else _repo_root()
    return base.joinpath(*_STORE_REL)


# ---------- fingerprint ----------

def _canon_path(file_path: str) -> str:
    return (file_path or "").strip().replace("\\", "/")


def normalize_snippet(snippet: str) -> str:
    """Strip leading/trailing whitespace per line and drop boundary blank lines —
    internal whitespace is left untouched. This makes the fingerprint stable across a
    re-indentation while keeping two snippets that differ only in internal spacing
    distinct (no false collision)."""
    lines = [ln.strip() for ln in (snippet or "").splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _h(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def fingerprint(file_path: str, rule_or_title: str, code_snippet: str) -> str:
    """Stable key for a finding: sha256 over the per-field digests of canon(file),
    rule/title, and the normalized snippet — joined with `|`. Each field is hashed
    FIRST so a literal `|` inside a path or title cannot shift the boundary and collide
    a distinct (file, rule) pair. No line number — a reformat that shifts lines does not
    break it."""
    key = "%s|%s|%s" % (_h(_canon_path(file_path)),
                        _h((rule_or_title or "").strip().lower()),
                        _h(normalize_snippet(code_snippet)))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ---------- flock ----------

def _flock(fh, exclusive: bool) -> bool:
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN)
        return True
    except (ImportError, OSError):
        return False


_warned_degraded = False


def _warn_degraded() -> None:
    global _warned_degraded
    if _warned_degraded:
        return
    _warned_degraded = True
    sys.stderr.write(
        "[dismissals_store] warning: file lock unavailable on this platform — "
        "two reviewers appending a large record concurrently may splice. "
        "Single-writer use is unaffected.\n")


# ---------- append / lookup ----------

def append(record: dict, *, root=None, store_path=None) -> dict:
    """Append one dismissal record (append-only, no read-modify-write). Fills
    actor+ts+schema_version when absent, then writes one JSON line under an exclusive
    lock. Returns the completed record."""
    rec = dict(record)
    rec.setdefault("schema_version", SCHEMA_VERSION)
    rec.setdefault("actor", resolve_actor())
    rec.setdefault("ts", datetime.now(timezone.utc).isoformat())
    path = _resolve_store(root, store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    fh = path.open("a", encoding="utf-8")
    locked = _flock(fh, True)
    if not locked:
        _warn_degraded()
    try:
        fh.write(line + "\n")
        fh.flush()
    finally:
        if locked:
            _flock(fh, False)
        fh.close()
    return rec


def lookup(fp: str, *, root=None, store_path=None) -> list:
    """Return every record whose fingerprint matches (none are hidden). An unparseable
    line — e.g. an old splice — is skipped with a warning, never raised."""
    path = _resolve_store(root, store_path)
    if not path.is_file():
        return []
    out = []
    # errors="replace" so a spliced/corrupt byte (the very failure the store tolerates)
    # cannot raise UnicodeDecodeError on the whole file before the per-line skip runs.
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            sys.stderr.write("[dismissals_store] skipping unparseable line\n")
            continue
        if rec.get("fingerprint") == fp:
            out.append(rec)
    return out


def _main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="review-dismissals store CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    fp = sub.add_parser("fingerprint", help="print a finding fingerprint")
    fp.add_argument("file")
    fp.add_argument("rule")
    fp.add_argument("snippet")
    lk = sub.add_parser("lookup", help="list dismissals for a fingerprint")
    lk.add_argument("fingerprint")
    args = p.parse_args(argv)
    if args.cmd == "fingerprint":
        print(fingerprint(args.file, args.rule, args.snippet))
    elif args.cmd == "lookup":
        for rec in lookup(args.fingerprint):
            print(json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
