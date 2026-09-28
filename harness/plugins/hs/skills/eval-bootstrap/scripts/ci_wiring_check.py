#!/usr/bin/env python3
"""ci_wiring_check.py — advisory: is the stamped eval CI file actually WIRED
into the repo's real pipeline, or just sitting in evals/ci/?

Closes lỗ #2: the scaffold stamps ONE CI file per forge (github ->
evals/ci/production-evals.yml, gitlab -> evals/ci/.gitlab-ci-evals.yml) and
stops. A file in evals/ci/ never runs on its own — github needs it under
.github/workflows/, gitlab needs the root .gitlab-ci.yml to `include:` it. This
check reads the card's `forge` and verifies the stamped file is PLACED where
that forge would execute it.

WIRED means "placed correctly", NOT "already ran on push/PR" (F6): a github
workflow with `on: workflow_dispatch` only is WIRED-but-caveated — placed right,
but it does not trigger automatically.

Advisory by construction: exit 0 always in the default mode (never blocks a
turn), `--strict` exits 1 on anything other than WIRED for a hard gate. It is
LOUD — never a silent pass — when it cannot determine wiring (no card / no
stamped CI file): an INDETERMINATE verdict, not a quiet OK (the exact
importorskip-silent failure mode this fix targets).

Stdlib only; never imports harness/scripts/ — self-contained like the rest of
this skill.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from pathlib import Path

WIRED = "WIRED"
NOT_WIRED = "NOT_WIRED"
INDETERMINATE = "INDETERMINATE"

_GH_EVAL_FILE = "production-evals.yml"
_GH_NAME_MARKER = "name: Production Evals"
_GL_EVAL_FILE = ".gitlab-ci-evals.yml"


def _load_forge(config_path: Path):
    """Read `forge` from the card JSON. Returns None when the card is missing
    or unreadable (-> INDETERMINATE, LOUD)."""
    if not config_path.is_file():
        return None
    try:
        card = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    forge = card.get("forge") if isinstance(card, dict) else None
    return forge if isinstance(forge, str) and forge.strip() else None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _strip_comments(text: str) -> str:
    """Drop YAML comments — both whole-line (`# ...`) and inline trailing
    (` value  # ...`) — so a mention of the eval file / a trigger keyword inside
    a comment is not mistaken for real wiring. A `#` not preceded by whitespace
    (e.g. inside `a#b` or a URL fragment) is left intact."""
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        out.append(re.sub(r"\s+#.*$", "", ln))
    return "\n".join(out)


def _runs_on_push_or_pr(text_no_comments: str) -> bool:
    """Does this workflow declare a REAL push / pull_request trigger? Scoped to
    the `on:` declaration so an unrelated `docker push` step name does not count.
    Handles the block form (`push:` key) and the inline-list form
    (`on: [push, workflow_dispatch]`). Comments already stripped by the caller."""
    if re.search(r"^\s*(push|pull_request)\s*:", text_no_comments, re.M):
        return True
    m = re.search(r"^\s*on\s*:\s*\[([^\]]*)\]", text_no_comments, re.M)
    return bool(m and re.search(r"\b(push|pull_request)\b", m.group(1)))


def _check_github(target: Path):
    stamped = target / "evals" / "ci" / _GH_EVAL_FILE
    if not stamped.is_file():
        return (INDETERMINATE,
                "no stamped eval workflow at evals/ci/%s — nothing to wire "
                "(run the scaffold first)" % _GH_EVAL_FILE)

    workflows = target / ".github" / "workflows"
    if not workflows.is_dir():
        return (NOT_WIRED,
                "the eval workflow is only in evals/ci/ — copy it into "
                ".github/workflows/ so GitHub Actions runs it on push/PR")

    for wf in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
        body = _strip_comments(_read(wf))
        if wf.name == _GH_EVAL_FILE or _GH_NAME_MARKER in body:
            if "workflow_dispatch" in body and not _runs_on_push_or_pr(body):
                return (WIRED,
                        "eval workflow present at .github/workflows/%s — BUT "
                        "`on: workflow_dispatch` only: placed correctly yet it "
                        "does NOT run automatically on push/PR" % wf.name)
            return (WIRED, "eval workflow present at .github/workflows/%s" % wf.name)

    return (NOT_WIRED,
            "no eval workflow found under .github/workflows/ — copy "
            "evals/ci/%s there so it runs on push/PR" % _GH_EVAL_FILE)


def _check_gitlab(target: Path):
    stamped = target / "evals" / "ci" / _GL_EVAL_FILE
    if not stamped.is_file():
        return (INDETERMINATE,
                "no stamped eval CI at evals/ci/%s — nothing to wire "
                "(run the scaffold first)" % _GL_EVAL_FILE)

    root_ci = target / ".gitlab-ci.yml"
    if not root_ci.is_file():
        return (NOT_WIRED,
                "no root .gitlab-ci.yml — create one with an `include:` pointing "
                "at evals/ci/%s so the eval jobs run" % _GL_EVAL_FILE)

    if _GL_EVAL_FILE in _strip_comments(_read(root_ci)):
        return (WIRED, "root .gitlab-ci.yml includes evals/ci/%s" % _GL_EVAL_FILE)

    return (NOT_WIRED,
            "root .gitlab-ci.yml does not include the eval CI — add "
            "`include: {local: 'evals/ci/%s'}`" % _GL_EVAL_FILE)


def check(target: Path, config_path: Path):
    forge = _load_forge(config_path)
    if forge is None:
        return (INDETERMINATE,
                "cannot read a `forge` from %s — no card, so wiring is "
                "undeterminable (NOT a pass: fix the card, then re-check)"
                % config_path)
    if forge == "github":
        return _check_github(target)
    if forge == "gitlab":
        return _check_gitlab(target)
    return (INDETERMINATE, "unknown forge %r (expected github|gitlab)" % forge)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Advisory check: is the stamped eval CI file wired into the "
                    "repo's real pipeline? (exit 0 always unless --strict)")
    parser.add_argument("--target", required=True, help="repo root to inspect")
    parser.add_argument("--config", default=None,
                        help="path to eval_config.json (default: <target>/evals/eval_config.json)")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on anything other than WIRED (default is advisory exit 0)")
    args = parser.parse_args(argv)

    target = Path(args.target)
    config_path = Path(args.config) if args.config else target / "evals" / "eval_config.json"

    verdict, guidance = check(target, config_path)
    print("%s: %s" % (verdict, guidance))
    if verdict == INDETERMINATE:
        print("WARNING: wiring is INDETERMINATE — this is LOUD on purpose, not a "
              "silent pass; do not claim 'CI wired' until this resolves to WIRED.",
              file=sys.stderr)
    elif verdict == NOT_WIRED:
        print("WARNING: CI is NOT_WIRED — do not claim 'CI wired'.", file=sys.stderr)

    if args.strict and verdict != WIRED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
