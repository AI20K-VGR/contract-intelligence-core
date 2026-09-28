#!/usr/bin/env python3
"""
Cross-platform encoding utilities for Windows compatibility.

Mirrors skill-creator's helper. Fixes UnicodeEncodeError on Windows by
reconfiguring stdout/stderr to UTF-8 and providing encoding-aware file
I/O helpers.
"""

import json
import math
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

# Process umask captured ONCE at import (single-threaded, under the import lock).
# write_text_atomic uses this for a new file's mode instead of the per-call
# os.umask(0)/restore dance, which is process-global and races under concurrent
# threads — corrupting other threads' file-creation modes and able to leave the
# umask stuck at 0 (world-writable). A CLI's umask is fixed for its lifetime, so
# the import-time value is the correct one.
_PROCESS_UMASK = os.umask(0)
os.umask(_PROCESS_UMASK)


def deterministic_json_default(o: Any) -> Any:
    """A `json.dumps(default=...)` that serializes a set/frozenset to a sorted
    list (by `(type-name, str)`) instead of the hash-seed-ordered `str(set)`,
    so a hand-edited `!!set` YAML value cannot make a snapshot content-hash or
    the emitted JSON differ run-to-run. Any other non-JSON-native value still
    falls back to `str` (the existing convention -- e.g. a PyYAML
    `datetime.date` from a `target_date`)."""
    if isinstance(o, (set, frozenset)):
        # Canonicalize a nested set/frozenset MEMBER before sorting, so the sort
        # key `str(c)` never runs on a still-hash-ordered set (which would flap
        # the outer order). Mirrors `_canon`/`_stringify_keys`, which recurse too.
        members = [deterministic_json_default(x) if isinstance(x, (set, frozenset)) else x
                   for x in o]
        return sorted(members, key=lambda c: (type(c).__name__, str(c)))
    return str(o)


def _safe_jsonify(o: Any, _seen: frozenset = frozenset()) -> Any:
    """Recursively rebuild a `yaml.safe_load`-produced structure into one
    `json.dumps(..., allow_nan=False)` cannot choke on, so a hostile hand-edit
    degrades (valid JSON, exit 0) instead of crashing or emitting non-conformant
    JSON. Handles the reachable hostile-edit classes:

    - **exotic dict KEY** (a `!!binary` bytes key, etc.): json rejects any key not
      str/int/float/bool/None BEFORE `default=` runs, so str-coerce every such key.
      A coerced key that collides with a sibling is disambiguated (`key#2`) rather
      than silently dropped. (A NATIVE non-string key that json accepts and
      stringifies itself — int `1`, bool `True`, `None` — is NOT disambiguated
      against a colliding string sibling; that is the same accepted non-injectivity
      as `spec_graph._stringify_keys`/`_canon`, and only bites a mapping that is
      already semantically malformed.)
    - **circular reference** (a YAML `&a […*a…]` anchor cycle): replace an ancestor
      back-edge with a marker (ancestor-path `_seen`, so a shared non-ancestor
      sibling is not a false cycle) — no infinite recursion.
    - **NaN / ±Infinity float VALUE**: json emits bare `NaN`/`Infinity` literals
      (invalid per RFC 8259) and never consults `default=`; coerce to a string.
    - any other non-JSON-native scalar (bytes value, `datetime.date`) → `str`.

    NOT depth-guarded: a >~1000-level nested-DISTINCT structure would still
    RecursionError here, but `yaml.safe_load`'s own composer ceiling (~450) keeps
    that unreachable from a hand-edited spec. Callers hit this only on the retry
    after a first `json.dumps` raises, so the happy path is byte-identical."""
    if isinstance(o, (set, frozenset)):
        return deterministic_json_default(o)
    if isinstance(o, float):
        return o if math.isfinite(o) else str(o)
    if isinstance(o, dict):
        if id(o) in _seen:
            return "[circular reference]"
        _seen = _seen | {id(o)}
        result: dict = {}
        for k, v in o.items():
            if isinstance(k, bool) or k is None or isinstance(k, (str, int)):
                key = k
            elif isinstance(k, float) and math.isfinite(k):
                key = k
            else:
                key = str(k)
            if key in result:
                n = 2
                while f"{key}#{n}" in result:
                    n += 1
                key = f"{key}#{n}"
            result[key] = _safe_jsonify(v, _seen)
        return result
    if isinstance(o, (list, tuple)):
        if id(o) in _seen:
            return "[circular reference]"
        return [_safe_jsonify(v, _seen | {id(o)}) for v in o]
    if isinstance(o, (str, int, bool)) or o is None:
        return o
    return str(o)


def dumps_json(obj: Any, **kwargs: Any) -> str:
    """`json.dumps` with `default=deterministic_json_default` and
    `allow_nan=False`, plus a fail-soft retry through `_safe_jsonify` so a hostile
    hand-edited spec degrades instead of escaping — upholds every emitter's
    "always exit 0, emit VALID JSON" and the snapshot's idempotent-write contract.
    `allow_nan=False` turns a silent non-conformant `NaN`/`Infinity` value into a
    caught ValueError so the retry sanitizes it; the retry also handles the
    TypeError (exotic key) and circular-reference (ValueError) classes. Deep-
    DISTINCT nesting past the recursion limit is out of scope — and unreachable,
    since `yaml.safe_load`'s composer ceiling is far shallower."""
    try:
        return json.dumps(obj, default=deterministic_json_default, allow_nan=False, **kwargs)
    except (TypeError, ValueError, RecursionError):
        return json.dumps(_safe_jsonify(obj), default=deterministic_json_default,
                          allow_nan=False, **kwargs)


