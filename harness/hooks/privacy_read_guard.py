#!/usr/bin/env python3
"""privacy_read_guard.py — block reads of secret files behind human approval (compliance).

PreToolUse:Read gate. When the LLM tries to Read a likely-secret file
(.env / .env.* , *.pem , *.key , credentials , secrets.yaml , id_rsa / id_ed25519)
the read is BLOCKED (exit 2) and an @@PRIVACY_PROMPT@@ marker carrying
AskUserQuestion JSON is emitted, so the controller surfaces the decision to the
human. On approval the file is read out-of-band via `bash cat <path>` (this gate
matches the Read tool only, so the approved bash read passes); on denial the agent
continues without the file.

Restores the upstream block->approve control that an earlier port had downgraded
to an advisory nudge. Compliance posture: default ON (a gate that ships asleep
protects nothing), fail-closed on its OWN errors, fail-open on absent/unparseable
input — blocking every Read on a transport hiccup would brick the session, and an
unparseable payload names no file to gate. example/sample/template files are
documentation and are exempt. HOOK_CLASS lives here in code, never in config.

Known residual (documented, not silently ignored): the human is asked, but the
approved read travels over `bash cat`, which this Read-matcher gate does not see —
a deliberately-evasive agent could read a secret straight over bash without
tripping the gate. Closing that fully means gating bash file-reads too (high
false-positive cost) or an out-of-band approval store; tracked in BACKLOG.
"""

import json
import os
import re
import sys
from pathlib import Path

# Block text is ASCII, but guard stderr encoding so a non-UTF-8 locale degrades to
# replacement chars instead of raising mid-write.
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older/detached streams; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "compliance"
_NAME = Path(__file__).stem

# Documentation/template files carrying these suffixes are exempt — they ship in
# repos as examples and hold no real secrets.
_SAFE = re.compile(r"\.(example|sample|template)$", re.IGNORECASE)

