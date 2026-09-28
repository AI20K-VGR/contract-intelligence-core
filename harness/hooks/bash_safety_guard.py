#!/usr/bin/env python3
"""bash_safety_guard.py — PreToolUse(Bash) compliance hook: destructive-command gate.

Blocks a small, high-precision set of catastrophic shell commands BEFORE they run:
root/system `rm -rf`, fork bomb, raw-device dd/mkfs/redirect/shred/wipefs,
`curl|sh`, recursive chmod/chown on root, and overwrite of critical system files.
Safety-first: this is the one gate that protects the HOST itself, independent of
any SDLC stage (gate_stage covers stage transitions; this covers blast radius).

Posture: compliance class — fail-CLOSED on its own errors, fail-OPEN on empty /
unparseable input (no command to gate). The pattern set is deliberately narrow and
TARGET-AWARE: it matches the wipe-the-machine class, NOT targeted deletes
(`rm -rf ./build`, `rm -rf /tmp/x`) or benign look-alikes (`dd of=file.img`,
`curl | jq`). It is defense-in-depth (raw-string regex over the command), not an
airtight sandbox — host perms and the AFK Docker isolation remain the primary
boundary; a determined operator can still spell a command around it.

Wrapper reach: the battery runs over every command-position view from
shell_unwrap, so `sh -c '<payload>'` and its family no longer hide their verb in
a quoted string (see core()). What that does NOT cover is written down rather
than left implied — command substitution, variable indirection, base64, other
interpreters, deferred execution — because a half-closed hole advertised as
closed is worse than an open one. The enumerated residual list with a reproducing
command per entry lives beside this plan's checklist, and the parser-side subset
is pinned by test_shell_unwrap.py::TestTheDocumentedResidualHoles.

HOOK_CLASS is a code constant; config (harness-hooks.yaml) can only toggle
enabled/mode, never reclassify the gate. Break-glass: `enabled: false` (the diff
is tracked and the skip is visible).
"""

import os
import re
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import shell_unwrap  # noqa: E402

HOOK_CLASS = "compliance"
_NAME = Path(__file__).stem

# Bare catastrophic targets for rm/chmod: root, glob-root, home, or a bare
# top-level system dir (optionally a trailing `/` or `/*`). The trailing
# lookahead is what keeps it precise — `/home/user/...` is a SUBPATH and does
# NOT match (only bare /home, /home/ or /home/* do), so targeted deletes stay
# allowed. `(?:/\*?)?` accepts the bare dir, a trailing slash (`/etc/`) and the
# glob (`/etc/*`) — a trailing slash must NOT be a bypass.
_SYSDIRS = "etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root|var|opt|srv|home"
_DANG_TARGET = re.compile(
    r"(?:^|\s)(?:"
    r"/(?:\.\.?|\*+)?|"        # /  /.  /..  /*  /**
    r"/\{[^}]*\}|"             # /{bin,etc}
    r"/{2,}|"                  # //  ///
    r"~[\w.-]*|"               # ~  ~root  ~user
    r"\$\{?HOME\}?|"           # $HOME  ${HOME}
    r"/(?:%s)(?:/\*?)?"         # /etc  /etc/  /etc/*
    r")/?(?=\s|$|;|&|\|)" % _SYSDIRS
)

# A command line splits into list/pipeline segments on these connectors; a
# dangerous target is only blamed on an rm/chmod in the SAME segment.
_CONNECTOR_RE = re.compile(r"[;&|\n]+")
# A trailing `#...` comment (at a word boundary) is not part of any command.
_COMMENT_RE = re.compile(r"(?:^|\s)#[^\n]*")

_RM_RECURSIVE = re.compile(r"\brm\b[^\n]*?(?:\s-\w*[rR]\w*\b|\s--recursive\b)")
_RM_NOPRESERVE = re.compile(r"\brm\b[^\n]*--no-preserve-root")
# `find <catastrophic> -delete` / `-exec rm` is a recursive system wipe via find —
# same catastrophic class as recursive rm, gated on the same _DANG_TARGET so a
# project-local `find . -delete` stays allowed.
_FIND_DESTRUCTIVE = re.compile(
    r"\bfind\b[^\n]*?(?:-delete\b|-exec\s+(?:rm|unlink|sh|bash)\b)")
