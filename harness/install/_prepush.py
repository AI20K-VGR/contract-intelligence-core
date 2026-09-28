#!/usr/bin/env python3
"""_prepush.py — pre-push transport gate install/uninstall (extracted from
install.py): pick a no-clobber backup path, install the shipped gate (backing up
a foreign hook), and reverse it. install.py re-exports these names, so callers
and tests that reach them through the `install` module see no change.
"""
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_manifest import sha256_file  # noqa: E402


def _prepush_backup_dest(hooks_dir: Path) -> Path:
    """Pick a no-clobber backup path for an existing foreign pre-push.

    A plain pre-push.bak is the first choice. But a re-install must never destroy
    a backup a user already has: if pre-push.bak exists and holds DIFFERENT
    content than the hook we are about to back up, fall back to a versioned
    pre-push.bak.1, .bak.2, ... so the original survives. (An identical existing
    .bak is a re-run of the same backup — reuse it, no version churn.)"""
    dst = hooks_dir / "pre-push"
    bak = hooks_dir / "pre-push.bak"
    if not bak.exists() or (dst.is_file() and sha256_file(bak) == sha256_file(dst)):
        return bak
    n = 1
    while True:
        cand = hooks_dir / ("pre-push.bak.%d" % n)
        if not cand.exists() or (
                dst.is_file() and sha256_file(cand) == sha256_file(dst)):
            return cand
        n += 1


def _install_prepush(source_root, target_root, result, dry_run):
    git_dir = target_root / ".git"
    if not git_dir.is_dir():
        result["warnings"].append(
            ".git not found — pre-push transport gate skipped "
            "(run the installer inside a git work tree)")
        return
    src = source_root / "harness" / "install" / "git-pre-push-hook.sh"
    hooks_dir = git_dir / "hooks"
    dst = hooks_dir / "pre-push"
    if dst.is_file() and sha256_file(dst) != sha256_file(src):
        bak = _prepush_backup_dest(hooks_dir)
        if not dry_run:
            shutil.copy2(dst, bak)
        result["actions"].append(
            "back up existing pre-push -> %s" % bak.name)
    if not dry_run:
        hooks_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        dst.chmod(0o755)
    result["actions"].append("install pre-push hook")


# The hook is identified by a STABLE header marker, not a byte-exact hash: a hook
# left by an OLDER harness version differs byte-for-byte from the current source
# (the scrub body has changed across releases), yet it is still OURS to clean —
# and under a global install it still bricks pushes. Matching the header line
# recognises every version's hook while leaving a user's foreign hook untouched.
_HOOK_MARKER = "git-pre-push-hook.sh — transport-level stage gate"


def _is_harness_hook(path: Path) -> bool:
    try:
        return _HOOK_MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _uninstall_prepush(source_root, target_root, result, dry_run):
    """Reverse the pre-push install. Only touch the hook if the CURRENT pre-push
    IS the harness hook (identified by its stable header marker, so a hook from
    ANY harness version is recognised): a user who installed their own hook AFTER
    us owns that slot, so we must not restore our .bak over it (that would clobber
    their live hook). When it is ours: restore the backed-up foreign hook from
    pre-push.bak (and consume the .bak), or, with no .bak, remove our hook
    outright."""
    hooks_dir = target_root / ".git" / "hooks"
    dst = hooks_dir / "pre-push"
    bak = hooks_dir / "pre-push.bak"
    if not dst.is_file():
        return
    if not _is_harness_hook(dst):
        # the live hook is NOT ours (a user-installed hook) — leave it and any
        # .bak exactly as-is.
        result["actions"].append(
            "pre-push is not the harness hook — left as-is (no restore)")
        return
    if bak.is_file() and not _is_harness_hook(bak):
        if not dry_run:
            shutil.copy2(bak, dst)
            bak.unlink()
        result["actions"].append("restore pre-push from pre-push.bak")
    else:
        # No .bak, OR the .bak is ITSELF a harness hook (install's hash-only
        # foreign-check backed up an older-version harness hook as if it were
        # foreign — see _install_prepush). Restoring it would re-install a stale
        # harness hook that fails closed once harness/ is removed. Just drop the
        # live hook; leave a harness-owned .bak on disk for forensics rather than
        # silently consuming it.
        if not dry_run:
            dst.unlink()
        result["actions"].append("remove harness pre-push hook")
