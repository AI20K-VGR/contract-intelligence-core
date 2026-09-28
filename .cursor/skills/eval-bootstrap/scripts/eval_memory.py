#!/usr/bin/env python3
"""eval_memory.py -- two-tier append-only JSONL memory store (L4 lock).

Tier-1 (per-repo, tracked): `<target>/evals/_memory/<type>.jsonl` for types
`lesson`/`incident`/`decision` -- a team + CI-visible record, needs
`--target`. Tier-2 (per-machine, cross-repo): type `standard` routes to a
resolved harness state home under `.../eval-memory/<type>.jsonl`. `--tier`
overrides the type's default routing.

Record schema (one JSON object per line): `schema_version, actor, ts, type,
id, domain, surface, stack, card_hash, body`. `id` is `<type>-<ts-compact>-
<4hex>` (4hex from `os.urandom(2)`) so a later protocol can cite it. `actor`
is `HARNESS_USER` env else `getpass.getuser()` -- attribution, not
authentication.

Honesty on redaction (read before trusting this as a PII control): `append`
runs the body through an email + phone-digit-run regex mask before writing,
plus a payload-shaped heuristic warning -- this is "email + phone redaction,
NOT a PII guarantee". A name, address, DOB, or ID number is NOT caught by
either regex. The load-bearing rule for tier-1 (git-tracked, forever) is
procedural: the body must be a lesson DESCRIPTION plus a sample-ID reference
-- never pasted raw sample content.

Honesty on write-atomicity: `append` wraps the write in `fcntl.flock(LOCK_EX)`
(POSIX/Linux) because a body over PIPE_BUF (4096 bytes) is NOT guaranteed
atomic under a naive O_APPEND write -- two concurrent unicode-heavy appends
can interleave mid-line and get silently dropped by `recall`'s tolerant
parser. This guarantee holds ONLY for writers going through this script on a
local Linux filesystem: NFS can no-op an flock silently, and a foreign writer
(git, a text editor, `echo >>`) is never locked out. `recall` itself does NOT
lock (it only reads) -- tolerant-read (skip a bad line, count it) is the
final backstop, not a first line of defense. Windows has no `fcntl`; this
script falls back to a dedicated create-exclusive lockfile there (see
`_append_locked_windows`) -- OS-native behavior, never exercised by this
repo's Linux CI.

Stdlib only. Paths resolve off `__file__` (never CWD); never imports
harness/scripts/ (this skill is self-contained). Reuses `eval_scaffold.
is_self_target` (tier-1 fence) and `eval_config`'s card-hash sidecar (for
`--auto-hash`) as SIBLING imports, same discipline as eval_config.py.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_config  # noqa: E402  (sibling import -- reuse card-hash sidecar)
import eval_scaffold  # noqa: E402  (sibling import -- self-target fence)

try:
    import fcntl
except ImportError:  # Windows has no POSIX flock
    fcntl = None


SCHEMA_VERSION = "1.0"

_TIER1_TYPES = frozenset({"lesson", "incident", "decision"})
_TIER2_TYPES = frozenset({"standard"})
_ALL_TYPES = _TIER1_TYPES | _TIER2_TYPES

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\d{7,}")

# PIPE_BUF on Linux -- the byte count a single write(2) is guaranteed atomic
# up to WITHOUT our own lock; also a reasonable "a lesson should be short"
# ceiling for the warning below.
MAX_BODY_BYTES = 4096


# --------------------------------------------------------------------------
# Tier-2 home resolution -- explicit per-OS branch, stdlib only.
# --------------------------------------------------------------------------

def _tier2_home() -> Path:
    """Per-machine, cross-repo home for `standard` records. Precedence:
    HARNESS_STATE_DIR (highest -- keeps e2e/isolation working) > per-OS
    default. Deliberately NOT `bin_root()` -- that is a read-only zone under
    global-install (hardened mode crashes, non-hardened silently writes
    cross-user, and it is lost on upgrade)."""
    override = os.environ.get("HARNESS_STATE_DIR")
    if override:
        return Path(override).expanduser() / "eval-memory"

    plat = sys.platform
    if plat.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or "~/AppData/Local"
        return Path(base).expanduser() / "harness" / "eval-memory"
    if plat == "darwin":
        return Path("~/Library/Application Support").expanduser() / "harness" / "eval-memory"

    # Linux (and other POSIX): copy of harness_paths.py:engine_home's
    # relative-XDG guard -- drift between the two must be kept in sync by
    # hand. A relative XDG_DATA_HOME is invalid per the XDG spec; `.resolve()`
    # on it would anchor to CWD (the exact bug this guard avoids), so we do
    # NOT add an "absolutize" branch -- just fall back to the default.
    base = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    if base != "~/.local/share" and not os.path.isabs(os.path.expanduser(base)):
        base = "~/.local/share"          # relative XDG invalid -> fall back to default
    return Path(base).expanduser() / "harness" / "eval-memory"


def _tier1_dir(target: str) -> Path:
    return Path(target) / "evals" / "_memory"


def _default_tier_for_type(type_: str) -> str:
    return "1" if type_ in _TIER1_TYPES else "2"


# --------------------------------------------------------------------------
# Locked append -- the O_APPEND-atomicity fix (a >4KB concurrent append can
# interleave and be silently lost without an exclusive lock around the write).
# --------------------------------------------------------------------------

def _append_locked(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is not None:
        fd = os.open(str(path), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                os.write(fd, data)
                os.fsync(fd)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    else:
        _append_locked_windows(path, data)


def _append_locked_windows(path: Path, data: bytes) -> None:
    """No fcntl on Windows. `msvcrt.locking()` locks a BYTE RANGE from the
    current file pointer -- a different primitive from flock's whole-file
    advisory lock, and awkward to map onto O_APPEND correctly. A dedicated
    create-exclusive lockfile alongside the data file is the simpler,
    unambiguous serialization primitive here. OS-native; this path is never
    exercised by this repo's CI (Linux-only)."""
    lock_path = path.with_name(path.name + ".lock")
    while True:
        try:
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.01)
    try:
        with open(path, "ab") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        os.close(lock_fd)
        os.unlink(lock_path)


