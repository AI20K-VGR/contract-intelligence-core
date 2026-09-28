#!/usr/bin/env python3
"""decision_register — the Decision Register: the authoritative home for
explicit architecture/process rulings (`DEC-<n>`).

A decision is recorded when a binding call is made that later work must not
re-litigate. The register kills re-litigation: the next time the same tension
surfaces, read the register FIRST and surface the prior ruling ("DEC-n decided
X because … — keep or supersede?") instead of re-debating.

Script-vs-LLM split: this script owns the deterministic structural work —
allocate the next monotonic id, validate the `^DEC-\\d+$` grammar + record
shape, append WITHOUT overwriting prior records, parse + list. The caller owns
the human RATIONALE prose passed in as `--rationale`.

Storage (dual-mode): the SSOT is `docs/decisions.yaml` when present — a YAML
list of records (load → mutate → dump), with `docs/decisions.md` rendered as a
secondary human view. Absent decisions.yaml, the legacy markdown form IS the
store: each ruling is one `---`-fenced YAML mini-frontmatter
(id/status/date/affects/supersedes) + a `## DEC-<n> — <title>` heading +
rationale block. Both modes resolve through fs_guard zone "docs" so a register
write can never escape the docs boundary.

ID grammar: `^DEC-\\d+$`, monotonic max+1 regardless of status — a superseded
DEC still counts toward the max, so ids are never reused. BOTH append paths
(--append with an explicit id, --append-alloc) run inside the register lock:
two concurrent agents on one machine cannot overwrite each other's appends
(see register_store for the degraded-lock posture on platforms without flock).

CLI:
    decision_register.py --root <dir> --alloc-id
    decision_register.py --root <dir> --append --id DEC-2 --title "..." \\
        --rationale "..." [--affects PRD-X] [--supersedes DEC-1]
    decision_register.py --root <dir> --append-alloc --title ... --rationale ...
    decision_register.py --root <dir> --list   # active records as JSON
"""

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml_io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import fs_guard  # noqa: E402
import decision_neighbors  # noqa: E402 — blast-radius detector (P1), DRY
import decision_confirm    # noqa: E402 — cross-scope confirm token (P2)
from register_store import (  # noqa: E402
    RECORD_RE as _RECORD_RE, atomic_write, escape_injection, register_lock,
    sanitize_field, scan_record_ids,
)

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import hook_runtime  # noqa: E402

# Windows consoles may default to a legacy codepage; UTF-8 JSON output must
# not crash there. reconfigure exists on 3.7+; guard for exotic stdouts.
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")


# This register's own heading anchor: a rationale line that is a bare `---`
# fence would split decisions.md into a phantom record; a `## DEC-<n>` line
# could smuggle a fake heading. Both are neutralized on write.
_INJ_DEC_HEADING_RE = re.compile(r"(?m)^(##\s+DEC-)")

# ID grammar: DEC- + digits, nothing else. Parent-free, globally monotonic.
DECISION_ID_RE = re.compile(r"^DEC-\d+$")

# Record template inline (one register, one shape — no template file to drift).
# A register record is machine-written state, so it carries actor + ts like the
# other stores (actor via resolve_actor, ts a UTC isoformat instant).
_RECORD_TEMPLATE = """---
id: {id}
status: {status}
date: {date}
actor: {actor}
ts: {ts}
{affects_line}{supersedes_line}{executed_by_line}---

## {id} — {title}

{rationale}
"""


class DecisionError(ValueError):
    """Raised on a grammar/shape/uniqueness violation (surfaced as a JSON
    finding by the CLI; raised directly for library callers)."""


class CrossScopeBlock(Exception):
    """A cross-scope flip without a matching confirm token. The ONE exit-2 path
    (DC-5): distinct from invalid_input (exit 0) so a caller can ESCALATE. The
    real enforcement is that the write is refused (raised BEFORE append_decision
    → the SSOT never changes); exit-2 is the signal, not the floor. The floor is
    write_guard blocking a direct edit of decisions.yaml (R1/R4).

    Callers branch on the stdout key `cross_scope_block`, NOT on $? (R8 — the
    caller is LLM prose that reads JSON, not a shell that inspects exit codes)."""

    def __init__(self, target, cross_scope, active_plan):
        self.target = target
        self.cross_scope = list(cross_scope)
        self.active_plan = active_plan
        super().__init__("cross-scope flip of %s needs confirmation" % target)

    def finding(self) -> Dict[str, Any]:
        cross = ",".join(self.cross_scope)
        return {
            "error": "cross_scope_block",
            "written": False,
            "target": self.target,
            "cross_scope": self.cross_scope,
            "active_plan": self.active_plan or "none",
            "confirm_cmd": ("decision_confirm.py --confirm --target %s "
                            "--neighbors %s" % (self.target, cross)),
            "hint": ("these rulings are not referenced by the active plan — if "
                     "this flip is intended, confirm with the command above; if "
                     "the active plan is wrong/ambiguous (0 or >1 in_progress), "
                     "set HARNESS_ACTIVE_PLAN to the right plan dir and retry"),
        }


# High bar for an IMPLICIT-flip warning (R11): a couple of shared domain words
# must NOT trip it — only a new ruling that clearly restates an existing one.
_IMPLICIT_MIN_SHARED = 5


