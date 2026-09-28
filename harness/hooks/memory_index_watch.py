#!/usr/bin/env python3
"""memory_index_watch.py — PostToolUse:{Write|Edit|MultiEdit, Bash} nudge (nudge-class).

`MEMORY.md` is loaded into every session's context, and this project's memory
directory is SHARED: six lanes resolve to the same `~/.claude/projects/<slug>/
memory/`. No git, no lock, no review. `scripts/memory_index_check.py` scores it;
this hook is what makes that gate ever run.

── WHY A HOOK, AND WHY THIS EVENT ─────────────────────────────────────────────
The directory is OUTSIDE every repo. No pre-commit hook can see it (editing a
memory produces no commit), CI never has it, and a test in the project suite
would score whatever the lane happens to hold. The only place the question is
well-posed is the host tree at the moment of the write — the same reasoning
`ledger_red_watch` sets out for `plans/BUGS.md`, and the same event.

── WHY IT KEYS ON A DIGEST, NOT `file_path` ───────────────────────────────────
Because that is how this file is actually written. Measured `260908`: this
session's own edits to `MEMORY.md` went through `python3 - <<PY` and `sed -i`,
neither of which carries a `tool_input.file_path`. Filtering on the path would
have watched the one spelling nobody uses.

The digest covers the index only, not the whole directory — a new memory file
that is never linked shows up as an orphan on the next index write, which is when
someone can act on it.

── WHAT IT REPORTS ────────────────────────────────────────────────────────────
Only what changed since the last look, baseline in `<data_root>/state/
memory_index.json` written with `os.replace`. Pre-existing problems are listed
once, under their own heading: a hook that blames this session for another
lane's orphan is a hook that gets switched off.

🛑 It does not block. PostToolUse runs after the write; `exit 2` cannot un-write
anything and only leaks the dispatcher's command line into the transcript.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001 — older streams; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import harness_paths  # noqa: E402
import hook_runtime  # noqa: E402
import memory_index_check  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem


def _memory_dir() -> Path | None:
    """The memory directory for THIS project, or None when it cannot be resolved.

    Derived from the session transcript's own project slug rather than guessed
    from cwd: a worktree and its host tree share one memory directory, and both
    must score the same file.
    """
    try:
        root = Path(harness_paths.data_root()).parent
    except Exception:  # noqa: BLE001 — a visibility hook never crashes a tool call
        return None
    slug = str(root.resolve()).replace("/", "-")
    candidate = Path.home() / ".claude" / "projects" / slug / "memory"
    return candidate if candidate.is_dir() else None


def _state_path() -> Path | None:
    try:
        return Path(harness_paths.data_root()) / "state" / "memory_index.json"
    except Exception:  # noqa: BLE001
        return None


def _read_state(p: Path) -> dict:
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001 — absent or malformed reads as "never looked"
        return {}


def _write_state(p: Path, payload: dict) -> None:
    """Atomic: `<data_root>/state/` is shared by every session on this tree."""
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)
    except Exception as e:  # noqa: BLE001
        hook_runtime.log_hook_error(_NAME, e)


def core(data: dict) -> None:
    memory_dir = _memory_dir()
    if memory_dir is None:
        return
    index = memory_dir / "MEMORY.md"
    if not index.is_file():
        return

    digest = hashlib.sha256(index.read_bytes()).hexdigest()
    state_path = _state_path()
    state = _read_state(state_path) if state_path else {}
    if state.get("digest") == digest:
        return  # the index did not change on this tool call

    problems = memory_index_check.check(memory_dir)
    seen = set(state.get("problems") or [])
    fresh = [p for p in problems if p not in seen]
    standing = [p for p in problems if p in seen]

    if state_path:
        _write_state(state_path, {"digest": digest, "problems": problems})

    if not problems:
        return
    lines = ["[memory-index] MEMORY.md changed and the index gate is red."]
    if fresh:
        lines += ["NEW since the last write:"] + [f"  · {p}" for p in fresh]
    if standing:
        lines += ["Already there before this write:"] + [f"  · {p}" for p in standing]
    lines.append(f"Re-run: python3 $HARNESS_BIN_ROOT/harness/scripts/memory_index_check.py {memory_dir}")
    hook_runtime.emit_nudge(_NAME, "\n".join(lines), session=data.get("session_id"),
                            default_channel="systemMessage")


def main(raw: str | None = None) -> None:
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
            core(data)
    except Exception as e:  # noqa: BLE001 — visibility never breaks a tool call
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.drain_or_continue()


if __name__ == "__main__":
    main()