# --------------------------------------------------------------------------
# Body mask (defence-in-depth, NOT a PII guarantee)
# --------------------------------------------------------------------------

def _looks_like_payload(body: str) -> bool:
    """Heuristic ONLY, never a hard gate: a body shaped like a data dump
    (very long, one long unbroken run, or many delimiter chars) probably has
    raw sample content pasted in rather than a lesson description. Steers
    the caller toward citing a sample-ID; does not block the append."""
    if len(body) > 800:
        return True
    if re.search(r"\S{60,}", body):
        return True
    if body.count("\n") > 6:
        return True
    if len(re.findall(r"[,|\t]", body)) > 20:
        return True
    return False


def _prepare_body(raw_body: str) -> str:
    if _looks_like_payload(raw_body):
        print(
            "WARNING: body looks like it may contain raw sample content -- "
            "reference a sample-ID and describe the lesson instead of pasting "
            "sample data.", file=sys.stderr)

    masked = _EMAIL_RE.sub("***@***.***", raw_body)
    masked = _PHONE_RE.sub(lambda m: "*" * len(m.group(0)), masked)

    encoded_len = len(masked.encode("utf-8"))
    if encoded_len > MAX_BODY_BYTES:
        print(
            "WARNING: body is %d bytes (> %d) -- a lesson should be short; "
            "consider trimming." % (encoded_len, MAX_BODY_BYTES), file=sys.stderr)
    return masked


# --------------------------------------------------------------------------
# Record construction
# --------------------------------------------------------------------------

def _build_record(type_: str, domain: str, surface: str, stack: str, body: str,
                   card_hash) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    ts_compact = re.sub(r"[^0-9]", "", ts)
    rid = "%s-%s-%s" % (type_, ts_compact, os.urandom(2).hex())
    actor = os.environ.get("HARNESS_USER") or getpass.getuser()
    return {
        "schema_version": SCHEMA_VERSION,
        "actor": actor,
        "ts": ts,
        "type": type_,
        "id": rid,
        "domain": domain,
        "surface": surface,
        "stack": stack,
        "card_hash": card_hash,
        "body": body,
    }


def _auto_card_hash(target: str):
    _, _json_path, sha_path = eval_config._card_paths(target)
    if not sha_path.is_file():
        print(
            "ERROR: no eval_config.sha256 under %s -- run eval_config.py write first"
            % sha_path.parent, file=sys.stderr)
        return None
    digest = sha_path.read_text(encoding="utf-8").strip()
    return "sha256:" + digest


# --------------------------------------------------------------------------
# append
# --------------------------------------------------------------------------

def cmd_append(args) -> int:
    if args.type not in _ALL_TYPES:
        print("ERROR: --type must be one of %s" % ", ".join(sorted(_ALL_TYPES)),
              file=sys.stderr)
        return 2

    if args.auto_hash and args.card_hash:
        print("ERROR: pass either --card-hash or --auto-hash, not both", file=sys.stderr)
        return 2

    tier = args.tier or _default_tier_for_type(args.type)

    if tier == "1":
        if not args.target:
            print("ERROR: tier-1 (type=%s) requires --target" % args.type, file=sys.stderr)
            return 2
        if eval_scaffold.is_self_target(args.target):
            print(
                "ERROR: self-target fence: %r is the harness/orchestrator repo that "
                "hosts this skill -- refusing to write eval memory into it."
                % args.target, file=sys.stderr)
            return 2
        record_dir = _tier1_dir(args.target)
    else:
        record_dir = _tier2_home()

    card_hash = None
    if args.auto_hash:
        if not args.target:
            print("ERROR: --auto-hash requires --target", file=sys.stderr)
            return 2
        card_hash = _auto_card_hash(args.target)
        if card_hash is None:
            return 2
    elif args.card_hash:
        card_hash = args.card_hash

    raw_body = sys.stdin.read() if args.body == "-" else args.body
    body = _prepare_body(raw_body)

    record = _build_record(args.type, args.domain, args.surface, args.stack, body, card_hash)
    path = record_dir / (args.type + ".jsonl")
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"

    try:
        _append_locked(path, line.encode("utf-8"))
    except OSError as e:
        print("ERROR: write failed: %s" % e, file=sys.stderr)
        return 2

    print(record["id"])
    return 0