def _confirm_ttl(root) -> int:
    """confirm_ttl_s from decision-governance.yaml; fail-open default 1800s when the
    knob file is absent/invalid (P4 owns the file; the gate degrades safely without
    it rather than hard-failing the write path)."""
    env = os.environ.get("HARNESS_DECISION_GOVERNANCE")
    p = Path(env) if env else Path(root) / "harness" / "data" / "decision-governance.yaml"
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("confirm_ttl_s"), int):
            return raw["confirm_ttl_s"]
    except (FileNotFoundError, OSError, yaml_io.YAMLError, ValueError):
        pass
    return 1800


def _active_plan_text(root) -> str:
    """All text of the active plan dir (plan.md + phase-*.md + artifacts/*) for scope
    classification. R6: gather the WHOLE dir, not just plan.md — a DEC created mid-
    execution is named in the Validation Log / a verification artifact before it
    reaches plan.md, and missing that would false-block the work in flight. Fully
    fail-soft: any resolution/read failure → "" (no plan text → all neighbours
    cross_scope → the gate leans toward asking, never crashes the write path)."""
    try:
        import artifact_check
        plan_dir = artifact_check.resolve_active_plan(root)
    except Exception:  # noqa: BLE001 — resolver failure must not break a write
        return ""
    if not plan_dir:
        return ""
    parts = []
    try:
        for f in sorted(Path(plan_dir).rglob("*")):
            if f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml", ".txt"):
                try:
                    parts.append(f.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
    except OSError:
        return ""
    return "\n".join(parts)


def _scope_of_flip(root, target: str) -> Dict[str, Any]:
    """Neighbours of `target` + their in_scope/cross_scope split vs the active plan.
    Pure read; used by the gate AND the --scan-flip dry run."""
    records = parse_decisions(root)
    neigh = decision_neighbors.neighbors(records, target)
    scope = decision_neighbors.classify_scope(neigh, _active_plan_text(root))
    return {"neighbors": neigh,
            "in_scope": scope["in_scope"],
            "cross_scope": scope["cross_scope"]}


def _gate_supersede(root, target: str) -> None:
    """Cross-scope confirm gate for an explicit supersede. Allows (with a one-line
    WARN when there are in-scope neighbours) unless a cross-scope neighbour exists
    without a matching confirm token — then raises CrossScopeBlock (write refused).

    Fail-OPEN on a scope-computation failure: if we cannot determine cross-scope, we
    do NOT block (treat as empty → allow). The block fires ONLY on a positively
    determined, unconfirmed cross-scope set."""
    try:
        scope = _scope_of_flip(root, target)
    except Exception:  # noqa: BLE001 — cannot compute scope → allow (degrade safe)
        return
    cross = scope["cross_scope"]
    if not cross:
        if scope["in_scope"]:
            sys.stderr.write(
                "[warn] flip %s: in-scope neighbour(s) %s — allowed\n"
                % (target, ", ".join(scope["in_scope"])))
        return
    active = None
    try:
        import artifact_check
        pd = artifact_check.resolve_active_plan(root)
        active = str(pd) if pd else None
    except Exception:  # noqa: BLE001
        active = None
    if decision_confirm.verify_and_consume(root, target, cross,
                                           ttl_s=_confirm_ttl(root)):
        return  # confirmed (and consumed) — confirm lib emits the trace event
    raise CrossScopeBlock(target, cross, active)


def _warn_implicit_flip(root, title: str, rationale: str) -> None:
    """Name the closest live ruling so the author opens it → WARN only, NEVER block.

    Deliberately NOT phrased as "this contradicts X": measured on this ledger the
    matcher cannot tell a flip from a same-area ruling, so it names something on
    essentially every append. An author shown a confident-sounding false alarm
    twice stops reading the third, which is the one that matters — so the warning
    says what it actually knows. Fail-soft."""
    try:
        records = parse_decisions(root)
        rival = decision_neighbors.implicit_flip_match(
            records, title, rationale, min_shared=_IMPLICIT_MIN_SHARED)
    except Exception:  # noqa: BLE001
        return
    if rival:
        sys.stderr.write(
            "[warn] phán quyết còn hiệu lực GẦN NHẤT với bản ghi mới: %s — mở ra đối "
            "chiếu, và thêm --supersedes %s nếu đây đúng là một lần lật.\n"
            "        Đây là độ gần CHỦ ĐỀ, không phải bằng chứng mâu thuẫn: đo trên "
            "chính sổ này, điểm của cặp-lật-thật và cặp-cùng-lĩnh-vực chồng lên nhau "
            "gần hết, nên cảnh báo này luôn nêu ra một cái tên kể cả khi không có lật.\n"
            % (rival, rival))


def sanitize_rationale(rationale: str) -> str:
    """Neutralize record-fence / DEC-heading injection in the multiline
    rationale, preserving the text."""
    return escape_injection(rationale, _INJ_DEC_HEADING_RE)


def _decisions_path(root) -> Path:
    """The markdown view path. In YAML mode this is the rendered secondary view;
    in legacy mode it is the source. Kept as the public name many callers/tests
    monkeypatch to redirect the register."""
    return Path(root) / "docs" / "decisions.md"


def _yaml_path(root) -> Path:
    """The pure-YAML SSOT path. When this file exists the register operates in
    YAML mode: CRUD on a YAML list, decisions.md rendered as a secondary view."""
    return Path(root) / "docs" / "decisions.yaml"


def _uses_yaml(root) -> bool:
    """True when the register is a pure-YAML SSOT (decisions.yaml present).
    Otherwise the legacy markdown path is the source (back-compat / un-migrated
    target repos)."""
    return _yaml_path(root).is_file()


# Canonical record field order (what a rendered YAML record lists, in order).
_REC_FIELDS = ("id", "status", "date", "actor", "ts", "affects", "supersedes",
               "executed_by", "title", "rationale")

# This register's own heading marker for the rendered markdown view.
_GENERATED_MARKER = (
    "<!-- generated from docs/decisions.yaml by decision_register.py — "
    "edit the YAML SSOT, not this file -->"
)

# Document-level frontmatter for the rendered view. decisions.md is a graph doc
# under docs/, so the docs-standardize contract requires id/type/status/owner/
# version at the top — distinct from each record's own `---`-fenced mini block.
# Kept static: this is the doc's schema identity, not a per-record value.
_DOC_FRONTMATTER = (
    "---\n"
    "id: harness.decisions\n"
    "type: adr\n"
    "status: stable\n"
    "owner: maintainer\n"
    "version: 1.0.0\n"
    "---"
)


def _lock_path(root) -> Path:
    return Path(root) / "docs" / ".decision_register.lock"


@contextlib.contextmanager
def _register_lock(root):
    """alloc-id + append as ONE critical section over this register's lock
    file (closes the looped-alloc TOCTOU window; also serializes plain
    appends so concurrent agents cannot drop each other's records)."""
    with register_lock(_lock_path(root)):
        yield


def parse_decisions(root) -> List[Dict[str, Any]]:
    """Every record (active AND superseded), in order. Missing file → empty
    list. Dispatches: YAML SSOT when decisions.yaml exists, else the legacy
    markdown source. A record with a malformed id is skipped (fail-soft — one
    corrupt block never sinks --list). Records carry the full prose rationale."""
    if _uses_yaml(root):
        return _parse_yaml(root)
    return _parse_md(root)


def _rationale_from_body(body: str, dec_id: str) -> str:
    """The prose under a record's `## DEC-<n> — <title>` heading (the rationale),
    or the whole body when no heading is present. Trailing whitespace trimmed."""
    m = re.search(r"^##\s+%s\b.*?$" % re.escape(dec_id), body, re.MULTILINE)
    text = body[m.end():] if m else body
    return text.strip()


def _parse_md(root) -> List[Dict[str, Any]]:
    """Legacy markdown source: split into `---`-fenced records, parse each."""
    path = _decisions_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return []

    records: List[Dict[str, Any]] = []
    for m in _RECORD_RE.finditer(text):
        try:
            fm = yaml_io.safe_load(m.group("fm")) or {}
        except (yaml_io.YAMLError, ValueError):
            # PyYAML's timestamp/int constructors raise a bare ValueError (not a
            # YAMLError) on out-of-range values — catch both so a malformed legacy
            # frontmatter record is skipped, not crashed-on (matches the YAML-mode
            # reader + the gate's _parse_artifact_text floor).
            continue
        if not isinstance(fm, dict):
            continue
        dec_id = str(fm.get("id", "")).strip()
        if not DECISION_ID_RE.match(dec_id):
            continue
        rec: Dict[str, Any] = {
            "id": dec_id,
            "status": str(fm.get("status", "active")).strip() or "active",
            "date": str(fm.get("date", "")).strip(),
            "actor": str(fm.get("actor", "")).strip(),
            "ts": str(fm.get("ts", "")).strip(),
        }
        for opt in ("affects", "supersedes", "executed_by"):
            val = fm.get(opt)
            rec[opt] = str(val).strip() if val not in (None, "") else ""
        rec["title"] = _title_from_body(m.group("body"), dec_id)
        rec["rationale"] = _rationale_from_body(m.group("body"), dec_id)
        records.append(rec)
    return records


def _norm_record(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coerce a raw YAML mapping to a canonical record dict, or None when the id
    is malformed (skipped fail-soft). `status` is preserved verbatim (NOT
    defaulted) so an explicit-empty status stays unflippable — the YAML analogue
    of a legacy record missing its `status:` line."""
    dec_id = str(raw.get("id", "")).strip()
    if not DECISION_ID_RE.match(dec_id):
        return None
    # A bare YAML key (e.g. `status:`) parses to None, NOT an absent key — so
    # dict.get's default never fires and str(None) would yield "None". Coalesce
    # null→"" so an explicit-empty/null status stays the unflippable analogue.
    def _req(key: str) -> str:
        val = raw.get(key)
        return str(val).strip() if val not in (None, "") else ""
    rec = {"id": dec_id,
           "status": _req("status"),
           "date": _req("date"),
           "actor": _req("actor"),
           "ts": _req("ts")}
    for opt in ("affects", "supersedes", "executed_by", "title", "rationale"):
        val = raw.get(opt)
        rec[opt] = str(val) if val not in (None, "") else ""
    return rec


def _load_yaml_raw(root) -> List[Dict[str, Any]]:
    """Raw YAML SSOT records (status preserved verbatim, empty stays empty so an
    explicit-empty status is unflippable). A whole-file parse failure yields []
    here; id allocation uses the resilient raw id-scan instead, so a corrupt
    record never collapses id reservation back to DEC-1."""
    path = _yaml_path(root)
    try:
        data = yaml_io.safe_load(path.read_text(encoding="utf-8"))
    except (yaml_io.YAMLError, OSError, UnicodeDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in data:
        if isinstance(raw, dict):
            rec = _norm_record(raw)
            if rec is not None:
                out.append(rec)
    return out


def _parse_yaml(root) -> List[Dict[str, Any]]:
    """YAML SSOT view: an empty status reads as 'active' for list purposes (the
    raw empty stays visible to _can_supersede via _load_yaml_raw)."""
    out = []
    for rec in _load_yaml_raw(root):
        view = dict(rec)
        view["status"] = rec["status"] or "active"
        out.append(view)
    return out


def _title_from_body(body: str, dec_id: str) -> str:
    m = re.search(r"^##\s+%s\s*[—-]\s*(?P<title>.+?)\s*$" % re.escape(dec_id),
                  body, re.MULTILINE)
    return m.group("title").strip() if m else ""


def list_active(root) -> List[Dict[str, Any]]:
    """Records with `status: active` only — the rulings still in force."""
    return [r for r in parse_decisions(root) if r["status"] == "active"]


def alloc_id(root) -> str:
    """Next free `DEC-<n>` = max-existing + 1 (DEC-1 on an empty register).
    Scans RAW `id:` lines so a corrupt-but-id-bearing block still reserves its
    number — a later repair can never collide with a meanwhile-allocated id."""
    used = []
    for dec_id in _scan_all_ids(root):
        m = re.match(r"^DEC-(\d+)$", dec_id)
        if m:
            used.append(int(m.group(1)))
    return "DEC-%d" % ((max(used) + 1) if used else 1)


# A rendered `## DEC-<n>` heading also reserves the number: a hand-added
# heading-only record (no `id:` fence) must still count, or id-alloc would
# hand out a number that already appears in the file.
_HEADING_ID_RE = re.compile(r"(?m)^##\s+(DEC-\d+)\b")

_YAML_KEY_LINE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):\s*(?P<val>.*)$")


def _scan_yaml_id_lines(text: str) -> List[str]:
    """Structure-aware `id:` scan over the YAML SSOT block-list text — the raw
    id-scan's whole purpose is reserving ids even when the file fails a
    whole-file `yaml.safe_load` (see _load_yaml_raw), so this walks lines by
    INDENTATION only, never invoking the YAML parser itself.

    Counts an `id:` line only when it sits at a record's own field indent —
    either the list-item form (`- id: DEC-1`) or the hand-written indented
    form (`-\\n  id: DEC-1`, both documented supported shapes) — established
    per record from its first key line. Any line indented DEEPER than that is
    always a continuation of a multi-line scalar VALUE (PyYAML renders a
    folded/quoted multi-line scalar's continuation lines one level deeper
    than the key that introduces it), never a sibling key — so a rationale
    that itself quotes a bare `id: DEC-999` line can never be mistaken for a
    real record id."""
    ids: List[str] = []
    field_indent: Optional[int] = None

    def _capture(key_val_text: str) -> None:
        m = _YAML_KEY_LINE_RE.match(key_val_text)
        if not m or m.group("key") != "id":
            return
        val = m.group("val").strip().strip("'\"")
        if DECISION_ID_RE.match(val):
            ids.append(val)

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line[indent:]
        if indent == 0 and stripped.startswith("-"):
            rest = stripped[1:]
            if rest[:1] == " ":
                rest = rest[1:]
                field_indent = indent + 2
                if rest:
                    _capture(rest)
            elif rest == "":
                field_indent = None  # resolved by the next line's indent
            else:
                field_indent = None  # not a `- key: value` list item — skip
            continue
        if field_indent is None:
            field_indent = indent  # first key line of a bare "-" record
        if indent != field_indent:
            continue  # deeper (scalar continuation) or malformed — never a key
        _capture(stripped)
    return ids


def _scan_yaml_field_lines(text: str):
    """The YAML SSOT text as a list of per-record `{key: [values]}` maps, or None
    when the text is not the flat block-list shape this scan can judge.

    Same indentation-only discipline as `_scan_yaml_id_lines` above, and for the
    same reason: a line indented DEEPER than a record's field indent is always a
    multi-line scalar continuation, never a sibling key. That is what makes a
    `rationale:` block quoting `status: superseded` in its prose harmless here.

    Values are collected per key as a LIST so a caller can tell "exactly one
    status key" from "a duplicate key it must not guess about"."""
    records: List[Dict[str, List[str]]] = []
    field_indent: Optional[int] = None
    started = False

    def _capture(key_val_text: str) -> None:
        m = _YAML_KEY_LINE_RE.match(key_val_text)
        if not m or not records:
            return
        records[-1].setdefault(m.group("key"), []).append(m.group("val").strip())

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line[indent:]
        if indent == 0:
            if not stripped.startswith("-"):
                # A column-0 line that is not a list item: a top-level mapping
                # (`decisions:`), flow style (`[]`, `{ broken`), or hand-mangled
                # text. None of those are this shape — decline rather than guess.
                return None
            started = True
            records.append({})
            rest = stripped[1:]
            if rest[:1] == " ":
                field_indent = indent + 2
                if rest[1:]:
                    _capture(rest[1:])
            elif rest == "":
                field_indent = None  # bare "-": resolved by the next line's indent
            else:
                return None  # `-foo` is not a list item at all
            continue
        if not started:
            return None  # indented content before any record marker
        if field_indent is None:
            field_indent = indent
        if indent != field_indent:
            continue  # deeper = scalar continuation; shallower = malformed
        _capture(stripped)
    return records


def scan_counts(root) -> Optional[Tuple[int, int]]:
    """`(records, superseded)` read by scanning LINES, or None when the register's
    shape is not certain enough to judge — the caller then pays `parse_decisions`.

    ── WHY THIS EXISTS ──────────────────────────────────────────────────────────
    `decision_reconcile.status()` runs on every Stop event and needs exactly two
    numbers. It got the second one from a full `parse_decisions()`, i.e. a
    `yaml.safe_load` of the whole register: measured **178.61 ms per Stop event**
    at 343 645 B, and this file only ever grows. The scan does it in 3.10 ms.

    Deliberately NOT solved with `yaml.CSafeLoader`: that takes 12.40 ms on the
    same bytes (so the scan is 4x faster even against the C parser) AND the C
    extension is not in `preflight_deps.py`, so leaning on it would silently
    restore the slow path wherever libyaml is absent.

    ── WHY IT RETURNS None INSTEAD OF A BEST GUESS ─────────────────────────────
    A count that is quietly wrong would mis-drive the reconcile nudge with no
    symptom. So the scan asserts a structural invariant — a flat block list where
    every record carries exactly ONE `status` key at its own field indent — and
    declines otherwise. Declining costs one parse on a shape that should not
    exist; guessing costs correctness on every Stop event.
    """
    if not _uses_yaml(root):
        return None
    try:
        text = _yaml_path(root).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    records = _scan_yaml_field_lines(text)
    if records is None:
        return None
    superseded = 0
    for rec in records:
        statuses = rec.get("status")
        # A missing status is normalised elsewhere and a duplicate key means the
        # file disagrees with itself. Either way this scan must not adjudicate it.
        if not statuses or len(statuses) != 1:
            return None
        if statuses[0].strip().strip("'\"") == "superseded":
            superseded += 1
    return len(records), superseded


def _scan_all_ids(root) -> List[str]:
    if _uses_yaml(root):
        try:
            text = _yaml_path(root).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            return []
        return _scan_yaml_id_lines(text) + _HEADING_ID_RE.findall(text)
    path = _decisions_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return []
    return scan_record_ids(text) + _HEADING_ID_RE.findall(text)


def render_md(records: List[Dict[str, Any]]) -> str:
    """Render the YAML SSOT records to the secondary markdown view. Deterministic
    (records sorted by DEC number), with the rationale + title injection-escaped
    so the rendered file can never be re-parsed into a phantom record."""
    def _num(r):
        m = re.match(r"^DEC-(\d+)$", r.get("id", ""))
        return int(m.group(1)) if m else 0

    parts = [_DOC_FRONTMATTER, "", "# Decision Register", "", _GENERATED_MARKER, ""]
    for r in sorted(records, key=_num):
        parts.append(_render_record(
            r["id"],
            sanitize_field(r.get("title", ""), _INJ_DEC_HEADING_RE),
            sanitize_rationale(r.get("rationale", "")),
            r.get("date", ""),
            sanitize_field(r.get("affects", ""), _INJ_DEC_HEADING_RE),
            r.get("supersedes", ""),
            sanitize_field(r.get("executed_by", ""), _INJ_DEC_HEADING_RE),
            r.get("status") or "active",
            r.get("actor", ""),
            r.get("ts", ""),
        ))
    return "\n".join(parts).rstrip() + "\n"


def _dump_yaml_records(root, records: List[Dict[str, Any]]) -> Path:
    """Write the YAML SSOT atomically AND re-render the markdown view. Both
    writes resolve through the docs fs_guard zone. Returns the markdown view
    path (the public artifact path callers/tests read)."""
    yp = _yaml_path(root)
    # Append-only guard: the resilient id-scan recovers ids even from a file
    # that failed a whole-file YAML parse (where _load_yaml_raw returns []).
    # If the records about to be written drop an id the scan can still see,
    # this dump would silently truncate history — the clobber. Refuse the
    # write and leave the SSOT byte-untouched; a human repairs the corrupt file.
    lost = set(_scan_all_ids(root)) - {r.get("id") for r in records}
    if lost:
        raise DecisionError(
            "refusing to overwrite the decision SSOT: the write would drop %d "
            "existing record(s) %s — docs/decisions.yaml likely failed to parse "
            "(corrupt). Repair it by hand instead of overwriting." % (
                len(lost), sorted(lost))
        )
    fs_guard.assert_under(yp, "docs", root=root)
    yp.parent.mkdir(parents=True, exist_ok=True)
    payload = [{k: r.get(k, "") for k in _REC_FIELDS} for r in records]
    # block-style, keys in canonical order, unicode kept; rationale with newlines
    # becomes a literal block scalar. YAML scalar quoting makes the rationale
    # injection-inert in the SSOT itself; the md render escapes for its own view.
    text = yaml_io.safe_dump(payload, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=4096)
    atomic_write(yp, text)
    md = _decisions_path(root)
    fs_guard.assert_under(md, "docs", root=root)
    atomic_write(md, render_md(records))
    return md


def _render_record(dec_id, title, rationale, date, affects, supersedes,
                   executed_by, status, actor, ts) -> str:
    """Fill the record template, emitting the optional link lines ONLY when present
    so an absent affects/supersedes never leaves a bare `affects:` key — and the strip
    never touches the rationale body, which may legitimately contain such a line.

    `affects` is free text, so it is rendered as a JSON-quoted scalar (valid
    YAML): an embedded `key: value` fragment stays INSIDE the string instead
    of becoming a second frontmatter key or breaking the YAML parse.
    `supersedes` needs no quoting — it is regex-validated to `DEC-\\d+`.
    `actor`/`ts` are machine-resolved (resolve_actor + UTC isoformat) and are
    JSON-quoted so a colon in the actor (`user:x@host`) can never split the
    frontmatter into a second key."""
    # Build the optional link lines conditionally — an absent field emits NOTHING, so
    # there is never an empty `affects:`/`supersedes:` line to strip back out. This keeps
    # the strip from ever touching the rationale body, which may legitimately contain a
    # line like `affects:` (a decision discussing the field).
    affects_line = ("affects: %s\n" % json.dumps(affects, ensure_ascii=False)) if affects else ""
    supersedes_line = ("supersedes: %s\n" % supersedes) if supersedes else ""
    # JSON-quoted for the same reason as `affects`/`actor`: the pointer grammar is
    # `path:needle`, so an unquoted value splits the frontmatter at its own colon
    # and the needle becomes a second key.
    executed_by_line = ("executed_by: %s\n"
                        % json.dumps(executed_by, ensure_ascii=False)) if executed_by else ""
    out = _RECORD_TEMPLATE.format(
        id=dec_id, status=status, date=date,
        actor=json.dumps(actor, ensure_ascii=False),
        ts=json.dumps(ts, ensure_ascii=False),
        affects_line=affects_line, supersedes_line=supersedes_line,
        executed_by_line=executed_by_line,
        title=title, rationale=rationale.strip(),
    )
    return out.strip() + "\n"


def append_decision(
    root,
    dec_id: str,
    title: str,
    rationale: str,
    affects: str = "",
    supersedes: str = "",
    date: Optional[str] = None,
    status: str = "active",
) -> Path:
    """Validate + append one record. Append-only: prior records untouched.
    Raises DecisionError on malformed/duplicate id or dangling supersedes.

    NOT self-locking: this is a read-modify-write over the whole file, so
    concurrent callers can drop each other's records. The CLI paths and
    append_alloc() hold the register lock around it; a library caller must
    do the same (wrap in `with register_lock(...)`).

    Injection escape covers ALL caller-supplied text: the multiline rationale
    keeps its line breaks (anchors escaped); the single-line title/affects/
    supersedes have newlines collapsed so they cannot open a phantom record
    or smuggle extra frontmatter keys."""
    if not DECISION_ID_RE.match(dec_id):
        raise DecisionError(
            "decision id %r does not match the grammar %s" % (dec_id, DECISION_ID_RE.pattern)
        )
    if not title.strip():
        raise DecisionError("a decision needs a non-empty title")
    if not rationale.strip():
        raise DecisionError("a decision needs a non-empty rationale (the WHY)")
    if supersedes and not DECISION_ID_RE.match(supersedes):
        raise DecisionError(
            "supersedes %r is not a valid decision id (%s)" % (supersedes, DECISION_ID_RE.pattern)
        )

    existing = parse_decisions(root)
    existing_by_id = {r["id"]: r for r in existing}
    if dec_id in existing_by_id:
        raise DecisionError(
            "%s already exists in the register; the register is append-only "
            "(use a fresh --alloc-id, and `supersedes:` to retire the old one)" % dec_id
        )
    if supersedes and supersedes not in existing_by_id:
        raise DecisionError(
            "supersedes %s but that id is not in the register" % supersedes
        )
    # No false supersede chain: a DEC that was already retired is dead — a
    # second ruling claiming to supersede it would re-retire a corpse and
    # imply the wrong lineage. Refuse, naming the offender and its live heir.
    if supersedes and existing_by_id[supersedes]["status"] == "superseded":
        raise DecisionError(
            "%s is already superseded — cannot supersede it again "
            "(false supersede chain); supersede the live ruling that replaced "
            "%s instead" % (supersedes, supersedes)
        )
    # The target must carry a flippable `status:` line, else _supersede_in_place
    # can't retire it and a direct caller strands two active rulings. (append_alloc
    # also gates this; do it here so the public library entry is symmetric.)
    if supersedes and not _can_supersede(root, supersedes):
        raise DecisionError(
            "%s cannot be superseded in place (no flippable `status:` line) — "
            "superseding it would strand two active rulings" % supersedes
        )

    actor = hook_runtime.resolve_actor()
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    rec_date = date or dt.date.today().isoformat()

    if _uses_yaml(root):
        # YAML SSOT: newlines are collapsed in EVERY free-text field, rationale
        # included — mirroring backlog_register.add(), which is immune to the
        # raw id-scan false-positive for exactly this reason. A collapsed
        # rationale can never render as a multi-line PyYAML scalar, so it can
        # never contain a bare `id: DEC-<n>` line for _scan_yaml_id_lines to
        # even have to distinguish from a real key — belt-and-suspenders on
        # top of that scan being structure-aware.
        records = _load_yaml_raw(root)
        records.append({
            "id": dec_id,
            "status": status,
            "date": rec_date,
            "actor": actor,
            "ts": ts,
            "affects": re.sub(r"[\r\n]+", " ", affects).strip(),
            "supersedes": supersedes,
            "title": re.sub(r"[\r\n]+", " ", title).strip(),
            "rationale": re.sub(r"[\r\n]+", " ", rationale).strip(),
        })
        return _dump_yaml_records(root, records)

    record = _render_record(
        dec_id,
        sanitize_field(title, _INJ_DEC_HEADING_RE),
        sanitize_rationale(rationale),
        rec_date,
        sanitize_field(affects, _INJ_DEC_HEADING_RE),
        supersedes,
        # A record being written now has nothing to point at yet, so the field is
        # emitted empty and the proof is filled in when the ruling actually lands.
        "",
        status,
        actor=actor, ts=ts,
    )

    path = _decisions_path(root)
    # Containment helper: resolve + contain BEFORE any mkdir/write so a
    # tampered path can never place the register outside the docs zone.
    fs_guard.assert_under(path, "docs", root=root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        prior = path.read_text(encoding="utf-8")
        sep = "" if prior.endswith("\n\n") else ("\n" if prior.endswith("\n") else "\n\n")
        new_text = prior + sep + record
    else:
        new_text = "# Decision Register\n\n" + record

    atomic_write(path, new_text)
    return path


def _supersede_in_place(root, dec_id: str) -> bool:
    """Flip an existing active record to `status: superseded`. The ONE in-place
    edit the register makes — only the status field of the retired record, never
    its prose. Returns True if a record was flipped. In YAML mode a record whose
    status is explicitly empty is NOT flippable (the analogue of a legacy record
    missing its `status:` line) — flipping it would silently retire a ruling the
    caller cannot see is unanchored."""
    if _uses_yaml(root):
        records = _load_yaml_raw(root)
        hit = False
        for r in records:
            if r["id"] == dec_id and str(r.get("status", "")).strip():
                r["status"] = "superseded"
                hit = True
                break
        if hit:
            _dump_yaml_records(root, records)
        return hit

    path = _decisions_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return False

    flipped = {"hit": False}

    def _flip(m):
        fm = m.group("fm")
        try:
            data = yaml_io.safe_load(fm) or {}
        except yaml_io.YAMLError:
            return m.group(0)
        if isinstance(data, dict) and str(data.get("id", "")).strip() == dec_id:
            new_fm, n = re.subn(r"^status:\s*\S+\s*$", "status: superseded",
                                fm, count=1, flags=re.MULTILINE)
            if n == 0:
                # No status: line to substitute (hand-edited record) —
                # reporting a flip here would leave the old ruling silently
                # active while the caller believes it retired.
                return m.group(0)
            flipped["hit"] = True
            # _RECORD_RE consumes the closing-fence newline AND the blank line
            # after it; reinsert the blank line so a canonical file round-trips
            # byte-stably (---\n\n## DEC-n, not ---\n## DEC-n).
            return "---\n%s\n---\n\n%s" % (new_fm, m.group("body").lstrip(chr(10)))
        return m.group(0)

    new_text = _RECORD_RE.sub(_flip, text)
    if flipped["hit"]:
        # atomic_write, not a bare truncating open() — legacy mode is the SSOT
        # itself here (append_decision's sibling write, 60 lines up, already
        # goes through atomic_write for the same file); a crash/power-loss
        # mid-write must never leave a truncated or empty register.
        atomic_write(path, new_text)
    return flipped["hit"]


def _can_supersede(root, dec_id: str) -> bool:
    """Dry-run feasibility of _supersede_in_place: does a record with this id
    exist AND carry a flippable `status:` line? Used to gate the append BEFORE
    writing the new record, so a supersede that cannot land never leaves a
    second active ruling on disk: this check gates the append, so the later
    flip cannot fail after the new record is written."""
    if _uses_yaml(root):
        for r in _load_yaml_raw(root):
            if r["id"] == dec_id:
                return bool(str(r.get("status", "")).strip())
        return False
    path = _decisions_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return False
    for m in _RECORD_RE.finditer(text):
        fm = m.group("fm")
        try:
            data = yaml_io.safe_load(fm) or {}
        except yaml_io.YAMLError:
            continue
        if isinstance(data, dict) and str(data.get("id", "")).strip() == dec_id:
            return re.search(r"^status:\s*\S+\s*$", fm, flags=re.MULTILINE) is not None
    return False


def migrate_to_yaml(root) -> Dict[str, Any]:
    """One-shot: convert a legacy markdown register to the YAML SSOT. Parses the
    existing decisions.md (preserving every record + its rationale), writes
    decisions.yaml, and re-renders decisions.md as the secondary view. Idempotent
    once decisions.yaml exists (re-running just re-dumps from the SSOT). Returns a
    summary with the migrated count."""
    with _register_lock(root):
        records = _parse_yaml(root) if _uses_yaml(root) else _parse_md(root)
        # _parse_yaml returns the view (status defaulted); for a dump we want the
        # raw records when already on YAML so an empty status round-trips.
        if _uses_yaml(root):
            records = _load_yaml_raw(root)
        _dump_yaml_records(root, records)
    return {"migrated": len(records), "yaml": str(_yaml_path(root))}


def _record_status(root, dec_id: str) -> Optional[str]:
    """The `status:` of the record with this id, or None if no such record
    exists. Read directly from the file so append_alloc can gate on the
    target's state BEFORE allocating or writing anything."""
    for rec in parse_decisions(root):
        if rec["id"] == dec_id:
            return rec["status"]
    return None


def append_alloc(
    root,
    title: str,
    rationale: str,
    affects: str = "",
    supersedes: str = "",
    date: Optional[str] = None,
    status: str = "active",
    dec_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one record in ONE locked critical section — the SINGLE home for
    the alloc/append/supersede-flip atomicity rule shared by both CLI write
    modes. `dec_id=None` allocates the next monotonic id INSIDE the lock (the
    --append-alloc path); an explicit `dec_id` is the --append path. Either way
    the alloc + append + flip run under one register lock, so two concurrent
    agents cannot overwrite each other's records, and a supersede that cannot
    land never leaves a second active ruling.

    On a dup-id race append_decision raises and the CLI surfaces a JSON finding
    — never a silently dropped ruling."""
    with _register_lock(root):
        # Gate the append on supersede feasibility FIRST: if the target cannot
        # be retired (missing record / no status: line), refuse before writing
        # the new ruling — otherwise a failed flip would leave two active
        # rulings on disk. The feasibility check gates the write, so the later
        # flip cannot strand a second active ruling.
        if supersedes and not _can_supersede(root, supersedes):
            raise DecisionError(
                "cannot retire %s (no record with a status: line to flip); "
                "refusing to append a ruling that would leave two active "
                "rulings — resolve %s by hand" % (supersedes, supersedes)
            )
        # No false supersede chain: refuse early (before alloc) if the target
        # is already retired, so the register stays byte-untouched. Names the
        # offender; the same guard lives in append_decision for direct callers.
        if supersedes and _record_status(root, supersedes) == "superseded":
            raise DecisionError(
                "%s is already superseded — cannot supersede it again "
                "(false supersede chain); supersede the live ruling that "
                "replaced %s instead" % (supersedes, supersedes)
            )
        # Cross-scope confirm gate (P3): added LAYER after the structural guards,
        # before the write. Explicit supersede → may raise CrossScopeBlock (write
        # refused, SSOT untouched). A new active ruling with no supersedes → WARN
        # only if it strongly restates a live ruling (implicit flip), never blocks.
        if supersedes:
            _gate_supersede(root, supersedes)
        elif (status or "active") == "active":
            _warn_implicit_flip(root, title, rationale)
        dec_id = dec_id or alloc_id(root)
        path = append_decision(
            root, dec_id=dec_id, title=title, rationale=rationale,
            affects=affects, supersedes=supersedes, date=date, status=status,
        )
        if supersedes and not _supersede_in_place(root, supersedes):
            raise DecisionError(
                "appended %s but could not retire %s; the register would have "
                "two active rulings — resolve %s by hand" % (
                    dec_id, supersedes, supersedes)
            )
    rel = lambda p: str(Path(p).relative_to(Path(root).resolve()))
    if _uses_yaml(root):
        # YAML mode: decisions.yaml is the SSOT, decisions.md a rendered view.
        # Report both explicitly and point `path` at the SSOT (the real write
        # target) so the output never reads as "appended to the markdown".
        return {"id": dec_id, "written": True,
                "ssot": rel(_yaml_path(root)),
                "rendered": rel(path),
                "path": rel(_yaml_path(root))}
    # Legacy mode: the markdown file IS the source of truth.
    return {"id": dec_id, "written": True, "path": rel(path)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--alloc-id", action="store_true",
                      help="print the next free DEC-<n>")
    mode.add_argument("--append", action="store_true",
                      help="append a decision record (explicit or alloc'd id)")
    mode.add_argument("--append-alloc", action="store_true",
                      help="atomic: alloc the next id AND append, locked")
    mode.add_argument("--list", action="store_true",
                      help="print active decisions as JSON")
    mode.add_argument("--migrate", action="store_true",
                      help="convert a legacy decisions.md to the YAML SSOT")
    mode.add_argument("--scan-flip", metavar="DEC-n",
                      help="dry-run: print neighbours + in_scope/cross_scope for a "
                           "proposed flip (exit 0 JSON; no write)")
    mode.add_argument("--scan-new", action="store_true",
                      help="dry-run: with --title/--rationale, print the live ruling "
                           "a new record would implicitly flip (exit 0 JSON)")
    ap.add_argument("--id", help="decision id (with --append); default = alloc")
    ap.add_argument("--title")
    ap.add_argument("--rationale")
    ap.add_argument("--affects", default="")
    ap.add_argument("--supersedes", default="")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    try:
        if args.alloc_id:
            print(json.dumps({"id": alloc_id(root)}, ensure_ascii=False))
            return 0
        if args.list:
            print(json.dumps({"active": list_active(root)}, indent=2,
                             ensure_ascii=False))
            return 0
        if args.migrate:
            print(json.dumps(migrate_to_yaml(root), ensure_ascii=False))
            return 0
        if args.scan_flip:
            print(json.dumps(_scope_of_flip(root, args.scan_flip),
                             ensure_ascii=False))
            return 0
        if args.scan_new:
            rival = decision_neighbors.implicit_flip_match(
                parse_decisions(root), args.title or "", args.rationale or "",
                min_shared=_IMPLICIT_MIN_SHARED)
            print(json.dumps({"implicit_flip_of": rival}, ensure_ascii=False))
            return 0
        if args.append_alloc:
            result = append_alloc(
                root, title=args.title or "", rationale=args.rationale or "",
                affects=args.affects, supersedes=args.supersedes,
            )
            print(json.dumps(result, ensure_ascii=False))
            return 0
        # --append: the explicit-id path delegates to the SAME locked critical
        # section (append_alloc) — one home for the alloc/append/supersede-flip
        # atomicity. The two write modes differ ONLY in whether the id is given:
        # an explicit --id is passed through; an absent --id allocs inside the
        # lock exactly like --append-alloc. So two concurrent appends still
        # serialize on the register lock, and a rejected supersede still leaves
        # the register byte-untouched (never zero-active + phantom-retired).
        result = append_alloc(
            root, title=args.title or "", rationale=args.rationale or "",
            affects=args.affects, supersedes=args.supersedes, dec_id=args.id,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except CrossScopeBlock as blk:
        # The ONE exit-2 path (DC-5): a positively-determined, unconfirmed
        # cross-scope flip. The write was already refused (raised before append);
        # exit 2 is the escalation signal. Caller branches on the stdout key
        # cross_scope_block, not on $? (R8).
        print(json.dumps(blk.finding(), ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001 — surface as finding
        # Analytical-script contract: a bad input surfaces as a JSON finding
        # on stdout + exit 0, never a bare traceback.
        print(json.dumps(
            {"error": "invalid_input", "message": str(exc), "written": False},
            ensure_ascii=False,
        ))
        return 0


if __name__ == "__main__":
    sys.exit(main())
