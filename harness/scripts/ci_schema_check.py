#!/usr/bin/env python3
"""Sole owner of the CI schema/config parse check.

Parses the hand-edited YAML config allowlist + every schema JSON, then runs
verify_install.py --strict. Exit != 0 if any file fails to parse or the manifest
drifts. Every CI face calls this via `ci.sh schema` instead of embedding its own copy
of the file list — that copy-paste is exactly what let one face carry a stale reference
to a since-removed data file while another face never listed it. One list, one home.
"""
import glob
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Hand-edited YAML config CI must be able to parse. This is the single authoritative
# list — every entry names a file that exists in the tree; no phantom entries.
_CONFIG_YAML = [
    "harness/data/harness-hooks.yaml",
    "harness/data/stage-policy.yaml",
    "harness/data/ownership.yaml",
    "harness/data/skill-chains.yaml",
    "harness/data/guard-policy.yaml",
    "harness/data/protected-branches.yaml",
    "harness/data/terminal-voice.yaml",
    "harness/install/hooks-registration.yaml",
]


def main() -> int:
    import yaml_io  # lazy: dep is declared + checked in preflight_deps

    for rel in _CONFIG_YAML:
        path = _ROOT / rel
        try:
            with path.open(encoding="utf-8") as fh:
                yaml_io.safe_load(fh)
        except FileNotFoundError:
            print(f"ci_schema_check: config file missing: {rel}", file=sys.stderr)
            return 1
        except yaml_io.YAMLError as exc:
            print(f"ci_schema_check: YAML parse error in {rel}: {exc}", file=sys.stderr)
            return 1
    print("yaml ok")

    for path in sorted(glob.glob(str(_ROOT / "harness" / "schemas" / "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"ci_schema_check: JSON parse error in {path}: {exc}", file=sys.stderr)
            return 1
    print("schemas ok")

    verify = _ROOT / "harness" / "scripts" / "verify_install.py"
    result = subprocess.run([sys.executable, str(verify), "--strict"], cwd=str(_ROOT))
    if result.returncode != 0:
        print("ci_schema_check: verify_install --strict failed", file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