_FORKBOMB = re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:")
_DD_DEV = re.compile(r"\bdd\b[^\n]*\bof=/dev/(?:sd|nvme|hd|vd|mmcblk|disk|xvd|loop|dm-|mapper/|md|ram)")
_MKFS = re.compile(r"\bmkfs(?:\.\w+)?\b[^\n]*/dev/")
_REDIR_DEV = re.compile(r"(?:>\s*|\btee\b[^\n]*\s)/dev/(?:sd|nvme|hd|vd|mmcblk|disk|xvd|loop|dm-|mapper/|md|ram)[a-z0-9]*")
_SHRED_DEV = re.compile(r"\bshred\b[^\n]*/dev/")
_WIPEFS = re.compile(r"\b(?:wipefs|sgdisk)\b[^\n]*/dev/")
_DISK_DESTROY = re.compile(
    r"\bblkdiscard\b[^\n]*/dev/"
    r"|\bmke2fs\b[^\n]*/dev/"
    r"|\bcryptsetup\b[^\n]*\bluks(?:Format|Erase)\b"
    r"|\bnvme\s+format\b"
    r"|\bbadblocks\b[^\n]*\s-\w*w"
    r"|\bhdparm\b[^\n]*--security-erase"
    r"|\b(?:parted|sfdisk)\b[^\n]*\b(?:mklabel|mkpart|--delete)\b"
)
# Allow intermediate pipe stages (curl ... | tee x | sh, curl | head | sh) by
# spanning any non-separator text up to the LAST pipe before the shell stage;
# stop at ; and newline so an unrelated downstream `| sh` is not falsely chained.
_CURL_SH = re.compile(r"\b(?:curl|wget|fetch)\b[^\n;]*\|\s*(?:sudo\s+)?(?:(?:ba|da|z|k)?sh|python3?|perl|ruby|node|php)\b")
_RCE_DOWNLOAD = re.compile(
    r"\b(?:ba|da|z|k)?sh\b[^\n]*<\(\s*(?:curl|wget|fetch)\b"
    r"|\b(?:eval|source)\s[^\n]*(?:\$\(|<\()\s*(?:curl|wget|fetch)\b"
)
_CHMOD_RECURSIVE = re.compile(r"\b(?:chmod|chown)\b[^\n]*(?:\s-\w*[rR]\w*\b|\s--recursive\b)")
_CRIT_OVERWRITE = re.compile(
    r"(?:>|\btee\b[^\n]*)\s*/etc/(?:passwd|shadow|sudoers|group|fstab|hosts|crontab)\b"
    r"|(?:>|\btee\b[^\n]*)\s*/boot/"
    r"|\btruncate\b[^\n]*\s/etc/(?:passwd|shadow|sudoers|group|fstab|crontab)\b"
    r"|\bdd\b[^\n]*\bof=/etc/(?:passwd|shadow|sudoers|group|fstab|crontab)\b"
    r"|\bcp\s+/dev/null\s+/etc/(?:passwd|shadow|sudoers|group|fstab|crontab)\b"
)


# Quoted spans. Two LENGTH-PRESERVING normalizations share these so a quoted
# dangerous verb (`echo "rm -rf /"`) is ignored WHILE a quoted target
# (`rm -rf '/'`) is still seen — contradictory needs that one view cannot serve.
_QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _verb_view(cmd: str) -> str:
    """Quoted SPANS → underscores (content destroyed) FIRST, then comment →
    spaces. Quotes are masked before the comment scan so a `#` living inside a
    quoted string cannot be misread as a comment start eating the rest of the
    line. A dangerous VERB living inside a quote is then not seen as a command,
    killing false positives like `git log --grep="rm -rf /"`. Length-preserving."""
    s = _QUOTED_SPAN_RE.sub(lambda m: "_" * len(m.group(0)), cmd)
    return _COMMENT_RE.sub(lambda m: " " * len(m.group(0)), s)


def _target_view(cmd: str) -> str:
    """Comment → spaces, quote CHARS → spaces (content kept). A quoted TARGET
    like `rm -rf '/'` is still seen as `/` at a word boundary. Length-preserving,
    so its offsets align with the verb view for per-segment pairing.

    The comment span is located on a QUOTE-MASKED probe (so a `#` inside a
    quoted string never starts a false comment), then blanked at the same
    offsets in `cmd` — this view must keep quote CONTENT, so it cannot just
    mask quotes to underscores like `_verb_view` does."""
    probe = _QUOTED_SPAN_RE.sub(lambda m: "_" * len(m.group(0)), cmd)
    chars = list(cmd)
    for m in _COMMENT_RE.finditer(probe):
        start, end = m.span()
        chars[start:end] = " " * (end - start)
    s = "".join(chars)
    return s.replace("'", " ").replace('"', " ")


def _segment_spans(view: str):
    """(start, end) of each list/pipeline segment, by offset — so the verb view
    and the target view (same length) are sliced at the same boundaries."""
    spans, start = [], 0
    for m in _CONNECTOR_RE.finditer(view):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(view)))
    return spans


