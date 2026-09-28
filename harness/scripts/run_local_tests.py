#!/usr/bin/env python3
"""run_local_tests.py — run the SAME pytest command CI runs, from one subcommand.

Reading `scripts/ci.sh` prose and hand-crafting the equivalent pytest invocation drifts
over time (a scheduler/marker/flag changes on one side and not the other). This wrapper
reads `harness/data/test-strategy.yaml` (the SSOT profile table, kept in lockstep with
ci.sh by `test_run_local_tests.py::test_strategy_matches_ci_sh`) and builds the argv —
so a dev or agent runs `--harness` / `--orchestrator` / etc. instead of remembering flags.

Matching the flags is not the same job as running the same job: ci.sh also exports
TMPDIR=/dev/shm when a tmpfs has room, and every `tmp_path` lands there instead of on
disk. Measured on a 20-core remote, same tree and commit, harness suite -- bare argv
90.82-97.23s (spread 7.1%), through ci.sh 84.35-84.48s (spread 0.2%). `ci_environment()`
carries that half; the drift gate compares flags only and was green across the gap.

`build_argv` and `ci_environment` are pure (no subprocess) so they are unit-tested
directly; `main` is the only seam that shells out, and `--all` always runs its profiles SEQUENTIALLY — a personal
16-core box does not want two xdist fan-outs contending for the same cores at once.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml_io

_DEFAULT_STRATEGY_PATH = Path(__file__).resolve().parent.parent / "data" / "test-strategy.yaml"

# --all runs the 3 full suites sequentially (harness/orchestrator/release) — the
# dev-loop-only `harness-fast` subset and the sub-second `scoring` check are each a
# single flag away and are not folded into --all.
_ALL_PROFILES = ("harness", "orchestrator", "release")

# argparse dest (dashes -> underscores) -> profile key in test-strategy.yaml.
_FLAG_TO_PROFILE = {
    "harness": "harness",
    "harness_fast": "harness-fast",
    "orchestrator": "orchestrator",
    "release": "release",
    "scoring": "scoring",
    "plugin_skills": "plugin-skills",
}


def load_strategy(path) -> Dict[str, Dict[str, Any]]:
    """Parse + validate test-strategy.yaml's `profiles` table. Raises ValueError on a
    missing/empty table or a profile entry missing its required `path` key — a caller
    should not get a confusing KeyError three calls deep in build_argv."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml_io.safe_load(text) or {}
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"{path}: missing or empty 'profiles' table")
    for name, cfg in profiles.items():
        if not isinstance(cfg, dict) or "path" not in cfg:
            raise ValueError(f"{path}: profile '{name}' missing required 'path' key")
    return profiles


def build_argv(profile: str, strategy: Dict[str, Dict[str, Any]]) -> List[str]:
    """Pure argv builder — path, -q, xdist scheduler (unless xdist: false), marker,
    -p no:randomly, per-ignore flags. No subprocess call here; that lives in main()."""
    if profile not in strategy:
        raise ValueError(f"unknown profile '{profile}' — known: {sorted(strategy)}")
    cfg = strategy[profile]
    path = cfg["path"]
    argv: List[str] = ["python3", "-m", "pytest", path, "-q"]

    if cfg.get("xdist", True) is not False:
        scheduler = cfg.get("scheduler", "load")
        argv += ["-n", "auto", "--dist", scheduler]

    marker = cfg.get("marker")
    if marker:
        argv += ["-m", marker]

    if cfg.get("norandomly"):
        argv += ["-p", "no:randomly"]

    for name in cfg.get("ignore") or []:
        argv.append(f"--ignore={path}/{name}")

    return argv


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--harness", action="store_true", help="full harness/tests, loadfile")
    group.add_argument("--harness-fast", action="store_true", help="harness subset, skips the heaviest files")
    group.add_argument("--orchestrator", action="store_true", help="orchestrator/tests, loadfile")
    group.add_argument("--release", action="store_true", help="release/tests, --dist load")
    group.add_argument("--scoring", action="store_true", help="orchestrator/tests -m scoring_contract")
    group.add_argument("--plugin-skills", action="store_true", help="harness/plugins/hs/skills, loadfile")
    group.add_argument("--all", action="store_true", help="harness + orchestrator + release, sequentially")
    parser.add_argument("--strategy", default=str(_DEFAULT_STRATEGY_PATH), help="path to test-strategy.yaml")
    parser.add_argument(
        "--collect-only", "--dry",
        dest="dry", action="store_true",
        help="pass --collect-only through to pytest so scope/count can be confirmed without running tests",
    )
    return parser


# ci.sh's tmpfs floor, mirrored here rather than shelled out to, because build_argv()
# must stay pure. 10 GiB = one run (measured 6.4-6.7 GiB of temp trees) plus 50%. A box
# that cleared the old 4 GiB floor could not hold a single run, and overrunning it kills
# pytest with INTERNALERROR on a worker whose test passes alone, with nothing in the
# message about space. NOT one run x pytest's retention of 3: that sizing refused a host
# with 20.8 GiB free whose prep had just cleaned it.
# test_the_tmpfs_floor_covers_what_a_run_actually_writes pins both copies.
_TMPFS_FLOOR_KB = 10538188


def _tmpfs_with_room(path="/dev/shm"):
    """True when `path` is a writable tmpfs with ci.sh's floor free. Separate from
    ci_environment so a test can state the machine condition instead of inheriting
    it -- this developer box runs at 1.4 GiB free, below the floor, so a test that
    read the real filesystem could never exercise the branch that matters (measured:
    both mutations of the resolver survived until this seam existed)."""
    # hasattr, not try/except OSError: on Windows os.statvfs does not EXIST, so the call
    # raises AttributeError and an `except OSError` misses it entirely
    # (test_no_product_module_calls_a_posix_only_os_function_unguarded reddens on it).
    # No statvfs also means no /dev/shm, so False is the right answer there anyway.
    if not hasattr(os, "statvfs"):
        return False
    if not (os.path.isdir(path) and os.access(path, os.W_OK)):
        return False
    try:
        st = os.statvfs(path)
    except OSError:
        return False
    return st.f_bavail * st.f_frsize // 1024 >= _TMPFS_FLOOR_KB


def ci_environment(env=None, *, tmpfs_has_room=None):
    """ci.sh's execution ENVIRONMENT, not just its argv.

    Matching the pytest flags is not the same job as running the same job. `ci.sh`
    exports TMPDIR=/dev/shm when a tmpfs has room, and that changes where every
    `tmp_path` lands -- the install family copies a ~28MB tree per test. Measured on a
    20-core remote, same tree and commit, harness suite: bare argv 90.82-97.23s with a
    7.1% spread, through ci.sh 84.35-84.48s with a 0.2% spread. The drift gate
    (test_strategy_matches_ci_sh) compares flags only and was green across all of it."""
    env = dict(os.environ if env is None else env)
    if tmpfs_has_room is None:
        tmpfs_has_room = _tmpfs_with_room()
    if not env.get("TMPDIR") and tmpfs_has_room:
        env["TMPDIR"] = "/dev/shm"
    return env


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    strategy = load_strategy(args.strategy)

    if args.all:
        profiles = list(_ALL_PROFILES)
    else:
        profiles = [profile for flag, profile in _FLAG_TO_PROFILE.items() if getattr(args, flag)]

    exit_code = 0
    for profile in profiles:
        cmd = build_argv(profile, strategy)
        if args.dry:
            cmd = cmd + ["--collect-only"]
        print(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd, env=ci_environment())
        if result.returncode != 0:
            exit_code = result.returncode
            break
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