def replace_lone_surrogates(s: str) -> str:
    """Replace every lone UTF-16 surrogate code point (U+D800–U+DFFF) in `s` with
    U+FFFD so the string is UTF-8-encodable.

    Such a code point enters a `str` via `os.fsdecode`'s `surrogateescape` handler
    when a filename holds an invalid-UTF-8 byte (a bad archive extraction, a
    cross-locale rsync/tar, an LLM-authored name with a stray byte). It rides a
    node's `file` field into the emitted JSON graph and, with `ensure_ascii=False`,
    `json.dumps` keeps it verbatim — so the crash surfaces only at the UTF-8 write
    sink (`UnicodeEncodeError`), not at serialize time. Every big-JSON/text CLI
    promises "always exit 0"; an uncaught encode error there breaks that contract
    with a raw traceback + accidental exit 1 that no JSON consumer can parse.

    U+FFFD (the REPLACEMENT CHARACTER) — NOT a `\\udcff`-style backslash escape:
    a backslash escape would round-trip back through `json.loads` to the SAME lone
    surrogate and re-crash any consumer that re-encodes the value, merely relocating
    the fault downstream. U+FFFD is terminal — no surrogate survives."""
    if not any(0xD800 <= ord(c) <= 0xDFFF for c in s):
        return s
    return "".join("�" if 0xD800 <= ord(c) <= 0xDFFF else c for c in s)


def emit_json(obj: Any, *, sort_keys: bool = False) -> None:
    """Print `obj` as indented JSON to stdout, surviving a closed downstream pipe.

    The analytical scripts emit large JSON and promise to "always exit 0". When their
    stdout is piped into a consumer that closes early (`check_consistency.py … | head`),
    the final write hits a broken pipe and — left unhandled — Python prints a traceback
    and exits non-zero, breaking that contract and noising the PO's terminal.

    On BrokenPipeError we swallow it and redirect stdout to os.devnull so the interpreter's
    flush-on-exit cannot re-raise.

    Lone surrogates are neutralised UP FRONT (replace_lone_surrogates), never reactively on a
    UnicodeEncodeError. A reactive catch only fires when stdout is a STRICT UTF-8 encoder; a
    runner whose stdout carries the `surrogateescape`/`surrogatepass` error handler (POSIX C
    locale, PEP 540 UTF-8 mode, or an explicit PYTHONIOENCODING) encodes `\\udcff` straight to a
    raw `0xff` byte WITHOUT raising — the guard never trips and an invalid-UTF-8 byte rides out
    onto the wire, breaking every JSON consumer. Sanitising before the write makes the emission
    valid UTF-8 regardless of the ambient error handler. The scan is a no-op fast-path (returns
    the same string) when the payload holds no surrogate, so a clean emit stays byte-identical.
    The single home every big-JSON CLI uses for this.
    """
    payload = replace_lone_surrogates(
        dumps_json(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys))

    def _to_devnull() -> None:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass

    def _write(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.write("\n")
        sys.stdout.flush()

    # payload is already surrogate-free (sanitised above), so the only write fault
    # left is a downstream pipe that closed early.
    try:
        _write(payload)
    except BrokenPipeError:
        _to_devnull()


def configure_utf8_console():
    """Reconfigure stdout/stderr for UTF-8 on Windows (cp1252 -> utf-8)."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass  # Python < 3.7


def read_text_utf8(path: Path) -> str:
    """Read file with explicit UTF-8 encoding."""
    return Path(path).read_text(encoding="utf-8")


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` so a concurrent reader never sees a partial file.

    A bare `path.write_text(...)` opens the destination 'wb' — a truncate-then-
    refill window a reader can observe as a 0-byte or half-written file (plain
    markdown/text has no JSON parse-error safety net to degrade on). Use this for
    any FIXED-path artifact a human or CI may read while a re-render is in flight
    (e.g. the traceability matrix). The new bytes go to a unique temp in the SAME
    directory (`mkstemp` is unique across threads AND processes — a shared pid
    makes a bare `.tmp-<pid>` name insufficient), then `os.replace()` swaps it in
    atomically: the reader always sees either the fully-old or the fully-new file.
    Content is regenerable, so writer-vs-writer is last-write-wins (no lock); only
    the torn READ needs closing. The temp is cleaned up on any failure.

    Permission mode matches a plain write_text: an existing file's mode is
    preserved, a new file gets `0o666 & ~umask` (mkstemp's fixed 0600 would else
    silently downgrade the target to owner-only). Newlines are written verbatim
    (`newline=""`, LF-as-authored) so the bytes are identical across platforms.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve an existing file's mode; a new file gets the import-time umask
    # applied to 0o666 (see _PROCESS_UMASK — read once at import, NOT per-call, so
    # this never runs the process-global os.umask(0)/restore dance that races under
    # concurrent threads and can leave the umask stuck world-writable).
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        mode = 0o666 & ~_PROCESS_UMASK
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        try:
            with open(tmp, "w", encoding=encoding, newline="") as fh:
                fh.write(text)
        except UnicodeEncodeError:
            # A lone surrogate (a non-UTF-8 filename surrogate-escaped into rendered
            # content) hit the strict encoder — same class the JSON sink guards.
            # Re-truncate and write the neutralised text so an advisory render never
            # crashes on an unlucky filename (see replace_lone_surrogates).
            with open(tmp, "w", encoding=encoding, newline="") as fh:
                fh.write(replace_lone_surrogates(text))
        os.chmod(tmp, mode)
        os.replace(tmp, str(path))  # atomic swap — no truncate-then-refill window
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