# --------------------------------------------------------------------------
# recall
# --------------------------------------------------------------------------

def _parse_filters(raw) -> dict:
    if not raw:
        return {}
    filters = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError("--filter: %r is not a key=value pair" % part)
        key, value = part.split("=", 1)
        filters[key.strip()] = value.strip()
    return filters


_NULL_FILTER_SENTINELS = {"none", "null"}


def _coerce_filter_value(value):
    # A record whose card_hash (or any field) is JSON null stores Python None;
    # a --filter value arrives as the string "None"/"null" and would never
    # match it. Map those sentinels back to None so `card_hash=None` filters
    # the un-hashed records as intended. Real hashes are 'sha256:...' tokens,
    # never these words, so there is no collision.
    if isinstance(value, str) and value.lower() in _NULL_FILTER_SENTINELS:
        return None
    return value


def _matches(record: dict, filters: dict) -> bool:
    return all(record.get(k) == _coerce_filter_value(v) for k, v in filters.items())


def _read_jsonl_tolerant(path: Path):
    records = []
    bad = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if not isinstance(rec, dict):
                bad += 1
                continue
            records.append(rec)
    return records, bad


def _resolve_recall_tiers(args):
    if args.tier == "1":
        return ["1"]
    if args.tier == "2":
        return ["2"]
    if args.tier == "both":
        return ["1", "2"]
    if args.type:
        return ["1"] if args.type in _TIER1_TYPES else ["2"]
    return ["1", "2"]


def cmd_recall(args) -> int:
    try:
        filters = _parse_filters(args.filter)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    tiers = _resolve_recall_tiers(args)
    if tiers == ["1"] and not args.target:
        print("ERROR: tier-1 recall requires --target", file=sys.stderr)
        return 2

    records = []
    skipped = 0
    for tier in tiers:
        if tier == "1":
            if not args.target:
                continue  # opportunistic "both" search -- skip tier-1 silently
            record_dir = _tier1_dir(args.target)
            candidate_types = [args.type] if args.type else sorted(_TIER1_TYPES)
        else:
            record_dir = _tier2_home()
            candidate_types = [args.type] if args.type else sorted(_TIER2_TYPES)

        for t in candidate_types:
            path = record_dir / (t + ".jsonl")
            if not path.is_file():
                continue
            recs, bad = _read_jsonl_tolerant(path)
            skipped += bad
            records.extend(recs)

    matched = [r for r in records if _matches(r, filters)]
    matched.sort(key=lambda r: str(r.get("ts", "")), reverse=True)
    top = matched[: args.limit]

    for r in top:
        print(json.dumps(r, sort_keys=True, ensure_ascii=False))
    print("# skipped_corrupt: %d" % skipped, file=sys.stderr)
    return 0


# --------------------------------------------------------------------------
# verify-home
# --------------------------------------------------------------------------

def cmd_verify_home(args) -> int:
    print("tier-2: %s" % _tier2_home())
    if args.target:
        print("tier-1: %s" % _tier1_dir(args.target))
    else:
        print("tier-1: (pass --target to resolve for a specific repo)")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Two-tier append-only JSONL memory store for eval-bootstrap "
                    "(tier-1 per-repo lesson/incident/decision, tier-2 cross-repo "
                    "per-machine standard). See module docstring for the honesty "
                    "scope on redaction and write-atomicity.")
    sub = parser.add_subparsers(dest="verb", required=True)

    p_append = sub.add_parser("append")
    p_append.add_argument("--type", required=True, choices=sorted(_ALL_TYPES))
    p_append.add_argument("--domain", required=True)
    p_append.add_argument("--surface", required=True)
    p_append.add_argument("--stack", required=True)
    p_append.add_argument("--body", required=True, help='lesson text, or "-" to read from stdin')
    p_append.add_argument("--target", default=None, help="target repo (required for tier-1 types)")
    p_append.add_argument("--card-hash", default=None)
    p_append.add_argument("--auto-hash", action="store_true",
                           help="derive card_hash from --target's evals/eval_config.sha256")
    p_append.add_argument("--tier", choices=("1", "2"), default=None,
                           help="override the type's default tier routing")

    p_recall = sub.add_parser("recall")
    p_recall.add_argument("--filter", default=None, help="k=v,k=v (AND-ed)")
    p_recall.add_argument("--limit", type=int, required=True,
                           help="max records to print -- required, never dumps the whole file")
    p_recall.add_argument("--type", default=None, choices=sorted(_ALL_TYPES))
    p_recall.add_argument("--target", default=None)
    p_recall.add_argument("--tier", choices=("1", "2", "both"), default=None)

    p_home = sub.add_parser("verify-home")
    p_home.add_argument("--target", default=None)

    args = parser.parse_args(argv)

    if args.verb == "append":
        return cmd_append(args)
    if args.verb == "recall":
        return cmd_recall(args)
    return cmd_verify_home(args)


if __name__ == "__main__":
    sys.exit(main())
