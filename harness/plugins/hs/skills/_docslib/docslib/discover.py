"""Walk docs/ → tập Doc (md có/không frontmatter). Bỏ qua zone raw/archive/generated + .docsignore."""
from __future__ import annotations

from pathlib import Path

import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPatternError

from .frontmatter import parse, Doc

SKIP_DIRS = {"_inbox", "_archive", "_generated", "__pycache__", ".git", "node_modules"}


class DocsIgnoreError(Exception):
    """A `.docsignore` pattern is not valid gitignore syntax (a bare `!`, a
    lone trailing backslash, ...). Wraps pathspec's own
    `GitWildMatchPatternError` (a bare `ValueError` with no context beyond the
    pattern text) so a malformed `.docsignore` fails the docs pipeline with a
    message naming the offending pattern, not a raw library traceback
    surfacing out of an unrelated call site."""


def _load_docsignore_lines(docs_root: Path) -> list[tuple[str, int]]:
    """Đọc .docsignore ở docs_root, trả về list (pattern, 1-based source line)
    (loại comment/dòng trống). The line number rides along so
    `_build_ignore_spec`'s error path can name the offending LINE (not just the
    offending pattern text) when the real on-disk `.docsignore` is the source
    — a plain list-of-patterns form would throw that away before the compile
    step ever sees it."""
    ignore_file = docs_root / ".docsignore"
    if not ignore_file.is_file():
        return []
    out: list[tuple[str, int]] = []
    for i, line in enumerate(ignore_file.read_text().splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append((stripped, i))
    return out


def _build_ignore_spec(patterns: list[str], *, lines: list[int] | None = None) -> pathspec.PathSpec:
    """gitignore-semantics matcher: `*` stops at `/`, `**` crosses it, a
    trailing `/` anchors a directory, `!` negates. `"gitignore"` (not the
    older `"gitwildmatch"` alias, which this pathspec version deprecates in
    its favor — same matching behavior, no warning). Compiles every pattern
    into a regex up front — call this ONCE per pattern set (`iter_md` below)
    and reuse the returned spec, not per-file; rebuilding per file was the
    wrong cost center to pay in a loop over every doc.

    `lines` (optional, 1-based, same length + order as `patterns`) lets a
    caller reading a REAL `.docsignore` file attribute a compile failure to
    its exact source line; omitted (the common case for a caller that built
    `patterns` by hand — tests, ad-hoc sets with no file behind them) falls
    back to naming the pattern's position in the list instead. Either way, a
    malformed pattern (a bare `!`, a lone trailing `\\`) raises
    `DocsIgnoreError` naming what and where — never pathspec's raw
    `GitWildMatchPatternError` escaping to an unrelated call site."""
    try:
        return pathspec.PathSpec.from_lines("gitignore", patterns)
    except GitWildMatchPatternError as exc:
        # `from_lines` gives up on the FIRST bad pattern without saying which —
        # recompile one at a time (each is O(1) vs. one regex compile) to find it.
        for i, pat in enumerate(patterns):
            try:
                pathspec.PathSpec.from_lines("gitignore", [pat])
            except GitWildMatchPatternError:
                where = ("line %d" % lines[i]) if lines and i < len(lines) \
                    else "pattern #%d" % (i + 1)
                raise DocsIgnoreError(
                    "invalid .docsignore pattern at %s: %r (%s)"
                    % (where, pat, exc)) from exc
        # Every pattern compiles alone but the FULL set still failed (e.g. a
        # negation whose interaction with an earlier pattern pathspec itself
        # rejects) — surface the original error rather than silently drop it.
        raise DocsIgnoreError(
            "invalid .docsignore pattern set: %s" % exc) from exc


def _is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """True if rel_path matches any `.docsignore` pattern. Single-path
    convenience for tests / small pattern sets — builds a fresh spec per call,
    so a per-file loop should use `_build_ignore_spec` once instead."""
    return _build_ignore_spec(patterns).match_file(rel_path)


def iter_md(docs_root: str | Path, ignore_patterns: list[str] | None = None):
    """Yield path mọi .md trong ZONE-2 (bỏ raw/archive/generated + .docsignore)."""
    docs_root = Path(docs_root)
    ignore_lines = None
    if ignore_patterns is None:
        pairs = _load_docsignore_lines(docs_root)
        ignore_patterns = [p for p, _n in pairs]
        ignore_lines = [n for _p, n in pairs]
    spec = _build_ignore_spec(ignore_patterns, lines=ignore_lines)
    for p in sorted(docs_root.rglob("*.md")):
        rel_parts = p.relative_to(docs_root).parts
        if any(seg in SKIP_DIRS for seg in rel_parts):
            continue
        # Code-default skip (top-level only, so a nested .../product/ is NOT
        # over-matched): docs/product/ is generated + validated in-harness by
        # hs:spec (its own strict_gate/validate), not by harness docs governance.
        if rel_parts and rel_parts[0] == "product":
            continue
        rel = str(p.relative_to(docs_root))
        if spec.match_file(rel):
            continue
        yield p


def discover(docs_root: str | Path, ignore_patterns: list[str] | None = None) -> list[Doc]:
    docs_root = Path(docs_root)
    # Pass ignore_patterns through AS GIVEN (including None) rather than
    # resolving it here via _load_docsignore: that plain-list form throws away
    # line numbers, so a caller relying on discover()'s default (read the real
    # .docsignore) would lose the exact-line naming _build_ignore_spec's error
    # path provides — let iter_md do its own (line-number-preserving) load.
    out = []
    for p in iter_md(docs_root, ignore_patterns):
        out.append(parse(p, rel=str(p.relative_to(docs_root))))
    return out
