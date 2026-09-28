#!/usr/bin/env python3
"""rule_nudge_hook — name the rules whose scope matches the file being written.

PreToolUse (Write/Edit/MultiEdit) nudge. When a file is about to be written, it
surfaces ONE terse stderr line naming up to N rules whose scope matches that file
(by id + title), so the operator sees the relevant review rules at the moment of
editing. Advisory only — it never blocks and ALWAYS continues (fail-open).

Enable resolution (precedence): HARNESS_RULE_NUDGE env wins when set — truthy on,
falsey off — a per-machine override in .claude/settings.local.json (gitignored, no
manifest drift). When the env is unset it falls through to harness-hooks.yaml
`enabled`, the same nudge plane every other nudge uses (class default OFF). Shipped
default: ON.

Noncode-target filter: the broad review rules carry scope ["**/*"] so they match
prose, data, and config too, but those are CODE-review rules — a per-edit nudge on
a markdown/JSON/YAML/doc file is noise. _is_code_target gates the nudge to code
targets. The filter lives HERE (the noise is a nudge problem); the standards' scope
is user-owned and untouched, so a full review still applies the rule everywhere.

Once per file per session: an ephemeral $TMPDIR flag keyed by session + file
de-dupes, so re-editing the same file stays quiet. (session_init GC-sweeps stale
flags by TTL.) The cap N is read from harness/data/standards.yaml (nudge_max_rules,
default 3) so a broad edit never floods the terminal, and the rule BODY is never
dumped — only id + title.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = "rule_nudge_hook"
_ENV = "HARNESS_RULE_NUDGE"
_FALSEY = frozenset({"", "0", "false", "no", "off"})
_DEFAULT_CAP = 3
_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

# Noncode targets the per-edit nudge should stay silent on. Extensions cover
# prose/data/config; dir prefixes cover trees that are doc/data by location even
# when a stray code file lands inside. Both are deny-lists over a fire-by-default
# base, so an unknown code extension (.zig, .ml, ...) still nudges.
_NONCODE_EXTS = frozenset({
    ".md", ".markdown", ".json", ".yaml", ".yml",
    ".txt", ".rst", ".lock", ".cfg", ".ini", ".toml",
})
_NONCODE_DIR_PREFIXES = ("docs/", "harness/data/", "harness/standards/", "plans/")


def _enabled() -> bool:
    """Precedence: HARNESS_RULE_NUDGE env override (truthy on / falsey off) when set,
    else the shared harness-hooks.yaml nudge plane (class default OFF)."""
    raw = os.environ.get(_ENV, "").strip().lower()
    if raw:  # env set → explicit per-repo override wins
        return raw not in _FALSEY
    return hook_runtime.hook_enabled(_NAME, HOOK_CLASS)


def _is_code_target(rel: str) -> bool:
    """True when the repo-relative path is a code edit worth nudging on. A
    noncode extension or a doc/data dir prefix → False; everything else (the
    fire-by-default base, including unknown code extensions) → True."""
    posix = rel.replace("\\", "/")
    if any(posix.startswith(p) for p in _NONCODE_DIR_PREFIXES):
        return False
    if Path(posix).suffix.lower() in _NONCODE_EXTS:
        return False
    return True


def _scripts_on_path() -> None:
    sd = str(Path(__file__).resolve().parent.parent / "scripts")
    if sd not in sys.path:
        sys.path.insert(0, sd)


def _nudge_cap(root: str) -> int:
    """nudge_max_rules from harness/data/standards.yaml (default 3)."""
    try:
        knob = Path(root) / "harness" / "data" / "standards.yaml"
        data = hook_runtime.yaml_load(knob.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            v = data.get("nudge_max_rules")
            if isinstance(v, int) and v > 0:
                return v
    except Exception:  # noqa: BLE001 — a missing/bad knob uses the default
        pass
    return _DEFAULT_CAP


def _relpath(file_path: str, root: str) -> Optional[str]:
    """Repo-relative posix path, or None when the file resolves OUTSIDE the root.
    Rule scopes are repo-relative globs, so a bare basename for an out-of-root file
    would falsely match a repo scope (and collide the per-file dedup) — skip it."""
    try:
        return Path(file_path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _temp_dir() -> Path:
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _safe(token: str) -> str:
    return hook_runtime.safe_session_id(token)


def _flag_path(session_id: str, rel: str) -> Path:
    return _temp_dir() / ("harness-rulenudge-%s-%s" % (_safe(session_id), _safe(rel)))


def _already_nudged(session_id: str, rel: str) -> bool:
    return _flag_path(session_id, rel).exists()


def _mark_nudged(session_id: str, rel: str) -> None:
    try:
        _flag_path(session_id, rel).write_text("1", encoding="utf-8")
    except OSError:
        pass


_UNIVERSAL = {"**/*", "**", "*"}


def _rank(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rules a reader could not have guessed, first.

    A cap of three spends its slots on whatever the loader returned first, and the
    loader returns the `**/*` rules first. On this repo that meant every Python file
    got the same three generic lines while the twenty-odd Python-specific rules sat
    behind a "(+31 more)" tail — an advisory that fired on every edit and told the
    agent nothing it did not already know.

    A rule scoped to every file in the repo is the one the agent is most likely to
    have internalised; a rule scoped to this file's kind is the one worth a line.
    So the universal tier goes last. It is a reordering, never a filter: a file
    matched only by universal rules still gets them, and ties keep loader order so
    this introduces no ranking among equals."""
    return sorted(rules, key=lambda r: all(
        s in _UNIVERSAL for s in (r.get("scope") or ["**/*"])))


