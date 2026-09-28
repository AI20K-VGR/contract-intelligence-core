#!/usr/bin/env python3
"""verify_trace_chain.py — read-only re-walk of the audit hash-chain.

Walks sorted trace-YYYYMMDD.jsonl files under the state/trace/ directory,
re-computing chain_hash for each record and reporting breaks.

Exit codes:
  0 — chain intact (may have FORK warnings for concurrent-append artifacts)
  1 — BREAK detected (tampered/deleted record) or missing post-cutover chain_hash
  2 — usage error

Subcommands:
  verify_trace_chain.py [--state-dir DIR] [--all | --date YYYYMMDD]
  verify_trace_chain.py anchor [--state-dir DIR] [--date YYYYMMDD]

The 'anchor' subcommand emits JSON {date, final_hash, count, cutover} to stdout
for the operator to commit outside the attacker's write zone. It does NOT write
any git-tracked file or invoke git.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Import _chain_hash directly from trace_log to avoid drift (DRY).
# Resolve via __file__ rather than CWD (code-standards §2).
_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(_HOOKS_DIR))

try:
    from trace_log import _chain_hash, _checkpoint_path, _read_checkpoint
except ImportError:
    # Fallback: inline the pure function if trace_log unavailable
    def _chain_hash(prev, record):  # noqa: F811
        rec_no_chain = {k: v for k, v in record.items() if k != "chain_hash"}
        canonical = json.dumps(
            rec_no_chain, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(
            ((prev or "") + canonical).encode("utf-8")
        ).hexdigest()

    def _checkpoint_path(trace_dir, date_str):  # noqa: F811
        return trace_dir / ("trace-checkpoint-%s.json" % date_str)

    def _read_checkpoint(trace_dir, date_str):  # noqa: F811
        try:
            p = _checkpoint_path(trace_dir, date_str)
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None


def _default_state_dir() -> Path:
    here = Path(__file__).resolve()
    harness_dir = here.parent.parent
    return harness_dir / "state" / "trace"


def _read_cutover_ts(trace_dir: Path) -> "str | None":
    """Find chain_cutover_ts from any checkpoint that carries it."""
    try:
        for cp_file in sorted(trace_dir.glob("trace-checkpoint-*.json")):
            try:
                cp = json.loads(cp_file.read_text(encoding="utf-8"))
                if "chain_cutover_ts" in cp:
                    return cp["chain_cutover_ts"]
            except Exception:
                continue
    except Exception:
        pass
    return None


def _list_files(trace_dir: Path, date_filter: "str | None" = None) -> list:
    if date_filter:
        # A date targets BOTH the legacy daily file AND that day's per-session
        # shards (trace-<date>-<disc>.jsonl) — else `verify --date`/`anchor --date`
        # silently skip a day that has only shards (false-clean).
        out = []
        legacy = trace_dir / ("trace-%s.jsonl" % date_filter)
        if legacy.exists():
            out.append(legacy)
        out.extend(sorted(trace_dir.glob("trace-%s-*.jsonl" % date_filter)))
        return out
    return sorted(trace_dir.glob("trace-*.jsonl"))


def _date_of_file(path: Path) -> str:
    return path.name[len("trace-"):-len(".jsonl")]


def _partition_files(files: list) -> tuple:
    """Split into (legacy, shards). Legacy = `trace-YYYYMMDD.jsonl` (the middle is
    exactly 8 digits). Shards = `trace-YYYYMMDD-<disc>.jsonl` (P2), each an
    INDEPENDENT chain from its own genesis. They must NOT share chain state: a
    shard sorts before the same-day legacy (ASCII '-' < '.'), so a shared walk
    would carry the shard's prev into the legacy file and false-BREAK (R3)."""
    legacy, shards = [], []
    for f in files:
        mid = _date_of_file(f)
        (legacy if (len(mid) == 8 and mid.isdigit()) else shards).append(f)
    return legacy, shards


