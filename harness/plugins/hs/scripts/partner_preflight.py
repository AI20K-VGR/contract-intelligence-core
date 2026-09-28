#!/usr/bin/env python3
"""partner_preflight.py — read-only ccs discovery + a gate honest about what it
finds. `ccs api list` prints a human ANSI table (verified against a live run)
— never parsed.

Provider names are resolved from ccs's OWN config, not guessed: the unified
`<ccs-home>/config.yaml` carries a `profiles:` map whose keys are exactly the
names a `ccs <name>` call resolves — so every real profile is discovered and
none is dropped by a hardcoded exclusion (shared/local are legitimate profiles
on setups that define them, not meta-junk). Only the profile KEYS are read;
the config's other blocks and any settings file's contents (which carry
ANTHROPIC_AUTH_TOKEN) are never read or emitted. When the unified config is
absent (older ccs), discovery falls back to globbing `*.settings.json`
basenames. The ccs home is resolved (HARNESS_CCS_HOME > ~/.ccs), not a fixed
literal. This module NEVER mutates ccs config and NEVER auto-installs ccs.
"""
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

_SUFFIX = ".settings.json"


def ccs_available() -> bool:
    """True iff the ccs binary this session would invoke actually resolves.
    Respects HARNESS_CCS_CMD (the fake-seam override, mirrors HARNESS_AGY_CMD)
    so a test can point this at a binary that does not exist. The override can
    be a multi-token command line (e.g. "python3 fixtures/fake_ccs.py", the
    shape partner_transport._ccs_cmd shlex-splits) — resolvability is checked
    against its FIRST token, never the raw string with embedded spaces."""
    override = os.environ.get("HARNESS_CCS_CMD")
    if override:
        tokens = shlex.split(override)
        exe = tokens[0] if tokens else override
    else:
        exe = "ccs"
    return shutil.which(exe) is not None


def _ccs_home() -> Path:
    """~/.ccs by default; HARNESS_CCS_HOME overrides for tests (mirrors the
    HARNESS_* env-seam convention elsewhere in the partner lane)."""
    override = os.environ.get("HARNESS_CCS_HOME")
    return Path(override) if override else (Path.home() / ".ccs")


def _profiles_from_config(home):
    """The `profiles:` keys of <home>/config.yaml — ccs's authoritative
    profile list. Returns None (not []) when the config is absent or
    unusable, so the caller can distinguish "no unified config, fall back to
    the glob" from "unified config lists zero profiles". Reads ONLY the
    profile keys; never emits the config's secret-bearing blocks."""
    cfg = home / "config.yaml"
    try:
        # yaml_io (harness/scripts/) is not on sys.path by default from a
        # skill's scripts/ dir -- add it before importing, so a real config
        # read failure below is not masked as "module not found".
        _harness_scripts = str(Path(__file__).resolve().parents[3] / "scripts")
        if _harness_scripts not in sys.path:
            sys.path.append(_harness_scripts)
        import yaml_io
        data = yaml_io.safe_load(cfg.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        # A malformed/unreadable config must not crash preflight — treat it as
        # "no unified config" and let the glob fallback try.
        return None
    if not isinstance(data, dict):
        return None
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return None
    return list(profiles.keys())


def _profiles_from_glob(home):
    """Legacy fallback: `*.settings.json` basenames under the ccs home. No
    hardcoded exclusion — shared/local are valid profiles where they exist."""
    return [p.name[: -len(_SUFFIX)] for p in home.glob("*" + _SUFFIX)]


def discover_providers() -> list:
    """Resolve the live provider list from ccs's own config (profiles: keys),
    falling back to the *.settings.json glob when no unified config is present.
    A name starting with "-" is dropped (it would be mis-parsed as a CLI flag
    by `ccs <name> -p ...`), regardless of source. Sorted. Fail-open: any error
    (missing/unreadable home, no resolvable home directory) returns [] rather
    than crashing preflight — a broken discovery must never brick the check,
    only report zero providers."""
    try:
        home = _ccs_home()
        names = _profiles_from_config(home)
        if names is None:
            names = _profiles_from_glob(home)
        return sorted(n for n in names if n and not str(n).startswith("-"))
    except (OSError, RuntimeError):
        # RuntimeError: Path.home() raises this (not OSError) when HOME
        # cannot be resolved on this platform.
        return []


def validate_provider(name) -> bool:
    """A provider is only ever invoked after it is confirmed in the live
    discovery list — never call ccs with an unvalidated name; refuse to
    call blind."""
    return name in discover_providers()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ccs partner-lane preflight check")
    ap.add_argument("--check", action="store_true",
                    help="print {ccs: bool, providers: [...]} as JSON")
    args = ap.parse_args(argv)

    if not args.check:
        ap.print_usage(sys.stderr)
        return 2

    available = ccs_available()
    providers = discover_providers() if available else []
    payload = {"ccs": available, "providers": providers}
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if not available:
        sys.stderr.write(
            "partner: ccs not found on PATH — install ccs before using the "
            "ccs partner lane (see your team's ccs setup doc); never "
            "auto-installed here\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
