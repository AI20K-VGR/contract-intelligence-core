#!/usr/bin/env python3
"""migrate_voice_output.py — migrate old terminal-voice.yaml schema to the new split schema.

Old schema (pre-split):
  terminal-voice.yaml carries `output_style` (code verbosity, 0..5) and
  `detail_level` (concise|standard|verbose — interview/turn verbosity).

New schema (post-split):
  output.yaml carries `code_style` (same semantic as output_style, 0..5).
  terminal-voice.yaml carries `terminal_voice_level` (0..5, absorbs detail_level).
  No `output_style` or `detail_level` in either file.

The runtime shims in voice_prefs.py and output_config.py already handle old
installs at read time. This script rewrites BOTH yaml files in a single pass:
read terminal-voice.yaml first, extract both legacy values, then write
terminal-voice.yaml, then write output.yaml.

Dry-run (default): prints a diff of what WOULD change, writes nothing.
--apply: backup both files, then migrate. Safe: backup suffix .bak.

Migration is idempotent: if the file already uses the new schema, no-op.
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

_TV_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "terminal-voice.yaml"
_OUT_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "output.yaml"

# detail_level → terminal_voice_level mapping (same as the runtime shim in voice_prefs.py)
_DETAIL_LEVEL_MAP = {"concise": 2, "standard": 3, "verbose": 5}


def _load_raw(path: str) -> dict:
    """Load a yaml file; return {} on missing/malformed."""
    import yaml_io
    try:
        raw = yaml_io.safe_load(Path(path).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (FileNotFoundError, OSError, yaml_io.YAMLError):
        return {}


def _existing_header(path: str) -> str:
    """The leading comment/blank header of an existing yaml file, kept across
    the migration rewrite (shared config_io extractor). Missing file → empty."""
    import config_io
    return config_io.leading_comment_block(path, "")


# Canonical output.yaml key order, mirroring output_config._CANONICAL_KEYS
# (kept in sync by hand — output_config is caged; do NOT import it here).
_OUTPUT_CANONICAL_ORDER = ("language", "humanize", "audience", "code_style")


def _ordered_output(data: dict) -> dict:
    """output.yaml keys in canonical order (language, humanize, audience,
    code_style); any unknown key is appended in its existing order."""
    ordered = {k: data[k] for k in _OUTPUT_CANONICAL_ORDER if k in data}
    for k in data:
        ordered.setdefault(k, data[k])
    return ordered


def _save_yaml(path: str, data: dict, header: str = "", *, sort: bool = True) -> None:
    """Write data to path as YAML, preserving a leading header comment if provided."""
    import yaml_io
    body = yaml_io.safe_dump(data, sort_keys=sort, allow_unicode=True, default_flow_style=False)
    Path(path).write_text(header + body, encoding="utf-8")


def migrate(tv_path: str = None,
            out_path: str = None,
            apply: bool = False,
            *,
            backup: bool = True) -> dict:
    """Run migration: read legacy fields, compute new values, print diff.

    If apply=True, backup both files and write the new values.
    Returns a dict with 'tv_changes' and 'out_changes' (what would change / changed).
    Idempotent: if neither old field is present, no-op.
    """
    if tv_path is None:
        tv_path = str(_TV_DEFAULT)
    if out_path is None:
        out_path = str(_OUT_DEFAULT)

    tv_path = str(tv_path)
    out_path = str(out_path)

    # Read BOTH files first (order: read tv first, then read out)
    tv_data = _load_raw(tv_path)
    out_data = _load_raw(out_path)

    # Extract legacy values
    old_output_style = tv_data.get("output_style")  # int or None
    old_detail_level = tv_data.get("detail_level")  # str or None

    # Validate legacy output_style
    if old_output_style is not None:
        if not isinstance(old_output_style, int) or not (0 <= old_output_style <= 5):
            old_output_style = None  # ignore invalid values

    # Compute new values
    tv_changes = {}
    out_changes = {}

    # terminal-voice.yaml changes
    if old_output_style is not None:
        tv_changes["remove_output_style"] = old_output_style
    if old_detail_level is not None:
        tv_changes["remove_detail_level"] = old_detail_level
        # Map detail_level → terminal_voice_level only if not already explicitly set
        if "terminal_voice_level" not in tv_data and old_detail_level in _DETAIL_LEVEL_MAP:
            new_tvl = _DETAIL_LEVEL_MAP[old_detail_level]
            tv_changes["set_terminal_voice_level"] = new_tvl

    # output.yaml changes
    # Set code_style from old output_style, only if output.yaml doesn't already have code_style
    if old_output_style is not None and out_data.get("code_style") is None:
        out_changes["set_code_style"] = old_output_style

    # Check if this is already a no-op
    no_op = not tv_changes and not out_changes

    # Print diff
    if no_op:
        print("migrate_voice_output: no legacy fields found — already migrated (no-op).")
    else:
        print("migrate_voice_output: planned changes (dry-run=%s):" % (not apply))
        if tv_changes:
            print("  terminal-voice.yaml:")
            for k, v in tv_changes.items():
                print("    %s: %r" % (k, v))
        if out_changes:
            print("  output.yaml:")
            for k, v in out_changes.items():
                print("    %s: %r" % (k, v))

    if not apply or no_op:
        return {"tv_changes": tv_changes, "out_changes": out_changes, "noop": no_op}

    # Apply: backup both files first (backup before any write)
    if backup:
        for path in (tv_path, out_path):
            p = Path(path)
            if p.exists():
                shutil.copy2(path, path + ".bak")

    # Rewrite terminal-voice.yaml: strip output_style + detail_level, set new tvl if needed
    new_tv = {k: v for k, v in tv_data.items()
              if k not in ("output_style", "detail_level")}
    if "set_terminal_voice_level" in tv_changes:
        new_tv["terminal_voice_level"] = tv_changes["set_terminal_voice_level"]
    _save_yaml(tv_path, new_tv, header=_existing_header(tv_path))

    # Rewrite output.yaml: add code_style from old output_style (canonical key order)
    if out_changes:
        new_out = dict(out_data)
        if "set_code_style" in out_changes:
            new_out["code_style"] = out_changes["set_code_style"]
        _save_yaml(out_path, _ordered_output(new_out),
                   header=_existing_header(out_path), sort=False)

    print("  Applied. Backups: %s.bak / %s.bak" % (tv_path, out_path))
    return {"tv_changes": tv_changes, "out_changes": out_changes, "noop": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Migrate terminal-voice.yaml from the pre-split schema. "
            "Dry-run by default (prints diff, writes nothing). "
            "Use --apply to execute."
        )
    )
    ap.add_argument("--tv", default=None, metavar="PATH",
                    help="path to terminal-voice.yaml (default: shipped data file)")
    ap.add_argument("--out", default=None, metavar="PATH",
                    help="path to output.yaml (default: shipped data file)")
    ap.add_argument("--apply", action="store_true",
                    help="write the migration (default: dry-run only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="explicit preview: print the diff, write nothing (the default; "
                         "named so an onboard step can invoke it literally)")
    ap.add_argument("--check", action="store_true",
                    help="surfacing probe: preview only, then exit 1 if legacy keys are "
                         "present (migration needed), 0 if already clean (no-op). Writes nothing.")
    ap.add_argument("--no-backup", action="store_true",
                    help="skip creating .bak backups before writing (not recommended)")
    args = ap.parse_args(argv)

    if args.apply and (args.dry_run or args.check):
        sys.stderr.write("migrate_voice_output: --apply cannot combine with --dry-run/--check\n")
        return 2

    # --check / --dry-run both force preview (no write); --check also reflects the
    # legacy state in the exit code so a surfacing step can branch on it.
    apply = args.apply and not (args.dry_run or args.check)
    result = migrate(
        tv_path=args.tv,
        out_path=args.out,
        apply=apply,
        backup=not args.no_backup,
    )
    if args.check:
        return 1 if not result.get("noop") else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