def _walk_files(files: list, trace_dir: Path, cutover_ts, use_checkpoints: bool):
    """Walk a group of trace files as ONE continuous chain, returning
    (total_records, pre_chain_skipped, break_found, fork_found). Legacy files
    carry prev across day-rollover checkpoints (use_checkpoints=True); a single
    shard is its own independent chain from genesis (use_checkpoints=False,
    seen_hashed + prev reset per call)."""
    total_records = 0
    pre_chain_skipped = 0
    break_found = False
    fork_found = False
    # Once ANY record has carried a chain_hash the chain is ACTIVE. With no cutover
    # checkpoint we cannot date the pre-chain era, so a LATER hashless record is a
    # deleted-hash tamper — not a pre-chain artifact.
    seen_hashed = False
    prev_chain = ""  # "" = genesis

    for i, fpath in enumerate(files):
        # If not the first file, try prev from the preceding file's checkpoint.
        if use_checkpoints and i > 0:
            prev_date = _date_of_file(files[i - 1])
            cp = _read_checkpoint(trace_dir, prev_date)
            if cp and cp.get("final_hash"):
                prev_chain = cp["final_hash"]
            # else: prev_chain stays as the last hash from the prior file

        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception as e:
            print("ERROR: cannot read %s: %s" % (fpath, e))
            break_found = True
            continue

        lines = [l for l in content.splitlines() if l.strip()]
        file_prev = prev_chain  # track prev within this file

        for lineno, line in enumerate(lines, start=1):
            try:
                rec = json.loads(line)
            except Exception:
                print("BREAK at %s line %d: invalid JSON" % (fpath.name, lineno))
                break_found = True
                continue

            ts = rec.get("ts", "")
            stored_hash = rec.get("chain_hash")
            total_records += 1

            # Pre-chain handling
            if stored_hash is None:
                if cutover_ts and ts >= cutover_ts:
                    print("BREAK at %s line %d ts=%s: post-cutover record missing chain_hash"
                          % (fpath.name, lineno, ts))
                    break_found = True
                elif cutover_ts is None and seen_hashed:
                    print("BREAK at %s line %d ts=%s: missing chain_hash after chain "
                          "active (no cutover checkpoint — deleted-hash tamper)"
                          % (fpath.name, lineno, ts))
                    break_found = True
                else:
                    pre_chain_skipped += 1
                continue

            seen_hashed = True
            expected = _chain_hash(file_prev, rec)

            if expected == stored_hash:
                file_prev = stored_hash
            elif stored_hash == _chain_hash(prev_chain, rec) and stored_hash != file_prev:
                # Fork: self-consistent with the original prev but not the current
                # file_prev — a concurrent-append artifact, hash-valid either way.
                print("WARN FORK at %s line %d ts=%s: concurrent-append detected"
                      % (fpath.name, lineno, ts))
                fork_found = True
            else:
                # BREAK BY DESIGN: over-report a suspected tamper rather than
                # silently accept an unknown chain branch.
                print("BREAK at %s line %d ts=%s: chain_hash mismatch"
                      " (expected %.12s... got %.12s...)"
                      % (fpath.name, lineno, ts, expected, stored_hash))
                break_found = True
                file_prev = stored_hash  # advance anyway to keep detecting

        prev_chain = file_prev

    return total_records, pre_chain_skipped, break_found, fork_found


