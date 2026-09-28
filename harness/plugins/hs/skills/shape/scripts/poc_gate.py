#!/usr/bin/env python3
"""poc_gate — read the tầng-1 review verdict and gate a technical proof-of-concept.

A story or task sometimes needs a technical feasibility check before it counts as
"roadmapped": does the thing actually work. That check runs entirely through the
harness's own already-closed dev loop (`hs:plan` -> `hs:cook` -> `hs:test` ->
`hs:code-review`), which already produces two machine-written verdict artifacts:
a review verdict (`review-decision.json`) and a verification verdict
(`verification.json`). This module never re-runs, re-derives, or spawns either
one — it only READS whatever the caller points it at (see
test_no_running_code_in_poc_gate / test_no_review_spawn_tokens_in_poc_gate below,
hard mechanical guards on that boundary, not just documentation) and records the
result on a POC sidecar record.

A POC is "closed" only when BOTH the review verdict and the verification verdict
read back as exactly PASS — PASS_WITH_RISK is a conscious soft-accept upstream,
not a closure license here either. Any artifact that is absent, unreadable, or
carries an unrecognized shape reads as an unknown verdict (`None`) rather than
raising: a moved/renamed artifact path, or a POC authored before the verifying
run even exists, must not crash the gate — it simply leaves the POC unclosed
until a real PASS/PASS/BLOCKED lands.

Storage: one file per POC, `<root>/docs/product/shape/poc/POC-<n>.md` (YAML
frontmatter + free-text body) — the same one-file-per-record shape the sibling
task and experiment sidecars use, so `gate()` can rewrite just that one record's
frontmatter in place without touching any sibling POC.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_paths import shape_dir, shape_path  # noqa: E402
from _sidecar import _default_actor, _now_iso, write_record, SidecarError  # noqa: E402
from _spec_bridge import load_frontmatter_parser as _load_frontmatter_parser  # noqa: E402

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


class PocError(ValueError):
    """Raised on a malformed POC input (unknown id, missing frontmatter, ...)."""


_POC_ID_RE = re.compile(r"^POC-([0-9]+)$")
_POC_FILE_RE = re.compile(r"^POC-([0-9]+)\.md$")

# Last-known verdict taxonomy, used only when the shipped schema below cannot
# be read (fail-open, matching every other reader in this module) -- NOT the
# primary source of truth (see _load_known_verdicts).
_FALLBACK_KNOWN_VERDICTS = ("PASS", "PASS_WITH_RISK", "BLOCKED")


def _load_known_verdicts() -> Tuple[str, ...]:
    """Read the verdict enum straight off the shipped harness schema
    (`harness/schemas/artifact-review-decision.json`) instead of hand-copying
    it locally -- a verdict renamed on the harness side then surfaces here
    too, instead of this module silently going stale. Falls back to the
    last-known tuple above only when the schema file itself is missing,
    unreadable, or malformed -- a moved schema must not crash `--gate`."""
    schema_path = Path(__file__).resolve().parents[5] / "schemas" / "artifact-review-decision.json"
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        enum = data["properties"]["verdict"]["enum"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return _FALLBACK_KNOWN_VERDICTS
    if isinstance(enum, list) and enum and all(isinstance(v, str) for v in enum):
        return tuple(enum)
    return _FALLBACK_KNOWN_VERDICTS


_KNOWN_VERDICTS = _load_known_verdicts()


def _assert_success_sentinel(known_verdicts: Tuple[str, ...], sentinel: str = "PASS") -> str:
    """`gate()`'s closure literal (`== "PASS"`) must be a real member of the
    schema-sourced `known_verdicts` -- otherwise a harness rename of the PASS
    verdict string would leave every future `gate()` call comparing against a
    value that can never appear, silently and permanently leaving `closed`
    False with no signal anywhere. Raises loudly (import time, via the module
    call below) rather than let that drift ride quietly."""
    if sentinel not in known_verdicts:
        raise RuntimeError(
            "poc_gate: success sentinel %r is not a member of the "
            "schema-sourced verdict set %r -- closure (`== %r`) would "
            "silently never match" % (sentinel, known_verdicts, sentinel)
        )
    return sentinel


# Fails loudly at import time if the harness verdict schema ever drops
# "PASS" -- see `_assert_success_sentinel` and gate()'s use below.
_SUCCESS_VERDICT = _assert_success_sentinel(_KNOWN_VERDICTS)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def poc_dir(root: RootLike) -> Path:
    return shape_dir(root) / "poc"


def _existing_poc_nums(root: RootLike) -> List[int]:
    d = poc_dir(root)
    if not d.exists():
        return []
    nums = []
    for p in sorted(d.glob("POC-*.md")):
        m = _POC_FILE_RE.match(p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


# ---------------------------------------------------------------------------
# Frontmatter render / read
# ---------------------------------------------------------------------------

def _render_body(poc_id: str, subject: str, title: str) -> str:
    return "# %s — %s\n\n%s\n" % (poc_id, title or poc_id, subject)


def read_poc(root: RootLike, poc_id: str) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter dict, body) for `poc_id`. Raises PocError on a missing
    file or malformed/non-mapping frontmatter -- never a raw parser traceback.

    Routed through `frontmatter_parser.parse_text` (the hardened SSOT)
    instead of a locally hand-tuned `_FRONTMATTER_RE` + `yaml.safe_load` +
    `(yaml.YAMLError, ValueError)` catch: PyYAML raises a wider family than
    that pair on malformed frontmatter -- e.g. a bare `AttributeError` from
    `construct_yaml_timestamp` on an explicit-tag `ts: !!timestamp 'not a
    ts'` -- and the SSOT already fails soft on the whole family in one place."""
    if not _POC_ID_RE.match(poc_id or ""):
        raise PocError("not a valid POC id: %r" % poc_id)
    path = shape_path(root, "poc/%s.md" % poc_id)
    return _read_poc_at(path, poc_id)


