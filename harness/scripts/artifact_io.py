"""artifact_io.py — the one gate-artifact writer: run_seq stamp + atomic write.

The three gate producers (plan_approval, write_verification, write_review_decision)
route their final write through stamp_and_write, so run_seq is stamped in a SINGLE
place (D1) and every gate artifact lands atomically. The orchestrator's watchdog reads
these by run_seq to reject a stale/prior-run artifact — which only works if the
producer stamps it.

D1 boundary discipline: tầng-1 does NOTHING with run_seq's semantics — it reads the env
the orchestrator exported and writes the field. Env absent → run_seq:null; a standalone
harness (no orchestrator) writes null forever and stays correct.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

_ENV_KEY = "HARNESS_RUN_SEQ"


class CrossVolumeError(RuntimeError):
    """The .tmp landed on a different volume than the target dir, so os.replace could
    not be atomic. Raised BEFORE any replace so the reader never sees a torn file."""


def _run_seq_from_env(env=None):
    """The orchestrator-exported run_seq as int, or None when absent/blank/malformed.
    Fail-open to null (never raise): a dev running the gate without an orchestrator
    must still write a valid artifact (back-compat)."""
    env = os.environ if env is None else env
    raw = env.get(_ENV_KEY)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _serialize(path: Path, rec: dict) -> str:
    if path.suffix == ".yaml":
        import yaml_io
        return yaml_io.safe_dump(rec, allow_unicode=True, sort_keys=False)
    return json.dumps(rec, ensure_ascii=False, indent=2) + "\n"


def atomic_write_text(path, body, *, newline=None) -> None:
    """Write `body` to `path` atomically AND durably. A .tmp in the SAME dir is
    fsync'd before os.replace, so "no torn/empty file" holds across a crash or power
    loss too: os.replace makes the directory entry atomic, but the tmp's data blocks
    may still be unflushed (the classic rename-without-fsync gap → an empty/partial
    file after power loss). A cross-volume tmp fails loud (CrossVolumeError) instead
    of a silently non-atomic replace, and a stray .tmp is never left for a reader to
    mistake for content. `newline` is passed straight to open() — register writers
    pass "" to keep literal CRLF/LF bytes."""
    path = Path(path)
    # A unique per-call tmp name (not a fixed "<name>.tmp"): two writers
    # racing on the SAME target must not share one tmp path — writer B's
    # open("w") would truncate writer A's still-open, not-yet-fsync'd tmp,
    # so A's later os.replace publishes B's partial bytes as the "finished"
    # artifact. mkstemp's O_EXCL create guarantees each caller gets its own
    # file, still in the SAME dir (so os.replace stays a same-volume rename).
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    # mkstemp defaults to 0600; widen to what a plain open() would have produced.
    # hasattr, not try/except: on Windows os.fchmod does not EXIST, so the call
    # raises AttributeError, which `except OSError` does not catch — measured as
    # an install failure on the 3-OS gate. The OSError arm still matters on POSIX,
    # where the call exists but a filesystem may refuse it.
    if hasattr(os, "fchmod"):
        try:
            os.fchmod(fd, 0o644)
        except OSError:
            pass
    with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        if os.stat(tmp).st_dev != os.stat(path.parent).st_dev:
            raise CrossVolumeError(
                "tmp %s and target dir %s are on different volumes — os.replace would "
                "not be atomic; refusing a torn write" % (tmp, path.parent))
        os.replace(tmp, path)
    except BaseException:
        # never leave a stray .tmp a reader might later mistake for content
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def stamp_and_write(path, record, *, env=None) -> dict:
    """Stamp run_seq (from HARNESS_RUN_SEQ, null if absent) into a COPY of `record`,
    serialize by suffix (.yaml/.json), and write it via atomic_write_text (same-dir
    fsync'd .tmp + same-volume assert + os.replace). Returns the stamped record."""
    path = Path(path)
    rec = dict(record)
    rec["run_seq"] = _run_seq_from_env(env)
    atomic_write_text(path, _serialize(path, rec))
    return rec


# Regenerable build caches, and the one place that says so. They are derived from
# the source beside them, they are stamped with the interpreter and the moment that
# produced them, and Python will prefer a `.pyc` to the `.py` next to it whenever the
# source's (mtime-to-the-second, size) still match. A tree copied to another machine
# fails that test or passes it by accident, so the cache is either dead weight in a
# tree a human was asked to read or a runtime executing code the copied source does
# not state. Neither is something a copy should decide by accident.
TRANSIENT_TREE_NAMES = ("__pycache__", "*.pyc", "*.pyo")


def copy_tree(src, dest, *, dirs_exist_ok: bool = True) -> None:
    """Copy a directory the way the harness copies one: source, never build output.

    The filter is by NAME rather than by directory, so a stray `.pyc` sitting beside
    its source travels no further than one inside a `__pycache__`.
    """
    shutil.copytree(str(src), str(dest), dirs_exist_ok=dirs_exist_ok,
                    ignore=shutil.ignore_patterns(*TRANSIENT_TREE_NAMES))


def strip_stale_blocks(text: str, begin: str, end: str) -> str:
    """Remove every well-formed block but the LAST, leaving a single BEGIN/END pair
    for the caller to replace. Defends against a prior bug that appended a second
    block instead of replacing the first: each extra leading block (BEGIN ... END) is
    excised so no orphan marker survives the rewrite."""
    while text.count(begin) > 1:
        b = text.find(begin)
        e = text.find(end, b)
        if e == -1:
            break  # an unpaired leading BEGIN — leave it for the caller
        # drop the block and any blank padding that immediately followed it
        rest = text[e + len(end):]
        rest = rest[1:] if rest.startswith("\n") else rest
        text = text[:b] + rest
    return text


def splice_block(existing: str, block: str, begin: str, end: str) -> str:
    """Put `block` into `existing` between its markers, preserving everything else.

    The one answer to "how does the harness edit a file it does not own". Prose
    OUTSIDE the markers is never touched — a whole-file write would delete a user's
    hand-written instructions, which is exactly what the runtime installer did before
    this was shared with it.

    rfind (last BEGIN) + the first END after it: replacing the LAST pair drains a
    duplicate leading block left by a prior bug, where find() would keep the first
    pair and orphan the rest.
    """
    if existing.count(begin) > 1:
        existing = strip_stale_blocks(existing, begin, end)
    b = existing.rfind(begin)
    e = existing.find(end, b) if b != -1 else -1
    if b != -1 and e != -1:
        return existing[:b] + block + existing[e + len(end):]
    sep = "" if not existing or existing.endswith("\n") else "\n"
    lead = "\n" if existing else ""
    return existing + sep + lead + block + "\n"
