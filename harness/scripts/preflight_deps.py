#!/usr/bin/env python3
"""preflight_deps.py — check that external deps the harness needs are importable
AND at a declared version.

Policy: external deps are allowed but CONTROLLED — harness/requirements.txt is the
single registry (range per package, REQUIRED/OPTIONAL tag), this script is the single
reader that turns it into a runnable gate. Run it once per machine after clone (and in
CI before tests).

Two distinct failure modes, both actionable:
  - a REQUIRED module that does not import at all -> the exact `pip install` command.
  - a REQUIRED module that imports fine but is OUTSIDE its declared range (e.g.
    `pyyaml==3.13`, a 2016 release: `import yaml` succeeds, `yaml.safe_load()` itself
    raises `AttributeError`) -> flagged by version, not silently passed.
OPTIONAL is never a failure — neither missing nor out-of-range. Both are reported,
because the second one was previously not looked for at all, which left half the
registry outside the very check the first two bullets exist for.

Posture downstream when someone skips this step:
  - compliance hooks fail CLOSED (exit 2 + the same install command),
  - telemetry/nudge hooks skip silently.

Usage:
    python3 harness/scripts/preflight_deps.py            # human report
    python3 harness/scripts/preflight_deps.py --quiet    # exit code only (hooks/CI)
"""

import importlib
import importlib.metadata
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REQUIREMENTS_FILE = _HERE.parent / "requirements.txt"

# pip distribution name -> import module name, ONLY where the default
# hyphen-to-underscore rule gets it wrong (e.g. "pytest-cov" -> "pytest_cov" already
# matches the rule; "PyYAML" -> "pyyaml" does not, the real module is "yaml").
_MODULE_OVERRIDES = {
    "pyyaml": "yaml",
    "python-dotenv": "dotenv",
    "pytest-xdist": "xdist",
    # The wheel's importable name is the top-level `_ruamel_yaml` C extension
    # module, NOT `ruamel.yaml.clib` (confirmed via the installed wheel's
    # RECORD/top_level.txt: it ships `_ruamel_yaml.*.so` at site-packages root,
    # no `ruamel/yaml/clib/` package dir at all). `import ruamel.yaml.clib`
    # always raises even when the C extension is correctly installed and live
    # (see yaml_io.py / test_yaml_io.py, which check it via CParser instead).
    "ruamel.yaml.clib": "_ruamel_yaml",
    # The pip name's trailing "-py" is not part of the importable package —
    # the wheel installs a top-level `markdown_it/` package, not `markdown_it_py`.
    "markdown-it-py": "markdown_it",
}

