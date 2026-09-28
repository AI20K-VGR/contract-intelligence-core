#!/usr/bin/env python3
"""stamp_artifact.py — PostToolUse hook: stamp harness provenance into plan/
report markdown as it is written (telemetry-class).

After a Write/Edit to a markdown file under plans/, this re-reads the file and
merges the harness version stamp into its frontmatter, so the artifact's origin
travels WITH it (copied off-host, it still names the harness version + tree
fingerprint that produced it). The release identity is read FRESH each fire, so
an upgrade applied mid-session lands on artifacts written afterward.

The write happens at the hook layer (plain file I/O, not the Write tool), so it
neither re-triggers PostToolUse nor trips write_guard (which gates the tool, not
a script's own write). The stamp is deterministic (no wall-clock), so re-firing
on every write reaches a fixed point. Fail-open + config gate are owned by
hook_runtime.run_telemetry_hook; scope is plans/**/*.md only.

Hook stdin protocol: { tool_name, tool_input: { file_path }, ... }.
"""

import os
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import harness_paths  # noqa: E402
import harness_release  # noqa: E402
import artifact_stamp  # noqa: E402

HOOK_CLASS = "telemetry"

_STEM = Path(__file__).stem


def _target_under_plans(file_path: str, root: Path):
    """The resolved path if it is a markdown file under plans/, else None."""
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    if p.suffix != ".md":
        return None
    try:
        p.relative_to((root / "plans").resolve())
    except ValueError:
        return None
    return p


def core(data: dict) -> None:
    inp = (data or {}).get("tool_input") or {}
    # TWO roots, two jobs — one variable cannot carry both.
    #
    # WHERE the artifact lives is a PROJECT question: plans/ is a project tree,
    # so under a global install the shared bin placed no real plan md and this
    # hook looked inert (same defect as phase_progress_writer's snapshot).
    #
    # WHICH engine stamped it is a BIN question: release.json is vendored beside
    # the engine, never copied into a project. Reading it from the project root
    # falls through to the dev fallback and writes `0.0.0-dev` + an empty digest
    # over a correct stamp — a downgrade is worse than the no-op it replaced,
    # because the artifact then carries a confident wrong answer. scaffold.py's
    # _release() documents the same split.
    #
    # Under self-host the two coincide, which is exactly why mixing them up
    # stays invisible here and only shows on a real global install.
    root = harness_paths.project_root()
    target = _target_under_plans(inp.get("file_path"), root)
    if target is None or not target.is_file():
        return
    rel = harness_release.read_release(harness_paths.bin_root())
    artifact_stamp.stamp_file(
        target, rel.get("harness_version", ""), rel.get("kit_digest", ""))


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
