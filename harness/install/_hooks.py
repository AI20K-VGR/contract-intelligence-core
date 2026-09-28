"""_hooks.py — settings.json hook-wiring transforms for the installer.

Pure transforms over the hook registration, split out of install.py so the
orchestrator stays thin:
  - load_registration: parse hooks-registration.yaml from the source tree;
  - materialize_hooks: build Claude Code's settings `hooks` object from it,
    translating the `$HARNESS_ROOT` placeholder to "$CLAUDE_PROJECT_DIR";
  - merge_hooks: additively merge into a user's existing hooks (dedup by command,
    never clobber) — idempotent;
  - strip_harness_hooks: drop only harness-owned hooks back out on uninstall.

install.py re-exports these names, so callers and tests that reach them through
the `install` module see no change.
"""
import json
import os
import re
from pathlib import Path

# Real Claude Code hook events. UserPromptExpansion is a live event on current
# Claude Code — verified via payload capture: a user-typed /hs:* fires it with a
# structured `command_name` — so it is wired (it captures user-typed skill
# invocations that the model-only PreToolUse:Skill path misses). On a host that
# does not support it the entry is inert (ignored), never an error. Genuinely
# unknown events are still allow-listed out and reported.
ALLOWED_EVENTS = {
    "SessionStart", "SessionEnd", "UserPromptSubmit", "UserPromptExpansion",
    "PreToolUse", "PostToolUse", "Stop", "SubagentStop", "SubagentStart",
    "PreCompact", "Notification",
}

# A command is "ours" when it INVOKES a harness hook script —
# .../harness/hooks/<name>.py — not merely when it mentions the directory. A
# substring test on "harness/hooks/" would delete a user's own audit hook (e.g.
# `grep harness/hooks/ …`) on uninstall, so match the hook .py filename shape.
_HARNESS_HOOK_CMD = re.compile(r"harness/hooks/[A-Za-z0-9_]+\.py(?![A-Za-z0-9_])")


def _invokes_harness_hook(command) -> bool:
    """True when a settings.json command runs a harness hook .py (not just names
    the dir). Single test for the uninstall strip."""
    return bool(_HARNESS_HOOK_CMD.search(str(command or "")))


def hook_interpreter() -> str:
    """The interpreter token written into each hook command at install time.

    `HARNESS_PY` wins (install.sh exports the interpreter it verified, so the
    exact working one is baked in); otherwise the platform default — `python` on
    Windows, where the python.org installer ships `python` / `py` but no
    `python3`, so a command hard-wired to `python3` is dead on every tool call;
    `python3` on POSIX, the canonical name."""
    override = os.environ.get("HARNESS_PY")
    if override:
        return override
    return "python" if os.name == "nt" else "python3"


def to_command(raw: str, py: str = None, mode: str = "project") -> str:
    """Translate a registration command to the live settings form: the
    `$HARNESS_PY` placeholder becomes the resolved interpreter and the
    installer-time `$HARNESS_ROOT` placeholder becomes the runtime root
    reference (quoted so a space in the path survives).

    `mode` picks the runtime root:
      - "project" (default, back-compat): `"$CLAUDE_PROJECT_DIR"` — the
        per-project harness/ tree lives inside the project.
      - "global": `"$HARNESS_BIN_ROOT"` — one shared binary serves many
        projects; the value is wired into settings.local.json by _wire_env.
    """
    if py is None:
        py = hook_interpreter()
    root_ref = ('"$HARNESS_BIN_ROOT"' if mode == "global"
                else '"$CLAUDE_PROJECT_DIR"')
    return (raw.replace("$HARNESS_PY", py)
            .replace("$HARNESS_ROOT", root_ref))


def load_registration(source_root: Path) -> dict:
    """Parse harness/install/hooks-registration.yaml from the source tree."""
    try:
        import yaml_io  # lazy: a declared dep, but keep import-time light
    except ImportError:
        import sys
        sys.path.append(str(Path(source_root) / "harness" / "scripts"))
        import yaml_io

    reg_path = (Path(source_root) / "harness" / "install"
                / "hooks-registration.yaml")
    raw = yaml_io.yaml_load(reg_path.read_text(encoding="utf-8")) or {}
    return raw