# Likely-secret path shapes (ported detection set). Matched against the full path
# so an absolute or nested target still trips (anchors use (^|/) and $).
# All patterns are case-INSENSITIVE: on a case-insensitive filesystem (macOS,
# Windows) `.ENV` IS the real `.env`, so a case variant must trip the same gate
# — a case-sensitive pattern here is a silent secret leak.
_SENSITIVE = [
    re.compile(r"(^|/)\.env$", re.IGNORECASE),   # .env, path/to/.env
    re.compile(r"(^|/)\.env\.", re.IGNORECASE),  # .env.local, .env.production, ...
    re.compile(r"credentials", re.IGNORECASE),
    re.compile(r"secrets?\.ya?ml$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),        # private keys / certs
    re.compile(r"\.key$", re.IGNORECASE),        # private keys
    # SSH private keys — all four common types (rsa/dsa/ecdsa/ed25519); ECDSA
    # is the default on many modern systems, so gating only rsa/ed25519 leaked it.
    # The (?!\.pub) lookahead lets the PUBLIC counterpart (id_rsa.pub, ...) read
    # freely — a public key is not a secret, and a false block trains rubber-stamping.
    re.compile(r"(^|/)id_(?:rsa|dsa|ecdsa|ed25519)(?!\.pub)", re.IGNORECASE),
    # --- cloud credential / config files ---
    re.compile(r"(^|/)\.aws/(?:config|credentials)$", re.IGNORECASE),
    re.compile(r"(^|/)\.azure/", re.IGNORECASE),
    re.compile(r"(^|/)\.kube/config$", re.IGNORECASE),
    re.compile(r"\.kubeconfig$", re.IGNORECASE),
    re.compile(r"(^|/)gcloud/[^/]*\.(?:json|db)$", re.IGNORECASE),
    # GCP service-account / oauth client-secret json
    re.compile(r"(?:^|/)(?:service[-_]?account|client[-_]?secret)[^/]*\.json$", re.IGNORECASE),
    # keystores / private-key containers (binary — a content scan cannot see them)
    re.compile(r"\.(?:p12|pfx|jks|keystore|pkcs12|p8)$", re.IGNORECASE),
    # registry / package token files
    re.compile(r"(^|/)\.(?:npmrc|pypirc|netrc)$", re.IGNORECASE),
    re.compile(r"(^|/)_netrc$", re.IGNORECASE),
    re.compile(r"(^|/)\.docker/config\.json$", re.IGNORECASE),
    # infra / app secret files
    re.compile(r"\.tfvars$", re.IGNORECASE),
    re.compile(r"(^|/)wp-config\.php$", re.IGNORECASE),
    re.compile(r"(^|/)database\.ya?ml$", re.IGNORECASE),
]

_PROMPT_START = "@@PRIVACY_PROMPT_START@@"
_PROMPT_END = "@@PRIVACY_PROMPT_END@@"


def _matches_sensitive(p: str) -> bool:
    """True when a single path string looks like a secret (suffix-exempt via _SAFE)."""
    if not p:
        return False
    base = p.rsplit("/", 1)[-1]
    if _SAFE.search(base):
        return False
    return any(pat.search(p) for pat in _SENSITIVE)


def _is_sensitive(path: str, data: dict = None) -> bool:
    if not path:
        return False
    if _matches_sensitive(path):
        return True
    # Also resolve symlink aliases: `ln -s .env innocent.txt; Read(innocent.txt)`
    # would otherwise slip a secret past on a non-matching name. write_guard already
    # resolves before matching; this closes the read-side asymmetry.
    try:
        real = os.path.realpath(path)
    except OSError:
        return False
    return real != path and _matches_sensitive(real)


_READ_TOOLS = ("Read", "NotebookRead")


def _read_target(data: dict) -> str:
    """The file path a pure-read tool is about to open; '' for any other tool.
    Covers Read and NotebookRead (both read a file whole); write-intent tools
    (Edit/Write) are out of scope here — they go through write_guard.

    `notebook_path` is NOT optional here: it is the key NotebookRead actually
    sends, so reading only file_path/path made NotebookRead sail past this guard
    entirely while the tool sat in _READ_TOOLS and looked covered. The rest of the
    harness already read both keys — write_guard and
    cook_delegate_nudge — so this was the one site the class fix missed. Do not
    trim this back to one key: the shape of the payload differs per tool, and the
    test that "covered" NotebookRead sent file_path, which the tool never uses."""
    if data.get("tool_name") not in _READ_TOOLS:
        return ""
    inp = data.get("tool_input") or {}
    return str(inp.get("file_path") or inp.get("notebook_path")
               or inp.get("path") or "")


def _block_reason(path: str) -> str:
    """An actionable block reason embedding the @@PRIVACY_PROMPT@@ marker the
    controller parses to raise an AskUserQuestion."""
    base = path.rsplit("/", 1)[-1]
    prompt = {
        "type": "PRIVACY_PROMPT",
        "file": path,
        "basename": base,
        "question": {
            "header": "File Access",
            "text": ('Read "%s"? It may hold secrets (API keys, passwords, '
                     "tokens)." % base),
            "options": [
                {"label": "Approve",
                 "description": "Allow reading %s this time" % base},
                {"label": "Skip", "description": "Continue without this file"},
            ],
        },
    }
    return (
        "reading a secrets file (%s) requires human approval — this protects "
        "sensitive data, it is not an error.\n%s\n%s\n%s\n"
        "Ask the user with AskUserQuestion using the JSON above. If approved, read "
        "the file out-of-band via bash cat %s. If denied, continue without the file."
        % (path, _PROMPT_START, json.dumps(prompt), _PROMPT_END, path)
    )


def core(data: dict):
    """Compliance core: None ⇒ allow; str ⇒ block reason. Gates only a Read of a
    secrets file; every other tool and every non-secret path passes. There is no
    in-band approval override: an approved read stays out-of-band via `bash cat`
    (see _block_reason), the only route this Read-matcher gate does not see."""
    target = _read_target(data)
    if not _is_sensitive(target, data):
        return None
    return _block_reason(target)


def main() -> int:
    # Compliance wrapper: fail-closed on its own errors, fail-open on absent input.
    raw = hook_runtime.read_stdin_json()
    hook_runtime.run_compliance_hook(_NAME, core, raw=json.dumps(raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