def verify(trace_dir: Path, date_filter: "str | None" = None) -> int:
    """Walk the chain and print findings. Returns exit code. Legacy daily files
    and per-session shards (P2) are partitioned and walked as SEPARATE chains
    (R3): legacy carries cross-day checkpoints, each shard is genesis-independent."""
    files = _list_files(trace_dir, date_filter)
    if not files:
        print("No trace files found in %s" % trace_dir)
        return 0

    legacy, shards = _partition_files(files)
    cutover_ts = _read_cutover_ts(trace_dir)

    total_records = 0
    pre_chain_skipped = 0
    break_found = False
    fork_found = False

    # Legacy chain: cross-day checkpoints carry prev between daily files.
    if legacy:
        t, p, b, f = _walk_files(legacy, trace_dir, cutover_ts, use_checkpoints=True)
        total_records += t; pre_chain_skipped += p; break_found |= b; fork_found |= f

    # Each shard is an independent chain from its own genesis — NO cutover, NO
    # checkpoint carry, fresh seen_hashed (R3).
    for shard in shards:
        t, p, b, f = _walk_files([shard], trace_dir, None, use_checkpoints=False)
        total_records += t; pre_chain_skipped += p; break_found |= b; fork_found |= f

    if cutover_ts:
        print("Pre-chain records skipped (ts < cutover=%s): %d" % (cutover_ts, pre_chain_skipped))
    else:
        if pre_chain_skipped:
            print("Pre-chain records skipped (no cutover ts found): %d" % pre_chain_skipped)

    if break_found:
        print("RESULT: BREAK — chain integrity violated (%d total records)" % total_records)
        return 1

    print("OK: %d records verified across %d files%s" % (
        total_records, len(files),
        (" (with FORK warnings)" if fork_found else "")
    ))
    return 0


def anchor(trace_dir: Path, date_filter: "str | None" = None) -> int:
    """Print head digest JSON for operator to commit externally. No git writes."""
    files = _list_files(trace_dir, date_filter)
    if not files:
        sys.stderr.write("No trace files found in %s\n" % trace_dir)
        return 1

    # The durable audit anchor is the legacy daily chain; prefer the newest
    # LEGACY file so a same-day shard never hijacks the anchor target. Fall back
    # to the newest shard only when no legacy file exists at all. Either way the
    # emitted `date` is the 8-char YYYYMMDD prefix — never a shard's
    # "YYYYMMDD-<disc>" stem, which is not a valid date.
    legacy, _shards = _partition_files(files)
    target = legacy[-1] if legacy else files[-1]
    date_str = _date_of_file(target)[:8]

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        sys.stderr.write("ERROR: cannot read %s: %s\n" % (target, e))
        return 1

    lines = [l for l in content.splitlines() if l.strip()]
    count = 0
    final_hash = ""
    for line in lines:
        try:
            rec = json.loads(line)
            h = rec.get("chain_hash")
            if h:
                final_hash = h
            count += 1
        except Exception:
            pass

    cutover_ts = _read_cutover_ts(trace_dir)
    out = {"date": date_str, "final_hash": final_hash, "count": count}
    if cutover_ts:
        out["cutover"] = cutover_ts
    print(json.dumps(out, ensure_ascii=False))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only re-walk of audit hash-chain",
    )
    parser.add_argument("--state-dir", default=None,
                        help="Path to trace directory (default: harness/state/trace)")
    parser.add_argument("--all", action="store_true", help="Verify all files")
    parser.add_argument("--date", default=None, help="Verify a specific date YYYYMMDD")
    subparsers = parser.add_subparsers(dest="subcommand")

    # anchor subcommand. It carries its own --state-dir/--date so the documented
    # form `anchor --state-dir DIR --date X` parses (argparse does not let a main
    # parser option follow a subcommand token).
    anchor_p = subparsers.add_parser("anchor", help="Emit head digest JSON for operator")
    # Distinct dest so the subparser's default None never clobbers a main-parser
    # --state-dir that was given before the `anchor` token.
    anchor_p.add_argument("--state-dir", default=None, dest="anchor_state_dir",
                          help="Path to trace directory (default: harness/state/trace)")
    anchor_p.add_argument("--date", default=None, help="Date YYYYMMDD (default: latest)")

    args = parser.parse_args()

    # Resolve state dir: a subcommand --state-dir wins, else the main-parser one.
    state_dir_raw = getattr(args, "anchor_state_dir", None) or args.state_dir
    if state_dir_raw:
        trace_dir = Path(state_dir_raw)
    else:
        trace_dir = _default_state_dir()

    if args.subcommand == "anchor":
        date_filter = args.date
        sys.exit(anchor(trace_dir, date_filter))
    else:
        date_filter = args.date if not args.all else None
        sys.exit(verify(trace_dir, date_filter))


if __name__ == "__main__":
    main()