# Class-to-default-priority mapping. Lower number = runs first.
# safety/compliance gates run first (protect), telemetry second, nudge last.
_CLASS_PRIORITY_DEFAULT = {
    "safety": 0,
    "compliance": 0,
    "telemetry": 50,
    "nudge": 90,
}


def _priority_of(entry: dict) -> int:
    """Effective sort priority for a registration entry.

    Explicit `priority:` field wins. Absent → class-based default. Unknown
    class → 50 (telemetry default: in the middle, does not disrupt safety gates).
    """
    explicit = entry.get("priority")
    if isinstance(explicit, (int, float)):
        return int(explicit)
    hook_class = str(entry.get("class") or "").strip().lower()
    return _CLASS_PRIORITY_DEFAULT.get(hook_class, 50)


def materialize_hooks(registration: dict, py: str = None, mode: str = "project"):
    """Build the Claude Code `hooks` settings object from the registration.

    Returns (hooks, skipped). `hooks` is keyed by event; each event holds a list
    of matcher-groups ({matcher?, hooks:[{type:command, command}]}); entries
    sharing an (event, matcher) collapse into one group, preserving order.
    `skipped` lists (event, command) for events outside ALLOWED_EVENTS.

    `py` is the interpreter token (default: resolved per platform / HARNESS_PY).

    Entries are stable-sorted by (_priority_of(entry), declaration-index) before
    grouping so compliance hooks always precede telemetry, telemetry precedes nudge
    — independent of YAML declaration order.
    """
    if py is None:
        py = hook_interpreter()
    hooks: dict = {}
    skipped: list = []
    # Stable-sort by (priority, original-index) before grouping.
    raw_entries = list(registration.get("hooks", []) or [])
    sorted_entries = sorted(
        enumerate(raw_entries),
        key=lambda idx_entry: (_priority_of(idx_entry[1]), idx_entry[0]),
    )
    for _orig_idx, entry in sorted_entries:
        event = entry.get("event")
        command = entry.get("command", "")
        matcher = entry.get("matcher")  # may be absent (no-matcher events)
        if event not in ALLOWED_EVENTS:
            skipped.append((event, command))
            continue
        groups = hooks.setdefault(event, [])
        group = _find_group(groups, matcher)
        if group is None:
            group = {} if matcher is None else {"matcher": matcher}
            group["hooks"] = []
            groups.append(group)
        group["hooks"].append(
            {"type": "command", "command": to_command(command, py, mode)})
    return hooks, skipped


def _find_group(groups: list, matcher):
    for g in groups:
        if g.get("matcher") == matcher:
            return g
    return None


def merge_hooks(existing: dict, new: dict) -> dict:
    """Additively merge `new` into `existing`: same (event, matcher) groups are
    joined, commands deduped by string, and every user-authored event/group/hook
    is preserved. Idempotent — merging the same `new` twice adds nothing."""
    result = json.loads(json.dumps(existing)) if existing else {}
    for event, groups in new.items():
        dst_groups = result.setdefault(event, [])
        for g in groups:
            matcher = g.get("matcher")
            target = _find_group(dst_groups, matcher)
            if target is None:
                dst_groups.append(json.loads(json.dumps(g)))
                continue
            seen = {h.get("command") for h in target.get("hooks", [])}
            for h in g.get("hooks", []):
                if h.get("command") not in seen:
                    target.setdefault("hooks", []).append(
                        json.loads(json.dumps(h)))
                    seen.add(h.get("command"))
    return result


def strip_harness_hooks(existing: dict) -> dict:
    """Drop every harness-owned hook (command points into harness/hooks/),
    pruning groups and events that empty out. User-authored hooks survive.

    A None / non-dict `existing` (a `"hooks": null` hand-edit reaches callers as None
    via `settings.get("hooks", {})`, which returns the stored None for a present-null
    key) is treated as "no hooks" instead of raising a raw `None.items()`."""
    if not isinstance(existing, dict):
        return {}
    result: dict = {}
    for event, groups in existing.items():
        new_groups = []
        for g in groups:
            kept = [h for h in g.get("hooks", [])
                    if not _invokes_harness_hook(h.get("command", ""))]
            if kept:
                ng = {k: v for k, v in g.items() if k != "hooks"}
                ng["hooks"] = kept
                new_groups.append(ng)
        if new_groups:
            result[event] = new_groups
    return result
