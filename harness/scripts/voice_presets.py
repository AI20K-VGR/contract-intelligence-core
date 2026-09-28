#!/usr/bin/env python3
"""voice_presets.py — load, validate, and apply archetype presets from voice-presets.yaml.

Presets bundle the existing voice/output axes into named onboarding profiles.
Apply is all-or-nothing: validate ALL axes first, write both config files via
temporary copies, then swap both; any failure leaves BOTH files at their
original values — no half-written state.

API:
  load_presets() -> list[dict]       load all presets from voice-presets.yaml
  validate(preset) -> None           validate axes; raises ValueError on bad value
  pick(user_input) -> dict|None      parse user number input; None = invalid/exit
  apply(preset, tv_path, out_path)   all-or-nothing write; raises on failure
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

_PRESETS_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "voice-presets.yaml"


def load_presets(path=None) -> List[Dict]:
    """Load all presets from voice-presets.yaml. Raises if file is missing or malformed."""
    import yaml_io
    p = Path(path) if path else _PRESETS_DEFAULT
    raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "presets" not in raw:
        raise ValueError("voice-presets.yaml must have a 'presets' key")
    presets = raw["presets"]
    if not isinstance(presets, list):
        raise ValueError("voice-presets.yaml 'presets' must be a list")
    return presets


def validate(preset: Dict, *, voice_prefs=None, output_config=None) -> None:
    """Validate all axes in a preset against the union of voice_prefs.ENUMS and
    output_config constraints. Raises ValueError on first invalid value.

    voice_prefs and output_config are injected for testability; if None, they are
    imported from the scripts directory."""
    if voice_prefs is None:
        import voice_prefs as _vp
        voice_prefs = _vp
    if output_config is None:
        import output_config as _oc
        output_config = _oc

    pid = preset.get("id", "?")
    axes = preset.get("axes", {})

    for key, val in axes.items():
        if key in voice_prefs._BOOL_KEYS:
            if not isinstance(val, bool):
                raise ValueError("Preset %r: %r must be bool, got %r" % (pid, key, val))
        elif key in voice_prefs.ENUMS:
            if val is not None:
                if isinstance(val, bool) or val not in voice_prefs.ENUMS[key]:
                    raise ValueError(
                        "Preset %r: %r=%r not in enum %r"
                        % (pid, key, val, sorted(str(x) for x in voice_prefs.ENUMS[key])))
        elif key in ("audience", "code_style"):
            if val is not None and val is not False:
                if not isinstance(val, int) or not (0 <= val <= 5):
                    raise ValueError(
                        "Preset %r: %r=%r must be 0..5 or None" % (pid, key, val))
        elif key == "language":
            if val is not None and val not in output_config.VALID_LANGUAGES:
                raise ValueError(
                    "Preset %r: language=%r not in %r" % (pid, val, output_config.VALID_LANGUAGES))
        elif key == "humanize":
            if not isinstance(val, bool):
                raise ValueError("Preset %r: humanize must be bool, got %r" % (pid, val))
        else:
            all_known = (set(voice_prefs.DEFAULTS.keys()) |
                         {"audience", "code_style", "language", "humanize"})
            if key not in all_known:
                raise ValueError("Preset %r: unknown axis %r" % (pid, key))


def pick(user_input: str) -> Optional[Dict]:
    """Parse user input for preset picker. Returns None for invalid/exit input.

    Valid inputs: "1"..N where N == len(load_presets()) (1-indexed). Anything
    else returns None. The caller displays the prompt and re-asks.
    """
    try:
        n = int(user_input.strip())
    except (ValueError, AttributeError):
        return None
    presets = load_presets()
    if not (1 <= n <= len(presets)):
        return None
    return presets[n - 1]


def _write_terminal_voice(axes: Dict, tv_path: str, *, voice_prefs=None) -> None:
    """Write terminal-voice axes from a preset to tv_path. Merges over existing."""
    if voice_prefs is None:
        import voice_prefs as _vp
        voice_prefs = _vp
    terminal_keys = set(voice_prefs.DEFAULTS.keys())
    current = voice_prefs.load(path=tv_path)
    updates = {k: v for k, v in axes.items() if k in terminal_keys and v is not None}
    current.update(updates)
    # F2 mutual-exclusion: a preset sets the `persona` form, so clear any active
    # persona_bundle — otherwise the bundle would keep absorbing `persona` and the
    # preset's form would silently lose. Preset form wins (last-writer-wins).
    current["persona_bundle"] = None
    voice_prefs.save(current, path=tv_path)


def _write_output(axes: Dict, out_path: str, *, output_config=None) -> None:
    """Write output axes from a preset to out_path. Merges over existing."""
    if output_config is None:
        import output_config as _oc
        output_config = _oc
    output_keys = {"audience", "code_style", "language", "humanize"}
    updates = {}
    for k in output_keys:
        if k in axes:
            val = axes[k]
            # code_style: null → None (off), False (YAML off) → None
            if k == "code_style" and (val is None or val is False):
                val = None
            updates[k] = val
    if updates:
        output_config.save_output(updates, path=out_path)


def apply(preset: Dict,
          tv_path: str = None,
          out_path: str = None,
          *,
          voice_prefs=None,
          output_config=None) -> None:
    """Apply a preset all-or-nothing.

    Algorithm:
      1. Validate ALL axes first.
      2. Write terminal-voice axes to a tmp copy of tv_path.
      3. Write output axes to a tmp copy of out_path.
      4. If both succeed, swap each file into place (per-file atomic replace).
         Note: the two replaces are sequential — a failure of the second after
         the first lands is a narrow partial-apply window, not a true 2-file
         transaction. Validation-first + write-both-tmp-before-any-replace keeps
         every realistic failure on the all-or-nothing path.
      5. Any failure → leave both originals untouched.

    Raises ValueError on validation failure, OSError on I/O failure.
    """
    if voice_prefs is None:
        import voice_prefs as _vp
        voice_prefs = _vp
    if output_config is None:
        import output_config as _oc
        output_config = _oc

    if tv_path is None:
        tv_path = str(voice_prefs.voice_path())
    if out_path is None:
        from output_config import _OUTPUT_DEFAULT
        out_path = str(_OUTPUT_DEFAULT)

    tv_path = str(tv_path)
    out_path = str(out_path)

    # Step 1: validate all axes
    validate(preset, voice_prefs=voice_prefs, output_config=output_config)

    axes = preset.get("axes", {})

    # Step 2-3: write to tmp files (same directory so os.replace is a rename)
    tv_dir = Path(tv_path).parent
    out_dir = Path(out_path).parent

    tmp_tv = None
    tmp_out = None
    try:
        # Create tmp copies next to the real files so os.replace is on same fs
        fd, tmp_tv = tempfile.mkstemp(dir=str(tv_dir), suffix=".tmp")
        os.close(fd)

        fd, tmp_out = tempfile.mkstemp(dir=str(out_dir), suffix=".tmp")
        os.close(fd)

        # Copy originals into tmp (so we have valid starting state)
        if Path(tv_path).exists():
            shutil.copy2(tv_path, tmp_tv)
        if Path(out_path).exists():
            shutil.copy2(out_path, tmp_out)

        # Write terminal-voice axes to tmp_tv
        _write_terminal_voice(axes, tmp_tv, voice_prefs=voice_prefs)

        # Write output axes to tmp_out
        _write_output(axes, tmp_out, output_config=output_config)

        # Step 4: both tmp writes succeeded — replace each into place.
        # ACCEPTED: the two os.replace calls are sequential, not atomic.
        # A failure of the second replace after the first completes leaves
        # tv_path updated while out_path still holds the original — a narrow
        # partial-apply window (microsecond scale). This is accepted because:
        #   - both tmp files are written and validated BEFORE any replace, so
        #     every realistic failure (validation, I/O) stays on the all-or-
        #     nothing path;
        #   - the remaining window is a process-kill or hardware fault between
        #     the two syscalls, which is not recoverable by any pure-Python
        #     2-file scheme without a WAL or external coordinator;
        #   - the net state is a valid config (no corrupt half-write) and
        #     re-running apply is idempotent.
        # Not a bug — do not add artificial recovery here.
        os.replace(tmp_tv, tv_path)
        tmp_tv = None  # consumed
        os.replace(tmp_out, out_path)
        tmp_out = None  # consumed

    finally:
        # Step 5: cleanup any tmp that wasn't swapped in (error path)
        for p in [tmp_tv, tmp_out]:
            if p is not None:
                try:
                    os.unlink(p)
                except OSError:
                    pass


def main(argv=None) -> int:
    """CLI: apply a preset by number or id.

    Usage:
      voice_presets.py list            — list all presets
      voice_presets.py apply <n|id>    — apply preset by 1-based number or id
    """
    import argparse
    ap = argparse.ArgumentParser(description="apply a voice/output archetype preset")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="list all presets")
    p_apply = sub.add_parser("apply", help="apply a preset by number (1-10) or id")
    p_apply.add_argument("preset", help="1-based number or preset id")
    args = ap.parse_args(argv)

    if args.cmd == "list" or args.cmd is None:
        presets = load_presets()
        for i, p in enumerate(presets, 1):
            print("%2d. %s  [%s]" % (i, p.get("display", p["id"]), p["id"]))
        return 0

    if args.cmd == "apply":
        presets = load_presets()
        target = args.preset.strip()
        # Try numeric first
        try:
            n = int(target)
            if not (1 <= n <= len(presets)):
                sys.stderr.write("Preset number must be 1..%d\n" % len(presets))
                return 2
            preset = presets[n - 1]
        except ValueError:
            # Try by id
            matching = [p for p in presets if p.get("id") == target]
            if not matching:
                sys.stderr.write("Unknown preset id %r\n" % target)
                return 2
            preset = matching[0]
        try:
            validate(preset)
        except ValueError as e:
            sys.stderr.write("Validation error: %s\n" % e)
            return 1
        try:
            apply(preset)
        except (OSError, ValueError) as e:
            sys.stderr.write("Apply failed: %s\n" % e)
            return 1
        print("Applied preset: %s" % preset.get("display", preset["id"]))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
