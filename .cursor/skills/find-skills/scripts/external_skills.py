#!/usr/bin/env python3
"""Reach the external skill ecosystem, behind a gate, and write down what came in.

An installed skill is not a library the agent calls. It is a body of INSTRUCTIONS the
agent reads and follows, loaded by name from then on, authored by someone this repo has
never met. That is why the decision to install one is not a paragraph in a skill body:
by the time it matters the paragraph is thousands of tokens back, and the package
manager's own confirmation is the first thing `-y` removes.

So the gate is here. `--allow-remote` is required before anything touches the network,
`--approved <package>` must name the SAME package being installed, the package name is
validated before a subprocess sees it, and the target is refused if it resolves inside
this repo — where a stranger's skill would sit beside ours, hashed into the same
manifest, indistinguishable from something this repo wrote and vouches for.

This script does not recommend. It parses, refuses, and records; the choice is the
user's, and popularity is not a safety property.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# `owner/repo@skill`. Deliberately narrow: this string becomes a subprocess argument
# and a directory name, and the two failure modes it prevents — a traversal segment
# and a shell-significant character — are both invisible in a happy-path test.
PACKAGE_RE = re.compile(r"\A[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*@[A-Za-z0-9][\w.-]*\Z")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
LEDGER = "external-skills.jsonl"
DEFAULT_TARGET = "~/.agents/skills"


def default_target() -> Path:
    """Where the ecosystem's own installer puts a global skill (measured, skills 1.5.23)."""
    return Path(os.path.expanduser(DEFAULT_TARGET))


def check_target(target, *, root) -> Path:
    """Refuse a destination inside this repo; return the resolved path otherwise.

    Resolved before comparing, so a path reaching back in through `..` or a symlink is
    caught by where it LANDS rather than by how it is spelled."""
    p = Path(target).expanduser().resolve()
    r = Path(root).resolve()
    if p == r or r in p.parents:
        raise ValueError(
            "refusing to install a third-party skill inside this repo (%s): it would be "
            "hashed into the harness manifest and read as ours" % p)
    return p


def parse_candidates(text: str) -> list:
    """Rows of `owner/repo@skill`, its install count, and its page.

    The banner line carries `<owner/repo@skill>` as a placeholder, so the pattern
    anchors the WHOLE line rather than searching for an `@`: `Install with npx skills
    add <owner/repo@skill>` contains a package-shaped substring and is not a result.
    An earlier version also tested for a literal `<`, which measured as unreachable —
    the anchor rejects both spellings on its own — and a guard that cannot fire tells
    the next reader the anchor is weaker than it is."""
    out, pending = [], None
    for raw in _ANSI.sub("", text).splitlines():
        line = raw.strip()
        m = re.match(r"\A([A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*@[\w .-]+?)"
                     r"(?:\s+([\d.]+[KM]?)\s+installs)?\Z", line)
        if m:
            pkg = m.group(1)
            # Measured against skills 1.5.23: a listing can print a DISPLAY name the
            # installer will not take — `claude-office-skills/skills@changelog
            # generator` came back for `changelog`, while its own page says
            # `changelog-generator`. Marked rather than silently repaired: guessing
            # the hyphenation would install whatever that guess happens to name.
            pending = {"package": pkg, "installs": m.group(2) or "", "url": "",
                       "installable": bool(PACKAGE_RE.match(pkg))}
            out.append(pending)
        elif pending is not None and line.startswith("└"):
            pending["url"] = line.lstrip("└ ").strip()
            pending = None
    return out


def _actor() -> str:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "hooks"))
        from hook_runtime import resolve_actor  # noqa: E402
        return resolve_actor()
    except Exception:  # noqa: BLE001 — attribution must not block the record
        return os.environ.get("HARNESS_ACTOR") or "unknown"


def ledger_path(state_dir=None) -> str:
    if state_dir:
        return str(Path(state_dir) / LEDGER)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))
        import harness_paths  # noqa: E402
        return str(harness_paths.state_dir() / LEDGER)
    except Exception:  # noqa: BLE001
        return str(Path("harness/state") / LEDGER)


def record_install(package: str, *, target: str, state_dir=None) -> dict:
    """One append-only line. `trust: third-party` is the field a later reader needs:
    everything else in the tree is ours, so an unlabelled entry would read as ours."""
    rec = {"package": package, "target": str(target), "trust": "third-party",
           "source": "skills.sh", "actor": _actor(),
           "ts": datetime.now(timezone.utc).isoformat()}
    p = Path(ledger_path(state_dir))
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _need_flag(args) -> None:
    if not args.allow_remote:
        print("the external ecosystem is off unless --allow-remote is passed. Resolve "
              "the local catalog first: `hs-run skills next --skill <name>` answers "
              "target_live / target_disabled / target_unknown, and only target_unknown "
              "is a reason to look outside.", file=sys.stderr)
        raise SystemExit(2)


def cmd_search(args) -> int:
    _need_flag(args)
    proc = subprocess.run(["npx", "-y", "skills@latest", "find", args.query],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          timeout=args.timeout)
    if proc.returncode != 0:
        print("the skills CLI failed: %s" % (proc.stderr.strip() or proc.returncode),
              file=sys.stderr)
        return 2
    json.dump({"query": args.query,
               "candidates": parse_candidates(proc.stdout),
               "trust": "third-party — an installed skill is instructions this agent "
                        "will follow; installs count is popularity, not safety",
               "next": "present the candidates; install only what the user names",
               "note": "installable:false means the printed name is a display name the "
                       "installer will not take — read the exact token off the "
                       "candidate's page; never guess it"},
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_install(args) -> int:
    _need_flag(args)
    if not PACKAGE_RE.match(args.package or ""):
        print("not a package name: %r (expected owner/repo@skill)" % args.package,
              file=sys.stderr)
        return 2
    if args.approved != args.package:
        print("this install is not approved. `--approved` must name the SAME package "
              "being installed; approval of one third-party skill is not approval of "
              "the next.", file=sys.stderr)
        return 2
    try:
        target = check_target(args.target or default_target(),
                              root=Path(__file__).resolve().parents[5].parent)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    proc = subprocess.run(["npx", "-y", "skills@latest", "add", args.package,
                           "-g", "-y", "--copy"],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          timeout=args.timeout)
    if proc.returncode != 0:
        print("install failed: %s" % (proc.stderr.strip() or proc.returncode),
              file=sys.stderr)
        return 2
    # --copy, not the default symlink: a symlinked body can change under us with no
    # local edit and no record, which is the one thing this ledger exists to prevent.
    rec = record_install(args.package, target=str(target), state_dir=args.state_dir)
    json.dump({"installed": rec, "stdout": proc.stdout.strip()[-2000:]},
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    # The shared options hang off BOTH the top-level parser and every subparser, so
    # `install X --allow-remote` and `--allow-remote install X` mean the same thing.
    # Otherwise the flag is positional-by-accident and the refusal a caller hits is
    # argparse's, which reads like the gate fired when it never ran.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--allow-remote", action="store_true",
                        help="required for anything that touches the network")
    common.add_argument("--timeout", type=int, default=180)
    common.add_argument("--state-dir", default=None)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", parents=[common])
    s.add_argument("query"); s.set_defaults(fn=cmd_search)
    i = sub.add_parser("install", parents=[common])
    i.add_argument("package")
    i.add_argument("--approved", default=None,
                   help="the package the user approved — must equal <package>")
    i.add_argument("--target", default=None)
    i.set_defaults(fn=cmd_install)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