# One declaration line: `PackageName>=X,<Y  # REQUIRED` (or `# OPTIONAL`). The tag is a
# trailing machine-readable marker; the prose comment above each line (WHY / what
# happens if absent) is for humans and is not parsed.
_DECL_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9._-]*)\s*(?P<specifier>[^#]*?)\s*#\s*"
    r"(?P<tag>REQUIRED|OPTIONAL)\s*$"
)


def _module_name(pip_name: str) -> str:
    key = pip_name.lower()
    return _MODULE_OVERRIDES.get(key, key.replace("-", "_"))


def parse_requirements(path: Path = None):
    """Parse the declaration file into (required, optional, ranges).

    required / optional: {import module name: pip distribution name} — the exact shape
    this module's REQUIRED/OPTIONAL have always had, so release/sbom.py and every
    existing caller needs no change when the declaration moves into a file.
    ranges: {import module name: (pip_name, version specifier string)}.
    """
    path = path or _REQUIREMENTS_FILE
    required, optional, ranges = {}, {}, {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _DECL_RE.match(line)
        if not m:
            continue
        pip_name = m.group("name")
        specifier = m.group("specifier").strip()
        module = _module_name(pip_name)
        ranges[module] = (pip_name, specifier)
        if m.group("tag") == "REQUIRED":
            required[module] = pip_name
        else:
            optional[module] = pip_name
    return required, optional, ranges


REQUIRED, OPTIONAL, _RANGES = parse_requirements()


def missing_required() -> list:
    """Return pip names of REQUIRED deps that cannot be imported at all.

    Version range violations are a SEPARATE, deliberate check (version_violations) —
    a module that imports fine is not "missing" in this function's sense, even if it is
    the wrong version.
    """
    out = []
    for module, pip_name in REQUIRED.items():
        try:
            importlib.import_module(module)
        except ImportError:
            out.append(pip_name)
    return out


def missing_optional() -> list:
    """Return pip names of OPTIONAL deps that cannot be imported.
    Does NOT fail — caller decides whether to warn.
    """
    out = []
    for module, pip_name in OPTIONAL.items():
        try:
            importlib.import_module(module)
        except ImportError:
            out.append(pip_name)
    return out


def _installed_version(pip_name: str):
    try:
        return importlib.metadata.version(pip_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _out_of_range(tier: dict) -> list:
    """Return (pip_name, reason) for deps in TIER that import fine but whose installed
    version is outside the declared range.

    `packaging` is itself a REQUIRED dep and its own absence is reported through the
    normal missing_required() path; if that import fails this function degrades to
    reporting nothing rather than crashing the whole script on it.
    """
    out = []
    try:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
        from packaging.version import InvalidVersion, Version
    except ImportError:
        return out
    for module, pip_name in tier.items():
        try:
            importlib.import_module(module)
        except ImportError:
            continue  # the missing-dep paths already report this
        _, specifier = _RANGES.get(module, (pip_name, ""))
        if not specifier:
            continue
        installed = _installed_version(pip_name)
        if installed is None:
            continue  # importable but no distribution metadata -- nothing to compare
        try:
            in_range = Version(installed) in SpecifierSet(specifier)
        except (InvalidVersion, InvalidSpecifier):
            continue
        if not in_range:
            out.append((pip_name, "%s %s does not satisfy the declared range %s"
                        % (pip_name, installed, specifier)))
    return out


def version_violations() -> list:
    """REQUIRED deps installed outside their declared range — a FAILURE (exit 1).

    This is the pyyaml==3.13 gap closed: that release imports without error and only
    breaks when `yaml.safe_load()` is actually called, so a plain import check alone
    reports OK on a broken install.
    """
    return _out_of_range(REQUIRED)


def optional_version_warnings() -> list:
    """OPTIONAL deps installed outside their declared range — a WARNING (still exit 0).

    The version check used to cover the REQUIRED tier only, which left the pyyaml==3.13
    shape — imports cleanly, fails at the call — completely unwatched for half the
    registry. Reporting it is worth doing; failing on it is not: this tier's contract is
    that absence never blocks the gate, and "present at an undeclared version" is a
    weaker signal than "absent", not a stronger one.
    """
    return _out_of_range(OPTIONAL)


def install_command(missing: list) -> str:
    return "pip install " + " ".join(sorted(missing))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    quiet = "--quiet" in argv
    missing = missing_required()
    violations = version_violations()
    if not missing and not violations:
        if not quiet:
            print("preflight OK: " + ", ".join(sorted(REQUIRED.values())))
            opt = missing_optional()
            if opt:
                sys.stderr.write(
                    "optional deps missing: %s — %s\n" % (
                        ", ".join(opt), install_command(opt)))
            stale = optional_version_warnings()
            if stale:
                sys.stderr.write(
                    "optional deps outside their declared range (warning, not a "
                    "failure):\n    %s\n" % "\n    ".join(r for _, r in stale))
        return 0
    if not quiet:
        if missing:
            sys.stderr.write(
                "preflight FAILED — missing dependencies: %s\n"
                "Install with:\n    %s\n" % (", ".join(missing), install_command(missing))
            )
        if violations:
            reasons = [reason for _, reason in violations]
            pins = [pip_name for pip_name, _ in violations]
            sys.stderr.write(
                "preflight FAILED — installed but outside the declared range:\n    %s\n"
                "Install with:\n    %s\n" % ("\n    ".join(reasons), install_command(pins))
            )
    return 1


# Backward compatibility: install.py and hooks call missing_deps().
missing_deps = missing_required


if __name__ == "__main__":
    sys.exit(main())
