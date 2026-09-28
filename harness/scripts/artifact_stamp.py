#!/usr/bin/env python3
"""artifact_stamp.py — stamp harness provenance into a markdown artifact.

A plan/report carries a YAML frontmatter stamp so its origin travels WITH the
file: copied anywhere, even away from the harness, it still says which harness
version (and exact tree fingerprint) produced it. The stamp is deliberately
deterministic — version + kit_digest + schema_version, NO wall-clock — so the
PostToolUse hook that calls it can re-fire on every write and reach a fixed
point: stamping the same text twice is byte-identical.

stamp_markdown is a pure text transform (no YAML dependency, no I/O): it merges
the harness_* keys into an existing frontmatter block or prepends one, never
touching other keys or the body/evidence. The CLI stamps files in place using
the live release identity (harness_release.read_release).
"""

import os
import sys
from pathlib import Path

STAMP_SCHEMA_VERSION = "1.0"
# Keys the stamp owns. Re-stamping strips these and re-appends, so a value change
# (e.g. a mid-session version bump) updates in place rather than duplicating.
_STAMP_KEYS = ("harness_version", "harness_kit_digest", "harness_schema_version")
_OPEN = "---"  # the YAML frontmatter delimiter line (newline kept separate)


def _stamp_lines(version: str, digest: str, schema_version: str) -> list:
    return [
        f"harness_version: {version}",
        f"harness_kit_digest: {digest}",
        f"harness_schema_version: {schema_version}",
    ]


def _is_stamp_key(line: str) -> bool:
    return any(line.startswith(k + ":") for k in _STAMP_KEYS)


def _opening_newline(text: str):
    """The terminator of the opening `---` frontmatter fence, or None when the
    text does not begin with one. Recognizes CRLF as well as LF so a
    Windows-authored artifact is merged, not double-stamped."""
    if text.startswith(_OPEN + "\r\n"):
        return "\r\n"
    if text.startswith(_OPEN + "\n"):
        return "\n"
    return None


def _body_newline(text: str) -> str:
    """The newline style of a body that has no frontmatter — so a prepended
    stamp matches the file's existing line endings."""
    i = text.find("\n")
    if i > 0 and text[i - 1] == "\r":
        return "\r\n"
    return "\n"


def _split_block(rest: str, nl: str):
    """Given the text AFTER the opening fence, return (content_lines, body) for
    the frontmatter, or (None, None) when there is no closing `---` fence.
    Handles an empty block whose closing fence immediately follows the opening
    one, and a block whose closing fence sits at EOF without a trailing newline.
    The body is returned byte-for-byte (line endings untouched)."""
    if rest == _OPEN:                       # "---<nl>---" at EOF, empty, no trailing nl
        return [], ""
    if rest.startswith(_OPEN + nl):         # "---<nl>---<nl>..." empty block + body
        return [], rest[len(_OPEN + nl):]
    needle = nl + _OPEN + nl                # closing fence on its own line
    idx = rest.find(needle)
    if idx != -1:
        return rest[:idx].split(nl), rest[idx + len(needle):]
    if rest.endswith(nl + _OPEN):           # closing fence at EOF, no trailing nl
        return rest[:-len(nl + _OPEN)].split(nl), ""
    return None, None                       # opening fence, no closing → not frontmatter


def stamp_markdown(text: str, version: str, digest: str,
                   schema_version: str = STAMP_SCHEMA_VERSION) -> str:
    """Return ``text`` with the harness provenance stamp merged into its
    frontmatter. Idempotent: re-stamping with the same inputs is a no-op.
    Frontmatter is detected for both LF and CRLF artifacts and for an empty
    block, so a stamp is never prepended above an existing one."""
    stamp = _stamp_lines(version, digest, schema_version)
    nl = _opening_newline(text)
    if nl is not None:
        rest = text[len(_OPEN + nl):]
        block, after = _split_block(rest, nl)
        if block is not None:
            kept = [ln for ln in block
                    if ln.strip() and not _is_stamp_key(ln)]
            new_block = nl.join(kept + stamp)
            return f"{_OPEN}{nl}{new_block}{nl}{_OPEN}{nl}{after}"
        # opening fence with no closing fence → treat as body, prepend fresh
    return _prepend(text, stamp)


def _prepend(text: str, stamp: list) -> str:
    nl = _body_newline(text)
    block = nl.join(stamp)
    sep = "" if (text == "" or text.startswith(("\n", "\r\n"))) else nl
    return f"{_OPEN}{nl}{block}{nl}{_OPEN}{nl}{sep}{text}"


def stamp_file(path: Path, version: str, digest: str,
               schema_version: str = STAMP_SCHEMA_VERSION) -> bool:
    """Stamp a file in place. Returns True if the file changed."""
    original = path.read_text(encoding="utf-8")
    stamped = stamp_markdown(original, version, digest, schema_version)
    if stamped == original:
        return False
    import artifact_io
    artifact_io.atomic_write_text(path, stamped)
    return True


def main(argv=None) -> int:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import harness_paths  # noqa: E402
    import harness_release  # noqa: E402
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: artifact_stamp.py FILE [FILE ...]", file=sys.stderr)
        return 2
    rel = harness_release.read_release(harness_paths.root())
    ver, dig = rel.get("harness_version", ""), rel.get("kit_digest", "")
    for f in argv:
        changed = stamp_file(Path(f), ver, dig)
        print(f"{'stamped' if changed else 'unchanged'}: {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