def _reason(cmd: str):
    """Return an actionable block reason, or None to allow. Ordered: rm first
    (most common catastrophic), then device writes, then remote-exec / perms.
    rm/chmod recursion is matched against the SAME segment as its target, so a
    system dir living in another segment, a comment, or an `echo` arg cannot
    false-trip the gate; self-contained patterns run over the whole command.

    Two views (same length, offset-aligned): the VERB view masks quoted spans so
    a dangerous verb quoted as a literal string (`git log --grep="rm -rf /"`) is
    not read as a command; the TARGET view keeps quote content so `rm -rf '/'`
    is still caught. (A verb quoted in isolation, `"rm" -rf /`, is the documented
    not-airtight residual.)"""
    vv = _verb_view(cmd)
    tv = _target_view(cmd)
    spans = _segment_spans(vv)
    if _RM_NOPRESERVE.search(vv):
        return ("`rm --no-preserve-root` — that flag exists only to enable a root "
                "wipe. Remove it; target a specific subpath.")
    if any(_RM_RECURSIVE.search(vv[s:e]) and _DANG_TARGET.search(tv[s:e])
           for s, e in spans):
        return ("recursive `rm` targeting a root / system / bare-home path. Target "
                "a specific project subpath instead (e.g. ./build, /tmp/<name>).")
    if any(_FIND_DESTRUCTIVE.search(vv[s:e]) and _DANG_TARGET.search(tv[s:e])
           for s, e in spans):
        return ("`find` deleting under a root / system / bare-home path — would wipe "
                "the system. Target a specific project subpath (e.g. ./build).")
    if _FORKBOMB.search(vv):
        return "fork bomb (`:(){ :|:& };:`) — would exhaust process table."
    if _DD_DEV.search(vv):
        return "`dd` writing to a raw block device (/dev/...) — would destroy a disk."
    if _MKFS.search(vv):
        return "`mkfs` on a block device — would format/erase a filesystem."
    if _REDIR_DEV.search(vv):
        return "redirect overwriting a raw block device (/dev/...)."
    if _SHRED_DEV.search(vv):
        return "`shred` on a raw block device — irreversible disk wipe."
    if _WIPEFS.search(vv):
        return "`wipefs`/`sgdisk` on a block device — would erase partition signatures."
    if _DISK_DESTROY.search(vv):
        return ("raw-device destroyer (blkdiscard/mke2fs/cryptsetup luksFormat/"
                "nvme format/badblocks -w/parted mklabel) — would irreversibly wipe a disk.")
    if _CURL_SH.search(vv):
        return ("piping a remote download straight into a shell (`curl ... | sh`) — "
                "download to a file, inspect, then run.")
    if _RCE_DOWNLOAD.search(vv):
        return ("executing a remote download via process substitution / eval "
                "(`bash <(curl ...)`, `eval $(curl ...)`) — download, inspect, then run.")
    if any(_CHMOD_RECURSIVE.search(vv[s:e]) and _DANG_TARGET.search(tv[s:e])
           for s, e in spans):
        return "recursive chmod/chown on a root / system path — would break the host."
    if _CRIT_OVERWRITE.search(vv):
        return "overwrite of a critical system file under /etc."
    return None


def _wrapper_note(payload: str) -> str:
    """Name the payload a block came from. A refusal whose text describes a
    command the caller cannot see in what they typed reads as a false positive
    even when it is correct, so the wrapper arm has to quote its trigger."""
    flat = " ".join(payload.split())
    if len(flat) > 80:
        flat = flat[:77] + "..."
    return "inside the shell-wrapper payload `%s` — " % flat


def core(data: dict):
    """Compliance core: None ⇒ allow; str ⇒ block reason. Only gates Bash tool
    calls; anything else (and empty commands) passes.

    The pattern battery runs over EVERY command-position view, not just the
    literal command: `sh -c 'rm -rf /'` hides its verb inside a quoted string,
    and `_verb_view` masks quoted spans on purpose (that masking is what keeps
    `git log --grep="rm -rf /"` from false-tripping). One view cannot serve both
    needs, so shell_unwrap promotes each genuine wrapper payload to its own view
    and each is scanned independently.

    Why fanning out views is safe in one direction only: views[0] IS the raw
    command, so every verdict this gate reached before still reaches. Extra views
    can only ADD a block, never remove one. Do not "optimise" this into scanning
    a single merged/unwrapped string — merging re-creates the very ambiguity the
    two-view design resolves, and replacing views[0] would let a wrapper LOSE a
    block the raw command used to catch.
    """
    if data.get("tool_name") != "Bash":
        return None
    cmd = hook_runtime.bash_command(data)
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    for index, view in enumerate(shell_unwrap.command_views(cmd)):
        reason = _reason(view)
        if not reason:
            continue
        return reason if index == 0 else _wrapper_note(view) + reason
    return None


def main() -> int:
    # Compliance wrapper: fail-closed on its own errors, fail-open on absent input,
    # honors the enabled gate; blocks with exit 2 + reason when core returns a str.
    hook_runtime.run_compliance_hook(_NAME, core)
    return 0


if __name__ == "__main__":
    sys.exit(main())