def core(data: Dict[str, Any], root: Optional[str] = None) -> Optional[str]:
    """Return the one-line advisory for a scope-matching code write, or None.

    Side effect: marks the per-file/session flag when it emits, so a second
    write/edit of the same file in the session stays silent."""
    if not isinstance(data, dict) or data.get("tool_name") not in _WRITE_TOOLS:
        return None
    tool_input = data.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path.strip():
        return None
    root = root or os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or "."
    rel = _relpath(file_path, root)
    if rel is None:
        return None  # a write outside the repo root has no repo-relative scope
    if not _is_code_target(rel):
        # Prose/data/config edit: stay silent AND leave no dedup marker (don't
        # add to the /tmp leak the GC sweep reclaims). The standards still cover the file
        # in a full review — only the per-edit nudge is suppressed.
        return None
    session_id = data.get("session_id") or ""
    if _already_nudged(session_id, rel):
        return None

    _scripts_on_path()
    import rule_view  # resolved after the path insert
    rules = rule_view.load_rules(root, scope_intersects=[rel]).get("rules", [])
    if not rules:
        return None

    cap = _nudge_cap(root)
    shown = _rank(rules)[:cap]
    # layer-b override rules carry no title — render the id alone (no dangling
    # separator); a shipped rule with a title shows "id — title".
    named = "; ".join(
        ("%s — %s" % (r.get("id"), t) if (t := (r.get("title") or "").strip())
         else "%s" % r.get("id"))
        for r in shown)
    extra = len(rules) - len(shown)
    tail = " (+%d more)" % extra if extra > 0 else ""
    _mark_nudged(session_id, rel)
    return "rules for %s: %s%s" % (rel, named, tail)


def main(argv: Optional[List[str]] = None) -> int:
    data = hook_runtime.read_stdin_json()
    d = data if isinstance(data, dict) else {}
    try:
        if _enabled():
            msg = core(data)
            if msg:
                hook_runtime.emit_nudge_and_continue(_NAME, msg, d)
                return 0
    except Exception as e:  # noqa: BLE001 — a nudge must never break the op
        try:
            hook_runtime.log_hook_error(_NAME, e)
        except Exception:
            pass
    hook_runtime.emit_continue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