def _read_poc_at(path: Path, label: str) -> Tuple[Dict[str, Any], str]:
    """Read (frontmatter, body) from an ACTUAL on-disk POC path. Split out from
    `read_poc` so `list_pocs` can read the real glob-matched file (e.g. a
    zero-padded `POC-01.md`) instead of re-deriving a canonical `POC-<num>.md`
    path that may not exist -- mirrors task_model / experiment_spec."""
    if not path.is_file():
        raise PocError("POC not found: %s" % label)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PocError("cannot read POC file (%s): %s" % (label, exc))
    fp = _load_frontmatter_parser()
    parsed = fp.parse_text(text, file_label=str(path))
    if not parsed["ok"]:
        raise PocError("malformed POC frontmatter (%s): %s" % (label, parsed["error"]))
    return parsed["frontmatter"], parsed["body"]


def write_poc(root: RootLike, poc_id: str, record: Dict[str, Any], body: str) -> Path:
    target = shape_path(root, "poc/%s.md" % poc_id)
    write_record(target, record, body)
    return target


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------

def author(
    root: RootLike,
    subject: str,
    title: str = "",
    plan_id: Optional[str] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Allocate the next POC-<n> and write it under `shape_path()`.

    `plan_id` is optional at author time: a POC is often authored before the
    plan that will verify it even exists, so leaving it unknown here must not
    raise -- it is filled in later by `gate()` once the verifying plan runs.
    """
    if not subject or not isinstance(subject, str):
        raise PocError("subject is required (what this POC verifies)")

    d = poc_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".poc.lock"
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            nums = _existing_poc_nums(root)
            new_num = (max(nums) + 1) if nums else 1
            poc_id = "POC-%d" % new_num

            resolved_actor = actor or _default_actor()
            record: Dict[str, Any] = {
                "id": poc_id,
                "subject": subject,
                "title": title,
                "plan_id": plan_id,
                "status": "open",
                "verdict": None,
                "verification_verdict": None,
                "closed": False,
                "review_decision_path": None,
                "verification_path": None,
                "actor": resolved_actor,
                "ts": _now_iso(),
            }
            body = _render_body(poc_id, subject, title)
            target = write_poc(root, poc_id, record, body)

            result = dict(record)
            result["path"] = str(target)
            return result
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Gate: read verdict artifacts, close (or not), write back
# ---------------------------------------------------------------------------

def _read_verdict_soft(path: Optional[RootLike]) -> Tuple[Optional[str], bool]:
    """Best-effort read of a JSON artifact's top-level `verdict` field.

    Returns `(verdict, unknown)`. `verdict` is `None` (never raises) when
    `path` is falsy, the file is missing or unreadable, its content is not
    valid JSON, or the parsed value is not one of the known verdict strings.
    `unknown` is True only in that last case -- a verdict VALUE was present
    but did not match `_KNOWN_VERDICTS` -- so a renamed/typo'd verdict is
    surfaced to the caller instead of silently collapsing into the same
    "artifact absent" bucket as a missing file. A changed artifact shape or
    an absent file must not crash the gate -- it only leaves the POC unclosed.
    """
    if not path:
        return None, False
    p = Path(path)
    if not p.is_file():
        return None, False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, False
    if not isinstance(data, dict):
        return None, False
    verdict = data.get("verdict")
    if verdict is None:
        return None, False
    if verdict in _KNOWN_VERDICTS:
        return verdict, False
    return None, True


def gate(
    root: RootLike,
    poc_id: str,
    review_decision_path: RootLike,
    verification_path: Optional[RootLike] = None,
    plan_id: Optional[str] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """READ (never spawn) the review verdict artifact -- optionally paired with
    a verification artifact -- and write the result onto the POC sidecar.

    `closed` is True only when both artifacts read back as exactly PASS; a
    missing/malformed/BLOCKED artifact simply leaves the POC unclosed. `plan_id`
    updates the sidecar only when given, so calling `gate()` before the
    verifying plan's id is known does not clobber (or require) it.

    The read-modify-write below runs under an exclusive flock on the SAME
    ``.poc.lock`` sidecar `author()` already takes -- without it, two
    concurrent `gate()` calls on the same POC could each read a stale
    frontmatter dict and clobber one another's verdict/closed write.
    """
    d = poc_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".poc.lock"
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            fm, body = read_poc(root, poc_id)

            review_verdict, review_unknown = _read_verdict_soft(review_decision_path)
            verification_verdict, verification_unknown = _read_verdict_soft(verification_path)
            closed = (
                review_verdict == _SUCCESS_VERDICT
                and verification_verdict == _SUCCESS_VERDICT
            )

            updated = dict(fm)
            updated["verdict"] = review_verdict
            updated["verification_verdict"] = verification_verdict
            updated["review_decision_path"] = (
                str(review_decision_path) if review_decision_path else None
            )
            updated["verification_path"] = str(verification_path) if verification_path else None
            updated["closed"] = closed
            # Surfaced, not silently folded into "unclosed": an artifact carrying a
            # verdict value outside _KNOWN_VERDICTS (a rename/typo on the harness
            # side) is a materially different situation from a missing/absent
            # artifact, even though both leave `closed` False.
            updated["verdict_unknown"] = review_unknown or verification_unknown
            # A re-gate that now FAILS must reopen a previously-closed POC -- keeping
            # a prior "closed" status here (falling back to `updated.get("status",
            # "open")`) would let a POC read as closed on disk while `closed` itself
            # is False, the exact divergence gate()'s own docstring promises never
            # happens.
            updated["status"] = "closed" if closed else "open"
            if plan_id:
                updated["plan_id"] = plan_id
            resolved_actor = actor or _default_actor()
            updated["gated_by"] = resolved_actor
            updated["gated_ts"] = _now_iso()

            write_poc(root, poc_id, updated, body)
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    result = dict(updated)
    result["path"] = str(shape_path(root, "poc/%s.md" % poc_id))
    return result


def list_pocs(root: RootLike) -> List[Dict[str, Any]]:
    """Return frontmatter dicts for every POC-<n>.md under the POC sidecar,
    sorted by numeric id. A malformed POC file is skipped rather than
    raising -- `--list` must never surface a raw traceback over one bad
    hand-edited record."""
    d = poc_dir(root)
    if not d.exists():
        return []
    numbered = []
    for p in d.glob("POC-*.md"):
        m = _POC_FILE_RE.match(p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    out = []
    for _num, p in sorted(numbered):
        try:
            fm, _body = _read_poc_at(p, p.name)
        except PocError:
            continue
        out.append(fm)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="poc_gate.py",
        description="Author a technical-POC sidecar record, or gate one by reading an "
        "already-produced review verdict (+ optional verification verdict) artifact. "
        "Never runs, re-derives, or spawns a review.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--add", action="store_true", help="allocate + author a new POC")
    mode.add_argument("--gate", action="store_true", help="read verdict artifact(s), close or not")
    mode.add_argument("--list", action="store_true", help="list existing POCs")
    p.add_argument("--id", default=None, help="POC-<n> id (required with --gate)")
    p.add_argument("--subject", default="", help="what this POC verifies (with --add)")
    p.add_argument("--title", default="")
    p.add_argument("--plan-id", default=None, help="plans/<plan_id> this POC is verified by")
    p.add_argument("--review-decision", default=None, help="path to a review-decision artifact")
    p.add_argument("--verification", default=None, help="path to a verification artifact")
    p.add_argument("--actor", default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.add:
        try:
            record = author(
                args.root, subject=args.subject, title=args.title,
                plan_id=args.plan_id, actor=args.actor,
            )
        except (PocError, SidecarError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        print(record["id"])
        return 0
    if args.gate:
        if not args.id or not args.review_decision:
            print("error: --gate requires --id and --review-decision", file=sys.stderr)
            return 1
        try:
            result = gate(
                args.root, args.id,
                review_decision_path=args.review_decision,
                verification_path=args.verification,
                plan_id=args.plan_id,
                actor=args.actor,
            )
        except (PocError, SidecarError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        if result.get("verdict_unknown"):
            print(
                "warning: a verdict artifact carried a value outside the known "
                "verdict set -- surfaced, not silently treated as unclosed",
                file=sys.stderr,
            )
        print("%s\t%s\t%s" % (result["id"], result["verdict"],
                               "closed" if result["closed"] else "open"))
        return 0
    if args.list:
        for rec in list_pocs(args.root):
            print("%s\t%s\t%s" % (rec.get("id", ""), rec.get("verdict", ""), rec.get("status", "")))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
